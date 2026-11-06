import { esc } from '../shared/dom.js';
import { dateTime } from '../shared/presentation.js';
import { view } from '../shared/templates.js';
import { state } from '../core/state.js';

export function groupedItems(items) {
  const groups = [];
  const ordered = [...items].sort((a,b) => a.start_at.localeCompare(b.start_at) || a.assignee_id-b.assignee_id);
  for (const item of ordered) {
    const last = groups.findLast(group => group.assignee_id === item.assignee_id);
    if (last && last.end_at === item.start_at && last.start_at.slice(0,10) === item.start_at.slice(0,10) && last.due_at === item.due_at) {
      last.end_at = item.end_at;
      last.quantity += item.quantity;
    } else groups.push({...item});
  }
  return groups;
}

export function alternativeCard(alternative, {request, round, isRequester, consents}) {
  const plan = alternative.plan_json;
  const items = plan.items || [];
  const selected = isRequester ? alternative.a_selected : alternative.b_selected;
  const phaseEditable = !request.needs_recoordination && ['NEGOTIATING','AWAITING_CONFIRMATION'].includes(request.status);
  const completed = !!alternative[isRequester ? 'a_selection_completed' : 'b_selection_completed'];
  const editable = phaseEditable && !completed;
  const people = new Set(items.map(item => item.assignee_id));
  const due = items.map(item => item.due_at || item.end_at).sort().at(-1);
  return view('alternative-card', {
    commonClass: `${alternative.a_selected && alternative.b_selected ? 'common' : ''} ${selected ? 'selected' : ''}`,
    alternativeId: alternative.id,
    disabled: editable ? '' : 'disabled',
    pressed: selected ? 'true' : 'false',
    selectLabel: esc(`${alternative.title} ${selected ? '선택 해제' : '선택'}`),
    letter: String.fromCharCode(64+Number(alternative.id)),
    selection: selected ? completed ? '✓ 선택완료' : '✓ 내가 선택한 대안' : editable ? '눌러서 선택' : '선택 종료',
    title: esc(alternative.title.replace(/^[ABC]안\s*·\s*/, '')),
    description: esc(plan.description),
    due: esc(dateTime(due)),
    quantity: esc(items.reduce((sum,item) => sum+Number(item.quantity),0)),
    people: people.size,
    items: groupedItems(items).map(item => view('alternative-item', {
      quantity:esc(item.quantity),
      assigneeName:esc(state.employees.find(person => person.id === item.assignee_id)?.name || '담당자'),
      startAt:esc(dateTime(item.start_at)), endAt:esc(dateTime(item.end_at)),
    })).join(''),
    specification:esc(plan.specification || '별도 규격 없음'),
    requesterName:esc(request.requester_name), requesterSelection:alternative.a_selected ? '선택함' : '미선택',
    assigneeName:esc(request.assignee_name), assigneeSelection:alternative.b_selected ? '선택함' : '미선택',
    consents:(plan.schedule_changes || []).map(change => `<div class="conflict"><b>${esc(change.title)} 일정 변경</b><br>${esc(dateTime(change.original_start_at))} → ${esc(dateTime(change.start_at))}</div>`).join('')
      + consents.filter(entry => entry.alternative_id === alternative.id).map(entry => view('alternative-consent', {
        employeeName:esc(entry.employee_name), status:{WAITING:'최종 확인 후 요청',PENDING:'동의 대기',APPROVED:'동의 완료',REJECTED:'동의 거부',CANCELLED:'요청 중단'}[entry.status],
      })).join(''),
    chooseButton:isRequester && alternative.a_selected && alternative.b_selected && alternative.a_selection_completed && alternative.b_selection_completed && phaseEditable
      ? view('choose-alternative-button', {alternativeId:alternative.id,label:round.selected_alternative_id === alternative.id ? '현재 최종 대안' : '최종 대안으로 지정'}) : '',
  });
}
