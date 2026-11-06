"""Add request wording and multiple accepted conditions without removing existing data."""
import json
from app.database import connect


def migrate():
    conn = connect()
    added = []
    try:
        with conn.cursor() as cur:
            for table,column,definition in [('requests','request_message','TEXT NULL'),('negotiations','accepted_condition_keys_json','JSON NULL')]:
                cur.execute('SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s',(table,column))
                if not cur.fetchone():
                    cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
                    added.append(f'{table}.{column}')
            cur.execute('''UPDATE negotiations SET accepted_condition_keys_json=JSON_ARRAY(accepted_condition_key)
                           WHERE accepted_condition_keys_json IS NULL AND accepted_condition_key IS NOT NULL AND accepted_condition_key<>%s''',('',))
        conn.commit()
        return dict(added=added,existing_requests_preserved=True)
    finally:
        conn.close()


if __name__ == '__main__':
    print(json.dumps(migrate()))
