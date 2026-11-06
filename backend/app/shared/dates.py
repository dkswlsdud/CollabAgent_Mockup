from datetime import datetime
from app.config import KST
from app.shared.errors import fail

def now():
    return datetime.now(KST).replace(tzinfo=None)


def parse_time(value):
    try:
        result = datetime.fromisoformat(str(value))
        if result.tzinfo:
            result = result.astimezone(KST).replace(tzinfo=None)
        return result
    except (ValueError, TypeError):
        fail("올바른 날짜와 시간을 입력해주세요.")
