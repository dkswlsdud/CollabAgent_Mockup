import { navigatePath, refreshData } from '../core/router.js';
import { state } from '../core/state.js';
import { $, esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { api, post } from '../core/api.js';
import { openDetail } from './request-detail.js';
import { toast } from '../shared/notifications.js';

export function openNew() { return navigatePath('/requests/new'); }

export function renderRequestNew() {
  let draft = null, original = '', busy = false;
  const removedConditionKeys = new Set();
  $('#app').innerHTML = view('request-new-page');
  const recipients = state.employees.filter(employee => employee.id !== state.user.id);
  const teams = [...new Set(recipients.map(employee => employee.department))].sort();
  $('#request-team').innerHTML = '<option value="">팀을 선택하세요</option>' + teams.map(team => `<option value="${esc(team)}">${esc(team)}</option>`).join('');
  function fillRecipients(selected = '') {
    $('#request-person').innerHTML = '<option value="">팀원을 선택하세요</option>' + recipients.filter(employee => employee.department === $('#request-team').value).map(employee =>
      view('request-employee-option', { employeeId: employee.id, name: esc(employee.name), department: esc(employee.department) })).join('');
    $('#request-person').value = String(selected);
  }
  fillRecipients();
  $('#request-files').addEventListener('change',()=>{ $('#request-file-list').innerHTML=Array.from($('#request-files').files || []).map(file=>`<li>${esc(file.name)} · ${(file.size/1024/1024).toFixed(1)}MB</li>`).join(''); });
  $('#request-team').addEventListener('change', () => fillRecipients());
  function renderQuestions() {
    document.querySelectorAll('#request-questions [data-answer-key]').forEach(input=>{
      const question=draft.questions.find(q=>q.key===input.dataset.answerKey);
      if (question) question.answer=input.value;
    });
    const active=(draft.questions || []).filter(q=>!removedConditionKeys.has(q.key));
    const extra=active.filter(q=>!['task_content','assignee_id','due_at'].includes(q.key) && !draft.conditions_json.some(c=>c.key===q.key));
    $('#request-questions').innerHTML=(active.length ? `<div class="analysis"><span>추가 확인: ${active.map(q=>esc(q.question)).join(' / ')}</span><button id="dismiss-intake-notice" class="text-button" type="button">닫기</button></div>` : '')+extra.map(q=>`<div class="field question-item"><label>${esc(q.question)}<input data-answer-key="${esc(q.key)}" value="${esc(q.answer || '')}" required /></label><button class="text-button" type="button" data-remove-question="${esc(q.key)}">질문 삭제</button></div>`).join('');
    if (active.length) $('#dismiss-intake-notice').addEventListener('click',()=>{ $('#request-questions .analysis').remove(); });
    document.querySelectorAll('[data-remove-question]').forEach(button=>button.addEventListener('click',()=>{
      removedConditionKeys.add(button.dataset.removeQuestion);
      draft.questions=draft.questions.filter(q=>q.key!==button.dataset.removeQuestion);
      renderQuestions();
    }));
  }
  function renderConditions() {
    const suggestions = draft.conditions_json.filter(condition => condition.origin === 'SUGGESTED');
    $('#request-suggestions').textContent = suggestions.length
      ? `이 요청을 진행하려면 ${suggestions.map(condition => condition.label).join(' · ')}도 확인이 필요합니다. AI가 제안한 ${suggestions.length}개 항목을 검토해주세요.`
      : '요청에서 확인된 조건입니다. 필요하면 조건을 직접 추가해주세요.';
    $('#request-conditions').innerHTML = draft.conditions_json.map((c, i) => `<div class="request-condition-item" data-condition-index="${i}"><div class="condition">
      <strong>${esc(c.label)}</strong><input data-condition-value data-answer-key="${esc(c.key)}" aria-label="${esc(c.label)}" value="${esc(c.value ?? '')}" ${c.key === 'quantity' ? 'type="number" min="1" max="1000"' : ''} required />
      <span>${esc(c.unit || '')}</span><select data-condition-constraint aria-label="${esc(c.label)} 변경 가능 여부"><option value="HARD">Hard · 변경 불가</option><option value="SOFT">Soft · 조정 가능</option></select>
      <button type="button" class="text-button remove-condition">삭제</button></div>
      ${c.origin === 'SUGGESTED' ? `<div class="condition-guidance"><span class="condition-origin">AI 제안</span> ${esc(c.reason || '업무 수행에 필요한 추가 확인 항목입니다.')}${c.question && !c.value ? `<p>${esc(c.question)}</p>` : ''}</div>` : ''}</div>`).join('');
    document.querySelectorAll('[data-condition-index]').forEach(row => {
      const c = draft.conditions_json[Number(row.dataset.conditionIndex)];
      row.querySelector('[data-condition-constraint]').value = c.constraint || 'HARD';
      row.querySelector('[data-condition-value]').addEventListener('input', e => { c.value = c.key === 'quantity' ? Number(e.target.value) : e.target.value; });
      row.querySelector('[data-condition-constraint]').addEventListener('change', e => { c.constraint = e.target.value; });
      row.querySelector('.remove-condition').addEventListener('click', () => { removedConditionKeys.add(c.key); draft.conditions_json.splice(Number(row.dataset.conditionIndex), 1); draft.questions=draft.questions.filter(q=>q.key!==c.key); renderConditions(); renderQuestions(); });
    });
  }
  $('#request-analyze').addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    $('#request-analyze').disabled = true;
    $('#request-submit').disabled = true;
    $('#request-error').textContent = '';
    $('#intake-status').textContent = 'AI가 요청을 분석하고 있습니다…';
    const version = state.renderId;
    try {
      const answers = {};
      const sameOriginal = $('#request-original').value.trim() === original;
      const previousConditions = sameOriginal ? draft?.conditions_json || [] : [];
      if (!sameOriginal) removedConditionKeys.clear();
      if (sameOriginal) document.querySelectorAll('[data-answer-key]').forEach(input => { if (input.value.trim()) answers[input.dataset.answerKey] = input.value.trim(); });
      if ($('#request-title').value.trim()) answers.task_content=$('#request-title').value.trim();
      if ($('#request-person').value) answers.assignee_id = $('#request-person').value;
      original = $('#request-original').value.trim();
      const result = await post('/requests/analyze', { original_text: original, answers, previous_conditions: previousConditions, removed_condition_keys: [...removedConditionKeys] });
      if (version !== state.renderId) return;
      const previous = draft;
      draft = result;
      for (const c of draft.conditions_json) {
        const old = previous?.conditions_json.find(old => old.key === c.key);
        c.constraint = old?.constraint || 'HARD';
        if (old) c.label = old.label;
      }
      // The request title is entered by the user and never overwritten by AI.
      const recipient = recipients.find(employee => employee.id === result.assignee_id);
      if (recipient) $('#request-team').value = recipient.department;
      fillRecipients(recipient?.id || '');
      $('#request-due').value = result.due_at || '';
      $('#request-review').hidden = false;
      $('#request-submit').disabled = false;
      $('#intake-status').textContent = 'AI 분석 완료 · 조건을 확인하고 변경 가능 여부를 선택하세요.';
      renderQuestions();
      renderConditions();
    } catch (error) {
      if (version === state.renderId) {
        draft = null;
        $('#request-review').hidden = true;
        $('#intake-status').textContent = '';
        $('#request-error').textContent = error.message;
      }
    }
    finally { busy = false; if (version === state.renderId) $('#request-analyze').disabled = false; }
  });
  $('#request-original').addEventListener('input', () => { $('#request-submit').disabled = true; });
  $('#add-condition').addEventListener('click', () => {
    if (!draft) return;
    const label = $('#new-condition-label').value.trim();
    if (!label) return toast('추가할 조건의 이름을 입력해주세요.');
    draft.conditions_json.push({ key: 'custom_' + Date.now(), label, value: '', unit: '', constraint: 'HARD', origin: 'MANUAL' });
    $('#new-condition-label').value = '';
    renderConditions();
  });
  $('#request-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || state.submitting || !draft) return;
    if ($('#request-original').value.trim() !== original) return toast('수정한 요청을 다시 분석해주세요.');
    state.submitting = true;
    $('#request-submit').disabled = true;
    $('#intake-status').textContent = 'AI가 정중한 협업 요청서를 작성하고 있습니다…';
    const version = state.renderId;
    try {
      const extra = [];
      document.querySelectorAll('#request-questions [data-answer-key]').forEach(input => {
        extra.push({ key: input.dataset.answerKey, label: input.closest('label').textContent.trim().slice(0, 100), value: input.value.trim(), constraint: 'HARD' });
      });
      const payload = { original_text: original, task_content: $('#request-title').value,
        assignee_id: Number($('#request-person').value), assignee_department: $('#request-team').value, due_at: $('#request-due').value,
        conditions_json: [{ key: 'deadline', label: '마감', constraint: $('#hard-deadline').value }, ...draft.conditions_json, ...extra] };
      const files=Array.from($('#request-files').files || []);
      if (files.length>5 || files.some(file=>file.size>10*1024*1024) || files.reduce((sum,file)=>sum+file.size,0)>20*1024*1024) throw Error('첨부파일은 최대 5개, 파일당 10MB, 전체 20MB까지 가능합니다.');
      let result;
      if (files.length) {
        const form=new FormData(); form.append('payload',JSON.stringify(payload));
        files.forEach(file=>form.append('attachments',file));
        result=await api('/requests',{method:'POST',body:form});
      } else result=await post('/requests',payload);
      await refreshData(false);
      if (version === state.renderId) await openDetail(result.id);
      toast('요청을 제출했습니다. 수행자의 요청함에서 확인할 수 있습니다.');
    } catch (error) { if (version === state.renderId) $('#request-error').textContent = error.message; }
    finally { state.submitting = false; if (version === state.renderId) $('#request-submit').disabled = false; }
  });
}
