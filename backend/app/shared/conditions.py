"""Read multiple accepted conditions while supporting existing single-choice rows."""
import json
from app.shared.errors import fail


def condition_keys(value):
    if value is None or value == '':
        return []
    if isinstance(value,str):
        if value.startswith('['):
            try:
                value = json.loads(value)
            except ValueError:
                fail('수용 가능한 조건을 확인해주세요.')
        else:
            value = [value]
    if not isinstance(value,list) or len(value)>30 or any(not isinstance(key,str) or not key for key in value):
        fail('수용 가능한 조건을 확인해주세요.')
    return list(dict.fromkeys(value))


def accepted_conditions(record):
    for field in ['accepted_condition_keys','accepted_condition_keys_json','accepted_condition_key']:
        if record.get(field) is not None:
            return condition_keys(record[field])
    return []
