import { esc } from '../shared/dom.js';
import { dateTime } from '../shared/presentation.js';
import { view } from '../shared/templates.js';
import { state } from '../core/state.js';
import { groupedItems } from './alternative-card.js';

export function consentDetail(data) {
  const request = data.request;
  const plan = data.alternative.plan_json;
  const name = id => esc(state.employees.find(employee => employee.id === id)?.name || '담당자');
  const items = plan.items || [];
  const work = entries => groupedItems(entries).map(item => view('alternative-item', {
    assigneeName:name(item.assignee_id), quantity:esc(item.quantity),
    startAt:esc(dateTime(item.start_at)), endAt:esc(dateTime(item.end_at)),
  })).join('');
  const ownItems = items.filter(item => item.assignee_id === state.user.id);
  const changes = plan.schedule_changes || [];
  const ownChanges = changes.filter(change => change.employee_id === state.user.id || change.requester_id === state.user.id);
  const changeList = entries => entries.map(change => `<div class="consent-change"><b>${esc(change.title)} · ${name(change.employee_id)}</b><p>기존 ${esc(dateTime(change.original_start_at))} ~ ${esc(dateTime(change.original_end_at))}</p><p>변경 ${esc(dateTime(change.start_at))} ~ ${esc(dateTime(change.end_at))}</p></div>`).join('');
  const conditions = (request.conditions_json || []).map((condition,index) => view('request-condition', {
    popoverId:`consent-${data.consent.id}-condition-${index}`, label:esc(condition.label),
    value:esc(condition.key === 'deadline' ? dateTime(request.due_at) : condition.value),
    constraint:esc(condition.constraint), constraintClass:condition.constraint === 'HARD' ? 'constraint-hard' : 'constraint-soft',
  })).join('');
  const chosen = items.map(item => item.due_at || item.end_at).sort().at(-1);
  const agreedConditions = (plan.conditions_json || request.conditions_json || []).map((condition,index) => {
    const value = condition.key === 'deadline' ? dateTime(chosen) : condition.key === 'quantity' ? items.reduce((sum,item) => sum+Number(item.quantity),0) : condition.key === 'specification' ? plan.specification : condition.value;
    return view('request-condition', {popoverId:`consent-${data.consent.id}-agreed-${index}`,label:esc(condition.label),value:esc(value),constraint:esc(condition.constraint),constraintClass:condition.constraint === 'HARD' ? 'constraint-hard' : 'constraint-soft'});
  }).join('');
  const response = data.response || {};
  const keys = response.accepted_condition_keys_json || (response.accepted_condition_key ? [response.accepted_condition_key] : []);
  return view('consent-detail', {
    attachments:(data.attachments || []).map(file=>`<a class="attachment-link" href="/api/attachments/${Number(file.id)}" download>${esc(file.filename)}</a>`).join(''),
    message:esc(request.request_message || request.original_text),
    requester:esc(request.requester_name), assignee:esc(request.assignee_name),
    due:esc(dateTime(request.due_at)), conditions, agreedConditions,
    comment:esc(response.assignee_comment || '추가 의견 없음'),
    maintained:esc(keys.map(key => request.conditions_json.find(condition => condition.key === key)?.label || key).join(' · ') || '별도 선택 없음'),
    feedback:[response.requester_feedback,response.assignee_feedback].filter(Boolean).map(value => `<p class="consent-message">${esc(value)}</p>`).join(''),
    requesterConfirmed:esc(dateTime(data.confirmation.a_confirmed_at)), assigneeConfirmed:esc(dateTime(data.confirmation.b_confirmed_at)),
    impact:work(ownItems)+changeList(ownChanges) || '<p class="hint">아래 확정 대안과 일정 변경 내용을 확인해주세요.</p>',
    alternativeTitle:esc(data.alternative.title), description:esc(plan.description),
    total:esc(items.reduce((total,item) => total+Number(item.quantity),0)), agreedDue:esc(dateTime(chosen)),
    specification:esc(plan.specification || '별도 규격 없음'), work:work(items),
    changes:changes.length ? '<h4>기존 일정 변경</h4>'+changeList(changes) : '',
    refusalNote:data.consent.reason ? `<p class="consent-refusal-note">${esc(data.consent.reason)}</p>` : '',
    actions:data.needs_calendar_settings ? `<button class="primary" onclick="configureConsentCalendar('${esc(data.consent.id)}')">내 일정 설정 · 등록</button>` : data.consent.status === 'PENDING'
      ? view('consent-actions',{consentId:esc(data.consent.id),rejectConsentId:esc(data.consent.id)})
      : view('consent-status',{label:{APPROVED:'동의 완료',REJECTED:'거부',CANCELLED:'요청 중단'}[data.consent.status] || esc(data.consent.status)}),
  });
}
