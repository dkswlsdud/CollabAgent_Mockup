"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def find_result(cur, parameters):
    sql = """
        SELECT *
        FROM results
        WHERE request_id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def lock_request_result(cur, parameters):
    sql = """
        SELECT *
        FROM results
        WHERE request_id=%s FOR UPDATE
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_direct_result(cur, parameters):
    sql = """
        INSERT INTO results(request_id,status,agreed_terms_json,reason,
        a_confirmed_at,b_confirmed_at,finalized_at) VALUES(%s,%s,%s,%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def delete_result(cur, parameters):
    from app.repositories import schedule_repository
    schedule_repository.delete_result_schedules(cur,parameters[0])
    sql = """
        DELETE
        FROM results
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def insert_pending_result(cur, parameters):
    sql = """
        INSERT INTO results(request_id,negotiation_id,status,agreed_terms_json)
        VALUES(%s,%s,'PENDING_CONFIRMATION',%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def confirm_result(cur, parameters, column):
    if column not in ("a_confirmed_at", "b_confirmed_at"):
        raise ValueError("Invalid update column")
    sql = f"""
        UPDATE results
        SET {column}=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def finalize_result(cur, parameters):
    sql = """
        UPDATE results
        SET status='ACCEPTED',finalized_at=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def update_agreed_terms(cur, parameters):
    cur.execute('UPDATE results SET agreed_terms_json=%s WHERE id=%s', parameters)


def insert_demo_direct_result(cur, parameters):
    sql = """
        INSERT INTO results(request_id,status,agreed_terms_json,reason,
        a_confirmed_at,b_confirmed_at,finalized_at) VALUES(%s,%s,%s,%s,%s,NOW(),NOW())
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def insert_demo_final_result(cur, parameters):
    sql = """
        INSERT INTO results(request_id,negotiation_id,status,agreed_terms_json,
        a_confirmed_at,b_confirmed_at,finalized_at) VALUES(%s,%s,%s,%s,NOW(),%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid
