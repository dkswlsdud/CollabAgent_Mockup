"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""

REQUEST_QUERY = """
        SELECT r.*,(SELECT status
        FROM results
        WHERE request_id=r.id) AS result_status,a.name AS requester_name,b.name AS assignee_name,
        a.department AS requester_department,b.department AS assignee_department,
        (SELECT consents_json FROM negotiations WHERE request_id=r.id ORDER BY round_no DESC LIMIT 1) AS latest_consents_json,
        (SELECT selected_alternative_key FROM negotiations WHERE request_id=r.id ORDER BY round_no DESC LIMIT 1) AS latest_selected_key,
        (SELECT a_confirmed_at FROM results WHERE request_id=r.id) AS result_a_confirmed_at,
        (SELECT b_confirmed_at FROM results WHERE request_id=r.id) AS result_b_confirmed_at
        FROM requests r
        JOIN employees a ON a.id=r.requester_id
        JOIN employees b ON b.id=r.assignee_id
    """


def list_user_requests(cur, parameters):
    sql = REQUEST_QUERY + """
        WHERE r.requester_id=%s OR r.assignee_id=%s
        ORDER BY r.id DESC
    """
    cur.execute(sql, parameters)
    return cur.fetchall()


def find_request(cur, parameters, lock):
    sql = """
        SELECT * FROM requests WHERE id=%s
    """
    if lock:
        sql += " FOR UPDATE"
    cur.execute(sql, parameters)
    return cur.fetchone()


def find_request_detail(cur, parameters):
    sql = REQUEST_QUERY + """
        WHERE r.id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_request(cur, parameters):
    sql = """
        INSERT INTO requests(requester_id,assignee_id,original_text,task_content,
        due_at,conditions_json,status) VALUES(%s,%s,%s,%s,%s,%s,'PENDING')
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def save_request_message(cur, parameters):
    cur.execute('UPDATE requests SET request_message=%s WHERE id=%s',parameters)


def mark_negotiating(cur, parameters):
    sql = """
        UPDATE requests
        SET status='NEGOTIATING'
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def resubmit(cur, parameters):
    cur.execute('UPDATE requests SET status=\'PENDING\',due_at=%s,conditions_json=%s WHERE id=%s', parameters)


def update_request_status(cur, parameters):
    sql = """
        UPDATE requests
        SET status=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def mark_accepted(cur, parameters):
    sql = """
        UPDATE requests
        SET status='ACCEPTED'
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def lock_request(cur, parameters):
    sql = """
        SELECT id
        FROM requests
        WHERE id=%s FOR UPDATE
    """
    cur.execute(sql, parameters)


def find_demo_request(cur, parameters):
    sql = """
        SELECT id
        FROM requests
        WHERE requester_id=%s
        AND task_content=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_demo_request(cur, parameters):
    sql = """
        INSERT INTO
        requests(requester_id,assignee_id,original_text,task_content,due_at,conditions_json,status)
        VALUES(%s,%s,%s,%s,%s,%s,'PENDING')
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def insert_demo_request_with_status(cur, parameters):
    sql = """
        INSERT INTO requests(requester_id,assignee_id,original_text,task_content,
        due_at,conditions_json,status) VALUES(%s,%s,%s,%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def find_seed_request(cur, parameters):
    sql = """
        SELECT *
        FROM requests
        WHERE id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_demo_incoming_request(cur, parameters):
    sql = """
        INSERT INTO requests(requester_id,assignee_id,original_text,task_content,
        due_at,conditions_json,status) VALUES(%s,%s,%s,%s,%s,%s,'PENDING')
    """
    cur.execute(sql, parameters)
