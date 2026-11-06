"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def delete_expired_sessions(cur, parameters):
    sql = """
        DELETE
        FROM app_sessions
        WHERE expires_at<=%s
    """
    cur.execute(sql, parameters)


def insert_session(cur, parameters):
    sql = """
        INSERT INTO app_sessions(token_hash,employee_id,expires_at) VALUES(%s,%s,%s)
    """
    cur.execute(sql, parameters)


def find_session_user(cur, parameters):
    sql = """
        SELECT e.id,e.login_id,e.name,e.department,e.email
        FROM app_sessions s
        JOIN employees e ON e.id=s.employee_id
        WHERE s.token_hash=%s
        AND s.expires_at>%s
        AND e.is_active=1
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def delete_session(cur, parameters):
    sql = """
        DELETE
        FROM app_sessions
        WHERE token_hash=%s
    """
    cur.execute(sql, parameters)
