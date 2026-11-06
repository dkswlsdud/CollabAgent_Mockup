"""request_service: 업무 규칙과 트랜잭션 처리."""

import re
from app.shared.notices import request_version,checked_version
from app.shared.calendar_preferences import selected_consents,settings_ready
from app.repositories import notice_repository,attachment_repository
from app.services.attachment_service import prepare_uploads
from app.shared.consent_state import selected_rejections
from app.shared.serialization import clean, dump
from app.shared.errors import fail
from app.shared.dates import now, parse_time
from app.shared.validation import text
from app.database import transaction
from app.services.ai_service import compose_request
from app.repositories import (
    employee_repository,
    negotiation_repository,
    request_repository,
    response_repository,
    result_repository,
    schedule_repository,
)


def requests_list(user):
    with transaction() as cur:
        rows = [
            clean(r)
            for r in request_repository.list_user_requests(cur, (user["id"], user["id"]))
        ]
        reads=notice_repository.reads(cur,user['id'],'REQUEST')
        for row in rows:
            history=[clean(n) for n in negotiation_repository.list_request_rounds(cur,(row['id'],))]
            result=clean(result_repository.find_result(cur,(row['id'],)))
            row['notice_version']=request_version(row,history,result)
            row['is_new']=reads.get(row['id'])!=row['notice_version']
            row['awaiting_calendar_settings']=bool(result and result['status']=='PENDING_CONFIRMATION' and history and settings_ready(result,history[0]))
    for row in rows:
        consents,selected = row.pop('latest_consents_json', None),row.pop('latest_selected_key', None)
        row['consent_rejections'] = selected_rejections(consents,selected)
        row['awaiting_related_consent'] = bool(row.get('result_a_confirmed_at') and row.get('result_b_confirmed_at') and row.get('result_status') == 'PENDING_CONFIRMATION' and any(c.get('status') == 'PENDING' and str(c['alternative_id']) == str(selected) for c in consents or []))
        row['needs_recoordination'] = bool(row['consent_rejections']) and row['status'] == 'NEGOTIATING'
    return dict(requests=rows)


def load_request(cur, request_id, user, lock=False):
    row = request_repository.find_request(cur, (request_id,), lock)
    if not row:
        fail("요청을 찾을 수 없습니다.", 404)
    if user["id"] not in {row["requester_id"], row["assignee_id"]}:
        fail("이 요청에 접근할 수 없습니다.", 403)
    return clean(row)


def request_detail(request_id, user):
    with transaction() as cur:
        load_request(cur, request_id, user)
        row = clean(request_repository.find_request_detail(cur, (request_id,)))
        rounds = [
            clean(r) for r in negotiation_repository.list_request_rounds(cur, (request_id,))
        ]
        response = clean(response_repository.find_response(cur, (request_id,)))
        result = clean(result_repository.find_result(cur, (request_id,)))
        alternatives_rows = rounds[0]["alternatives_json"] or [] if rounds else []
        consent_rows = rounds[0]["consents_json"] or [] if rounds else []
        rejections = selected_rejections(consent_rows, rounds[0].get('selected_alternative_key') if rounds else None)
        row['needs_recoordination'] = bool(rejections) and row['status'] == 'NEGOTIATING'
        row['consent_rejections'] = rejections
        row['awaiting_related_consent'] = bool(result and result.get('status') == 'PENDING_CONFIRMATION' and result.get('a_confirmed_at') and result.get('b_confirmed_at') and any(c.get('status') == 'PENDING' and str(c['alternative_id']) == str(rounds[0].get('selected_alternative_key')) for c in consent_rows))
        row.pop('latest_consents_json', None)
        row.pop('latest_selected_key', None)
        notice_version=request_version(row,rounds,result)
        attachments=attachment_repository.metadata(cur,request_id)
        row['awaiting_calendar_settings']=bool(result and result['status']=='PENDING_CONFIRMATION' and rounds and settings_ready(result,rounds[0]))
        from app.services.schedule_service import analysis_for
        analysis = analysis_for(cur, row['assignee_id'], parse_time(row['due_at']), row) if row['status'] in {'PENDING', 'NEGOTIATING'} else None
        current = now()
        period_start = current.replace(hour=0,minute=0,second=0,microsecond=0)
        period_end = parse_time(row['due_at'])
        schedule_timeline = dict(start_at=period_start.isoformat(),end_at=period_end.isoformat(),current_at=current.isoformat(),
            schedules=[clean(s) for s in schedule_repository.list_period_schedules(cur,(row['assignee_id'],period_start,period_end))] if period_end>period_start else [])
    return dict(
        request=row,
        notice_version=notice_version,attachments=attachments,
        needs_calendar_settings=bool(user['id']!=row['requester_id'] and row['awaiting_calendar_settings'] and str(user['id']) not in (result['agreed_terms_json'].get('calendar_preferences') or {})),
        rounds=rounds,
        alternatives=alternatives_rows,
        consents=consent_rows,
        response=response,
        result=result,
        analysis=analysis,
        schedule_timeline=schedule_timeline,
    )


