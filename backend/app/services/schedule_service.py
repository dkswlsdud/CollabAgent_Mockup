"""schedule_service: 업무 규칙과 트랜잭션 처리."""

import calendar
from datetime import datetime, timedelta
from app.services.plan_service import condition_value
from app.shared.serialization import clean
from app.shared.errors import fail
from app.shared.dates import now, parse_time
from app.shared.validation import text
from app.shared.conditions import accepted_conditions
from app.database import transaction
from app.repositories import employee_repository, schedule_repository


def schedules(options, user):
    month = options.get("month", now().strftime("%Y-%m"))
    try:
        first = datetime.strptime(month, "%Y-%m")
        end = first + timedelta(days=calendar.monthrange(first.year, first.month)[1])
    except ValueError:
        fail("월은 YYYY-MM 형식이어야 합니다.")
    scope = options.get("scope", "team")
    if scope not in {"my", "team"}:
        fail("잘못된 일정 범위입니다.")
    selected_employee_id = options.get('employee_id')
    if selected_employee_id not in (None, ''):
        try:
            selected_employee_id = int(selected_employee_id)
            if selected_employee_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            fail('직원 선택 값을 확인해주세요.')
        if scope != 'team':
            fail('직원 필터는 팀 일정에서 사용할 수 있습니다.')
    else:
        selected_employee_id = None
    with transaction() as cur:
        department = user['department']
        if scope == 'team':
            employees = employee_repository.list_active_employees(cur)
            department = options.get('department') or department
            if department not in {e['department'] for e in employees}:
                fail('등록된 부서를 선택해주세요.')
            if selected_employee_id is not None and not any(e['id'] == selected_employee_id and e['department'] == department for e in employees):
                fail('선택한 부서의 직원을 선택해주세요.', 403)
        rows = [
            clean(r)
            for r in schedule_repository.list_schedules(
                cur,
                end,
                first,
                scope,
                user["id"],
                department,
                selected_employee_id,
            )
        ]
    for row in rows:
        row.pop('due_at', None)
    return dict(schedules=rows, month=month, scope=scope)


def schedule_detail(schedule_id):
    with transaction() as cur:
        row = clean(schedule_repository.find_schedule(cur, (schedule_id,)))
    if not row:
        fail("일정을 찾을 수 없습니다.", 404)
    row.pop('due_at', None)
    return dict(schedule=row)


def schedule_values(data):
    title = text(data, "title")
    start, end = (parse_time(data.get("start_at")), parse_time(data.get("end_at")))
    kind = data.get("type", "WORK")
    priority, workload = (
        data.get("priority", "MEDIUM"),
        data.get("workload", "MEDIUM"),
    )
    if end <= start:
        fail("종료는 시작보다 늦어야 합니다.")
    if kind not in {"WORK", "MEETING", "PERSONAL"}:
        fail("일정 유형을 확인해주세요.")
    if priority not in {"LOW", "MEDIUM", "HIGH"} or workload not in {
        "LOW",
        "MEDIUM",
        "HIGH",
    }:
        fail("우선순위와 작업량을 확인해주세요.")
    return (title,kind,start,end,priority,workload,str(data.get('memo',''))[:2000])


def create_schedule(data, user):
    values = schedule_values(data)
    with transaction() as cur:
        employee_repository.lock_employee(cur, (user['id'],))
        schedule_id = schedule_repository.insert_schedule(cur,(user['id'],*values))
    return dict(id=schedule_id)


def owned_schedule(cur, schedule_id, user):
    employee_repository.lock_employee(cur,(user['id'],))
    row = schedule_repository.lock_schedule(cur,schedule_id)
    if not row:
        fail('일정을 찾을 수 없습니다.',404)
    if row['employee_id'] != user['id']:
        fail('본인의 일정만 수정하거나 삭제할 수 있습니다.',403)
    return row


def update_schedule(schedule_id, data, user):
    with transaction() as cur:
        row = owned_schedule(cur,schedule_id,user)
        values = schedule_values(data)
        status = data.get('status',row['status'])
        if status not in {'SCHEDULED','IN_PROGRESS','COMPLETED','CANCELLED'}:
            fail('일정 상태를 확인해주세요.')
        schedule_repository.update_schedule(cur,(*values,status,schedule_id))
    return dict(ok=True,id=schedule_id)


def delete_schedule(schedule_id, user):
    with transaction() as cur:
        owned_schedule(cur,schedule_id,user)
        schedule_repository.delete_schedule(cur,schedule_id)
    return dict(ok=True)


