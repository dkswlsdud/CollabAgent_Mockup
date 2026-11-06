import { navigatePath, refreshData, syncNav } from '../core/router.js';
import { state } from '../core/state.js';
import { api, post } from '../core/api.js';
import { dateTime, displayStatus, tag, requestTitle } from '../shared/presentation.js';
import { view } from '../shared/templates.js';
import { $, esc } from '../shared/dom.js';
import { statusNames } from '../shared/constants.js';
import { toast } from '../shared/notifications.js';
import { alternativeCard } from '../components/alternative-card.js';
import { requestSchedule } from '../components/request-schedule.js';
import { closeResponseDialog, openResponseDialog } from '../components/response-dialog.js';

const generationFailures = new Map();
const selectionNotices = new Set();
function generationFailureMessage(message) {
  return message || '대안을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.';
}

export function openDetail(id) {
  return navigatePath('/requests/' + id);
}

export async function renderRequestDetail(id) {
  const version = state.renderId;
  try {
    const data = await api('/requests/' + id);
    if (version !== state.renderId || state.page !== 'request-detail') return;
    const result = data.result;
    data.request.status = displayStatus(data.request.status, result?.status);
    data.rounds = data.rounds.map((negotiation) => ({
      ...negotiation,
      b_decision: negotiation.assignee_comment || negotiation.accepted_condition_keys_json?.length || negotiation.accepted_condition_key ? 'CONDITIONAL_ACCEPT' : null,
      b_comment: negotiation.assignee_comment,
      a_feedback: negotiation.requester_feedback,
      b_feedback: negotiation.assignee_feedback,
      selected_alternative_id: negotiation.selected_alternative_key
        ? Number(negotiation.selected_alternative_key)
        : null,
      a_confirmed_at: result?.negotiation_id === negotiation.id ? result.a_confirmed_at : null,
      b_confirmed_at: result?.negotiation_id === negotiation.id ? result.b_confirmed_at : null,
      agreed_at: result?.finalized_at,
    }));
    state.activeDetail = data;
    const collaborationRequest = data.request,
      round = data.rounds[0],
      isRequester = collaborationRequest.requester_id === state.user.id;
    state.requestBox = isRequester ? 'sent' : 'received';
    syncNav();
    let body = view('request-summary', {
      statusTag: tag(collaborationRequest),
      requestId: collaborationRequest.id,
      roundLabel: round ? round.round_no + '차 조율' : '협상 없음',
      title: esc(requestTitle(collaborationRequest)),
      originalText: esc(collaborationRequest.request_message || collaborationRequest.original_text),
      requesterName: esc(collaborationRequest.requester_name),
      assigneeName: esc(collaborationRequest.assignee_name),
      dueAt: dateTime(collaborationRequest.due_at),
      conditions: (collaborationRequest.conditions_json || [])
        .map((entry, index) =>
          view('request-condition', {
            popoverId: `request-condition-${index}`,
            label: esc(entry.label),
            value: esc(
              entry.key === 'deadline' ? dateTime(collaborationRequest.due_at) : entry.value,
            ),
            constraint: esc(entry.constraint),
            constraintClass: entry.constraint === 'HARD' ? 'constraint-hard' : 'constraint-soft',
          }),
        )
        .join(''),
    });
    if (collaborationRequest.needs_recoordination) {
      body = view('consent-rejection-notice', {entries:(collaborationRequest.consent_rejections || []).map(entry => `<li><strong>${esc(entry.employee_name)} 님이 동의를 거부했습니다.</strong><p>${esc(entry.reason)}</p></li>`).join('')}) + body;
    } else {
      const inherited = round?.request_snapshot_json?.related_party_rejections || [];
      if (inherited.length) body = `<section class="recoordination-context"><b>관계자 거부 의견을 반영해 재조정 중입니다.</b>${inherited.map(entry => `<p>${esc(entry.employee_name)}: ${esc(entry.reason)}</p>`).join('')}</section>` + body;
    }
    if (data.attachments?.length) body += `<section class="request-attachments"><h3>첨부파일</h3>${data.attachments.map(file=>`<a href="/api/attachments/${Number(file.id)}" download>${esc(file.filename)} <small>${(file.size/1024/1024).toFixed(1)}MB</small></a>`).join('')}</section>`;
    let footer = '';
    if (round?.request_snapshot_json?.previous_response) {
      body += `<div class="analysis">재요청 사유: ${esc(round.requester_feedback || '')}<br>이전 거절 사유: ${esc(round.request_snapshot_json.previous_response.reject_reason || '')}</div>`;
    }
    const analysis = data.analysis || round?.analysis_json;
    if (data.schedule_timeline && !isRequester) body += requestSchedule(data.schedule_timeline,collaborationRequest);
    if (collaborationRequest.status === 'SUBMITTED' && !isRequester) {
      body += view('response-form', {
            acceptClass: '',
            conditionalClass: 'recommended',
            rejectClass: '',
            acceptBadge: '',
            conditionalBadge: '<span class="response-recommendation">추천</span>',
            rejectBadge: '',
          });
    }
    if (data.response && !round) {
      body += view('direct-response', {
        decision: data.response.decision === 'ACCEPTED' ? '수락' : '거절',
        reason: esc(data.response.reject_reason || '원래 조건으로 수락했습니다.'),
      });
    }
    if (round?.b_decision) {
      body += view('negotiation-response', {
        decision: { ACCEPT: '수락', CONDITIONAL_ACCEPT: '조건부 수락', REJECT: '거절' }[
          round.b_decision
        ],
        comment: esc(round.b_comment || '추가 의견 없음'),
        conditions: esc((round.accepted_condition_keys_json || (round.accepted_condition_key ? [round.accepted_condition_key] : [])).map(key => collaborationRequest.conditions_json.find(condition => condition.key===key)?.label || key).join(' · ') || '기타 의견 참고'),
      });
    }
    if (collaborationRequest.status === 'NEGOTIATING' && !data.alternatives.length)
      footer = view('generate-alternatives-button');
    if (data.alternatives.length) {
      const common = data.alternatives.filter(a => a.a_selected && a.b_selected);
      body += `<div class="analysis">공통 선택 대안 ${common.length}개${common.length ? ' · ' + common.map(a => esc(a.title)).join(', ') : ' · 양측의 선택이 겹치지 않으면 재조정 의견을 남겨주세요.'}</div>`;
      body += view('alternatives-section', {
        role: isRequester ? '요청자' : '수행자',
        selectionStatus:esc(`${collaborationRequest.requester_name}: ${data.alternatives.every(a => a.a_selection_completed) ? '선택완료' : '선택 중'} · ${collaborationRequest.assignee_name}: ${data.alternatives.every(a => a.b_selection_completed) ? '선택완료' : '선택 중'}`),
        completionDisabled:data.alternatives.every(a => a[isRequester ? 'a_selection_completed' : 'b_selection_completed']) || !data.alternatives.some(a => a[isRequester ? 'a_selected' : 'b_selected']) || collaborationRequest.status !== 'NEGOTIATING' || collaborationRequest.needs_recoordination ? 'disabled' : '',
        completionLabel:data.alternatives.every(a => a[isRequester ? 'a_selection_completed' : 'b_selection_completed']) ? '선택완료 ✓' : '선택완료',
        allUnavailable:!isRequester && collaborationRequest.status === 'NEGOTIATING' && !collaborationRequest.needs_recoordination && !data.alternatives.some(a => a.b_selection_completed)
          ? '<div class="all-unavailable"><label><input id="all-unavailable" type="checkbox" onchange="toggleAllUnavailable()" /> 대안 모두 불가</label><div id="all-unavailable-feedback" hidden><label for="all-unavailable-comment">재조정 의견 (선택)</label><textarea id="all-unavailable-comment" rows="3" maxlength="2000" placeholder="다시 조율할 조건이 있다면 작성해주세요."></textarea><p class="hint">의견 없이 선택완료하면 협의가 종료됩니다. 의견을 작성하면 새 대안을 생성합니다.</p></div></div>' : '',
        cards: data.alternatives.map(alternative => alternativeCard(alternative, {request:collaborationRequest,round,isRequester,consents:data.consents})).join(''),
      });
    }
    if (collaborationRequest.status === 'AWAITING_CONFIRMATION') {
      body += view('confirmation-section', {
        alternativeTitle: esc(
          data.alternatives.find((alternative) => alternative.id === round.selected_alternative_id)
            ?.title || '미지정',
        ),
        requesterName: esc(collaborationRequest.requester_name),
        requesterStatus: round.a_confirmed_at ? '확인 완료 ✓' : '확인 대기',
        assigneeName: esc(collaborationRequest.assignee_name),
        assigneeStatus: round.b_confirmed_at ? '확인 완료 ✓' : '확인 대기',
        disabledAttribute: collaborationRequest.needs_recoordination || (isRequester ? round.a_confirmed_at : round.b_confirmed_at)
          ? 'disabled'
          : '',
        alternativeId: round.selected_alternative_id,
        consentStatus:confirmationConsents(data,round),
        settingsAction:!isRequester && data.needs_calendar_settings ? `<button class="primary" onclick="act('calendar_settings')">내 일정 설정 · 등록</button>` : '',
        preferencesSummary:isRequester ? '요청자는 일정 등록 대상이 아니므로 내 일정 설정이 필요하지 않습니다.' : calendarSettingsSummary(data.result?.agreed_terms_json?.calendar_preferences?.[String(state.user.id)],data.consents.some(c=>String(c.alternative_id)===String(round.selected_alternative_id))),
      });
      // Completion follows the second final confirmation or the last related-party approval.
    }
    if (collaborationRequest.status === 'AGREED')
      body += view('agreement-success', {
        finalizedAt: dateTime(data.result?.finalized_at),
      });
    if (['NEGOTIATING', 'REJECTED'].includes(collaborationRequest.status) && !collaborationRequest.needs_recoordination)
      footer = view('renegotiate-button') + footer;
    if (isRequester && ['SUBMITTED', 'NEGOTIATING', 'AWAITING_CONFIRMATION', 'REJECTED'].includes(collaborationRequest.status)) {
      footer += '<button class="secondary" onclick="cancelRequest()">요청 취소</button>';
    }
    if (isRequester && collaborationRequest.status === 'REJECTED') {
      body += '<div class="section-title">수정 후 재요청</div><div class="field"><label for="resubmit-due">새 마감 일시</label><input id="resubmit-due" type="datetime-local" /></div><div class="field"><label for="resubmit-feedback">변경 내용·재요청 사유</label><textarea id="resubmit-feedback" rows="3"></textarea></div>';
      footer += '<button class="primary" onclick="resubmitRequest()">수행자에게 다시 요청</button>';
    }
    const archivedRounds = data.rounds.filter(item => item.status !== 'IN_PROGRESS' && item.status !== 'AGREED');
    if (archivedRounds.length)
      body += view('round-history', {
        rounds: archivedRounds
          .map((item) =>
            view('round-history-item', {
              number: item.round_no,
              status: statusNames[item.status] || esc(item.status),
              feedback: esc(item.a_feedback || item.b_feedback || item.b_comment || '기록 없음'),
              closedAt: dateTime(item.closed_at),
            }),
          )
          .join(''),
      });
    if (generationFailures.has(id)) body += `<section id="alternative-error" class="alternative-error" role="alert"><strong>대안 생성 안내</strong><p>${esc(generationFailures.get(id))}</p></section>`;
    const footerHint = ['NEGOTIATING', 'REJECTED'].includes(collaborationRequest.status) && !collaborationRequest.needs_recoordination
      ? '<p id="renegotiate-hint" class="hint request-footer-hint">대안이 모두 마음에 들지 않을 시, 작성해주세요.</p>' : '';
    $('#app').innerHTML = view('request-detail-page', { body, footer, footerHint });
    const noticeKey = `${state.user.id}:${id}:${round?.id}`;
    if (isRequester && collaborationRequest.status === 'NEGOTIATING' && !collaborationRequest.needs_recoordination
        && data.alternatives.length && data.alternatives.every(a => a.a_selection_completed && a.b_selection_completed)
        && !data.alternatives.some(a => a.a_selected && a.b_selected) && !selectionNotices.has(noticeKey)) {
      selectionNotices.add(noticeKey);
      openResponseDialog({decision:'NO_COMMON',conditions:[],onSubmit:async () => {
        closeResponseDialog();
        openRenegotiate();
        return true;
      }});
    }
    if (data.notice_version) {
      const marked=await post('/requests/'+id+'/read',{version:data.notice_version}).catch(()=>null);
      if (!marked) return;
      state.requests.forEach(row=>{if(row.id===id && row.notice_version===data.notice_version) row.is_new=false;});
      if (state.user) syncNav();
    }
  } catch (error) {
    if (version === state.renderId)
      $('#app').innerHTML = view('screen-error', { message: esc(error.message) });
  }
}

