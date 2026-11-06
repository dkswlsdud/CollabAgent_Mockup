"""Complete one confirmed agreement and all calendar updates in the caller's transaction."""
from app.repositories import negotiation_repository, request_repository, result_repository
from app.services.schedule_service import save_schedule_items
from app.shared.dates import now
from app.shared.errors import fail
from app.shared.calendar_preferences import require_preferences


def complete_agreement(cur, row, result, negotiation):
    if result['status'] == 'ACCEPTED':
        return
    if not result.get('a_confirmed_at') or not result.get('b_confirmed_at'):
        fail('양측 최종 확인이 필요합니다.', 409)
    selected = str(negotiation['selected_alternative_key'])
    consents = [c for c in negotiation.get('consents_json') or [] if str(c['alternative_id']) == selected]
    if any(c['status'] != 'APPROVED' for c in consents):
        fail('필요한 관계자 동의가 완료되지 않았습니다.', 409)
    require_preferences(row,result['agreed_terms_json'])
    save_schedule_items(cur, row, result['id'], result['agreed_terms_json'])
    result_repository.finalize_result(cur, (now(), result['id']))
    negotiation_repository.finalize_round(cur, (now(), negotiation['id']))
    request_repository.mark_accepted(cur, (row['id'],))
