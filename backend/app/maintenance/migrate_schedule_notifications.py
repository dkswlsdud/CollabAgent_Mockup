"""Add account-specific unread calendar state without changing existing schedules."""
import json
from app.database import connect


def migrate():
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='schedules' AND COLUMN_NAME='is_new'")
            added = not bool(cur.fetchone())
            if added:
                cur.execute('ALTER TABLE schedules ADD COLUMN is_new BOOLEAN NOT NULL DEFAULT FALSE')
        conn.commit()
        return dict(added=added, existing_schedules_preserved=True)
    finally:
        conn.close()


if __name__ == '__main__':
    print(json.dumps(migrate()))