export async function act(action, data = {}, { keepDialogOnError = false } = {}) {
  if (state.submitting) return;
  if (state.user.id!==state.activeDetail.request.requester_id && (action === 'calendar_settings' || (action === 'confirm' && !state.activeDetail.consents.some(c=>String(c.alternative_id)===String(state.activeDetail.rounds[0]?.selected_alternative_id)))) && (!data.schedule_priority || !data.schedule_workload)) {
    return openResponseDialog({decision:'SCHEDULE_SETTINGS',conditions:[],title:'최종 확인 · 내 일정 설정',submitLabel:'설정하고 최종 확인',
      onSubmit:values => act(action,{...data,schedule_priority:values.schedule_priority,schedule_workload:values.schedule_workload},{keepDialogOnError:true})});
  }
  state.submitting = true;
  const id = state.activeDetail.request.id;
  if (action==='generate') generationFailures.delete(id);
  const generateButton = action === 'generate' ? $('#generate-alternatives') : null;
  if (generateButton) {
    generateButton.disabled = true;
    generateButton.textContent = '대안 3개를 생성하고 있습니다…';
  }
  try {
    await post('/requests/' + id + '/action', { action, ...data });
    await refreshData(false);
    if (state.routeId === id) await openDetail(id);
    toast(action === 'reject_all' ? '대안 모두 불가로 협의를 종료했습니다.' : action === 'generate' ? '대안 3개를 생성했습니다.' : action === 'finalize' ? '합의와 일정을 DB에 저장했습니다.' : '변경 사항을 저장했습니다.');
    return true;
  } catch (error) {
    if (action==='generate') {
      if (state.page==='request-detail' && state.routeId===id) {
        generationFailures.set(id,generationFailureMessage(error.message));
        await renderRequestDetail(id);
      }
      return false;
    }
    if (keepDialogOnError) throw error;
    toast(error.message);
    await openDetail(id);
  } finally {
    state.submitting = false;
    if (generateButton) {
      generateButton.disabled = false;
      generateButton.textContent = '대안 생성 ✧';
    }
  }
}

