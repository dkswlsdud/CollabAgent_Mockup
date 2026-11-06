"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def delete_response(cur, request_id):
    cur.execute('DELETE FROM responses WHERE request_id=%s', (request_id,))


def find_response(cur, parameters):
    sql = """
        SELECT *
        FROM responses
        WHERE request_id=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def insert_response(cur, parameters):
    sql = """
        INSERT INTO responses(request_id,decision,reject_reason) VALUES(%s,%s,%s)
    """
    cur.execute(sql, parameters)
