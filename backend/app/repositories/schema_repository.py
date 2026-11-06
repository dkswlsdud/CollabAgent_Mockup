"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def apply_schema_statement(cur, statement):
    sql = statement
    cur.execute(sql)
