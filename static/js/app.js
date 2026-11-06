import { initializeSidebar, toggleNavigationMenu } from './components/sidebar.js';
import { $ } from './shared/dom.js';
import { enterApp, logout } from './pages/auth.js';
import { navigate, openRequestBox, refreshData, renderRoute, showLogin } from './core/router.js';
import { toast } from './shared/notifications.js';
import { state } from './core/state.js';
import { loadViews } from './shared/templates.js';
import { api } from './core/api.js';
import './core/template-actions.js';

initializeSidebar();
$('#logout').addEventListener('click', logout);

$('#refresh').addEventListener('click', () =>
  refreshData().then(() => toast('최신 데이터를 불러왔습니다.')),
);

$('#schedule-toggle').addEventListener('click', () => {
  toggleNavigationMenu('#schedule-toggle', '#schedule-submenu');
});

$('#home-brand').addEventListener('click', (e) => {
  e.preventDefault();
  openRequestBox('received');
});

$('#request-nav').addEventListener('click', () => toggleNavigationMenu('#request-nav', '#request-submenu'));
document.querySelectorAll('[data-request-box]').forEach((button) => {
  button.addEventListener('click', () => openRequestBox(button.dataset.requestBox));
});

$('#history-nav').addEventListener('click', () => navigate('history'));

const scopeButtons = document.querySelectorAll('[data-scope]');

scopeButtons.forEach((b) =>
  b.addEventListener('click', () => navigate('calendar', b.dataset.scope)),
);

window.addEventListener('focus', () => {
  if (state.user && !$('#my-calendar-dialog').open && ['inbox','consents','request-detail','calendar'].includes(state.page)) refreshData(!document.querySelector('.consent-full-card[open]'));
});

// Keep cross-account approvals and new calendar notifications visible without disturbing open forms.
window.setInterval?.(() => {
  if (!state.user || document.hidden || state.submitting || $('#my-calendar-dialog').open || $('#response-dialog').open || $('#schedule-dialog').open) return;
  refreshData(['inbox','consents','request-detail'].includes(state.page) && !document.querySelector('.consent-full-card[open]'));
}, 20000);

window.addEventListener('popstate', () => {
  renderRoute().catch((error) => toast(error.message));
});

async function boot() {
  await loadViews();
  // The site entry always starts with an explicit employee login, even if a cookie exists.
  if (location.pathname === '/' || location.pathname.replace(/\/$/, '') === '/login') {
    state.user = null;
    showLogin(false);
    return;
  }
  try {
    const result = await api('/auth/me');
    state.user = result.user;
    await enterApp();
  } catch (e) {
    showLogin();
    if (!e.message.includes('로그인')) $('#auth-error').textContent = e.message;
  }
}

boot().catch((error) => {
  $('#auth-root').textContent = '화면을 불러오지 못했습니다. 새로고침 후 다시 시도해주세요.';
  console.error(error);
});
