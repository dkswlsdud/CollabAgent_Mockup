import hashlib
import json
import re
from copy import deepcopy
from app.shared.serialization import dump
from app.shared.errors import fail


def version(value):
    canonical = json.dumps(json.loads(dump(value)), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def request_version(row,rounds,result):
    notice_rounds = deepcopy(rounds)
    for negotiation in notice_rounds:
        alternatives = negotiation.get('alternatives_json') or []
        for side in ('a', 'b'):
            completed = bool(alternatives) and all(a.get(f'{side}_selection_completed') for a in alternatives)
            for alternative in alternatives:
                # Draft clicks are visible in the detail, but only submitted choices
                # constitute a new notification for the collaboration.
                selected = bool(alternative.get(f'{side}_selected')) if completed else False
                alternative[f'{side}_selected'] = selected
                alternative[f'{side}_selection_completed'] = completed
    return version(dict(request={k:row.get(k) for k in ['id','task_content','due_at','status','updated_at']},round=notice_rounds,result=result))


def consent_version(n,c):
    return version(dict(round=n['id'],consent=c,selected=n.get('selected_alternative_key'),
        confirmations=[n.get('a_confirmed_at'),n.get('b_confirmed_at')],
        consents=n.get('consents_json'),preferences=(n.get('agreed_terms_json') or {}).get('calendar_preferences')))


def checked_version(data):
    value=data.get('version')
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):fail('확인한 알림 정보가 올바르지 않습니다.')
    return value
