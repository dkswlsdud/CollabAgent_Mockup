"""WSGI and local development entry point; business logic lives in app/."""
import sys
from app import create_app

app = create_app()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        from app.services.demo_service import init_db
        init_db()
    else:
        app.run(host="0.0.0.0", port=8000)