export function respond(decision) {
  if (state.submitting) return;
  const request = state.activeDetail?.request;
  if (!request || request.assignee_id !== state.user?.id || request.status !== 'SUBMITTED') return;
  if (decision === 'ACCEPT') {
    return openResponseDialog({decision:'SCHEDULE_SETTINGS',conditions:[],title:'수락 · 내 일정 등록',submitLabel:'수락하고 일정 등록',
      onSubmit:values => act('respond',{decision,comment:'',accepted_condition_keys:[],schedule_priority:values.schedule_priority,schedule_workload:values.schedule_workload},{keepDialogOnError:true})});
  }
  if (!['CONDITIONAL_ACCEPT','REJECT'].includes(decision)) return;
  return openResponseDialog({decision,conditions:request.conditions_json || [],
    onSubmit:async data => {
      const id = request.id;
      const saved = await act('respond',data,{keepDialogOnError:true});
      if (!saved) return false;
      closeResponseDialog();
      if (decision === 'CONDITIONAL_ACCEPT' && state.page === 'request-detail' && state.routeId === id) {
        openResponseDialog({decision:'GENERATE',conditions:[],onSubmit:async () => {
          closeResponseDialog();
          if (state.page === 'request-detail' && state.routeId === id) await act('generate');
          return true;
        }});
      }
      return true;
    }});
}

