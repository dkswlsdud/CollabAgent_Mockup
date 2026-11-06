"""employee_service: 업무 규칙과 트랜잭션 처리."""

from app.database import transaction
from app.repositories import employee_repository


def employees():
    with transaction() as cur:
        rows = employee_repository.list_active_employees(cur)
    return dict(employees=rows, departments=sorted({e["department"] for e in rows}))
