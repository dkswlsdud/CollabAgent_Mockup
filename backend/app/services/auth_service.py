"""auth_service: 업무 규칙과 트랜잭션 처리."""

import hashlib
import secrets
from datetime import timedelta
from werkzeug.security import check_password_hash
from app.shared.errors import fail
from app.shared.dates import now
from app.shared.validation import text
from app.database import transaction
from app.repositories import auth_repository, employee_repository


def health():
    with transaction() as cur:
        employee_repository.check_connection(cur)
        initialized = employee_repository.count_employees(cur)["total"] > 0
    return dict(ok=True, initialized=initialized)


def new_session(cur, employee_id):
    token = secrets.token_urlsafe(32)
    auth_repository.delete_expired_sessions(cur, (now(),))
    auth_repository.insert_session(
        cur,
        (
            hashlib.sha256(token.encode()).hexdigest(),
            employee_id,
            now() + timedelta(days=7),
        ),
    )
    return token


def login(data):
    login_id = text(data, "login_id", 50)
    password = text(data, "password", 128)
    with transaction() as cur:
        user = employee_repository.find_employee_by_login_id(cur, (login_id,))
        if not user or not check_password_hash(user.pop("password_hash"), password):
            fail("아이디 또는 비밀번호가 올바르지 않습니다.", 401)
        user = {k: user[k] for k in ("id", "login_id", "name", "department", "email")}
        token = new_session(cur, user["id"])
    return (user, token)


def session_user(token):
    with transaction() as cur:
        return auth_repository.find_session_user(
            cur, (hashlib.sha256(token.encode()).hexdigest(), now())
        )


def logout(token):
    with transaction() as cur:
        auth_repository.delete_session(cur, (hashlib.sha256(token.encode()).hexdigest(),))
    return dict(ok=True)