export function cancelRequest() {
  if (window.confirm('이 협업 요청을 취소할까요?')) return act('cancel');
}

export function resubmitRequest() {
  return act('resubmit', { due_at: $('#resubmit-due').value, feedback: $('#resubmit-feedback').value });
}

export function openRenegotiate() {
  const request = state.activeDetail?.request;
  if (state.submitting || !request || !['NEGOTIATING','REJECTED'].includes(request.status) || request.needs_recoordination) return;
  return openResponseDialog({decision:'FEEDBACK', conditions:[],
    onSubmit:async data => {
      const id = request.id;
      const saved = await act('renegotiate',{feedback:data.comment},{keepDialogOnError:true});
      if (!saved) return false;
      closeResponseDialog();
      if (state.page === 'request-detail' && state.routeId === id) await act('generate');
      return true;
    }});
}

export function toggleAllUnavailable() {
  const checked = $('#all-unavailable')?.checked;
  $('#all-unavailable-feedback').hidden = !checked;
  $('#complete-selection').disabled = !checked && !state.activeDetail.alternatives.some(a => a.b_selected);
}

export async function completeSelection() {
  if (state.submitting) return;
  if (!$('#all-unavailable')?.checked || state.user.id === state.activeDetail.request.requester_id)
    return act('complete_selection');
  const feedback = $('#all-unavailable-comment').value.trim();
  if (!feedback) return act('reject_all');
  const id = state.activeDetail.request.id;
  const saved = await act('renegotiate',{feedback});
  if (saved && state.page === 'request-detail' && state.routeId === id) return act('generate');
}

