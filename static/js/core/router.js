import { closeMyCalendarDialog } from '../components/my-calendar-dialog.js';
import { state } from './state.js';
import { showAuth } from '../pages/auth.js';
import { $ } from '../shared/dom.js';
import { renderCalendar, renderScheduleDetail, renderScheduleNew } from '../pages/calendar.js';
import { renderHistory } from '../pages/history.js';
import { renderRequestNew } from '../pages/requests.js';
import { renderRequestDetail, renderRequestRenegotiate } from '../pages/request-detail.js';
import { renderConsents, renderInbox } from '../pages/inbox.js';
import { api } from './api.js';
import { displayStatus } from '../shared/presentation.js';
import { toast } from '../shared/notifications.js';
import { closeScheduleDialog } from '../components/schedule-dialog.js';
import { closeResponseDialog } from '../components/response-dialog.js';

// URL과 화면 상태를 한곳에서 연결합니다.
export const routes = {
  '/login': { page: 'login' },
  '/requests/sent': { page: 'inbox', box: 'sent' },
  '/requests/received': { page: 'inbox', box: 'received' },
  '/requests/consents': { page: 'consents', box: 'consents' },
  '/requests/new': { page: 'request-new' },
  '/calendar/team': { page: 'calendar', scope: 'team' },
  '/calendar/my': { page: 'calendar', scope: 'my' },
  '/schedules/new': { page: 'schedule-new' },
  '/history': { page: 'history' },
};


export function resolveRoute(path) {
  if (routes[path]) return routes[path];
  const request = path.match(/^\/requests\/([1-9]\d*)(\/renegotiate)?$/);
  if (request)
    return { page: request[2] ? 'request-renegotiate' : 'request-detail', id: Number(request[1]) };
  const schedule = path.match(/^\/schedules\/([1-9]\d*)$/);
  if (schedule) return { page: 'schedule-detail', id: Number(schedule[1]) };
  return null;
}

export function routePath(nextPage, nextScope = state.scope) {
  if (nextPage === 'calendar') return '/calendar/' + nextScope;
  if (nextPage === 'inbox') return '/requests/' + state.requestBox;
  return (
    {
      login: '/login',
      'request-new': '/requests/new',
      'schedule-new': '/schedules/new',
      history: '/history',
    }[nextPage] || '/requests/received'
  );
}

export function updateAddress(path, replace = false) {
  if (location.pathname === path && !location.search && !location.hash) return;
  history[replace ? 'replaceState' : 'pushState'](null, '', path);
}

export function showLogin(rememberDestination = true) {
  closeMyCalendarDialog();
  closeResponseDialog();
  closeScheduleDialog();
  const currentPath = location.pathname.replace(/\/$/, '') || '/';
  if (rememberDestination && resolveRoute(currentPath)?.page !== 'login') {
    state.loginDestination = resolveRoute(currentPath) ? currentPath : '/requests/received';
  }
  state.renderId++;
  state.page = 'login';
  updateAddress('/login', true);
  showAuth();
}

export async function renderRoute() {
  closeMyCalendarDialog();
  closeResponseDialog();
  closeScheduleDialog();
  let path = location.pathname.replace(/\/$/, '') || '/';
  if (path === '/calendar/all') path = '/calendar/team';
  if (path === '/requests') path = '/requests/received';
  if (!resolveRoute(path)) path = state.user ? '/requests/received' : '/login';
  if (!state.user) {
    if (path !== '/login') state.loginDestination = path;
    showLogin(false);
    return;
  }
  if (path === '/login') path = state.loginDestination;
  const route = resolveRoute(path) || routes['/requests/received'];
  updateAddress(path, true);
  state.renderId++;
  state.page = route.page;
  state.routeId = route.id || null;
  if (route.box && route.box !== state.requestBox) state.filter = 'all';
  if (route.box) state.requestBox = route.box;
  if (route.scope) state.scope = route.scope;
  await render();
}

