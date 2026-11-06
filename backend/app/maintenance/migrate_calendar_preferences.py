"""Require explicit schedule preferences for unfinished agreements; preserve prior checks."""
import json
from app.database import connect
from app.shared.serialization import clean,dump


def migrate():
    conn=connect()
    changed=[]
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT x.*,r.requester_id,r.assignee_id,n.selected_alternative_key,n.consents_json
                FROM results x JOIN requests r ON r.id=x.request_id JOIN negotiations n ON n.id=x.negotiation_id
                WHERE x.status='PENDING_CONFIRMATION' AND n.status='IN_PROGRESS' FOR UPDATE""")
            for result in map(clean,cur.fetchall()):
                plan=result['agreed_terms_json']
                if plan.get('calendar_preferences_required'):continue
                plan['calendar_preferences_required']=True
                plan.setdefault('calendar_preferences',{})
                selected=[c for c in result['consents_json'] or [] if str(c['alternative_id'])==str(result['selected_alternative_key'])]
                refused=any(c['status']=='REJECTED' for c in selected)
                if not refused:
                    plan['previous_final_confirmation']={key:result.get(key) for key in ['a_confirmed_at','b_confirmed_at']}
                    for c in selected:
                        if c.get('responded_at'):c['previous_response']={key:c.get(key) for key in ['status','responded_at']}
                        c['status']='WAITING'
                        c.pop('requested_at',None)
                        c.pop('responded_at',None)
                    cur.execute('UPDATE results SET a_confirmed_at=NULL,b_confirmed_at=NULL WHERE id=%s',(result['id'],))
                    cur.execute('UPDATE negotiations SET consents_json=%s WHERE id=%s',(dump(result['consents_json']),result['negotiation_id']))
                cur.execute('UPDATE results SET agreed_terms_json=%s WHERE id=%s',(dump(plan),result['id']))
                changed.append(dict(request_id=result['request_id'],requires_new_confirmation=not refused))
        conn.commit()
        return dict(updated=changed,completed_agreements_preserved=True)
    except Exception:
        conn.rollback()
        raise
    finally:conn.close()


if __name__=='__main__':print(json.dumps(migrate()))
