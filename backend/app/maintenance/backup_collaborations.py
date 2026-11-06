"""Print a consistent JSON backup before replacing collaboration scenarios."""
import base64
import json
from datetime import date, datetime
from decimal import Decimal
from app.database import connect


def encode(value):
    if isinstance(value, bytes):
        return {'__base64__': base64.b64encode(value).decode('ascii')}
    if isinstance(value, (datetime, date, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def snapshot():
    conn = connect()
    try:
        conn.begin()
        data = {}
        with conn.cursor() as cur:
            for table in ['employees', 'requests', 'responses', 'negotiations', 'results',
                          'schedules', 'request_attachments', 'collaboration_reads']:
                cur.execute('SELECT * FROM ' + table)
                data[table] = cur.fetchall()
        return data
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, default=encode))
