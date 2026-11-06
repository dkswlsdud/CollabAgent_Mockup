"""Export business data, or explicitly replace requests and schedules for a fresh demo."""
import argparse
import json
from datetime import date, datetime, time, timedelta
from app.database import connect


# name, title, day from Monday, start hour, end hour, type, priority, status, workload, requester
FIXTURES = [
    ('김민지','10월 캠페인 결과 정리',0,9,10,'WORK','MEDIUM','COMPLETED','LOW',None),
    ('김민지','11월 캠페인 전략 수립',0,10,18,'WORK','HIGH','IN_PROGRESS','HIGH',None),
    ('김민지','신제품 홍보 문안 검토',1,10,12,'WORK','HIGH','SCHEDULED','MEDIUM',None),
    ('김민지','마케팅 주간 회의',2,10,11,'MEETING','MEDIUM','SCHEDULED','LOW',None),
    ('김민지','파트너 제안 자료 정리',4,14,16,'WORK','LOW','SCHEDULED','LOW',None),
    ('최유진','광고 성과 보고 완료',0,9,10,'WORK','LOW','COMPLETED','MEDIUM',None),
    ('최유진','광고 지표 모니터링',0,10,12,'WORK','MEDIUM','IN_PROGRESS','LOW',None),
    ('최유진','신규 광고 캠페인 세팅',1,13,17,'WORK','HIGH','SCHEDULED','HIGH','김민지'),
    ('최유진','SNS 콘텐츠 기획',3,9,12,'WORK','MEDIUM','SCHEDULED','MEDIUM',None),
    ('최유진','콘텐츠 검토 회의',4,15,16,'MEETING','LOW','SCHEDULED','LOW',None),
    ('최유진','취소된 광고 운영 미팅',3,14,16,'MEETING','LOW','CANCELLED','LOW',None),
    ('이서준','기존 배너 파일 정리',0,9,10,'WORK','LOW','COMPLETED','LOW',None),
    ('이서준','제품 상세페이지 리뉴얼',0,10,18,'WORK','HIGH','IN_PROGRESS','HIGH','김민지'),
    ('이서준','상세페이지 시안 마무리',1,9,12,'WORK','HIGH','SCHEDULED','HIGH','김민지'),
    ('이서준','디자인팀 주간 회의',2,14,15,'MEETING','MEDIUM','SCHEDULED','LOW',None),
    ('이서준','SNS 캠페인 이미지 제작',4,9,12,'WORK','MEDIUM','SCHEDULED','MEDIUM','최유진'),
    ('이서준','연차 휴가',7,9,18,'PERSONAL','HIGH','SCHEDULED','LOW',None),
    ('이서준','뉴스레터 이미지 보정',8,13,16,'WORK','LOW','SCHEDULED','LOW','박지훈'),
    ('정하은','브랜드 가이드 정리',0,9,11,'WORK','MEDIUM','COMPLETED','MEDIUM',None),
    ('정하은','아이콘 시안 제작',0,13,17,'WORK','MEDIUM','IN_PROGRESS','MEDIUM',None),
    ('정하은','아이콘 디자인 검수',3,10,12,'WORK','HIGH','SCHEDULED','MEDIUM',None),
    ('정하은','디자인팀 주간 회의',2,14,15,'MEETING','MEDIUM','SCHEDULED','LOW',None),
    ('정하은','브랜드 레퍼런스 조사',4,13,15,'WORK','LOW','SCHEDULED','LOW',None),
    ('박지훈','지난 뉴스레터 발행',0,9,10,'WORK','HIGH','COMPLETED','MEDIUM',None),
    ('박지훈','뉴스레터 초안 작성',0,10,13,'WORK','MEDIUM','IN_PROGRESS','MEDIUM',None),
    ('박지훈','신제품 소개 원고 작성',1,9,17,'WORK','HIGH','SCHEDULED','HIGH','김민지'),
    ('박지훈','콘텐츠 편집 회의',2,11,12,'MEETING','MEDIUM','SCHEDULED','LOW',None),
    ('박지훈','지난 원고 교정',3,14,16,'WORK','LOW','SCHEDULED','LOW',None),
]

# Keep meetings, leave and two small tasks on a single day; other work spans days.
DAY_SPANS = {
    ('김민지','10월 캠페인 결과 정리'): (-4,0),
    ('김민지','11월 캠페인 전략 수립'): (0,2),
    ('김민지','신제품 홍보 문안 검토'): (3,4),
    ('김민지','파트너 제안 자료 정리'): (7,9),
    ('최유진','광고 성과 보고 완료'): (-4,0),
    ('최유진','광고 지표 모니터링'): (0,2),
    ('최유진','신규 광고 캠페인 세팅'): (3,4),
    ('최유진','SNS 콘텐츠 기획'): (7,9),
    ('이서준','제품 상세페이지 리뉴얼'): (0,3),
    ('이서준','상세페이지 시안 마무리'): (8,10),
    ('이서준','SNS 캠페인 이미지 제작'): (2,4),
    ('이서준','뉴스레터 이미지 보정'): (11,14),
    ('정하은','브랜드 가이드 정리'): (-3,0),
    ('정하은','아이콘 시안 제작'): (0,2),
    ('정하은','아이콘 디자인 검수'): (3,4),
    ('정하은','브랜드 레퍼런스 조사'): (7,9),
    ('박지훈','뉴스레터 초안 작성'): (0,1),
    ('박지훈','신제품 소개 원고 작성'): (2,4),
    ('박지훈','지난 원고 교정'): (7,9),
}


