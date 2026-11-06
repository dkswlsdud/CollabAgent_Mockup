import { $ , esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';

let initialized = false;
let version = 0;

export function closeResponseDialog() {
  version++;
  const dialog = $('#response-dialog');
  if (dialog?.open) dialog.close();
}

export function openResponseDialog({decision,conditions,onSubmit,title,submitLabel}) {
  const dialog = $('#response-dialog');
  const body = $('#response-dialog-body');
  if (!initialized) {
    $('#response-dialog-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      if (dialog.open) return;
      version++;
      body.textContent = '';
      document.body.classList.remove('response-dialog-open');
    });
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
    initialized = true;
  }
  const current = ++version;
  let busy = false;
  const conditional = decision === 'CONDITIONAL_ACCEPT';
  const feedback = decision === 'FEEDBACK';
  const generation = decision === 'GENERATE';
  const noCommon = decision === 'NO_COMMON';
  const consentRejection = decision === 'CONSENT_REJECT';
  const settings = decision === 'SCHEDULE_SETTINGS';
  $('#response-dialog-title').textContent = noCommon ? '재조정이 필요해요' : settings ? title || '내 일정 등록 설정' : consentRejection ? '관계자 동의 거부' : generation ? '대안 생성' : feedback ? '재조정 의견' : conditional ? '조건부 수락' : '요청 거절';
  body.innerHTML = noCommon ? view('no-common-dialog') : settings ? view('schedule-preferences-dialog',{submitLabel:esc(submitLabel || '확인')}) : consentRejection ? view('consent-reject-dialog') : generation ? view('response-generate-dialog') : feedback ? view('response-feedback-dialog') : conditional ? view('response-conditional-dialog', {
    conditionOptions: conditions.map(condition => view('response-condition-option', {
      value:esc(condition.key), label:esc(condition.label),
      constraint:esc(condition.constraint),
      constraintClass:condition.constraint === 'HARD' ? 'constraint-hard' : 'constraint-soft',
      detail:esc(condition.value || (condition.key === 'deadline' ? '요청 마감 일시 기준' : '상세 내용 없음')),
    })).join('') || '<p class="hint">등록된 조건이 없습니다. 기타 의견을 작성해주세요.</p>',
  }) : view('response-reject-dialog');
  $('#response-cancel').addEventListener('click', () => dialog.close());
  $('#request-response-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    const comment = generation || settings || noCommon ? '' : $('#response-comment').value.trim();
    const keys = conditional ? Array.from(document.querySelectorAll('#response-dialog input[name="keep"]:checked'),input => input.value) : [];
    $('#response-error').textContent = '';
    if (!settings && !generation && !noCommon && !conditional && !comment) { $('#response-error').textContent = feedback ? '재조정 의견을 입력해주세요.' : '거절 사유를 입력해주세요.'; return; }
    if (conditional && !keys.length && !comment) { $('#response-error').textContent = '유지 가능한 조건을 선택하거나 기타 의견을 입력해주세요.'; return; }
    const schedulePriority = settings ? $('#response-dialog input[name="schedule-priority"]:checked')?.value : undefined;
    const scheduleWorkload = settings ? $('#response-dialog input[name="schedule-workload"]:checked')?.value : undefined;
    if (settings && (!['LOW','MEDIUM','HIGH'].includes(schedulePriority) || !['LOW','MEDIUM','HIGH'].includes(scheduleWorkload))) {
      $('#response-error').textContent = '우선순위와 작업량을 모두 선택해주세요.';
      return;
    }
    busy = true;
    $('#response-submit').disabled = true;
    try {
      const saved = await onSubmit({decision,comment,accepted_condition_keys:keys,...(settings ? {schedule_priority:schedulePriority,schedule_workload:scheduleWorkload} : {})});
      if (saved && current === version && dialog.open) closeResponseDialog();
    } catch (error) {
      if (current === version && dialog.open) $('#response-error').textContent = error.message;
    } finally {
      busy = false;
      if (current === version && dialog.open) $('#response-submit').disabled = false;
    }
  });
  if (!dialog.open) dialog.showModal();
  document.body.classList.add('response-dialog-open');
}