def analysis_for(cur, employee_id, due, row=None):
    from app.services.planning_service import free_slots, window
    start = window(row)[0] if row else max(now(), due - timedelta(days=7))
    rows = [
        clean(r)
        for r in schedule_repository.list_workload_schedules(
            cur, (employee_id, start, due)
        )
    ]
    slots = free_slots(rows, start, due)
    needed = (condition_value(row, 'quantity') or 1) if row else 1
    available = len(slots)
    high = sum(r.get('priority') == 'HIGH' or r.get('workload') == 'HIGH' for r in rows)
    return dict(
        feasibility='IMPOSSIBLE' if not available else 'PARTIAL' if available < needed or high else 'POSSIBLE',
        summary=f'마감 전 빈 시간 {available}시간 / 요청 작업 {needed}시간. 진행 중인 일정 {len(rows)}건, 높은 우선순위·작업량 일정 {high}건을 확인했습니다. 목업은 수량 1개당 1시간으로 계산합니다.',
        recommended_response='CONDITIONAL_ACCEPT',
        recommendation_method='FIXED_DEMO',
        conflicts=rows,
        method="AVAILABILITY_RULES",
        available_hours=available,
        required_hours=needed,
        window_start=start.isoformat(),
        window_end=due.isoformat(),
    )


def save_schedule_items(cur, row, result_id, plan, allow_past=False, employee_ids=None):
    people = {row['requester_id'], row['assignee_id']} | {i['assignee_id'] for i in plan.get('items', [])} | {c['employee_id'] for c in plan.get('schedule_changes', [])}
    people.update(plan.get('related_employee_ids',[]))
    people.update(c['requester_id'] for c in plan.get('schedule_changes', []) if c.get('requester_id'))
    for person in sorted(people):
        employee_repository.lock_employee(cur, (person,))
    for change in plan.get('schedule_changes', []):
        if employee_ids is not None and change['employee_id'] not in employee_ids:
            continue
        current = schedule_repository.lock_schedule(cur, change['schedule_id'])
        if not current or parse_time(current['start_at']) != parse_time(change['original_start_at']) or parse_time(current['end_at']) != parse_time(change['original_end_at']):
            fail('변경 대상 일정이 갱신되었습니다. 재조정해주세요.', 409)
    # This is a mock workflow: registration must not be gated by calendar feasibility.
    registered=set(plan.get('calendar_registered_employee_ids',[]))
    targets=(set(employee_ids) if employee_ids is not None else people)-registered
    targets.discard(row['requester_id'])
    for change in plan.get('schedule_changes', []):
        if change['employee_id'] in targets:
            schedule_repository.reschedule(cur, change)
    for item in plan["items"]:
        if item['assignee_id'] not in targets:
            continue
        schedule_repository.insert_result_schedule(
            cur,
            (
                item["assignee_id"],
                row["requester_id"],
                result_id,
                item["item_key"],
                row["task_content"][:255],
                parse_time(item["start_at"]),
                parse_time(item["end_at"]),
                (plan.get('calendar_preferences',{}).get(str(item['assignee_id'])) or {}).get('priority','MEDIUM'),
                (plan.get('calendar_preferences',{}).get(str(item['assignee_id'])) or {}).get('workload','MEDIUM'),
            ),
        )

    # Non-executing participants see the agreed period without reserving extra work capacity.
    scheduled = {item['assignee_id'] for item in plan['items']} | {c['employee_id'] for c in plan.get('schedule_changes', [])}
    start = min(parse_time(item['start_at']) for item in plan['items'])
    end = max(parse_time(item['end_at']) for item in plan['items'])
    for employee_id in sorted(people - scheduled):
        if employee_id not in targets:
            continue
        schedule_repository.insert_result_overview(cur, (
            employee_id, row['requester_id'], result_id, f'overview:{employee_id}',
            row['task_content'][:255], start, end,
            (plan.get('calendar_preferences',{}).get(str(employee_id)) or {}).get('priority','MEDIUM'),
            (plan.get('calendar_preferences',{}).get(str(employee_id)) or {}).get('workload','LOW')))