def build_rows(employees, monday):
    if monday.weekday() != 0:
        raise ValueError('week-start must be a Monday')
    ids = {employee['name']:employee['id'] for employee in employees}
    if len(ids) != len(employees):
        raise ValueError('Employee names must be unique for this demo reset')
    rows = []
    for name,title,day,start,end,kind,priority,status,workload,requester in FIXTURES:
        start_day,end_day = DAY_SPANS.get((name,title),(day,day))
        begin = datetime.combine(monday + timedelta(days=start_day),time(start))
        finish = datetime.combine(monday + timedelta(days=end_day),time(end))
        rows.append((ids[name],ids[requester] if requester else None,title,kind,begin,finish,
                     None,priority,status,workload,'직원 일정 시연용: 우선순위·상태·작업량 비교'))
    return rows


def extend_existing_schedules(monday):
    """Update only schedule dates, preserving requests, identities and other metadata."""
    if monday.weekday() != 0:
        raise ValueError('week-start must be a Monday')
    conn = connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT s.id,e.name,s.title,s.type,s.start_at,s.end_at FROM schedules s JOIN employees e ON e.id=s.employee_id ORDER BY s.id FOR UPDATE')
            existing = cur.fetchall()
            changed = []
            small_tasks = {('이서준','기존 배너 파일 정리'),('박지훈','지난 뉴스레터 발행')}
            for row in existing:
                if row['type'] != 'WORK' or (row['name'],row['title']) in small_tasks:
                    continue
                span = DAY_SPANS.get((row['name'],row['title']))
                if span:
                    begin = datetime.combine(monday + timedelta(days=span[0]),row['start_at'].time())
                    finish = datetime.combine(monday + timedelta(days=span[1]),row['end_at'].time())
                elif row['start_at'].date() == row['end_at'].date():
                    begin,finish = row['start_at'],row['end_at']
                    for _ in range(2):
                        finish += timedelta(days=1)
                        while finish.weekday() >= 5:
                            finish += timedelta(days=1)
                else:
                    continue
                if begin != row['start_at'] or finish != row['end_at']:
                    cur.execute('UPDATE schedules SET start_at=%s,end_at=%s WHERE id=%s',(begin,finish,row['id']))
                    changed.append(dict(id=row['id'],name=row['name'],title=row['title'],start=begin,end=finish))
            cur.execute('SELECT type,COUNT(*) AS total,SUM(DATE(start_at)<>DATE(end_at)) AS multi_day,SUM(DATE(start_at)=DATE(end_at)) AS single_day FROM schedules GROUP BY type')
            summary = cur.fetchall()
        conn.commit()
        return dict(updated=len(changed),changes=changed,summary=summary)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def snapshot():
    conn = connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT id,name,department,is_active FROM employees ORDER BY id')
            result = {'employees':cur.fetchall()}
            for table in ['requests','responses','negotiations','results','schedules']:
                cur.execute(f'SELECT * FROM {table} ORDER BY id')
                result[table] = cur.fetchall()
        return result
    finally:
        conn.rollback()
        conn.close()


def reset(monday):
    conn = connect()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute('SELECT id,name,department FROM employees ORDER BY id FOR UPDATE')
            employees = cur.fetchall()
            rows = build_rows(employees,monday)
            before = {}
            for table in ['schedules','results','responses','negotiations','requests']:
                cur.execute(f'SELECT COUNT(*) AS total FROM {table}')
                before[table] = cur.fetchone()['total']
                cur.execute(f'DELETE FROM {table}')
            cur.executemany('''INSERT INTO schedules(employee_id,requester_id,title,type,start_at,end_at,due_at,priority,status,workload,memo)
                               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',rows)
            cur.execute('SELECT e.name,e.department,COUNT(*) AS count FROM schedules s JOIN employees e ON e.id=s.employee_id GROUP BY e.id,e.name,e.department ORDER BY e.department,e.name')
            summary = cur.fetchall()
            cur.execute('SELECT status,COUNT(*) AS count FROM schedules GROUP BY status')
            statuses = cur.fetchall()
            cur.execute('SELECT priority,COUNT(*) AS count FROM schedules GROUP BY priority')
            priorities = cur.fetchall()
            cur.execute('SELECT workload,COUNT(*) AS count FROM schedules GROUP BY workload')
            workloads = cur.fetchall()
        conn.commit()
        return dict(deleted=before,schedules=len(rows),employees=summary,statuses=statuses,priorities=priorities,workloads=workloads)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--extend-schedules',action='store_true')
    parser.add_argument('--week-start',type=date.fromisoformat)
    args = parser.parse_args()
    if args.snapshot and not args.apply and not args.extend_schedules:
        result = snapshot()
    elif args.extend_schedules and args.week_start and not args.snapshot and not args.apply:
        result = extend_existing_schedules(args.week_start)
    elif args.apply and args.week_start and not args.snapshot and not args.extend_schedules:
        result = reset(args.week_start)
    else:
        parser.error('Use --snapshot or explicitly pass --apply --week-start YYYY-MM-DD')
    print(json.dumps(result,ensure_ascii=True,default=str))
