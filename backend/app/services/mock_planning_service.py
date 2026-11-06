"""Fixed presentation fixtures. Never block creation based on calendar feasibility."""
from datetime import timedelta
from app.shared.dates import parse_time
from app.shared.errors import fail


def generate_proposals(payload):
    row=payload['request']
    owner=row['assignee_id']
    conditions={c['key']:c for c in row['conditions_json']}
    quantity=int(conditions.get('quantity',{}).get('value') or 1)
    people=[p for p in payload['employees'] if p['id'] not in {owner,row['requester_id']}]
    candidates=people or payload.get('related_candidates',[])
    if not candidates:
        fail('관계자 계정이 없습니다. 대안3의 동의 요청을 받을 직원을 등록해주세요.',409)
    rejected={r['employee_id'] for r in payload.get('related_party_rejections',[])}
    peer=next((p for p in candidates if p['id'] not in rejected),candidates[0])
    assigned=peer['id'] in {p['id'] for p in people}
    begin=(parse_time(payload['current_at'])+timedelta(days=1)).replace(hour=9,minute=0,second=0,microsecond=0)
    while begin.weekday()>=5:begin+=timedelta(days=1)
    def item(person,count,index):
        start=begin+timedelta(minutes=10*index)
        return dict(assignee_id=person,quantity=count,start_at=start.isoformat(),
                    end_at=(start+timedelta(minutes=10)).isoformat(),due_at=row['due_at'])
    shared=([item(owner,quantity-1,2),item(peer['id'],1,2)] if quantity>1 else [item(peer['id'],1,2)]) if assigned else [item(owner,quantity,2)]
    plans=[[item(owner,quantity,0)],[item(owner,quantity,1)],shared]
    titles=['대안1','대안2','대안3(관계자 필요)']
    feedback=payload.get('feedback') or {}
    if payload.get('related_party_rejections') or feedback.get('requester_feedback') or feedback.get('assignee_feedback'):
        titles=[f'대안{index}-재생성' for index in range(1,4)]
    descriptions=['수행자가 진행하는 고정 시연안입니다.','다른 방식으로 진행하는 고정 시연안입니다.',
        f"{peer['name']} 님의 동의가 필요한 고정 시연안입니다. 양측 최종 확인 후 동의 요청을 보냅니다."]
    return dict(mode='FIXED_DEMO',alternatives=[dict(title=titles[index],description=descriptions[index],
        items=items,schedule_changes=[],specification=conditions.get('specification',{}).get('value'),
        condition_values=[],related_employee_ids=[peer['id']] if index==2 else []) for index,items in enumerate(plans)],reason='')
