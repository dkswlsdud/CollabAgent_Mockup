"""Replace collaborations with demos 2–5; ordinary employee schedules survive."""
import argparse
import copy
import json
from datetime import timedelta
from app.database import connect
from app.shared.dates import now,parse_time
from app.shared.serialization import clean,dump
from app.services.planning_service import generate
from app.services.consent_service import register_consent_calendar
from app.services.agreement_service import complete_agreement
from app.repositories import request_repository as requests,response_repository as responses
from app.repositories import negotiation_repository as rounds,result_repository as results


CASES=[
    (2,'조건부 수락 후 합의 성공','김민지','이서준','select'),
    (3,'관계자 대안 채택 후 수락 시연','이서준','김민지','consent_accept'),
    (4,'관계자 대안 채택 후 거절 시연','이서준','김민지','consent_decline'),
    (5,'조건부 수락 후 공통 대안 없음','이서준','김민지','no_common'),
]

STEPS={
    'pending':'이서준으로 로그인하여 요청 조건을 확인하고 수락합니다. 내 일정 설정을 제출한 뒤 합의 기록과 일정을 확인합니다.',
    'generate':'이서준이 조건부 수락한 상태입니다. 이서준 계정으로 대안 생성 버튼을 누른 뒤, 김민지와 이서준이 각각 가능한 대안을 선택하고 선택완료합니다. 김민지가 공통 대안을 지정한 뒤 양측 최종 확인을 진행합니다.',
    'consent_accept':'관계자 대안3을 채택하고 양측 최종 확인까지 마친 상태입니다. 아래 관계자 계정으로 로그인하여 동의 요청을 열고 수락 및 내 일정 설정을 제출합니다. 이후 김민지 계정으로 내 일정 설정 · 등록을 마치고 합의 완료를 확인합니다.',
    'consent_decline':'관계자 대안3을 채택하고 양측 최종 확인까지 마친 상태입니다. 아래 관계자 계정으로 로그인하여 동의 요청을 열고 거부 사유를 작성해 거절합니다. 이후 이서준 계정으로 거부 사유와 재조정 필요 표시를 확인합니다.',
    'no_common':'양측 모두 선택완료했지만 이서준은 대안1, 김민지는 대안2를 골라 공통 대안이 없는 상태입니다. 요청자 이서준 계정으로 상세 화면을 열면 재조정 의견 안내 팝업이 뜹니다. 재조정 의견을 제출하면 AI 호출 없이 대안1-재생성, 대안2-재생성, 대안3-재생성을 표시합니다.',
    'select':'이서준이 조건부 수락 후 대안 3개 생성까지 마친 상태입니다. 김민지 계정으로 로그인하면 대안 3개가 바로 보입니다. 김민지와 이서준이 각각 대안1을 선택하고 선택완료한 뒤, 김민지가 대안1을 최종 지정합니다. 양측 최종 확인과 이서준의 일정 설정을 마치고 합의 성공을 확인합니다.',
    'consent':'양측 최종 확인이 끝나 관계자의 분담 동의를 기다리는 상태입니다. 아래 관계자로 로그인하여 동의와 내 일정 설정을 제출합니다. 이후 김민지로 돌아와 내 일정 설정을 마치고 합의 완료를 확인합니다.',
    'refused':'양측 최종 확인 후 관계자가 업무 과다로 분담을 거부한 상태입니다. 김민지 또는 이서준으로 거부 사유를 확인하고 재조정 시작 · 대안 생성을 누른 뒤 다시 선택·확인합니다.',
}


