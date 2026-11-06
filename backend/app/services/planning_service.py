"""AI generates proposals; the server validates conditions, schedules and consents."""
import copy
from app.shared.conditions import accepted_conditions
from app.shared.consent_state import rejection_context
from datetime import timedelta
from app.shared.dates import now, parse_time
from app.shared.errors import AppError, fail
from app.services.plan_service import new_alternative
from app.services.mock_planning_service import generate_proposals as demo_proposals
from app.shared.serialization import clean, dump
from app.repositories import employee_repository, schedule_repository


def generate_proposals(payload):
    return demo_proposals(payload)


def free_slots(schedules, start, end, ignore_ids=()):
    """One-hour slots, weekdays 09–18, with exact interval overlap checks."""
    day = start.replace(hour=9, minute=0, second=0, microsecond=0)
    result = []
    while day < end:
        if day.weekday() < 5:
            for hour in range(9, 18):
                begin = day.replace(hour=hour)
                finish = begin + timedelta(hours=1)
                if begin < start or finish > end:
                    continue
                if not any(s['id'] not in ignore_ids and s.get('status') not in {'COMPLETED', 'CANCELLED'}
                           and parse_time(s['start_at']) < finish and parse_time(s['end_at']) > begin for s in schedules):
                    result.append((begin, finish))
        day += timedelta(days=1)
    return result


def window(row):
    due = parse_time(row['due_at'])
    start = max(now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
                (due - timedelta(days=7)).replace(hour=9, minute=0, second=0, microsecond=0))
    return start, due


def workload(cur, employee_id, start, end):
    return [dict(s) for s in schedule_repository.list_workload_schedules(cur, (employee_id, start, end))]



def generate(cur, row, negotiation, allow_changes=True):
    from app.services.schedule_service import validate_plan
    start = now()
    due = parse_time(row['due_at'])
    horizon = max(start, due) + timedelta(days=14)
    all_people = employee_repository.list_active_employees(cur)
    owner = next((e for e in all_people if e['id'] == row['assignee_id']), None)
    if not owner:
        fail('수행자 정보를 확인해주세요.', 409)
    people = [e for e in all_people if e['id'] == owner['id'] or
              (allow_changes and e['department'] == owner['department'] and e['id'] != row['requester_id'])]
    employees = [dict(id=e['id'], name=e['name'], department=e['department']) for e in people]
    schedules = [clean(s) for person in people for s in workload(cur, person['id'], start, horizon)]
    schedule_map = {s['id']: s for s in schedules}
    movable = [s['id'] for s in schedules if allow_changes and s['employee_id'] == owner['id']
               and s['type'] == 'WORK' and s['priority'] == 'LOW' and s['status'] == 'SCHEDULED'
               and not s.get('result_id')]
    keep = accepted_conditions(negotiation)
    payload = dict(current_at=start.isoformat(), planning_end=horizon.isoformat(),
                   request={k: row.get(k) for k in ['id', 'requester_id', 'assignee_id', 'task_content',
                                                   'due_at', 'conditions_json', 'request_message']},
                   accepted_condition_keys=keep, related_party_rejections=rejection_context(negotiation),
                   feedback={k: negotiation.get(k) for k in ['assignee_comment', 'requester_feedback', 'assignee_feedback']},
                   employees=employees, schedules=[{k: s.get(k) for k in ['id', 'employee_id', 'title', 'type',
                         'status', 'priority', 'workload', 'start_at', 'end_at']} for s in schedules],
                   reschedulable_ids=movable)
    payload['related_candidates']=[dict(id=e['id'],name=e['name'],department=e['department']) for e in all_people
                                   if e['id'] not in {row['requester_id'],row['assignee_id']}]
    output = generate_proposals(payload)
    demo=output.get('mode')=='FIXED_DEMO'
    proposals, signatures, errors = [], set(), []
    for candidate in output['alternatives']:
        try:
            proposal = normalize_proposal(candidate, row, people, schedule_map, movable, keep, start, horizon)
            if demo:
                related=candidate.get('related_employee_ids',[])
                allowed={p['id'] for p in payload['related_candidates']}
                if not isinstance(related,list) or any(type(p) is not int or p not in allowed for p in related):
                    fail('관계자 계정을 확인해주세요.')
                proposal['plan_json']['related_employee_ids']=list(dict.fromkeys(related))
            else:
                validate_plan(cur, row, proposal['plan_json'])
            plan = proposal['plan_json']
            signature = dump(dict(items=sorted([{k:v for k,v in item.items() if k != 'item_key'} for item in plan['items']], key=lambda i: (i['assignee_id'], i['start_at'], i['quantity'])),
                                  changes=sorted(plan['schedule_changes'], key=lambda c: c['schedule_id']),
                                  conditions=plan['conditions_json'], specification=plan['specification']))
            if signature in signatures:
                continue
            signatures.add(signature)
            proposal.update(id=len(proposals)+1, validation='DEMO' if demo else 'VALID')
            if demo:
                proposal['title'] = candidate['title']
            proposals.append(proposal)
        except AppError as error:
            errors.append(error.message)
        except (KeyError, TypeError, ValueError, AttributeError):
            errors.append('작업 항목이나 일정 변경 정보의 형식이 올바르지 않습니다.')
    if len(proposals) != 3:
        reason = errors[0] if errors else str(output.get('reason') or '조건을 유지하는 서로 다른 세 가지 방식으로 다시 제안해야 합니다.')[:1000]
        fail(f'서로 다른 유효한 대안 3개가 필요하지만 {len(proposals)}개만 확인되었습니다. ' + reason + ' 재조정 의견을 작성하거나 다시 생성해주세요.', 409)
    consents = []
    names = {e['id']: e['name'] for e in all_people}
    for alternative in proposals:
        plan = alternative['plan_json']
        parties = {i['assignee_id'] for i in plan['items']}
        parties.update(plan.get('related_employee_ids',[]))
        for change in plan['schedule_changes']:
            parties.update(p for p in [change['employee_id'], change.get('requester_id')] if p)
        for person in sorted(parties - {row['assignee_id'], row['requester_id']}):
            consents.append(dict(id=len(consents)+1, employee_id=person, employee_name=names.get(person, str(person)),
                                 alternative_id=alternative['id'], description=alternative['title']+' · '+plan['description'], status='PENDING'))
    return proposals, consents


