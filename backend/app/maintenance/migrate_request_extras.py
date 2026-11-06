from pathlib import Path
from app.database import connect


def migrate():
    schema=(Path(__file__).resolve().parents[2]/'sql'/'schema.sql').read_text(encoding='utf-8')
    conn=connect()
    try:
        with conn.cursor() as cur:
            for statement in schema.split(';'):
                if statement.strip().startswith(('CREATE TABLE IF NOT EXISTS request_attachments','CREATE TABLE IF NOT EXISTS collaboration_reads')):
                    cur.execute(statement)
        conn.commit()
    finally:conn.close()


if __name__=='__main__':
    migrate()
    print('Attachment and per-account notice tables ready.')
