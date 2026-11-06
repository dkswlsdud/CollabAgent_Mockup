import { calendarGrid } from '../components/calendar-grid.js';
import { state } from '../core/state.js';
import { $, esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { heading } from '../shared/presentation.js';
import { api, post } from '../core/api.js';
import { navigate, navigatePath } from '../core/router.js';
import { typeNames } from '../shared/constants.js';
import { toast } from '../shared/notifications.js';
import { openScheduleDialog } from '../components/schedule-dialog.js';
import { scheduleDetails } from '../shared/schedule-details.js';

export function shiftMonth(delta) {
  let [year, monthNumber] = state.month.split('-').map(Number);
  const date = new Date(year, monthNumber - 1 + delta, 1);
  state.month = date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
  renderCalendar();
}

export function todayMonth() {
  const date = new Date();
  state.month = date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
  renderCalendar();
}

export function setMonth(value) {
  if (/^\d{4}-\d{2}$/.test(value)) {
    state.month = value;
    renderCalendar();
  }
}

export function isoLocal(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export async function renderCalendar() {
  const renderVersion = ++state.renderId;
  const departments = [...new Set(state.employees.map(employee => employee.department))].sort();
  if (!departments.includes(state.calendarDepartment)) state.calendarDepartment = state.user.department;
  const titles = {
    team: ['팀 일정', `${esc(state.calendarDepartment)}의 월별 일정을 바로 확인하세요.`],
    my: ['내 일정', `${esc(state.user.name)} 님의 업무·회의·개인 일정을 모아봤어요.`],
  };
  const [year, monthNumber] = state.month.split('-').map(Number);
  const teamEmployees = state.employees.filter(employee => employee.department === state.calendarDepartment);
  if (state.calendarEmployeeId && !teamEmployees.some(employee => String(employee.id) === state.calendarEmployeeId)) state.calendarEmployeeId = '';
  $('#app').innerHTML = view('calendar-' + state.scope + '-page', {
    toolbar: view('calendar-toolbar', {
      year: year,
      monthNumber: monthNumber,
      month: state.month,
      teamFilter:
        state.scope === 'team'
            ? view('calendar-employee-filter', {
                departmentOptions: departments.map(department => view('calendar-team-option', {
                  value: esc(department),
                  selectedAttribute: department === state.calendarDepartment ? 'selected' : '',
                  label: esc(department),
                })).join(''),
                options: teamEmployees.map(employee => view('calendar-team-option', {
                  value: employee.id,
                  selectedAttribute: String(employee.id) === state.calendarEmployeeId ? 'selected' : '',
                  label: esc(employee.name),
                })).join(''),
              })
          : view('calendar-scope', {
              label: esc(state.user.name) + ' · ' + esc(state.user.department),
            }),
    }),
    heading: heading('SCHEDULE', titles[state.scope][0], titles[state.scope][1], view('new-schedule-button')),
  });
  if (state.scope === 'team') {
    $('#calendar-department-select').addEventListener('change', event => {
      state.calendarDepartment = event.target.value;
      state.calendarEmployeeId = '';
      return renderCalendar();
    });
    $('#calendar-employee-select').addEventListener('change', event => {
      state.calendarEmployeeId = event.target.value;
      return renderCalendar();
    });
  }
  try {
    const data = await api(
      '/schedules?' +
        new URLSearchParams({
          month: state.month,
          scope: state.scope,
          ...(state.scope === 'team' ? { department: state.calendarDepartment } : {}),
          ...(state.scope === 'team' && state.calendarEmployeeId ? { employee_id: state.calendarEmployeeId } : {}),
        }),
    );
    if (renderVersion !== state.renderId || state.page !== 'calendar') return;
    const items = data.schedules;
    $('#schedule-total').textContent = `${items.length}개 일정`;
    $('#calendar-body').className = '';
    $('#calendar-body').innerHTML = calendarGrid(state.month, items, isoLocal(new Date()));
    document
      .querySelectorAll('[data-schedule-id]')
      .forEach((button) =>
        button.addEventListener('click', () =>
          openSchedule(items.find((schedule) => schedule.id === Number(button.dataset.scheduleId))),
        ),
      );
  } catch (error) {
    if (renderVersion === state.renderId && $('#calendar-body')) {
      $('#calendar-body').innerHTML = view('calendar-error', {
        message: esc(error.message),
      });
    }
  }
}

export function openSchedule(schedule) {
  return openScheduleDialog(schedule.id, { onChange: renderCalendar });
}

export async function renderScheduleDetail(id) {
  const version = state.renderId;
  try {
    const data = await api('/schedules/' + id);
    if (version !== state.renderId) return;
    $('#app').innerHTML = view('schedule-detail-page', { details: scheduleDetails(data.schedule) });
  } catch (error) {
    if (version === state.renderId)
      $('#app').innerHTML = view('screen-error', { message: esc(error.message) });
  }
}

export function openScheduleForm() {
  return navigatePath('/schedules/new');
}

export function renderScheduleNew() {
  const day = state.month + '-01';
  $('#app').innerHTML = view('schedule-new-page', {
    employeeName: esc(state.user.name),
    typeOptions: Object.entries(typeNames)
      .map(([k, v]) =>
        view('schedule-type-option', {
          value: k,
          label: v,
        }),
      )
      .join(''),
    startDay: day,
    endDay: day,
  });
  $('#schedule-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (state.submitting) return;
    state.submitting = true;
    try {
      await post('/schedules', {
        title: $('#schedule-title').value,
        type: $('#schedule-type').value,
        start_at: $('#schedule-start').value,
        end_at: $('#schedule-end').value,
        priority: $('#schedule-priority').value,
        workload: $('#schedule-workload').value,
        memo: $('#schedule-memo').value,
      });
      state.month = $('#schedule-start').value.slice(0, 7);
      await navigate('calendar', 'my');
      toast('내 일정을 DB에 저장했습니다.');
    } catch (error) {
      $('#schedule-error').textContent = error.message;
    } finally {
      state.submitting = false;
    }
  });
}
