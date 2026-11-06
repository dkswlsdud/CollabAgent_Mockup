"""consent_service: 업무 규칙과 트랜잭션 처리."""

from app.shared.serialization import clean, dump
from app.shared.errors import fail
from app.shared.calendar_preferences import calendar_preference, selected_consents, settings_ready, preferences_complete
from app.shared.dates import now
from app.database import transaction
from app.shared.notices import consent_version,checked_version
from app.repositories import notice_repository,attachment_repository
from app.services.agreement_service import complete_agreement
from app.repositories import negotiation_repository, request_repository, result_repository, schedule_repository
from app.services.schedule_service import save_schedule_items


def consent_detail(consent_id, user):
    try:
        round_id, key = consent_id.split('_', 1)
        round_id = int(round_id)
    except (ValueError, AttributeError):
        fail('올바른 동의 요청이 아닙니다.')
    with transaction() as cur:
        n = clean(negotiation_repository.find_consent_round(cur, (round_id,)))
        if not n:
            fail('동의 요청을 찾을 수 없습니다.', 404)
        consent = next((c for c in n.get('consents_json') or []
                        if str(c['id']) == key and c['employee_id'] == user['id']), None)
        if not consent:
            fail('본인에게 전달된 동의 요청만 확인할 수 있습니다.', 403)
        result = clean(result_repository.find_result(cur, (n['request_id'],)))
        if (n['status'] not in {'IN_PROGRESS', 'AGREED'} or not result
                or result.get('negotiation_id') != round_id
                or not result.get('a_confirmed_at') or not result.get('b_confirmed_at')
                or str(consent['alternative_id']) != str(n.get('selected_alternative_key'))
                or consent.get('status') not in {'PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'}):
            fail('양측 최종 확인 후 본인에게 전달된 협업만 확인할 수 있습니다.', 409)
        alternative = next((a for a in n.get('alternatives_json') or []
                            if str(a['id']) == str(consent['alternative_id'])), None)
        if not alternative:
            fail('확정된 대안을 찾을 수 없습니다.', 404)
        row = clean(request_repository.find_request_detail(cur, (n['request_id'],)))
        if not row:
            fail('협업 요청을 찾을 수 없습니다.', 404)
        request = {key: row.get(key) for key in ['id', 'task_content', 'request_message', 'original_text',
                   'requester_name', 'assignee_name', 'assignee_department', 'due_at', 'conditions_json', 'status']}
        projected=dict(n,a_confirmed_at=result.get('a_confirmed_at'),b_confirmed_at=result.get('b_confirmed_at'),agreed_terms_json=result['agreed_terms_json'])
        ready=settings_ready(result,n)
        blocked=any(c['status'] in {'REJECTED','CANCELLED'} for c in selected_consents(n))
        return dict(request=request, notice_version=consent_version(projected,consent),attachments=attachment_repository.metadata(cur,n['request_id']),consent=dict(consent, id=consent_id), alternative=alternative,
                    needs_calendar_settings=bool(result['status']=='PENDING_CONFIRMATION' and not blocked and consent['status']=='APPROVED' and user['id'] not in result['agreed_terms_json'].get('calendar_registered_employee_ids',[])),
                    calendar_registered=result['status']=='ACCEPTED' or user['id'] in result['agreed_terms_json'].get('calendar_registered_employee_ids',[]),
                    confirmation={key: result.get(key) for key in ['a_confirmed_at', 'b_confirmed_at', 'finalized_at']},
                    response={key: n.get(key) for key in ['assignee_comment', 'accepted_condition_keys_json',
                                                         'accepted_condition_key', 'requester_feedback', 'assignee_feedback']})


def my_consents(user):
    with transaction() as cur:
        negotiations = negotiation_repository.list_open_round_consents(cur)
        reads=notice_repository.reads(cur,user['id'],'CONSENT')
        rows = []
        for n in map(clean, negotiations):
            for c in n["consents_json"] or []:
                if (c.get("employee_id") == user["id"] and n.get('a_confirmed_at') and n.get('b_confirmed_at')
                        and str(c['alternative_id']) == str(n.get('selected_alternative_key')) and c.get('status') != 'WAITING'):
                    item = dict(c, id=f"{n['id']}_{c['id']}")
                    item['request_id']=n['request_id']
                    item['notice_version']=consent_version(n,c)
                    item['is_new']=reads.get(n['request_id'])!=item['notice_version']
                    ready=all(entry['status']=='APPROVED' for entry in selected_consents(n))
                    blocked=any(entry['status'] in {'REJECTED','CANCELLED'} for entry in selected_consents(n))
                    item['needs_calendar_settings']=bool(not blocked and c['status']=='APPROVED' and user['id'] not in (n.get('agreed_terms_json') or {}).get('calendar_registered_employee_ids',[]))
                    item['calendar_registered']=user['id'] in (n.get('agreed_terms_json') or {}).get('calendar_registered_employee_ids',[])
                    item['request_title'] = n.get('request_title') or '협업 요청'
                    item["alternative_title"] = next(
                        (
                            a["title"]
                            for a in n["alternatives_json"] or []
                            if a["id"] == c["alternative_id"]
                        ),
                        "대안",
                    )
                    rows.append(item)
    return dict(consents=rows)


