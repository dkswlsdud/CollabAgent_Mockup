import { $, esc } from '../shared/dom.js';
import { state } from '../core/state.js';
import { api } from '../core/api.js';
import { view } from '../shared/templates.js';
import { calendarGrid } from './calendar-grid.js';
import { closeScheduleDialog, openScheduleDialog } from './schedule-dialog.js';

let initialized = false;
let version = 0;
let month = '';

function todayKst() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en', {
    timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',
  }).formatToParts(new Date()).map(part => [part.type,part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function closeMyCalendarDialog() {
  version++;
  const dialog = $('#my-calendar-dialog');
  if (dialog?.open) dialog.close();
}

export function openMyCalendarDialog() {
  if (!state.user || state.page !== 'request-detail') return;
  const dialog = $('#my-calendar-dialog');
  if (!initialized) {
    $('#my-calendar-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      if (dialog.open) return;
      version++;
      closeScheduleDialog();
      $('#my-calendar-body').textContent = '';
      document.body.classList.remove('my-calendar-open');
    });
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
    initialized = true;
  }
  month = todayKst().slice(0,7);
  $('#my-calendar-title').textContent = `${state.user.name}님의 내 일정`;
  if (!dialog.open) dialog.showModal();
  document.body.classList.add('my-calendar-open');
  return renderMonth();
}

async function renderMonth() {
  const current = ++version;
  const userId = state.user?.id;
  const dialog = $('#my-calendar-dialog');
  const body = $('#my-calendar-body');
  const isCurrent = () => current === version && dialog.open && state.user?.id === userId;
  body.innerHTML = view('my-calendar-popup', {month:esc(month)});
  function shift(delta) {
    const [year,number] = month.split('-').map(Number);
    month = new Date(Date.UTC(year,number-1+delta,1)).toISOString().slice(0,7);
    return renderMonth();
  }
  $('#my-calendar-prev').addEventListener('click', () => shift(-1));
  $('#my-calendar-next').addEventListener('click', () => shift(1));
  $('#my-calendar-today').addEventListener('click', () => { month=todayKst().slice(0,7); return renderMonth(); });
  $('#my-calendar-month').addEventListener('change', event => {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(event.target.value)) return;
    month=event.target.value;
    return renderMonth();
  });
  try {
    const data = await api('/schedules?'+new URLSearchParams({scope:'my',month}));
    if (!isCurrent()) return;
    const items = data.schedules;
    $('#my-calendar-count').textContent = `${items.length}개 일정`;
    $('#my-calendar-grid').innerHTML = calendarGrid(month,items,todayKst());
    body.querySelectorAll('[data-schedule-id]').forEach(button => button.addEventListener('click', () =>
      openScheduleDialog(Number(button.dataset.scheduleId),{onChange:renderMonth})));
  } catch (error) {
    if (isCurrent()) $('#my-calendar-grid').innerHTML = `<p class="form-error">${esc(error.message)}</p>`;
  }
}
