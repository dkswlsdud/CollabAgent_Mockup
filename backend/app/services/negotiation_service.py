"""negotiation_service: 업무 규칙과 트랜잭션 처리."""

from app.services.request_service import load_request
from app.services.schedule_service import analysis_for, save_schedule_items, accepted_request_plan, save_accepted_request_schedule
from app.shared.serialization import clean, dump
from app.shared.errors import fail
from app.shared.dates import now, parse_time
from app.shared.validation import text
from app.database import transaction
from app.repositories import negotiation_repository, request_repository, response_repository, result_repository
from app.services.planning_service import generate
from app.services.agreement_service import complete_agreement
from app.shared.calendar_preferences import calendar_preference, selected_consents, settings_ready, preferences_complete
from app.shared.conditions import condition_keys, accepted_conditions
from app.shared.consent_state import selected_rejections, rejection_context


def insert_round(cur, row, number):
    analysis = analysis_for(cur, row["assignee_id"], parse_time(row["due_at"]), row)
    return negotiation_repository.insert_round(
        cur, (row["id"], number, dump(row), dump(analysis))
    )


def request_action(request_id, data, user):
    action = data.get("action")
    with transaction() as cur:
        row = load_request(cur, request_id, user, True)
        is_a = user["id"] == row["requester_id"]
        negotiation = clean(negotiation_repository.lock_latest_round(cur, (request_id,)))
        result = clean(result_repository.lock_request_result(cur, (request_id,)))
        rejections = selected_rejections((negotiation or {}).get('consents_json'), (negotiation or {}).get('selected_alternative_key'))
        if rejections and action in {'select','complete_selection','reject_all','choose','confirm','generate','finalize'}:
            fail('관계자가 동의를 거부했습니다. 재조정 시작을 눌러 새 대안을 생성해주세요.', 409)
        if action == 'cancel':
            if not is_a:
                fail('요청자만 요청을 취소할 수 있습니다.', 403)
            if row['status'] not in {'PENDING', 'NEGOTIATING', 'REJECTED'}:
                fail('취소할 수 없는 상태입니다.', 409)
            if result:
                result_repository.delete_result(cur, (result['id'],))
            negotiation_repository.cancel_open_rounds(cur, request_id)
            request_repository.update_request_status(cur, ('CANCELLED', request_id))
            result_repository.insert_direct_result(cur, (request_id, 'CANCELLED', None, '요청자가 취소했습니다.', None, None, now()))
        elif action == 'resubmit':
            if not is_a or row['status'] != 'REJECTED':
                fail('요청자만 거절된 요청을 다시 제출할 수 있습니다.', 409)
            due = parse_time(data.get('due_at'))
            if due <= now():
                fail('새 마감은 현재 시각 이후여야 합니다.')
            feedback = text(data, 'feedback', 2000)
            row['previous_result'] = result
            row['previous_response'] = clean(response_repository.find_response(cur, (request_id,)))
            nid = insert_round(cur, row, negotiation['round_no'] + 1 if negotiation else 1)
            negotiation_repository.close_failed_round(cur, (feedback, now(), nid), 'requester_feedback')
            if result:
                result_repository.delete_result(cur, (result['id'],))
            response_repository.delete_response(cur, request_id)
            request_repository.resubmit(cur, (due, dump(row['conditions_json']), request_id))
        elif action == "respond":
            if is_a:
                fail("수행자 계정으로 응답해주세요.", 403)
            if row["status"] != "PENDING":
                fail("이미 응답한 요청입니다.", 409)
            decision = data.get("decision")
            if decision not in {"ACCEPT", "CONDITIONAL_ACCEPT", "REJECT"}:
                fail("응답을 선택해주세요.")
            comment = str(data.get("comment", "")).strip()[:2000]
            keep = condition_keys(data.get('accepted_condition_keys',data.get('accepted_condition_key')))
            if not set(keep).issubset({c['key'] for c in row['conditions_json']}):
                fail("유효한 수용 조건이 아닙니다.")
            if decision == "REJECT" and (not comment):
                fail("거절 사유를 입력해주세요.")
            if decision == 'CONDITIONAL_ACCEPT' and not keep and not comment:
                fail('수용 가능한 조건이나 기타 의견을 입력해주세요.')
            response_repository.insert_response(
                cur,
                (
                    request_id,
                    "ACCEPTED" if decision == "ACCEPT" else "REJECTED",
                    None if decision == "ACCEPT" else comment or "조건 조율 요청",
                ),
            )
            if decision == "CONDITIONAL_ACCEPT":
                nid = insert_round(cur, row, negotiation['round_no'] + 1 if negotiation else 1)
                negotiation_repository.update_response_conditions(cur, (keep, comment, nid))
                request_repository.mark_negotiating(cur, (request_id,))
            else:
                status = "ACCEPTED" if decision == "ACCEPT" else "REJECTED"
                plan = None
                if decision == 'ACCEPT':
                    choice = calendar_preference(data)
                    plan = accepted_request_plan(row)
                    plan['calendar_preferences'] = {str(user['id']):choice}
                result_id = result_repository.insert_direct_result(
                    cur,
                    (
                        request_id,
                        status,
                        dump(plan) if plan else None,
                        comment or None,
                        now() if plan else None,
                        now(),
                        now(),
                    ),
                )
                if plan:
                    save_accepted_request_schedule(cur, row, result_id, plan)
                request_repository.update_request_status(cur, (status, request_id))
        elif action == 'reject_all':
            if is_a:
                fail('수행자만 대안 모두 불가를 제출할 수 있습니다.', 403)
            alternatives = (negotiation or {}).get('alternatives_json') or []
            if row['status'] != 'NEGOTIATING' or not alternatives or result or any(a.get('b_selection_completed') for a in alternatives):
                fail('대안을 선택 중일 때만 모두 불가를 제출할 수 있습니다.', 409)
            reason = '수행자가 모든 대안을 불가로 제출하고 재조정 의견을 남기지 않아 협의를 종료했습니다.'
            for alternative in alternatives:
                alternative.update(b_selected=False,b_selection_completed=True)
            negotiation_repository.update_alternatives(cur,(dump(alternatives),negotiation['id']))
            reset_consents(cur,negotiation)
            negotiation_repository.close_failed_round(cur,(reason,now(),negotiation['id']),'assignee_feedback')
            result_repository.insert_direct_result(cur,(request_id,'REJECTED',None,reason,None,None,now()))
            request_repository.update_request_status(cur,('REJECTED',request_id))
        elif action in {'renegotiate', 'restart_after_rejection'}:
            if row["status"] not in {"NEGOTIATING", "REJECTED"}:
                fail("재조정 가능한 상태가 아닙니다.", 409)
            if action == 'restart_after_rejection':
                if not rejections or type(data.get('source_round_id')) is not int or data['source_round_id'] != negotiation['id']:
                    fail('이미 재조정이 시작되었거나 처리할 거부 내역이 없습니다. 최신 내용을 확인해주세요.', 409)
                feedback = '관계자 동의 거부를 반영하여 새 대안을 요청합니다.'
            else:
                feedback = text(data, 'feedback', 2000)
            context = rejection_context(negotiation)
            if negotiation:
                snapshot = dict(negotiation.get('request_snapshot_json') or {})
                snapshot.update(final_result=result, archived_feedback={key:negotiation.get(key) for key in ['requester_feedback','assignee_feedback']})
                negotiation_repository.archive_round_snapshot(cur, (dump(snapshot), negotiation['id']))
            if negotiation:
                column = "requester_feedback" if is_a else "assignee_feedback"
                negotiation_repository.close_failed_round(
                    cur, (feedback, now(), negotiation["id"]), column
                )
            if result:
                result_repository.delete_result(cur, (result["id"],))
            nid = insert_round(
                cur, dict(row, related_party_rejections=context), negotiation["round_no"] + 1 if negotiation else 1
            )
            column = "requester_feedback" if is_a else "assignee_feedback"
            negotiation_repository.update_feedback(cur, (feedback, nid), column)
            if negotiation:
                negotiation_repository.update_response_conditions(cur, (accepted_conditions(negotiation), negotiation.get('assignee_comment'), nid))
                other = 'assignee_feedback' if is_a else 'requester_feedback'
                if negotiation.get(other):
                    negotiation_repository.update_feedback(cur, (negotiation[other], nid), other)
            request_repository.mark_negotiating(cur, (request_id,))
        else:
            if action == "finalize" and row["status"] == "ACCEPTED":
                return dict(ok=True)
            if row["status"] != "NEGOTIATING" or not negotiation:
                fail("진행 중인 협상이 없습니다.", 409)
            nid = negotiation["id"]
            alternatives = negotiation["alternatives_json"] or []
            alt = next(
                (a for a in alternatives if a["id"] == data.get("alternative_id")), None
            )
            if action == "generate":
                if alternatives:
                    fail("이미 대안이 생성되었습니다.", 409)
                alternatives, consents = generate(cur, row, negotiation)
                for consent in consents:
                    consent['status'] = 'WAITING'
                negotiation_repository.update_consents(cur, (dump(consents), nid))
            elif action == "select":
                if not alt:
                    fail("이 회차의 대안이 아닙니다.")
                if type(data.get('selected')) is not bool:
                    fail('선택 여부는 참 또는 거짓이어야 합니다.')
                if any(candidate.get('a_selection_completed' if is_a else 'b_selection_completed') for candidate in alternatives):
                    fail('선택완료 후에는 대안을 변경할 수 없습니다. 변경하려면 재조정해주세요.',409)
                column = 'a_selected' if is_a else 'b_selected'
                if bool(alt.get(column)) == data['selected']:
                    return dict(ok=True)
                alt[column] = data['selected']
                for candidate in alternatives:
                    candidate['a_selection_completed' if is_a else 'b_selection_completed'] = False
                reset_consents(cur, negotiation)
                negotiation_repository.clear_selected_alternative(cur, (nid,))
                if result:
                    result_repository.delete_result(cur, (result["id"],))
            elif action == 'complete_selection':
                if not alternatives or not any(a.get('a_selected' if is_a else 'b_selected') for a in alternatives):
                    fail('대안을 하나 이상 선택해주세요.')
                for candidate in alternatives:
                    candidate['a_selection_completed' if is_a else 'b_selection_completed'] = True
            elif action == "choose":
                if not is_a:
                    fail("요청자가 최종 대안을 지정해주세요.", 403)
                if not alt or not alt["a_selected"] or (not alt["b_selected"]):
                    fail("양측이 공통 선택한 대안이 필요합니다.")
                if not all(a.get('a_selection_completed') and a.get('b_selection_completed') for a in alternatives):
                    fail('양측 모두 선택완료 버튼을 눌러주세요.', 409)
                if result and str(negotiation['selected_alternative_key']) == str(alt['id']):
                    return dict(ok=True)
                if result:
                    result_repository.delete_result(cur, (result["id"],))
                reset_consents(cur, negotiation)
                plan = dict(alt['plan_json'],calendar_preferences_required=True,calendar_preferences={})
                result_id = result_repository.insert_pending_result(cur, (request_id,nid,dump(plan)))
                negotiation_repository.update_selected_alternative(
                    cur, (str(alt["id"]), nid)
                )
            elif action == "confirm":
                if not result or result["status"] != "PENDING_CONFIRMATION":
                    fail("최종 대안 지정 후 확인해주세요.", 409)
                if (
                    str(data.get("alternative_id"))
                    != negotiation["selected_alternative_key"]
                ):
                    fail("최종 대안이 변경되었습니다.", 409)
                related = selected_consents(negotiation)
                choice = calendar_preference(data) if not related and not is_a else None
                plan = result['agreed_terms_json']
                preferences = plan.setdefault('calendar_preferences',{})
                column = "a_confirmed_at" if is_a else "b_confirmed_at"
                if result.get(column) and (is_a or related or str(user['id']) in preferences):
                    return dict(ok=True)
                if choice:preferences[str(user['id'])] = choice
                plan['calendar_preferences_required'] = True
                result_repository.update_agreed_terms(cur,(dump(plan),result['id']))
                result[column] = now()
                result_repository.confirm_result(cur, (result[column], result["id"]), column)
                if result.get('a_confirmed_at') and result.get('b_confirmed_at'):
                    consents = negotiation['consents_json'] or []
                    for consent in consents:
                        if str(consent['alternative_id']) == str(negotiation['selected_alternative_key']) and not consent.get('requested_at'):
                            consent.update(status='PENDING', requested_at=now().isoformat())
                    negotiation_repository.update_consents(cur, (dump(consents), nid))
                    if not any(str(c['alternative_id']) == str(negotiation['selected_alternative_key']) for c in consents):
                        complete_agreement(cur, row, result, negotiation)
            elif action == 'calendar_settings':
                if is_a:
                    fail('요청자는 일정 등록 및 일정 설정 대상이 아닙니다.',409)
                if not result or result['status']!='PENDING_CONFIRMATION' or not settings_ready(result,negotiation):
                    fail('양측 최종 확인과 관계자 전원 동의 후 내 일정을 설정해주세요.',409)
                plan=result['agreed_terms_json']
                plan.setdefault('calendar_preferences',{})[str(user['id'])]=calendar_preference(data)
                result_repository.update_agreed_terms(cur,(dump(plan),result['id']))
                if preferences_complete(row,plan):complete_agreement(cur,row,result,negotiation)
            elif action == "finalize":
                if not is_a:
                    fail("요청자가 합의를 확정해주세요.", 403)
                if (
                    not result
                    or not result["a_confirmed_at"]
                    or (not result["b_confirmed_at"])
                ):
                    fail("양측 최종 확인이 필요합니다.")
                key = negotiation["selected_alternative_key"]
                if any(
                    (
                        str(c.get("alternative_id")) == key
                        and c["status"] != "APPROVED"
                        for c in negotiation["consents_json"] or []
                    )
                ):
                    fail("필요한 관계자 동의가 완료되지 않았습니다.")
                complete_agreement(cur, row, result, negotiation)
            else:
                fail("지원하지 않는 동작입니다.")
            negotiation_repository.update_alternatives(cur, (dump(alternatives), nid))
    return dict(ok=True)


def reset_consents(cur, negotiation):
    consents = negotiation.get('consents_json') or []
    for consent in consents:
        consent.update(status='WAITING')
        consent.pop('requested_at', None)
        consent.pop('responded_at', None)
    negotiation_repository.update_consents(cur, (dump(consents), negotiation['id']))