export async function navigatePath(path) {
  if (!state.user) {
    state.loginDestination = path;
    showLogin(false);
    return;
  }
  updateAddress(path);
  await renderRoute();
}

export function navigate(next, nextScope) {
  return navigatePath(routePath(next, nextScope));
}

export function openRequestBox(box) {
  return navigatePath('/requests/' + box);
}

export function syncNav() {
  document
    .querySelectorAll('[data-page]')
    .forEach((b) =>
      b.classList.toggle(
        'active',
        b.dataset.page === state.page ||
          (b.dataset.page === 'inbox' && (state.page.startsWith('request-') || state.page === 'consents')) ||
          (b.dataset.page === 'calendar' && state.page.startsWith('schedule-')),
      ),
    );
  document
    .querySelectorAll('[data-scope]')
    .forEach((b) => b.classList.toggle('active', state.page === 'calendar' && b.dataset.scope === state.scope));
  $('#breadcrumb').textContent =
    state.page === 'calendar'
      ? { team: '일정 / 팀 일정', my: '일정 / 내 일정' }[state.scope]
      : {
          inbox: state.requestBox === 'sent' ? '협업 요청함 / 나의 요청' : '협업 요청함 / 받은 요청',
          consents: '협업 요청함 / 관계자 동의 요청',
          'request-new': '새 협업 요청',
          'request-detail': '협업 요청 상세',
          'request-renegotiate': '재조정 의견',
          'schedule-new': '내 일정 추가',
          'schedule-detail': '일정 상세',
          history: '합의 기록',
        }[state.page];
  document
    .querySelectorAll('[data-request-box]')
    .forEach((button) =>
      button.classList.toggle(
        'active',
        ['inbox','consents'].includes(state.page) && button.dataset.requestBox === state.requestBox,
      ),
    );
  const sentNew=state.requests.some(r=>r.requester_id===state.user.id && r.is_new);
  const receivedNew=state.requests.some(r=>r.assignee_id===state.user.id && r.is_new);
  const consentNew=state.consents.some(c=>c.is_new);
  $('#sent-new-badge').hidden=!sentNew;
  $('#received-new-badge').hidden=!receivedNew;
  $('#consents-new-badge').hidden=!consentNew;
  $('#requests-new-badge').hidden=!(sentNew||receivedNew||consentNew);
  $('#schedule-new-badge').hidden = !state.newScheduleCount;
  $('#schedule-new-badge').title = `새 일정 ${state.newScheduleCount}건`;

}

export async function render() {
  if (!state.user) return;
  syncNav();
  if (state.page === 'calendar') return renderCalendar();
  if (state.page === 'consents') return renderConsents();
  if (state.page === 'history') return renderHistory();
  if (state.page === 'request-new') return renderRequestNew();
  if (state.page === 'request-detail') return renderRequestDetail(state.routeId);
  if (state.page === 'request-renegotiate') return renderRequestRenegotiate(state.routeId);
  if (state.page === 'schedule-new') return renderScheduleNew();
  if (state.page === 'schedule-detail') return renderScheduleDetail(state.routeId);
  renderInbox();
}

export async function refreshData(renderPage = true) {
  try {
    const [a, b, notificationData] = await Promise.all([api('/requests'), api('/consents'), api('/schedules/notifications')]);
    const previousNotices = new Set(state.requests.filter(r => r.needs_recoordination).map(r => r.id));
    const newNotices = a.requests.filter(r => r.needs_recoordination && !previousNotices.has(r.id));
    if (newNotices.length) toast(`관계자가 동의를 거부한 협업 ${newNotices.length}건이 있습니다. 재조정이 필요합니다.`);
    state.requests = a.requests.map((r) => ({ ...r, status: displayStatus(r.status, r.result_status) }));
    state.consents = b.consents;
    state.newScheduleCount = notificationData.count;
    if (state.user) syncNav();
    if (renderPage) await render();
  } catch (e) {
    toast(e.message);
  }
}