def answer_consent(consent_id, data, user):
    status = data.get("status")
    if status not in {"APPROVED", "REJECTED"}:
        fail("동의 또는 거부를 선택해주세요.")
    reason = None
    if status == 'REJECTED':
        reason = data.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
            fail('거부 사유를 2000자 이내로 입력해주세요.')
        reason = reason.strip()
    try:
        nid, key = consent_id.split("_", 1)
        nid = int(nid)
    except ValueError:
        fail("올바른 동의 요청이 아닙니다.")
    with transaction() as cur:
        n = negotiation_repository.find_round_request(cur, (nid,))
        if not n:
            fail("동의 요청이 없습니다.", 404)
        request_repository.lock_request(cur, (n["request_id"],))
        n = clean(negotiation_repository.lock_round_consents(cur, (nid,)))
        if n["status"] != "IN_PROGRESS":
            fail("진행 중인 동의 요청이 아닙니다.", 409)
        result = clean(result_repository.lock_request_result(cur, (n['request_id'],)))
        if (not result or result.get('status') != 'PENDING_CONFIRMATION' or result.get('negotiation_id') != nid or not result.get('a_confirmed_at') or not result.get('b_confirmed_at')):
            fail('양측 최종 확인 후 전달된 동의 요청에만 응답할 수 있습니다.', 409)
        consents = n["consents_json"] or []
        c = next(
            (
                c
                for c in consents
                if str(c["id"]) == key
                and c["employee_id"] == user["id"]
                and (c["status"] == "PENDING")
                and str(c['alternative_id']) == str(n.get('selected_alternative_key'))
            ),
            None,
        )
        if not c:
            fail("응답 가능한 동의 요청이 없습니다.", 409)
        c.update(status=status, responded_at=now().isoformat())
        if status == 'REJECTED':
            c['reason'] = reason
            for other in consents:
                if other is not c and str(other['alternative_id']) == str(c['alternative_id']) and other['status'] == 'PENDING':
                    other.update(status='CANCELLED', reason='다른 관계자의 동의 거부로 재조정이 필요합니다.')
        negotiation_repository.update_consents(cur, (dump(consents), nid))
        row = clean(request_repository.find_request(cur, (n['request_id'],), True))
        if status=='APPROVED' and ('schedule_priority' in data or 'schedule_workload' in data):
            register_consent_calendar(cur,row,result,user['id'],data)
        if status=='REJECTED':
            schedule_repository.delete_result_schedules(cur,result['id'])
            result['agreed_terms_json']['calendar_registered_employee_ids']=[]
            result_repository.update_agreed_terms(cur,(dump(result['agreed_terms_json']),result['id']))
        selected = [entry for entry in consents if str(entry['alternative_id']) == str(n['selected_alternative_key'])]
        if status == 'APPROVED' and selected and all(entry['status'] == 'APPROVED' for entry in selected):
            row = clean(request_repository.find_request(cur, (n['request_id'],), True))
            if preferences_complete(row,result['agreed_terms_json']):
                complete_agreement(cur,row,result,n)
                return dict(ok=True,completed=True)
        registered=user['id'] in result['agreed_terms_json'].get('calendar_registered_employee_ids',[])
    return dict(ok=True, completed=False,schedule_registered=registered,needs_calendar_settings=status=='APPROVED' and not registered)


def register_consent_calendar(cur,row,result,employee_id,data):
    plan=result['agreed_terms_json']
    if employee_id in plan.get('calendar_registered_employee_ids',[]):return
    if employee_id not in plan.setdefault('related_employee_ids',[]):
        plan['related_employee_ids'].append(employee_id)
    plan.setdefault('calendar_preferences',{})[str(employee_id)]=calendar_preference(data)
    save_schedule_items(cur,row,result['id'],plan,employee_ids={employee_id})
    plan.setdefault('calendar_registered_employee_ids',[]).append(employee_id)
    result_repository.update_agreed_terms(cur,(dump(plan),result['id']))


def consent_calendar_settings(consent_id,data,user):
    detail=consent_detail(consent_id,user)
    nid=int(consent_id.split('_',1)[0])
    with transaction() as cur:
        request_repository.lock_request(cur,(detail['request']['id'],))
        n=clean(negotiation_repository.lock_round_consents(cur,(nid,)))
        result=clean(result_repository.lock_request_result(cur,(n['request_id'],)))
        if not result or result['status']!='PENDING_CONFIRMATION' or n['status']!='IN_PROGRESS' or not result.get('a_confirmed_at') or not result.get('b_confirmed_at'):
            fail('양측 최종 확인 후 본인의 동의를 마치고 일정을 설정해주세요.',409)
        if not any(c['employee_id']==user['id'] and c['status']=='APPROVED' for c in selected_consents(n)):
            fail('동의한 관계자만 본인 일정을 설정할 수 있습니다.',403)
        if any(c['status'] in {'REJECTED','CANCELLED'} for c in selected_consents(n)):
            fail('관계자가 동의를 거부한 협업은 재조정 후 등록해주세요.',409)
        row=clean(request_repository.find_request(cur,(n['request_id'],),True))
        register_consent_calendar(cur,row,result,user['id'],data)
        completed=settings_ready(result,n) and preferences_complete(row,result['agreed_terms_json'])
        if completed:complete_agreement(cur,row,result,n)
    return dict(ok=True,completed=completed,schedule_registered=True)


def acknowledge_consent(consent_id,data,user):
    detail=consent_detail(consent_id,user)
    value=checked_version(data)
    with transaction() as cur:notice_repository.acknowledge(cur,user['id'],detail['request']['id'],'CONSENT',value)
    return dict(ok=True)
