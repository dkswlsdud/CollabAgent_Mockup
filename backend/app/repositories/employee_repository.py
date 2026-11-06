"""SQL 매핑과 DB 조회/저장. 호출한 서비스의 트랜잭션 커서를 공유합니다."""


def check_connection(cur):
    sql = """
        SELECT 1
    """
    cur.execute(sql)


def count_employees(cur):
    sql = """
        SELECT COUNT(*) AS total
        FROM employees
    """
    cur.execute(sql)
    return cur.fetchone()


def find_employee_by_login_id(cur, parameters):
    sql = """
        SELECT *
        FROM employees
        WHERE login_id=%s
        AND is_active=1
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def list_active_employees(cur):
    sql = """
        SELECT id,name,department,email
        FROM employees
        WHERE is_active=1
        ORDER BY department,name
    """
    cur.execute(sql)
    return cur.fetchall()


def find_active_employee(cur, parameters):
    sql = """
        SELECT id
        FROM employees
        WHERE id=%s
        AND is_active=1
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def lock_employee(cur, parameters):
    sql = """
        SELECT id
        FROM employees
        WHERE id=%s FOR UPDATE
    """
    cur.execute(sql, parameters)


def insert_demo_employee(cur, parameters):
    sql = """
        INSERT IGNORE INTO employees(login_id,password_hash,name,department,email)
        VALUES(%s,%s,%s,%s,%s)
    """
    cur.execute(sql, parameters)


def find_employee_by_email(cur, parameters):
    sql = """
        SELECT id
        FROM employees
        WHERE email=%s
    """
    cur.execute(sql, parameters)
    return cur.fetchone()


def find_demo_employees(cur, parameters):
    sql = """
        SELECT id,name,email
        FROM employees
        WHERE email IN (%s,%s)
    """
    cur.execute(sql, parameters)
    return cur.fetchall()
