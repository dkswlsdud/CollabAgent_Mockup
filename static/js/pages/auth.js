import { $ } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { api, post } from '../core/api.js';
import { state } from '../core/state.js';
import { displayStatus } from '../shared/presentation.js';
import { renderRoute, showLogin } from '../core/router.js';
import { toast } from '../shared/notifications.js';
import { resetNavigationMenus } from '../components/sidebar.js';

// 직원 계정은 employees 테이블에서 관리합니다. 공개 회원가입은 제공하지 않습니다.
export function showAuth() {
  resetNavigationMenus();
  state.user = null;
  state.employees = [];
  state.departments = [];
  state.requests = [];
  state.consents = [];
  state.newScheduleCount = 0;
  $('#schedule-new-badge').hidden = true;
  for (const id of ['sent','received','consents','requests']) $('#'+id+'-new-badge').hidden=true;
  state.activeDetail = null;
  state.calendarEmployeeId = '';
  state.calendarDepartment = '';
  document.body.classList.add('signed-out');
  $('#app').innerHTML = '';
  $('#profile-name').textContent = '';
  $('#profile-team').textContent = '';
  $('#profile-login-id').textContent = '';
  $('#profile-initial').textContent = '';
  $('#profile-status').hidden = true;
  $('#auth-root').innerHTML = view('auth-page', { demoAccount: view('demo-account') });
  $('#auth-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = $('.auth-submit');
    if (button.disabled) return;
    button.disabled = true;
    $('#auth-error').textContent = '';
    try {
      const result = await post('/auth/login', {
        login_id: $('#auth-login-id').value.trim(),
        password: $('#auth-password').value,
      });
      state.user = result.user;
      state.loginDestination = '/requests/received';
      await enterApp();
    } catch (error) {
      state.user = null;
      document.body.classList.add('signed-out');
      $('#auth-error').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  $('#auth-login-id').focus();
}

export function fillDemo(loginId = 'minji.kim') {
  $('#auth-login-id').value = loginId;
  $('#auth-password').value = 'Collab123!';
  $('#auth-login-id').focus();
}

export async function enterApp() {
  const [employeeData, requestData, consentData, notificationData] = await Promise.all([
    api('/employees'),
    api('/requests'),
    api('/consents'),
    api('/schedules/notifications'),
  ]);
  state.employees = employeeData.employees;
  state.departments = employeeData.departments;
  state.requests = requestData.requests.map((collaborationRequest) => ({
    ...collaborationRequest,
    status: displayStatus(collaborationRequest.status, collaborationRequest.result_status),
  }));
  state.consents = consentData.consents;
  state.newScheduleCount = notificationData.count;
  $('#profile-name').textContent = state.user.name;
  $('#profile-team').textContent = state.user.department;
  $('#profile-login-id').textContent = state.user.login_id;
  $('#profile-status').hidden = false;
  $('#profile-initial').textContent = state.user.name[0];
  $('#top-date').textContent = new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'full',
    timeZone: 'Asia/Seoul',
  }).format(new Date());
  await renderRoute();
  if (!state.user) return;
  document.body.classList.remove('signed-out');
  $('#auth-root').innerHTML = '';
}

export async function logout() {
  try {
    await post('/auth/logout', {});
    state.user = null;
    state.requests = [];
    state.consents = [];
    state.renderId++;
    state.loginDestination = '/requests/received';
    showLogin(false);
  } catch (error) {
    toast(error.message);
  }
}