def create_request(data, user, files=None):
    uploads=prepare_uploads(files or [])
    content, original = (
        text(data, "task_content", 1000),
        text(data, "original_text", 5000),
    )
    due = parse_time(data.get("due_at"))
    try:
        assignee_id = int(data.get("assignee_id"))
    except (TypeError, ValueError):
        fail("수행자를 선택해주세요.")
    conditions = data.get("conditions_json")
    if not isinstance(conditions, list) or not conditions or len(conditions) > 30:
        fail("요청 조건을 확인해주세요.")
    keys = set()
    for condition in conditions:
        if (
            not isinstance(condition, dict)
            or not isinstance(condition.get("key"), str)
            or (not re.fullmatch("[a-z_][a-z0-9_]{0,99}", condition["key"]))
            or (condition.get("constraint") not in {"HARD", "SOFT"})
        ):
            fail("각 조건의 식별 키와 Hard/Soft를 확인해주세요.")
        if condition["key"] in keys:
            fail("조건 키가 중복되었습니다.")
        keys.add(condition["key"])
    if 'deadline' not in keys:
        fail('마감 조건이 필요합니다.')
    quantity = next((c.get("value") for c in conditions if c["key"] == "quantity"), 1)
    specification = next(
        (c.get("value") for c in conditions if c["key"] == "specification"), None
    )
    if type(quantity) is not int or not 1 <= quantity <= 1000:
        fail("수량은 1~1000 사이 정수로 입력해주세요.")
    if specification is not None and (
        not isinstance(specification, str)
        or not specification.strip()
        or len(specification) > 500
    ):
        fail("규격은 500자 이내로 입력해주세요.")
    for condition in conditions:
        if condition['key'] != 'deadline' and (condition.get('value') is None or str(condition['value']).strip() == '' or len(str(condition['value'])) > 1000):
            fail('추가 조건의 값을 입력해주세요.')
        if not isinstance(condition.get('label'), str) or not condition['label'].strip() or len(condition['label']) > 100:
            fail('조건 이름을 확인해주세요.')
    if due <= now():
        fail('마감은 현재 시각 이후로 입력해주세요.')
    if assignee_id == user["id"]:
        fail("다른 직원을 수행자로 선택해주세요.")
    with transaction() as cur:
        employee = next((e for e in employee_repository.list_active_employees(cur) if e['id']==assignee_id),None)
    if not employee:
        fail('수행자를 찾을 수 없습니다.')
    if data.get('assignee_department') and data['assignee_department'] != employee['department']:
        fail('선택한 팀과 팀원을 확인해주세요.')
    message = compose_request(dict(original_text=original,task_content=content,due_at=due.isoformat(),conditions_json=conditions,
                                   requester={k:user.get(k) for k in ['name','department']},assignee={k:employee[k] for k in ['id','name','department']}))
    with transaction() as cur:
        if not employee_repository.find_active_employee(cur, (assignee_id,)):
            fail("수행자를 찾을 수 없습니다.")
        request_id = request_repository.insert_request(
            cur, (user["id"], assignee_id, original, content, due, dump(conditions))
        )
        request_repository.save_request_message(cur,(message,request_id))
        for name,mime,content in uploads:attachment_repository.insert(cur,request_id,name,mime,content)
        row = dict(
            id=request_id,
            requester_id=user["id"],
            assignee_id=assignee_id,
            task_content=content,
            due_at=due,
            conditions_json=conditions,
        )
    return dict(id=request_id)


def acknowledge_request(request_id,data,user):
    value=checked_version(data)
    with transaction() as cur:
        load_request(cur,request_id,user)
        notice_repository.acknowledge(cur,user['id'],request_id,'REQUEST',value)
    return dict(ok=True)
