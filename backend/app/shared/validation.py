from app.shared.errors import fail

def text(data, key, maximum=255):
    value = str(data.get(key, "")).strip()
    if not value or len(value) > maximum:
        fail(f"{key} 항목을 확인해주세요. (최대 {maximum}자)")
    return value


