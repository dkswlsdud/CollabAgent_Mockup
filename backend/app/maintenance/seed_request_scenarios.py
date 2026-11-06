"""Explicitly add five authored demo scenarios without changing employee schedules."""
import argparse
import copy
import json
from datetime import datetime
from app.database import connect
from app.shared.serialization import dump
from app.services.plan_service import new_alternative
from app.services.schedule_service import analysis_for, validate_plan
from app.repositories import request_repository, response_repository, result_repository, negotiation_repository


def build_scenarios(employees):
    people = {e['name']:e for e in employees}

    def case(number, requester, assignee, title, due, quantity, deadline='HARD', count='HARD', spec='1200×600px'):
        return dict(number=number, title=f'[시연 {number}] {title}', requester_id=people[requester]['id'],
                    assignee_id=people[assignee]['id'], due_at=f'2026-11-{due:02}T18:00:00',
                    original_text=f'{assignee} 님에게 11월 {due}일 18시까지 {title} {quantity}건을 요청합니다. 규격·검토 기준: {spec}.',
                    conditions_json=[dict(key='deadline',label='마감',constraint=deadline),
                                     dict(key='quantity',label='수량',value=quantity,unit='건' if number==5 else '개',constraint=count),
                                     dict(key='specification',label='검토 기준' if number==5 else '규격',value=spec,constraint='HARD')],
                    rounds=[], alternatives=[], consents=[], result=None, status='NEGOTIATING')

    def item(name, day, start, end, quantity):
        return dict(assignee_id=people[name]['id'],quantity=quantity,start_at=f'2026-11-{day:02}T{start:02}:00:00',
                    end_at=f'2026-11-{day:02}T{end:02}:00:00',due_at=f'2026-11-{day:02}T18:00:00')

    def alternative(row, key, title, items, description, keep):
        for index, value in enumerate(items,1): value['item_key'] = f'delivery_{index}'
        value = new_alternative(row,key,title,items,description)
        value['plan_json'].update(method='DEMO_SCENARIO',conditions_json=copy.deepcopy(row['conditions_json']),accepted_condition_key=keep)
        value['validation'] = 'VALID'
        return value

    easy = case(1,'김민지','정하은','프로모션 아이콘 제작',6,2,count='SOFT',spec='64×64px PNG')
    easy['status'] = 'PENDING'

    rejected = case(2,'최유진','이서준','긴급 광고 배너 제작',4,5)
    rejected.update(status='REJECTED', reason='11월 5일 18시까지 진행 중인 상세페이지 리뉴얼이 우선순위 높음·작업량 많음으로 잡혀 있어, 11월 4일까지 배너 5개를 제작하기 어렵습니다.')

    split = case(3,'최유진','이서준','SNS 썸네일 분할 납품',12,8,deadline='SOFT')
    split.update(keep='quantity', comment='11월 12일부터 작업 가능하며, 당일에는 4개까지 가능합니다. 나머지는 다음 영업일에 납품하고 싶습니다.')
    split['alternatives'] = [
        alternative(split,1,'A안 · 4개씩 분할 납품',[item('이서준',12,13,17,4),item('이서준',13,9,13,4)],
                    '11/12 오후 4개, 11/13 오전 4개를 제작합니다. 수량과 규격은 유지하고 Soft 마감을 연장합니다.','quantity'),
        alternative(split,2,'B안 · 일정 종료 후 일괄 납품',[item('이서준',17,9,17,8)],
                    '기존 뉴스레터 이미지 보정 일정이 끝난 뒤 11/17에 8개를 일괄 제작합니다.','quantity'),
    ]

    shared = case(4,'박지훈','이서준','뉴스레터 이미지 업무 분담',6,12)
    shared.update(keep='deadline',comment='11월 6일까지 제가 6개를 맡을 수 있습니다. 나머지 6개는 같은 디자인팀 정하은 님과 분담하고 싶습니다.')
    shared['alternatives'] = [
        alternative(shared,1,'A안 · 이서준 6개 + 정하은 6개',[item('이서준',6,9,15,6),item('정하은',6,12,18,6)],
                    '이서준은 11/6 09~15시, 정하은은 검수 일정이 끝난 12~18시에 작업합니다. 정하은의 동의가 필요합니다.','deadline'),
        alternative(shared,2,'B안 · 이서준 5개 + 정하은 7개',[item('이서준',6,9,14,5),item('정하은',4,17,18,1),item('정하은',6,12,18,6)],
                    '정하은의 11/4 마지막 한 시간과 11/6 오후를 활용해 7개를 분담합니다.','deadline'),
    ]
    shared['alternatives'][0].update(a_selected=True,b_selected=True)
    shared['alternatives'][1]['b_selected'] = True
    shared['selected'] = 1
    shared['consents'] = [dict(id=index,employee_id=people['정하은']['id'],employee_name='정하은',alternative_id=index,
                             description=f'뉴스레터 이미지 {6 if index==1 else 7}개 제작 분담에 동의해주세요.',status='PENDING') for index in (1,2)]

    retry = case(5,'정하은','김민지','브랜드 소개 문구 검토',9,6,deadline='SOFT',count='SOFT',spec='브랜드 말투와 핵심 메시지 유지')
    retry.update(keep='specification',comment='11월 9일부터 검토할 수 있고, 당일에는 4건까지 가능합니다.')
    first = [
        alternative(retry,1,'A안 · 6건 유지, 하루 연장',[item('김민지',9,9,13,4),item('김민지',10,9,11,2)],
                    '11/9에 4건, 11/10에 2건을 검토해 수량 6건을 유지합니다.','specification'),
        alternative(retry,2,'B안 · 4건으로 조정',[item('김민지',9,9,13,4)],
                    '마감을 유지하면서 Soft 수량을 4건으로 줄입니다.','specification'),
    ]
    first[0]['a_selected'] = True
    first[1]['b_selected'] = True
    retry['history'] = dict(alternatives=first,requester_feedback='검토 6건은 모두 필요합니다. 마감을 11/10으로 연장하는 안을 수용하겠습니다.',
                            assignee_feedback='11/9에는 4건만 가능해서 수량 조정안을 선택했습니다. 하루 연장이 가능하면 6건을 검토할 수 있습니다.')
    retry['alternatives'] = [
        alternative(retry,1,'A안 · 4건 + 2건 분할 검토',[item('김민지',9,9,13,4),item('김민지',10,9,11,2)],
                    '양측 수정 의견을 반영해 마감을 11/10으로 연장하고 수량 6건을 유지합니다.','specification'),
        alternative(retry,2,'B안 · 11/10 일괄 검토',[item('김민지',10,9,15,6)],
                    '11/9 기존 일정은 유지하고 11/10에 6건을 일괄 검토합니다.','specification'),
    ]
    return [easy,rejected,split,shared,retry]