def validate_plan(cur, row, plan, allow_past=False, ignore_result_id=None, employee_ids=None):
    if not isinstance(plan, dict) or not plan.get("items"):
        fail("납품 계획이 필요합니다.")
    conditions = {c["key"]: c for c in row["conditions_json"]}
    quantity = condition_value(row, "quantity") or 1
    keep = accepted_conditions(plan)
    hard_quantity = conditions.get('quantity', {}).get('constraint') == 'HARD' or 'quantity' in keep
    changes = plan.get('schedule_changes') or []
    changed_ids = {c['schedule_id'] for c in changes}
    if len(changed_ids) != len(changes):
        fail('변경 일정이 중복되었습니다.')
    people = {e['id']: e for e in employee_repository.list_active_employees(cur)}
    owner = people.get(row['assignee_id'])
    proposed = []
    for change in changes:
        if employee_ids is not None and change['employee_id'] not in employee_ids:
            proposed.append(dict(assignee_id=change['employee_id'],start_at=change['start_at'],end_at=change['end_at'],due_at=change['end_at']))
            continue
        current = schedule_repository.find_schedule(cur, (change['schedule_id'],))
        if not current or current['employee_id'] != row['assignee_id'] or current['type'] != 'WORK' or current['priority'] != 'LOW' or current['status'] != 'SCHEDULED' or current.get('result_id'):
            fail('변경 가능한 낮은 우선순위 업무가 아닙니다.', 409)
        if parse_time(current['start_at']) != parse_time(change['original_start_at']) or parse_time(current['end_at']) != parse_time(change['original_end_at']) or current.get('requester_id') != change.get('requester_id'):
            fail('변경 대상 일정이 바뀌었습니다. 재조정해주세요.', 409)
        proposed.append(dict(assignee_id=change['employee_id'], start_at=change['start_at'], end_at=change['end_at'], due_at=change['end_at']))
    proposed += plan['items']
    total = 0
    for index, item in enumerate(proposed):
        if item in plan['items']:
            if type(item.get('quantity')) is not int or item['quantity']<=0:
                fail('작업 수량은 양의 정수여야 합니다.')
            total+=item['quantity']
        if employee_ids is not None and item['assignee_id'] not in employee_ids:
            continue
        person = people.get(item['assignee_id'])
        if not person or not owner or (item['assignee_id'] != row['assignee_id'] and person['department'] != owner['department']):
            fail('같은 팀의 활성 직원에게만 업무를 분담할 수 있습니다.')
        start, end, due = map(
            parse_time, (item["start_at"], item["end_at"], item["due_at"])
        )
        if not allow_past and start < now() and not (ignore_result_id is not None and item['assignee_id'] in plan.get('calendar_registered_employee_ids',[])):
            fail('이미 지난 시간에는 작업을 배정할 수 없습니다. 재조정해주세요.', 409)
        if start >= end or end > due:
            fail("작업 기간이 마감 안에 들어오도록 계획을 조정해주세요.")
        if item in plan['items'] and (conditions["deadline"]["constraint"] == "HARD" or 'deadline' in keep) and due > parse_time(
            row["due_at"]
        ):
            fail("Hard 마감을 초과했습니다.")
        if (
            start.hour < 9
            or end.hour > 18
            or (end.hour == 18 and end.minute > 0)
            or (start.date() != end.date())
        ):
            fail("작업 시간을 09:00~18:00 안에 배치해주세요.")
        if start.weekday() >= 5:
            fail("주말에는 작업을 배정할 수 없습니다.")
        conflicts = schedule_repository.list_workload_schedules(cur, (item['assignee_id'], start, end))
        conflict = next((s for s in conflicts if s['id'] not in changed_ids and (ignore_result_id is None or s.get('result_id')!=ignore_result_id) and parse_time(s['start_at']) < end and parse_time(s['end_at']) > start), None)
        if conflict:
            fail(
                f"기존 일정 '{conflict['title']}'과 작업 시간이 겹칩니다. 재조정이 필요합니다.",
                409,
            )
        for prior in proposed[:index]:
            if (
                prior["assignee_id"] == item["assignee_id"]
                and parse_time(prior["start_at"]) < end
                and (parse_time(prior["end_at"]) > start)
            ):
                fail("대안 내부 작업 시간이 서로 겹칩니다.")
    if hard_quantity and isinstance(quantity, int) and (total != quantity):
        fail("Hard 수량을 유지해야 합니다.")
    if (conditions.get('specification', {}).get('constraint') == 'HARD' or 'specification' in keep) and plan.get(
        "specification"
    ) != condition_value(row, "specification"):
        fail("Hard 규격을 유지해야 합니다.")
    supplied = {c['key']: c for c in plan.get('conditions_json', row['conditions_json'])}
    for key, condition in conditions.items():
        if (condition['constraint'] == 'HARD' or key in keep) and key not in {'quantity', 'deadline', 'specification'}:
            if supplied.get(key, {}).get('value') != condition.get('value'):
                fail(f"{condition.get('label', key)} 조건을 유지해야 합니다.")


def accepted_request_plan(row):
    """Explicit acceptance registers the agreed request period without availability planning."""
    start, end = now(), parse_time(row['due_at'])
    if end <= start:
        end=start+timedelta(minutes=10)
    return dict(method='DIRECT_ACCEPTANCE', conditions_json=row['conditions_json'],
                items=[dict(item_key='accepted_request', assignee_id=row['assignee_id'],
                            quantity=condition_value(row, 'quantity') or 1,
                            start_at=start.isoformat(), end_at=end.isoformat(), due_at=end.isoformat())])


def save_accepted_request_schedule(cur, row, result_id, plan):
    employee_repository.lock_employee(cur, (row['assignee_id'],))
    item = plan['items'][0]
    schedule_repository.insert_result_schedule(cur, (
        row['assignee_id'], row['requester_id'], result_id, item['item_key'],
        row['task_content'][:255], parse_time(item['start_at']), parse_time(item['end_at']),
        plan['calendar_preferences'][str(row['assignee_id'])]['priority'],
        plan['calendar_preferences'][str(row['assignee_id'])]['workload']))


def schedule_notifications(user):
    with transaction() as cur:
        return schedule_repository.schedule_notification_count(cur, user['id'])


def read_schedule_notifications(data, user):
    ids = data.get('schedule_ids')
    if not isinstance(ids, list) or len(ids) > 2000 or any(type(key) is not int or key <= 0 for key in ids):
        fail('확인한 일정 목록이 올바르지 않습니다.')
    with transaction() as cur:
        schedule_repository.read_schedule_notifications(cur, user['id'], ids)
        return schedule_repository.schedule_notification_count(cur, user['id'])
