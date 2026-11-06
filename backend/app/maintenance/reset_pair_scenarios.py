"""Replace collaboration demos with six Kim Minji / Lee Seojun scenarios, atomically."""
import argparse
import copy
import json
from datetime import timedelta
from app.database import connect
from app.shared.dates import now, parse_time
from app.shared.serialization import clean, dump
from app.services.planning_service import free_slots
from app.services.plan_service import new_alternative
from app.services.schedule_service import validate_plan, analysis_for, save_schedule_items
from app.repositories import request_repository as requests, response_repository as responses
from app.repositories import result_repository as results, negotiation_repository as rounds


HELPER_MEMO = '시연용 · 박지훈 요청 일정 변경 동의 테스트'


def reset(apply=False):
    conn = connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT id,name,department FROM employees WHERE is_active=1 ORDER BY id FOR UPDATE')
            people = {e['name']:e for e in cur.fetchall()}
            if not {'김민지','이서준','박지훈','정하은','최유진'}.issubset(people):
                raise RuntimeError('Five demo employees are required')
            # Undo only unchanged, previously applied moves before removing collaboration records.
            cur.execute("SELECT agreed_terms_json FROM results WHERE status='ACCEPTED' AND agreed_terms_json IS NOT NULL")
            restored = 0
            for result in map(clean, cur.fetchall()):
                for change in result['agreed_terms_json'].get('schedule_changes', []):
                    cur.execute('''UPDATE schedules SET start_at=%s,end_at=%s,is_new=FALSE
                        WHERE id=%s AND employee_id=%s AND result_id IS NULL AND start_at=%s AND end_at=%s''',
                        (change['original_start_at'],change['original_end_at'],change['schedule_id'],change['employee_id'],change['start_at'],change['end_at']))
                    restored += cur.rowcount
            cur.execute('DELETE FROM schedules WHERE result_id IS NOT NULL')
            removed_schedules = cur.rowcount
            for table in ['results','responses','negotiations','requests']:
                cur.execute('DELETE FROM '+table)
            cur.execute("DELETE FROM schedules WHERE memo IN (%s,%s)",(HELPER_MEMO,'pair-scenario-helper'))
            cur.execute('SELECT * FROM schedules ORDER BY id')
            existing = [clean(row) for row in cur.fetchall()]
            start = now().replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
            horizon = start+timedelta(days=45)
            reserved = []

            def take(name, hours=1, after=None, reserve=True):
                person = people[name]['id']
                slots = free_slots([row for row in existing+reserved if row['employee_id']==person],max(start,after or start),horizon)
                available = set(slots)
                for begin, _ in slots:
                    end = begin+timedelta(hours=hours)
                    if all((begin+timedelta(hours=i),begin+timedelta(hours=i+1)) in available for i in range(hours)):
                        if reserve:
                            reserved.append(dict(id=-len(reserved)-1,employee_id=person,start_at=begin.isoformat(),end_at=end.isoformat(),status='SCHEDULED'))
                        return begin,end
                raise RuntimeError('No available demo time for '+name)

            # Park is an original requester of Lee's existing low-priority task, not a cross-team assignee.
            helper_start, helper_end = take('이서준',after=(start+timedelta(days=14)).replace(hour=9),reserve=False)
            cur.execute('''INSERT INTO schedules(employee_id,requester_id,title,type,start_at,end_at,priority,workload,memo)
                VALUES(%s,%s,%s,'WORK',%s,%s,'LOW','LOW',%s)''',
                (people['이서준']['id'],people['박지훈']['id'],'콘텐츠팀 요청 이미지 간단 보정',helper_start,helper_end,HELPER_MEMO))
            helper_id = cur.lastrowid
            cur.execute('SELECT * FROM schedules WHERE id=%s',(helper_id,))
            helper = clean(cur.fetchone())
            existing.append(helper)

            def case(number, sender, worker, title, quantity=2, deadline='HARD', spec='1200×600px PNG'):
                return dict(number=number,requester_id=people[sender]['id'],assignee_id=people[worker]['id'],
                    requester=sender,assignee=worker,task_content=title.split(' · ',1)[0],due_at=horizon.isoformat(),
                    conditions_json=[dict(key='deadline',label='마감',constraint=deadline),dict(key='quantity',label='수량',value=quantity,unit='건' if worker=='김민지' else '개',constraint='HARD'),dict(key='specification',label='규격·검토 기준',value=spec,constraint='HARD')])

            def item(name, period, quantity):
                return dict(assignee_id=people[name]['id'],quantity=quantity,start_at=period[0].isoformat(),end_at=period[1].isoformat(),due_at=horizon.isoformat())

            def option(row, index, title, items, description, changes=None):
                for key, value in enumerate(items,1):value['item_key']=f'delivery_{key}'
                alt = new_alternative(row,index,'ABC'[index-1]+'안 · '+title,items,description)
                alt['plan_json'].update(method='DEMO_SCENARIO',conditions_json=copy.deepcopy(row['conditions_json']),accepted_condition_keys=['deadline','specification'],schedule_changes=changes or [])
                alt['validation']='VALID'
                return alt

            def set_due(row, alternatives):
                row['due_at'] = max(parse_time(i['end_at']) for a in alternatives for i in a['plan_json']['items']).replace(hour=18,minute=0).isoformat()
                for a in alternatives:
                    for i in a['plan_json']['items']:i['due_at']=row['due_at']

            report=[]
            def persist(row, status, alternatives=None, related=None, refused=False, completed=False):
                alternatives=alternatives or []
                if alternatives:set_due(row,alternatives)
                for alt in alternatives:validate_plan(cur,row,alt['plan_json'])
                message=f"{row['assignee']} 님, {row['due_at'][:10]}까지 {row['task_content'].split('] ',1)[-1]} 작업을 부탁드립니다. 수량과 규격을 확인해주세요."
                rid=requests.insert_request(cur,(row['requester_id'],row['assignee_id'],f"[시연 {row['number']}] {message}",row['task_content'],row['due_at'],dump(row['conditions_json'])))
                requests.save_request_message(cur,(message,rid))
                row['id']=rid
                if status!='PENDING':
                    comment='수량과 규격은 유지하고, 제시된 작업 시간 또는 관계자 분담으로 진행하고 싶습니다.'
                    responses.insert_response(cur,(rid,'ACCEPTED' if completed else 'REJECTED',None if completed else comment))
                    if completed:
                        plan=alternatives[0]['plan_json']
                        result_id=results.insert_direct_result(cur,(rid,'ACCEPTED',dump(plan),None,now(),now(),now()))
                        save_schedule_items(cur,row,result_id,plan)
                    else:
                        snapshot={k:row[k] for k in ['id','requester_id','assignee_id','task_content','due_at','conditions_json']}
                        analysis=analysis_for(cur,row['assignee_id'],parse_time(row['due_at']),row)
                        nid=rounds.insert_round(cur,(rid,1,dump(snapshot),dump(analysis)))
                        rounds.update_response_conditions(cur,(['deadline','specification'],comment,nid))
                        consents=[]
                        if related:
                            for alt in alternatives:
                                alt.update(a_selected=alt['id']==1,b_selected=alt['id']==1,a_selection_completed=True,b_selection_completed=True)
                                consent=dict(id=alt['id'],employee_id=people[related]['id'],employee_name=related,alternative_id=alt['id'],description=alt['title']+' · '+alt['plan_json']['description'],status='WAITING')
                                if alt['id']==1:
                                    consent.update(status='REJECTED' if refused else 'WAITING')
                                    if refused:consent['requested_at']=now().isoformat()
                                    if refused:consent.update(reason='현재 담당 업무량이 많아 이번 제작 업무는 분담하기 어렵습니다. 해당 분담 없이 다시 조율해주세요.',responded_at=now().isoformat())
                                consents.append(consent)
                            rounds.update_selected_alternative(cur,('1',nid))
                            plan=dict(alternatives[0]['plan_json'],calendar_preferences_required=True,calendar_preferences={})
                            result_id=results.insert_pending_result(cur,(rid,nid,dump(plan)))
                            if refused:cur.execute('UPDATE results SET a_confirmed_at=NOW(),b_confirmed_at=NOW() WHERE id=%s',(result_id,))
                        rounds.update_alternatives(cur,(dump(alternatives),nid))
                        rounds.update_consents(cur,(dump(consents),nid))
                    requests.update_request_status(cur,(status,rid))
                report.append(dict(id=rid,title=row['task_content'],requester=row['requester'],assignee=row['assignee'],status=status,related=related,refused=refused,due_at=row['due_at']))

            pending=case(1,'김민지','이서준','이벤트 배너 제작 · 응답 대기')
            pending['due_at']=take('이서준',reserve=False)[0].replace(hour=18).isoformat()
            persist(pending,'PENDING')
            accepted=case(2,'이서준','김민지','홍보 문구 검토 · 수락 완료',1,spec='브랜드 말투와 핵심 메시지 유지')
            persist(accepted,'ACCEPTED',[option(accepted,1,'문구 검토',[item('김민지',take('김민지'),1)],'김민지가 홍보 문구 1건을 검토합니다.')],completed=True)
            choice=case(3,'김민지','이서준','카드뉴스 제작 · 대안 선택',deadline='SOFT')
            after=parse_time(pending['due_at'])+timedelta(hours=1)
            choices=[option(choice,index,'작업 시간 조정 '+str(index),[item('이서준',take('이서준',hours=2,after=after),2)],'이서준의 기존 업무를 유지하고 비어 있는 두 시간에 카드뉴스 2개를 제작합니다.') for index in range(1,4)]
            persist(choice,'NEGOTIATING',choices)
            shared=case(4,'이서준','김민지','캠페인 문구 검토 · 최유진 동의 대기',spec='핵심 메시지와 상품명 유지')
            sharing=[]
            for index in range(1,4):
                main=take('김민지')
                other=take('최유진',after=main[0])
                sharing.append(option(shared,index,'김민지·최유진 분담 '+str(index),[item('김민지',main,1),item('최유진',other,1)],'김민지가 문구 1건, 같은 마케팅팀 최유진이 1건을 검토합니다. 최유진의 분담 동의가 필요합니다.'))
            persist(shared,'NEGOTIATING',sharing,related='최유진')
            refusal=case(5,'김민지','이서준','프로모션 이미지 제작 · 정하은 거부 후 재조정')
            refused_options=[]
            for index in range(1,4):
                main=take('이서준',after=after)
                other=take('정하은',after=main[0])
                refused_options.append(option(refusal,index,'이서준·정하은 분담 '+str(index),[item('이서준',main,1),item('정하은',other,1)],'이서준과 정하은이 이미지 1개씩 제작합니다. 정하은의 분담 동의가 필요합니다.'))
            persist(refusal,'NEGOTIATING',refused_options,related='정하은',refused=True)
            shift=case(6,'김민지','이서준','긴급 배너 보정 · 박지훈 일정 변경 동의',1)
            moves=[]
            for index in range(1,4):
                moved=take('이서준',after=helper_start+timedelta(days=3))
                change=dict(schedule_id=helper_id,employee_id=people['이서준']['id'],requester_id=people['박지훈']['id'],title=helper['title'],original_start_at=helper['start_at'],original_end_at=helper['end_at'],start_at=moved[0].isoformat(),end_at=moved[1].isoformat())
                moves.append(option(shift,index,'기존 저우선순위 업무 순연 '+str(index),[item('이서준',(helper_start,helper_end),1)],'박지훈이 요청한 기존 이미지 보정 업무를 뒤로 옮기고 긴급 배너를 먼저 처리합니다. 기존 요청자 박지훈의 동의가 필요합니다.',[change]))
            persist(shift,'NEGOTIATING',moves,related='박지훈')
        if apply:conn.commit()
        else:conn.rollback()
        return dict(applied=apply,old_generated_schedules_removed=removed_schedules,old_schedule_moves_restored=restored,base_schedules_preserved=len(existing)-1,helper_schedule_id=helper_id,scenarios=report)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    print(json.dumps(reset(parser.parse_args().apply),ensure_ascii=False,default=str))