def seed(apply=False):
    conn = connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT id,name,department FROM employees WHERE is_active=1 ORDER BY id' + (' FOR UPDATE' if apply else ''))
            employees = cur.fetchall()
            scenarios = build_scenarios(employees)
            cur.execute('SELECT id,employee_id,title,start_at,end_at,status,priority,workload FROM schedules ORDER BY id')
            schedules_before = cur.fetchall()
            report = []
            for scenario in scenarios:
                cur.execute('SELECT id,status FROM requests WHERE requester_id=%s AND assignee_id=%s AND task_content=%s',
                            (scenario['requester_id'],scenario['assignee_id'],scenario['title']))
                existing = cur.fetchone()
                if existing:
                    report.append(dict(number=scenario['number'],id=existing['id'],status=existing['status'],added=False))
                    continue
                for option in scenario['alternatives'] + scenario.get('history',{}).get('alternatives',[]):
                    validate_plan(cur,scenario,option['plan_json'])
                if not apply:
                    report.append(dict(number=scenario['number'],title=scenario['title'],status=scenario['status'],validated=True))
                    continue
                request_id = request_repository.insert_request(cur,(scenario['requester_id'],scenario['assignee_id'],scenario['original_text'],scenario['title'],
                                                                     scenario['due_at'],dump(scenario['conditions_json'])))
                request_repository.update_request_status(cur,(scenario['status'],request_id))
                if scenario['status']=='REJECTED':
                    response_repository.insert_response(cur,(request_id,'REJECTED',scenario['reason']))
                    result_repository.insert_direct_result(cur,(request_id,'REJECTED',None,scenario['reason'],None,None,None))
                elif scenario['status']=='NEGOTIATING':
                    response_repository.insert_response(cur,(request_id,'REJECTED',scenario['comment']))
                    row = dict(id=request_id,requester_id=scenario['requester_id'],assignee_id=scenario['assignee_id'],task_content=scenario['title'],
                               due_at=scenario['due_at'],conditions_json=scenario['conditions_json'])
                    analysis = analysis_for(cur,row['assignee_id'],datetime.fromisoformat(row['due_at']),row)
                    analysis['method'] = 'DEMO_SCENARIO'
                    analysis['summary'] += ' 수행자 의견: ' + scenario['comment']
                    history = scenario.get('history')
                    if history:
                        cur.execute('''INSERT INTO negotiations(request_id,round_no,request_snapshot_json,analysis_json,alternatives_json,consents_json,
                                     accepted_condition_key,assignee_comment,requester_feedback,assignee_feedback,status,closed_at)
                                     VALUES(%s,1,%s,%s,%s,'[]',%s,%s,%s,%s,'FAILED',NOW())''',
                                    (request_id,dump(row),dump(analysis),dump(history['alternatives']),scenario['keep'],scenario['comment'],history['requester_feedback'],history['assignee_feedback']))
                    negotiation_id = negotiation_repository.insert_round(cur,(request_id,2 if history else 1,dump(row),dump(analysis)))
                    negotiation_repository.update_response_conditions(cur,(scenario['keep'],scenario['comment'],negotiation_id))
                    negotiation_repository.update_alternatives(cur,(dump(scenario['alternatives']),negotiation_id))
                    negotiation_repository.update_consents(cur,(dump(scenario['consents']),negotiation_id))
                    if history:
                        for column in ['requester_feedback','assignee_feedback']:
                            negotiation_repository.update_feedback(cur,(history[column],negotiation_id),column)
                    if scenario.get('selected'):
                        chosen = next(a for a in scenario['alternatives'] if a['id']==scenario['selected'])
                        negotiation_repository.update_selected_alternative(cur,(str(chosen['id']),negotiation_id))
                        result_id = result_repository.insert_pending_result(cur,(request_id,negotiation_id,dump(chosen['plan_json'])))
                        cur.execute('UPDATE results SET a_confirmed_at=NOW(),b_confirmed_at=NOW() WHERE id=%s',(result_id,))
                report.append(dict(number=scenario['number'],id=request_id,title=scenario['title'],status=scenario['status'],added=True))
            cur.execute('SELECT id,employee_id,title,start_at,end_at,status,priority,workload FROM schedules ORDER BY id')
            if cur.fetchall() != schedules_before:
                raise RuntimeError('Existing schedules changed unexpectedly')
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return dict(applied=apply,scenarios=report,schedules_unchanged=len(schedules_before))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Commit the five scenarios; otherwise only validate them.')
    args = parser.parse_args()
    print(json.dumps(seed(args.apply),ensure_ascii=True,default=str))
