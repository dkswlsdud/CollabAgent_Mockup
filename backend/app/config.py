"""실행 환경과 공통 설정."""

from datetime import timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
KST = timezone(timedelta(hours=9))
COOKIE = "collab_session"