def normalize_proposal(candidate, row, people, schedules, movable, keep, start, horizon):
    """Ignore model authority fields; derive participants and original schedule facts from DB."""
    if not isinstance(candidate, dict):
        fail('AI 대안 형식이 올바르지 않습니다.')
    title, description = candidate['title'], candidate['description']
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        fail('AI 대안 제목을 확인해주세요.')
    if not isinstance(description, str) or not description.strip() or len(description) > 5000:
        fail('AI 대안 설명을 확인해주세요.')
    items = candidate['items']
    changes = candidate['schedule_changes']
    if not isinstance(items, list) or not 1 <= len(items) <= 1000 or not isinstance(changes, list) or len(changes) > 30:
        fail('AI 작업 항목 수를 확인해주세요.')
    allowed = {p['id'] for p in people}
    normalized_items, normalized_changes = [], []
    for index, item in enumerate(items):
        if type(item['assignee_id']) is not int or item['assignee_id'] not in allowed:
            fail('제공된 수행자와 같은 팀 직원에게만 배정할 수 있습니다.')
        if type(item['quantity']) is not int or not 1 <= item['quantity'] <= 1000:
            fail('작업 수량은 양의 정수여야 합니다.')
        begin, end, due = (parse_time(item[k]) for k in ['start_at', 'end_at', 'due_at'])
        if begin < start or due > horizon:
            fail('AI 작업 일정이 허용된 계획 기간을 벗어났습니다.')
        normalized_items.append(dict(item_key=f'delivery_{index+1}', assignee_id=item['assignee_id'], quantity=item['quantity'],
                                     start_at=begin.isoformat(), end_at=end.isoformat(), due_at=due.isoformat()))
    for change in changes:
        if type(change['schedule_id']) is not int or change['schedule_id'] not in movable:
            fail('이동 가능한 낮은 우선순위 업무만 순연할 수 있습니다.')
        original = schedules[change['schedule_id']]
        begin, end = parse_time(change['start_at']), parse_time(change['end_at'])
        if begin < start or end > horizon or end-begin != parse_time(original['end_at'])-parse_time(original['start_at']):
            fail('기존 일정의 작업 길이와 계획 기간을 유지해야 합니다.')
        normalized_changes.append(dict(schedule_id=original['id'], employee_id=original['employee_id'],
            requester_id=original.get('requester_id'), title=original['title'], original_start_at=original['start_at'],
            original_end_at=original['end_at'], start_at=begin.isoformat(), end_at=end.isoformat()))
    conditions = copy.deepcopy(row['conditions_json'])
    by_key = {c['key']: c for c in conditions}
    values = candidate['condition_values']
    if not isinstance(values, list) or len(values) > len(conditions):
        fail('AI 조건 항목을 확인해주세요.')
    seen = set()
    for value in values:
        key = value['key']
        if key not in by_key or key in seen:
            fail('알 수 없거나 중복된 조건입니다.')
        seen.add(key)
        if key in {'deadline', 'quantity', 'specification'}:
            continue  # Structured schedule fields are authoritative for these conditions.
        if not (isinstance(value['value'], (str, int, float)) or value['value'] is None):
            fail('조건 값의 형식이 올바르지 않습니다.')
        by_key[key]['value'] = value['value']
    specification = candidate['specification']
    if specification is not None and not isinstance(specification, str):
        fail('규격의 형식이 올바르지 않습니다.')
    proposal = new_alternative(row, 0, title.strip(), normalized_items, description.strip())
    proposal['plan_json'].update(method='MOCK', specification=specification, schedule_changes=normalized_changes,
                                conditions_json=conditions, accepted_condition_keys=keep)
    return proposal
