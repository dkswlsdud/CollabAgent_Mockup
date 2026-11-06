"""Employee-selected metadata for automatically registered collaboration schedules."""
from app.shared.errors import fail, AppError


def calendar_preference(data):
    priority, workload = data.get('schedule_priority'), data.get('schedule_workload')
    if priority not in {'LOW','MEDIUM','HIGH'} or workload not in {'LOW','MEDIUM','HIGH'}:
        fail('내 일정의 우선순위와 작업량을 모두 선택해주세요.')
    return dict(priority=priority,workload=workload)


def calendar_participants(row,plan):
    people = {row['requester_id'],row['assignee_id']} | {i['assignee_id'] for i in plan['items']}
    people.update(plan.get('related_employee_ids',[]))
    for change in plan.get('schedule_changes',[]):
        people.add(change['employee_id'])
        if change.get('requester_id'):people.add(change['requester_id'])
    people.discard(row['requester_id'])
    return people


def require_preferences(row, plan):
    if not plan.get('calendar_preferences_required'):
        return
    people=calendar_participants(row,plan)
    preferences = plan.get('calendar_preferences') or {}
    for employee_id in people:
        chosen = preferences.get(str(employee_id)) or {}
        calendar_preference(dict(schedule_priority=chosen.get('priority'),schedule_workload=chosen.get('workload')))


def selected_consents(negotiation):
    return [c for c in negotiation.get('consents_json') or [] if str(c['alternative_id']) == str(negotiation.get('selected_alternative_key'))]


def settings_ready(result, negotiation):
    return bool(result and result.get('a_confirmed_at') and result.get('b_confirmed_at') and
                all(c['status']=='APPROVED' for c in selected_consents(negotiation)))


def preferences_complete(row, plan):
    try:
        require_preferences(row,plan)
        return True
    except AppError:
        return False
