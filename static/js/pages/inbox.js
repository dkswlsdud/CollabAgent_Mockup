import { openResponseDialog } from '../components/response-dialog.js';
import { consentDetail } from '../components/consent-detail.js';
import { state } from '../core/state.js';
import { refreshData, render, syncNav } from '../core/router.js';
import { $, esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { heading, tag, requestTitle } from '../shared/presentation.js';
import { api, post } from '../core/api.js';
import { toast } from '../shared/notifications.js';

export function setFilter(next) {
  state.filter = next;
  render();
}

export function renderInbox() {
  const boxRequests = state.requests.filter((collaborationRequest) =>
    state.requestBox === 'sent'
      ? collaborationRequest.requester_id === state.user.id
      : collaborationRequest.assignee_id === state.user.id,
  );
  const boxTitle = state.requestBox === 'sent' ? '나의 요청' : '받은 요청';
  const completedStatuses = ['AGREED', 'REJECTED', 'CANCELLED', 'FAILED'];
  const knownStatuses = ['SUBMITTED', 'NEGOTIATING', 'AWAITING_CONFIRMATION', ...completedStatuses];
  const other = boxRequests.filter(r => !knownStatuses.includes(r.status)).length;
  const done = boxRequests.filter(
      (collaborationRequest) => completedStatuses.includes(collaborationRequest.status),
    ).length,
    wait = boxRequests.filter(
      (collaborationRequest) => collaborationRequest.status === 'SUBMITTED',
    ).length,
    neg = boxRequests.filter((collaborationRequest) =>
      ['NEGOTIATING', 'AWAITING_CONFIRMATION'].includes(collaborationRequest.status),
    ).length;
  const rows = boxRequests.filter(
    (collaborationRequest) =>
      state.filter === 'all' ||
      collaborationRequest.status === state.filter ||
      (state.filter === 'NEGOTIATING' && collaborationRequest.status === 'AWAITING_CONFIRMATION') ||
      (state.filter === 'COMPLETED' && completedStatuses.includes(collaborationRequest.status)) ||
      (state.filter === 'OTHER' && !knownStatuses.includes(collaborationRequest.status)),
  );
  $('#app').innerHTML = view('requests-' + state.requestBox + '-page', {
    heading: heading(
      'COLLABORATION HUB',
      boxTitle,
      state.requestBox === 'sent'
        ? '내가 동료에게 보낸 협업 요청을 확인하세요.'
        : '동료가 나에게 보낸 협업 요청에 응답하세요.',
      view('new-request-button'),
    ),
    statistics: [
      ['전체 요청', boxRequests.length, '▣'],
      ['응답 대기', wait, '◷'],
      ['조율 중', neg, '⇄'],
      ['완료', done, '✓'],
      ...(other ? [['기타 상태', other, '⋯']] : []),
    ]
      .map((statistic, index) =>
        view('inbox-statistic', {
          className: index === 0 ? 'accent' : '',
          label: statistic[0],
          icon: statistic[2],
          count: statistic[1],
        }),
      )
      .join(''),
    requestCount: boxRequests.length,
    tabs: [
      ['all', '전체'],
      ['SUBMITTED', '응답 대기'],
      ['NEGOTIATING', '조율 중'],
      ['COMPLETED', '완료'],
      ...(other ? [['OTHER', '기타']] : []),
    ]
      .map(([value, label]) =>
        view('inbox-tab', {
          activeClass: state.filter === value ? 'active' : '',
          value: value,
          label: label,
        }),
      )
      .join(''),
    requestCards:
      rows
        .map((collaborationRequest) =>
          view('request-card', {
            requestId: collaborationRequest.id,
            newClass:collaborationRequest.is_new ? 'is-new' : '',newBadge:collaborationRequest.is_new ? '<span class="new-label">New</span>' : '',
            keyboardRequestId: collaborationRequest.id,
            statusTag: tag(collaborationRequest),
            rejectionNotice:'',
            formattedId: String(collaborationRequest.id).padStart(3, '0'),
            direction: collaborationRequest.requester_id === state.user.id ? '보낸 요청' : '받은 요청',
            title: esc(requestTitle(collaborationRequest)),
            description: esc(collaborationRequest.request_message || collaborationRequest.original_text),
            requesterInitial: esc(collaborationRequest.requester_name[0]),
            requesterName: esc(collaborationRequest.requester_name),
            assigneeInitial: esc(collaborationRequest.assignee_name[0]),
            assigneeName: esc(collaborationRequest.assignee_name),
            assigneeDepartment: esc(collaborationRequest.assignee_department),
            dueDate: esc(collaborationRequest.due_at?.slice(0, 10) || '미정'),
            negotiationNote:
              collaborationRequest.status === 'NEGOTIATING' ? view('request-negotiation-note') : '',
          }),
        )
        .join('') || view('empty-inbox'),
    sidebar: view('inbox-sidebar', {
      department: esc(state.user.department),
      employeeName: esc(state.user.name),
      pendingConsentCount: state.consents.filter((consent) => consent.status === 'PENDING').length,
      consentCards: consentCards(),
    }),
  });
}

function consentCards(detailed = false) {
  return state.consents.map(consent => view(detailed ? 'consent-full-card' : 'consent-card', {
    consentId:esc(consent.id),
    status:consent.needs_calendar_settings ? '내 일정 설정 대기' : esc({PENDING:'동의 대기',APPROVED:'동의 완료',REJECTED:'거부',CANCELLED:'요청 중단'}[consent.status] || consent.status),
    title:esc(requestTitle({task_content:consent.request_title || '협업 요청'})),
    description:esc(consent.description?.startsWith(consent.alternative_title + ' · ')
      ? consent.description.slice(consent.alternative_title.length + 3) : consent.description || ''),
    newClass:consent.is_new ? 'is-new' : '',newBadge:consent.is_new ? '<span class="new-label">New</span>' : '',
    actions:consent.needs_calendar_settings ? `<button class="primary" onclick="configureConsentCalendar('${esc(consent.id)}')">내 일정 설정</button>` : consent.status === 'PENDING'
      ? view('consent-actions',{consentId:esc(consent.id),rejectConsentId:esc(consent.id)})
      : view('consent-status',{label:{APPROVED:'동의 완료',REJECTED:'거부',CANCELLED:'요청 중단'}[consent.status] || esc(consent.status)}),
  })).join('') || view('empty-consents');
}

export function renderConsents() {
  $('#app').innerHTML = view('consents-page', {
    heading:heading('COLLABORATION HUB','관계자 동의 요청','요청자와 수행자가 최종 확인한 협업 중 내 동의가 필요한 요청입니다.'),
    pending:state.consents.filter(consent => consent.status === 'PENDING').length,
    cards:consentCards(true),
  });
}

export function answerConsent(id, status) {
  if (state.submitting) return;
  if (status === 'REJECTED') {
    return openResponseDialog({decision:'CONSENT_REJECT',conditions:[],
      onSubmit:data => sendConsentReply(id,status,data.comment,true)});
  }
  if (status==='APPROVED') {
    return openResponseDialog({decision:'SCHEDULE_SETTINGS',conditions:[],title:'관계자 동의 · 내 일정 등록',submitLabel:'동의하고 일정 등록',
      onSubmit:data=>sendConsentReply(id,status,'',true,{schedule_priority:data.schedule_priority,schedule_workload:data.schedule_workload})});
  }
  return sendConsentReply(id,status);
}

async function sendConsentReply(id, status, reason = '', keepDialogOnError = false, preferences = {}) {
  if (state.submitting) return false;
  state.submitting = true;
  try {
    const result = await post('/consents/' + id, {status,reason,...preferences});
    await refreshData();
    toast(status === 'REJECTED' ? '동의 거부 사유를 요청자와 수행자에게 전달했습니다.' : result.schedule_registered ? '동의하고 내 일정에 등록했습니다.' : result.completed ? '모든 동의가 완료되어 협업과 일정이 자동 반영되었습니다.' : '응답을 저장했습니다.');
    if (result.needs_calendar_settings) configureConsentCalendar(id);
    return true;
  } catch (error) {
    if (keepDialogOnError) throw error;
    toast(error.message);
    return false;
  } finally {
    state.submitting = false;
  }
}


export async function loadConsentDetail(id, container) {
  if (!container.open || container.dataset.loading === 'true' || container.dataset.loaded === 'true') return;
  const userId = state.user?.id;
  const body = $('#consent-detail-' + id);
  container.dataset.loading = 'true';
  body.textContent = '협업 상세 내용을 불러오는 중입니다…';
  try {
    const data = await api('/consents/' + encodeURIComponent(id));
    if (container.isConnected === false || state.user?.id !== userId || state.page !== 'consents') return;
    body.innerHTML = consentDetail(data);
    if (data.notice_version) {
      await post('/consents/'+encodeURIComponent(id)+'/read',{version:data.notice_version});
      state.consents.forEach(c=>{if(c.id===id && c.notice_version===data.notice_version) c.is_new=false;});
      syncNav();
      container.classList?.remove('is-new');
      container.querySelector?.('.new-label')?.remove();
    }
    container.dataset.loaded = 'true';
  } catch (error) {
    if (container.isConnected === false || state.user?.id !== userId || state.page !== 'consents') return;
    body.innerHTML = `<p class="form-error">${esc(error.message)}</p><button class="secondary" type="button" onclick="loadConsentDetail('${esc(id)}',this.closest('details'))">다시 불러오기</button>`;
  } finally {
    container.dataset.loading = 'false';
  }
}


export function configureConsentCalendar(id) {
  return openResponseDialog({decision:'SCHEDULE_SETTINGS',conditions:[],title:'내 일정 등록 설정',submitLabel:'설정하고 등록',onSubmit:async data=>{
    const result=await post('/consents/'+id+'/calendar-settings',{schedule_priority:data.schedule_priority,schedule_workload:data.schedule_workload});
    await refreshData();
    toast('내 일정에 등록했습니다.');
    return true;
  }});
}