export async function renderRequestRenegotiate(id) {
  const version = state.renderId;
  try {
    const data = await api('/requests/' + id);
    if (version !== state.renderId) return;
    state.activeDetail = data;
    const status = data.request.status;
    if (!['NEGOTIATING', 'REJECTED'].includes(status))
      throw new Error('재조정할 수 없는 요청입니다.');
    $('#app').innerHTML = view('request-renegotiate-page', { requestId: id });
  } catch (error) {
    if (version === state.renderId)
      $('#app').innerHTML = view('screen-error', { message: esc(error.message) });
  }
}

export function submitFeedback() {
  const feedback = $('#feedback').value.trim();
  if (!feedback) return toast('재조정 의견을 입력해주세요.');
  act('renegotiate', { feedback });
}


export function toggleAlternative(id) {
  if (state.submitting) return;
  const data = state.activeDetail;
  if (!data || data.request.needs_recoordination || !['NEGOTIATING','AWAITING_CONFIRMATION'].includes(data.request.status)) return;
  const alternative = data.alternatives.find(item => item.id === id);
  if (!alternative) return;
  const requester = data.request.requester_id === state.user?.id;
  if (!requester && data.request.assignee_id !== state.user?.id) return;
  if (data.alternatives.some(item => item[requester ? 'a_selection_completed' : 'b_selection_completed'])) return;
  if (!requester && $('#all-unavailable')?.checked) {
    $('#all-unavailable').checked = false;
    toggleAllUnavailable();
  }
  return act('select',{alternative_id:id,selected:!(requester ? alternative.a_selected : alternative.b_selected)});
}


function confirmationConsents(data, round) {
  const consents = data.consents.filter(consent => String(consent.alternative_id) === String(round.selected_alternative_id));
  if (!consents.length) return '<div class="confirmation-consents"><h4>관계자 동의 현황</h4><p class="hint">추가로 동의가 필요한 관계자가 없습니다. 양측 최종 확인이 끝나면 자동으로 완료됩니다.</p></div>';
  const sent = !!(round.a_confirmed_at && round.b_confirmed_at);
  const labels = {WAITING:'요청 전',PENDING:'동의 대기',APPROVED:'동의 완료',REJECTED:'동의 거부',CANCELLED:'요청 중단'};
  return `<section class="confirmation-consents"><h4>관계자 동의 현황</h4><p class="hint">${data.request.needs_recoordination ? '관계자가 동의를 거부해 해당 대안의 완료가 중단되었습니다. 재조정 시작을 눌러주세요.' : sent ? '양측 최종 확인이 완료되어 관계자에게 동의를 요청했습니다. 관계자는 동의 시 바로 등록하고, 수행자는 전원 동의 후 일정을 설정합니다.' : '양측 최종 확인이 완료되면 관계자에게 동의 요청이 자동으로 전달됩니다.'}</p>${consents.map(consent => `<div class="consent-progress-row"><b>${esc(consent.employee_name)}</b><span class="consent-progress ${esc(sent ? consent.status : 'WAITING')}">${esc(sent ? labels[consent.status] || consent.status : '요청 전')}</span></div>`).join('')}</section>`;
}


export async function restartAfterRejection() {
  const data = state.activeDetail;
  if (state.submitting || !data?.request.needs_recoordination || !data.rounds[0]) return;
  const id = data.request.id;
  const saved = await act('restart_after_rejection',{source_round_id:data.rounds[0].id});
  if (saved && state.page === 'request-detail' && state.routeId === id) await act('generate');
}


function calendarSettingsSummary(choice,related) {
  if (!choice && related) return '관계자 전원 동의가 끝나면 내 일정의 우선순위와 작업량을 선택합니다.';
  if (!choice) return '최종 확인을 누르면 내 일정의 우선순위와 작업량을 선택할 수 있습니다.';
  const priority={LOW:'낮음',MEDIUM:'보통',HIGH:'높음'};
  const workload={LOW:'적음',MEDIUM:'보통',HIGH:'많음'};
  return `내 일정 설정 · 우선순위 ${priority[choice.priority]} · 작업량 ${workload[choice.workload]}`;
}