def reset(apply=False):
    conn=connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT id,name,department FROM employees WHERE is_active=1 ORDER BY id FOR UPDATE')
            people={p['name']:p for p in cur.fetchall()}
            if not {'김민지','이서준','박지훈','정하은','최유진'}.issubset(people):
                raise RuntimeError('Five demo accounts are required')
            # Only undo unchanged shifts which were applied by a completed old collaboration.
            cur.execute("SELECT agreed_terms_json FROM results WHERE status='ACCEPTED'")
            restored=0
            for record in map(clean,cur.fetchall()):
                for c in (record['agreed_terms_json'] or {}).get('schedule_changes',[]):
                    cur.execute('''UPDATE schedules SET start_at=%s,end_at=%s,is_new=FALSE
                        WHERE id=%s AND result_id IS NULL AND employee_id=%s AND start_at=%s AND end_at=%s''',
                        (c['original_start_at'],c['original_end_at'],c['schedule_id'],c['employee_id'],c['start_at'],c['end_at']))
                    restored+=cur.rowcount
            cur.execute('DELETE FROM schedules WHERE result_id IS NOT NULL')
            removed=cur.rowcount
            for table in ['collaboration_reads','request_attachments','results','responses','negotiations','requests']:
                cur.execute('DELETE FROM '+table)
            cur.execute('DELETE FROM schedules WHERE memo IN (%s,%s)',('시연용 · 박지훈 요청 일정 변경 동의 테스트','pair-scenario-helper'))
            cur.execute('SELECT COUNT(*) AS count FROM schedules')
            preserved=cur.fetchone()['count']
            report=[]
            for number,name,sender,worker,phase in CASES:
                stamp=now()
                due=(stamp+timedelta(days=7)).replace(hour=18,minute=0,second=0,microsecond=0)
                title=f'시연{number} - {name}'
                conditions=[dict(key='deadline',label='마감',constraint='HARD'),
                    dict(key='quantity',label='수량',constraint='HARD',value=2,unit='건'),
                    dict(key='specification',label='검토 기준',constraint='SOFT',value='시연 자료를 검토하고 문서 댓글로 의견 전달',unit='')]
                original=f'{name} 시연입니다. 자료 2건 검토를 부탁드립니다.\n\n[시연 순서]\n{STEPS[phase]}'
                row=dict(requester_id=people[sender]['id'],assignee_id=people[worker]['id'],task_content=title,
                         due_at=due.isoformat(),conditions_json=conditions)
                rid=requests.insert_request(cur,(row['requester_id'],row['assignee_id'],original,title,due,dump(conditions)))
                row['id']=rid
                requests.save_request_message(cur,(f'{worker} 님, {due:%Y-%m-%d %H:%M}까지 시연 자료 2건 검토를 부탁드립니다. {original}',rid))
                related=[]
                if phase in {'rejected','cancelled'}:
                    status='REJECTED' if phase=='rejected' else 'CANCELLED'
                    reason='시연용 거절 사유입니다. 요청 범위 재협의가 필요합니다.' if phase=='rejected' else '요청자가 시연 협업을 취소했습니다.'
                    if phase=='rejected':responses.insert_response(cur,(rid,'REJECTED',reason))
                    results.insert_direct_result(cur,(rid,status,None,reason,None,None,stamp))
                    requests.update_request_status(cur,(status,rid))
                elif phase!='pending':
                    comment='마감과 수량을 유지하며 시연 대안을 비교하고 싶습니다.'
                    responses.insert_response(cur,(rid,'REJECTED',comment))
                    analysis=dict(method='FIXED_DEMO',recommended_response='CONDITIONAL_ACCEPT',summary='시연용 조건부 수락 추천입니다.')
                    nid=rounds.insert_round(cur,(rid,1,dump(row),dump(analysis)))
                    rounds.update_response_conditions(cur,(['deadline','quantity'],comment,nid))
                    requests.update_request_status(cur,('NEGOTIATING',rid))
                    if phase!='generate':
                        alternatives,consents=generate(cur,row,dict(assignee_comment=comment,accepted_condition_keys_json=['deadline','quantity']))
                        for c in consents:c['status']='WAITING'
                        chosen=1 if phase=='confirm' else 3
                        selected=alternatives[chosen-1]
                        if phase=='partial':
                            park=people['박지훈']
                            selected['plan_json'].setdefault('related_employee_ids',[]).append(park['id'])
                            consents.append(dict(id=max(c['id'] for c in consents)+1,employee_id=park['id'],employee_name=park['name'],
                                alternative_id=3,description='박지훈 님의 추가 확인을 기다리는 시연입니다.',status='WAITING'))
                        if phase not in {'select','no_common'}:
                            for a in alternatives:
                                a.update(a_selected=a['id']==chosen,b_selected=a['id']==chosen,a_selection_completed=True,b_selection_completed=True)
                            rounds.update_selected_alternative(cur,(str(chosen),nid))
                            plan=dict(copy.deepcopy(selected['plan_json']),calendar_preferences_required=True,calendar_preferences={})
                            result_id=results.insert_pending_result(cur,(rid,nid,dump(plan)))
                            if phase!='confirm':
                                results.confirm_result(cur,(stamp,result_id),'a_confirmed_at')
                                results.confirm_result(cur,(stamp,result_id),'b_confirmed_at')
                                for c in consents:
                                    if c['alternative_id']==chosen:
                                        c.update(status='PENDING',requested_at=stamp.isoformat())
                                        related.append(c['employee_name'])
                                first=next(c for c in consents if c['alternative_id']==chosen)
                                if phase=='refused':
                                    first.update(status='REJECTED',reason='현재 담당 업무가 많아 이번 이미지 검토를 분담하기 어렵습니다. 제 분담 없이 다른 방식으로 재조정해주세요.',responded_at=stamp.isoformat())
                                if phase in {'partial','settings','completed'}:
                                    first.update(status='APPROVED',responded_at=stamp.isoformat())
                            rounds.update_alternatives(cur,(dump(alternatives),nid))
                            rounds.update_consents(cur,(dump(consents),nid))
                            if phase in {'partial','settings','completed'}:
                                result=clean(results.find_result(cur,(rid,)))
                                register_consent_calendar(cur,row,result,first['employee_id'],dict(schedule_priority='HIGH',schedule_workload='LOW'))
                                if phase=='completed':
                                    for actor in [row['assignee_id']]:
                                        result['agreed_terms_json']['calendar_preferences'][str(actor)]=dict(priority='MEDIUM',workload='MEDIUM')
                                    results.update_agreed_terms(cur,(dump(result['agreed_terms_json']),result_id))
                                    n=clean(rounds.lock_latest_round(cur,(rid,)))
                                    complete_agreement(cur,row,result,n)
                        else:
                            if phase=='no_common':
                                for alternative in alternatives:
                                    alternative.update(a_selected=alternative['id']==1,b_selected=alternative['id']==2,
                                                       a_selection_completed=True,b_selection_completed=True)
                            rounds.update_alternatives(cur,(dump(alternatives),nid))
                            rounds.update_consents(cur,(dump(consents),nid))
                if related:
                    original+='\n\n[관계자]\n'+', '.join(related)
                    requests.save_request_message(cur,(f'{worker} 님, {due:%Y-%m-%d %H:%M}까지 시연 자료 2건 검토를 부탁드립니다. {original}',rid))
                report.append(dict(id=rid,title=title,requester=sender,assignee=worker,phase=phase,related=related))
            cur.execute('SELECT COUNT(*) AS count FROM requests')
            if cur.fetchone()['count']!=len(CASES):raise RuntimeError('Unexpected collaboration count')
        if apply:conn.commit()
        else:conn.rollback()
        return dict(applied=apply,ordinary_schedules_preserved=preserved,old_collaboration_schedules_removed=removed,
                    old_schedule_shifts_restored=restored,scenarios=report)
    except Exception:
        conn.rollback()
        raise
    finally:conn.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    print(json.dumps(reset(parser.parse_args().apply),ensure_ascii=False))
