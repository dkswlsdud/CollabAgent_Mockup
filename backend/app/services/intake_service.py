"""Natural-language intake and missing-field questions for the mock workflow."""
import re
import hashlib
from datetime import datetime, timedelta
from app.database import transaction
from app.repositories import employee_repository
from app.services.ai_service import extract_request
from app.shared.dates import now, parse_time
from app.shared.validation import text
from app.shared.errors import fail


def extract_date(value, today=None):
    today = today or now()
    match = re.search(r'(?:(\d{4})[년./-]\s*)?(\d{1,2})[월./-]\s*(\d{1,2})일?', value)
    try:
        if match:
            date = datetime(int(match[1] or today.year), int(match[2]), int(match[3]), 18)
        elif '모레' in value:
            date = today + timedelta(days=2)
        elif '내일' in value:
            date = today + timedelta(days=1)
        elif '오늘' in value:
            date = today
        else:
            weekday = next((i for i, day in enumerate('월화수목금토일') if day + '요일' in value), None)
            if weekday is None:
                return None
            offset = weekday - today.weekday()
            if '다음 주' in value or '다음주' in value:
                offset += 7
            elif offset < 0:
                offset += 7
            date = today + timedelta(days=offset)
        time = re.search(r'(?:(오전|오후)\s*)?(\d{1,2})시(?:\s*(\d{1,2})분)?', value)
        hour, minute = 18, 0
        if time:
            hour, minute = int(time[2]), int(time[3] or 0)
            if time[1] == '오후' and hour < 12:
                hour += 12
            if time[1] == '오전' and hour == 12:
                hour = 0
        return date.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat(timespec='minutes')
    except ValueError:
        return None


def analyze(data, user):
    original = text(data, 'original_text', 5000)
    answers = data.get('answers') or {}
    if not isinstance(answers, dict):
        fail('추가 답변 형식을 확인해주세요.')
    with transaction() as cur:
        employees = [e for e in employee_repository.list_active_employees(cur) if e['id'] != user['id']]
    previous = data.get('previous_conditions') or []
    removed = data.get('removed_condition_keys') or []
    if not isinstance(previous,list) or len(previous)>29 or any(not isinstance(c,dict) for c in previous) or not isinstance(removed,list) or len(removed)>100 or any(not isinstance(key,str) for key in removed):
        fail('이전 조건 정보를 확인해주세요.')
    base = extract_request(dict(original_text=original, answers=answers, previous_conditions=previous,removed_condition_keys=removed,
                                today=now().isoformat(), employees=[{k:e[k] for k in ['id','name','department']} for e in employees]))
    if not isinstance(base, dict):
        fail('AI 분석 결과가 없습니다. 다시 시도해주세요.', 502)
    for key in ['task_content', 'due_at', 'assignee_id']:
        if answers.get(key):
            base[key] = answers[key]
    try:
        base['assignee_id'] = int(base.get('assignee_id'))
    except (TypeError, ValueError):
        base['assignee_id'] = None
    if base['assignee_id'] not in {e['id'] for e in employees}:
        base['assignee_id'] = None
    if base.get('due_at'):
        try:
            base['due_at'] = parse_time(base['due_at']).isoformat(timespec='minutes')
        except Exception:
            base['due_at'] = None
    conditions = []
    seen = {'deadline'}
    for c in base.get('conditions_json') or []:
        if not isinstance(c, dict) or not re.fullmatch('[a-z_][a-z0-9_]{0,99}', str(c.get('key', ''))) or c['key'] in seen or c['key'] in removed:
            continue
        seen.add(c['key'])
        value = answers.get(c['key'], c.get('value'))
        if c.get('origin') == 'SUGGESTED':
            prior = next((old for old in previous if old.get('key') == c['key']),{})
            value = answers.get(c['key'],prior.get('value',''))
        if c['key'] == 'quantity':
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = None
        conditions.append(dict(key=c['key'], label=str(c.get('label', c['key']))[:100], value=value,
                               unit=str(c.get('unit', ''))[:20], constraint=next((old.get('constraint','HARD') for old in previous if old.get('key')==c['key']),'HARD'),origin=c.get('origin','EXTRACTED'),
                               reason=str(c.get('reason',''))[:1000],question=str(c.get('question',''))[:500]))
    for c in previous:
        if c.get('key') != 'deadline' and c.get('key') not in {value['key'] for value in conditions} and c.get('key') not in removed and re.fullmatch('[a-z_][a-z0-9_]{0,99}',str(c.get('key',''))):
            conditions.append(dict(c,value=answers.get(c['key'],c.get('value',''))))
    # Additional answers become explicit request conditions, including dynamically generated clarifications.
    known = {c['key'] for c in conditions} | {'task_content', 'due_at', 'assignee_id'}
    for key, value in answers.items():
        if key not in known and key not in removed and re.fullmatch('[a-z_][a-z0-9_]{0,99}', str(key)) and str(value).strip():
            conditions.append(dict(key=key, label='추가 확인', value=str(value)[:1000], unit='', constraint='HARD'))
    questions = []
    if len(conditions)>29:
        fail('추가 조건은 최대 29개까지 등록할 수 있습니다. 불필요한 조건을 삭제해주세요.')
    for key, label in [('task_content', '업무 내용'), ('due_at', '마감 일시'), ('assignee_id', '수행자')]:
        if not base.get(key):
            questions.append(dict(key=key, label=label, question=f'{label}을 알려주세요.'))
    for c in conditions:
        if c.get('value') in (None, ''):
            questions.append(dict(key=c['key'], label=c['label'], question=c.get('question') or f"{c['label']}을 알려주세요."))
    for question in base.get('questions') or []:
        if any(question == c.get('question') for c in conditions):
            continue
        key = 'clarification_' + hashlib.sha256(str(question).encode()).hexdigest()[:12]
        if key in removed:
            continue
        if answers.get(key):
            condition = next((c for c in conditions if c['key'] == key), None)
            if condition:
                condition['label'] = str(question)[:100]
        else:
            questions.append(dict(key=key, label='추가 확인', question=str(question)))
    return dict(original_text=original, task_content=base.get('task_content') or '', due_at=base.get('due_at'),
                assignee_id=base.get('assignee_id'), conditions_json=conditions, questions=questions,
                ready=not questions, method='LLM')
