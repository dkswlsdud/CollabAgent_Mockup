"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def list_schedules(
    cur, end, first, scope, employee_id, employee_department, selected_employee_id=None
):
    clauses = ["s.start_at<%s", "s.end_at>%s", "s.status<>'CANCELLED'"]
    args = [end, first]
    if scope == "my":
        clauses.append("s.employee_id=%s")
        args.append(employee_id)
    elif scope == "team":
        clauses.append("e.department=%s")
        args.append(employee_department)
    if selected_employee_id is not None:
        clauses.append('s.employee_id=%s')
        args.append(selected_employee_id)
    cur.execute(
        """
        SELECT s.*,e.name AS employee_name,e.department,r.name AS requester_name
        FROM schedules s JOIN employees e ON e.id=s.employee_id
        LEFT JOIN employees r ON r.id=s.requester_id
        WHERE """ + " AND ".join(clauses) + " ORDER BY s.start_at,s.id",
        args,
    )
    return cur.fetchall()


def find_schedule(cur, parameters):
    sql = """
        SELECT s.*,e.name AS employee_name,e.department,r.name AS requester_name
        FROM schedules s
        JOIN employees e ON e.id=s.employee_id
        LEFT JOIN employees r ON r.id=s.requester_id
        WHERE s.id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_schedule(cur, parameters):
    sql = """
        INSERT INTO schedules(employee_id,title,type,start_at,end_at,priority,workload,memo)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def list_workload_schedules(cur, parameters):
    sql = """
        SELECT id,employee_id,requester_id,result_id,title,type,status,start_at,end_at,workload,priority
        FROM schedules
        WHERE employee_id=%s
        AND status NOT IN ('COMPLETED','CANCELLED')
        AND (result_item_key IS NULL OR result_item_key NOT LIKE 'overview:%%')
        AND end_at>=%s
        AND start_at<=%s
        ORDER BY start_at
    """
    cur.execute(sql, parameters)
    return cur.fetchall()


def list_period_schedules(cur, parameters):
    cur.execute('''SELECT id,employee_id,title,type,status,start_at,end_at,priority,workload
                   FROM schedules WHERE employee_id=%s AND end_at>%s AND start_at<%s
                   AND status<>'CANCELLED' ORDER BY start_at,end_at,id''',parameters)
    return cur.fetchall()


def insert_result_schedule(cur, parameters):
    sql = """
        INSERT INTO schedules(employee_id,requester_id,result_id,result_item_key,
        title,type,start_at,end_at,priority,workload,is_new) VALUES(%s,%s,%s,%s,%s,'WORK',%s,%s,%s,%s,TRUE)
    """
    cur.execute(sql, parameters)


def lock_schedule(cur, schedule_id):
    cur.execute('SELECT * FROM schedules WHERE id=%s FOR UPDATE', (schedule_id,))
    return cur.fetchone()


def update_schedule(cur, parameters):
    cur.execute('''UPDATE schedules SET title=%s,type=%s,start_at=%s,end_at=%s,
                   priority=%s,workload=%s,memo=%s,status=%s WHERE id=%s''',parameters)


def delete_schedule(cur, schedule_id):
    cur.execute('DELETE FROM schedules WHERE id=%s',(schedule_id,))


def delete_result_schedules(cur,result_id):
    cur.execute('DELETE FROM schedules WHERE result_id=%s',(result_id,))


def reschedule(cur, change):
    cur.execute('UPDATE schedules SET start_at=%s,end_at=%s,is_new=TRUE WHERE id=%s',
                (change['start_at'], change['end_at'], change['schedule_id']))


def find_schedule_conflict(cur, parameters):
    sql = """
        SELECT title
        FROM schedules
        WHERE employee_id=%s
        AND status NOT IN ('COMPLETED','CANCELLED')
        AND (result_item_key IS NULL OR result_item_key NOT LIKE 'overview:%%')
        AND start_at<%s
        AND end_at>%s
        LIMIT 1
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def find_demo_schedule(cur, parameters):
    sql = """
        SELECT id
        FROM schedules
        WHERE employee_id=%s
        AND title=%s
        AND start_at=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_demo_schedule(cur, parameters):
    sql = """
        INSERT INTO schedules(employee_id,title,type,start_at,end_at,priority,workload,memo)
        VALUES(%s,%s,%s,%s,%s,'MEDIUM','MEDIUM','Collab Agent 테스트 일정')
    """
    cur.execute(sql, parameters[:5])


def insert_result_overview(cur, parameters):
    cur.execute("""INSERT INTO schedules(employee_id,requester_id,result_id,result_item_key,
        title,type,start_at,end_at,priority,workload,is_new,memo)
        VALUES(%s,%s,%s,%s,%s,'WORK',%s,%s,%s,%s,TRUE,'협업 진행 현황 · 실제 작업 배정은 수행자 일정을 기준으로 확인')""", parameters)


def schedule_notification_count(cur, employee_id):
    cur.execute("SELECT COUNT(*) AS count FROM schedules WHERE employee_id=%s AND is_new=TRUE AND status<>'CANCELLED'", (employee_id,))
    return cur.fetchone()


def read_schedule_notifications(cur, employee_id, ids):
    if not ids:
        return
    placeholders = ','.join(['%s']*len(ids))
    cur.execute(f'UPDATE schedules SET is_new=FALSE WHERE employee_id=%s AND id IN ({placeholders})', [employee_id, *ids])
