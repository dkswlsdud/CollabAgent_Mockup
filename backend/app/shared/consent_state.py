"""Shared refusal context for participant notices and AI recoordination."""


def selected_rejections(consents, selected_key):
    return [dict(employee_id=c['employee_id'], employee_name=c.get('employee_name', '관계자'),
                 reason=c.get('reason') or '거부 사유가 기록되지 않았습니다.',
                 alternative_id=c['alternative_id'], responded_at=c.get('responded_at'))
            for c in consents or [] if c.get('status') == 'REJECTED'
            and str(c['alternative_id']) == str(selected_key)]


def rejection_context(negotiation):
    if not negotiation:
        return []
    inherited = (negotiation.get('request_snapshot_json') or {}).get('related_party_rejections') or []
    current = selected_rejections(negotiation.get('consents_json'), negotiation.get('selected_alternative_key'))
    alternatives = {str(a['id']): a for a in negotiation.get('alternatives_json') or []}
    for entry in current:
        plan = alternatives.get(str(entry['alternative_id']), {}).get('plan_json') or {}
        entry['declined_items'] = [item for item in plan.get('items') or [] if item['assignee_id'] == entry['employee_id']]
        entry['declined_schedule_changes'] = [change for change in plan.get('schedule_changes') or []
                                              if entry['employee_id'] in {change['employee_id'], change.get('requester_id')}]
    result, seen = [], set()
    for entry in inherited + current:
        key = (entry['employee_id'], entry['reason'])
        if key not in seen:
            result.append(entry)
            seen.add(key)
    return result
