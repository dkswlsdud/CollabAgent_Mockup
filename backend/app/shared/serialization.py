import json
from datetime import date, datetime

JSON_FIELDS = {
    'latest_consents_json',
    'accepted_condition_keys_json',
    "conditions_json",
    "request_snapshot_json",
    "analysis_json",
    "alternatives_json",
    "consents_json",
    "agreed_terms_json",
}


def dump(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: v.isoformat())


def clean(row):
    if not row:
        return row
    return {
        k: (
            json.loads(v)
            if k in JSON_FIELDS and isinstance(v, str)
            else v.isoformat() if isinstance(v, (date, datetime)) else v
        )
        for k, v in row.items()
    }


