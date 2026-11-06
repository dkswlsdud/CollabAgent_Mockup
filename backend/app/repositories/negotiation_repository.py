"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""
from app.shared.conditions import condition_keys
from app.shared.serialization import dump


def list_request_rounds(cur, parameters):
    sql = """
        SELECT *
        FROM negotiations
        WHERE request_id=%s
        ORDER BY round_no DESC
    """
    cur.execute(sql, parameters)
    return cur.fetchall()


def insert_round(cur, parameters):
    sql = """
        INSERT INTO negotiations(request_id,round_no,request_snapshot_json,analysis_json)
        VALUES(%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid


def lock_latest_round(cur, parameters):
    sql = """
        SELECT *
        FROM negotiations
        WHERE request_id=%s
        ORDER BY round_no DESC
        LIMIT 1 FOR UPDATE
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def update_response_conditions(cur, parameters):
    keys,comment,negotiation_id = parameters
    keys = condition_keys(keys)
    sql = """
        UPDATE negotiations
        SET accepted_condition_key=%s,accepted_condition_keys_json=%s,assignee_comment=%s
        WHERE id=%s
    """
    cur.execute(sql, (keys[0] if keys else None,dump(keys),comment,negotiation_id))


def close_failed_round(cur, parameters, column):
    if column not in ("requester_feedback", "assignee_feedback"):
        raise ValueError("Invalid update column")
    sql = f"""
        UPDATE negotiations
        SET {column}=%s,status='FAILED',closed_at=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def update_feedback(cur, parameters, column):
    if column not in ("requester_feedback", "assignee_feedback"):
        raise ValueError("Invalid update column")
    sql = f"""
        UPDATE negotiations
        SET {column}=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def clear_selected_alternative(cur, parameters):
    sql = """
        UPDATE negotiations
        SET selected_alternative_key=NULL
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def update_selected_alternative(cur, parameters):
    sql = """
        UPDATE negotiations
        SET selected_alternative_key=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def finalize_round(cur, parameters):
    sql = """
        UPDATE negotiations
        SET status='AGREED',closed_at=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def update_alternatives(cur, parameters):
    sql = """
        UPDATE negotiations
        SET alternatives_json=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def list_open_round_consents(cur):
    sql = """
        SELECT n.*,r.task_content AS request_title,x.a_confirmed_at,x.b_confirmed_at,x.agreed_terms_json
        FROM negotiations n JOIN requests r ON r.id=n.request_id
        JOIN results x ON x.negotiation_id=n.id AND x.request_id=r.id
        WHERE n.status='IN_PROGRESS' AND x.status='PENDING_CONFIRMATION' AND x.a_confirmed_at IS NOT NULL AND x.b_confirmed_at IS NOT NULL
    """
    cur.execute(sql)
    return cur.fetchall()


def find_round_request(cur, parameters):
    sql = """
        SELECT request_id
        FROM negotiations
        WHERE id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def lock_round_consents(cur, parameters):
    sql = """
        SELECT id,request_id,selected_alternative_key,consents_json,status
        FROM negotiations
        WHERE id=%s FOR UPDATE
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def find_consent_round(cur, parameters):
    cur.execute('SELECT * FROM negotiations WHERE id=%s', parameters)
    return cur.fetchone()


def archive_round_snapshot(cur, parameters):
    cur.execute('UPDATE negotiations SET request_snapshot_json=%s WHERE id=%s', parameters)


def update_consents(cur, parameters):
    sql = """
        UPDATE negotiations
        SET consents_json=%s
        WHERE id=%s
    """
    cur.execute(sql, parameters)


def cancel_open_rounds(cur, request_id):
    cur.execute("UPDATE negotiations SET status='CANCELLED',closed_at=NOW() WHERE request_id=%s AND status='IN_PROGRESS'", (request_id,))


def insert_demo_failed_round(cur, parameters):
    sql = """
        INSERT INTO negotiations(request_id,round_no,request_snapshot_json,
        status,requester_feedback,closed_at) VALUES(%s,1,%s,'FAILED',%s,NOW())
    """
    cur.execute(sql, parameters)


def insert_demo_round(cur, parameters):
    sql = """
        INSERT INTO negotiations(request_id,round_no,request_snapshot_json,analysis_json,
        alternatives_json,consents_json,accepted_condition_key,assignee_comment,
        selected_alternative_key,status,closed_at) VALUES(%s,%s,%s,%s,%s,%s,'deadline',%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.lastrowid
