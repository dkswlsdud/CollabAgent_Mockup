import { syncNav } from '../core/router.js';
import { $ } from '../shared/dom.js';
import { state } from '../core/state.js';
import { api, post } from '../core/api.js';
import { scheduleDetails } from '../shared/schedule-details.js';
import { esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { toast } from '../shared/notifications.js';

let initialized = false;
let requestId = 0;

export function closeScheduleDialog() {
  const dialog = $('#schedule-dialog');
  requestId++;
  if (dialog?.open) dialog.close();
}

export async function openScheduleDialog(id, { onChange } = {}) {
  const dialog = $('#schedule-dialog');
  const body = $('#schedule-dialog-body');
  if (!initialized) {
    $('#schedule-dialog-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      if (dialog.open) return;
      requestId++;
      body.textContent = '';
      document.body.classList.remove('schedule-dialog-open');
    });
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
    initialized = true;
  }
  const currentRequest = ++requestId;
  const currentRender = state.renderId;
  let busy = false;
  const isCurrent = () => currentRequest === requestId && dialog.open;
  async function change(options, message) {
    if (busy) return;
    busy = true;
    const buttons = ['#schedule-delete','#schedule-edit','#schedule-edit-save','#schedule-edit-cancel'];
    for (const selector of buttons) { const button = $(selector); if (button) button.disabled = true; }
    try {
      await api('/schedules/' + id, options);
      if (currentRender === state.renderId && state.user && (!dialog.open || isCurrent())) {
        closeScheduleDialog();
        await onChange?.();
      }
      toast(message);
    } catch (error) {
      if (isCurrent()) $('#schedule-action-error').textContent = error.message;
    } finally {
      busy = false;
      if (isCurrent()) for (const selector of buttons) { const button = $(selector); if (button) button.disabled = false; }
    }
  }
  function showDetails(schedule) {
    body.innerHTML = scheduleDetails(schedule);
    if (schedule.employee_id !== state.user?.id) return;
    body.innerHTML += view('schedule-owner-actions');
    $('#schedule-edit').addEventListener('click', () => showEditor(schedule));
    $('#schedule-delete').addEventListener('click', () => {
      if (window.confirm(`'${schedule.title}' 일정을 삭제할까요?`)) return change({method:'DELETE',body:'{}'},'일정을 삭제했습니다.');
    });
  }
  function showEditor(schedule) {
    body.innerHTML = view('schedule-edit-form', {
      title: esc(schedule.title), start: esc(schedule.start_at.replace(' ','T').slice(0,16)),
      end: esc(schedule.end_at.replace(' ','T').slice(0,16)), memo: esc(schedule.memo || ''),
    });
    for (const key of ['type','status','priority','workload']) $('#edit-schedule-' + key).value = schedule[key] || 'MEDIUM';
    $('#schedule-edit-cancel').addEventListener('click', () => showDetails(schedule));
    $('#schedule-editor').addEventListener('submit', event => {
      event.preventDefault();
      const data = {};
      for (const key of ['title','type','status','priority','workload','memo']) data[key] = $('#edit-schedule-' + key).value;
      data.start_at = $('#edit-schedule-start').value;
      data.end_at = $('#edit-schedule-end').value;
      return change({method:'PUT',body:JSON.stringify(data)},'일정을 수정했습니다.');
    });
  }
  body.textContent = '일정 정보를 불러오고 있습니다…';
  if (!dialog.open) dialog.showModal();
  document.body.classList.add('schedule-dialog-open');
  try {
    const data = await api('/schedules/' + id);
    if (currentRequest !== requestId || currentRender !== state.renderId || !dialog.open) return;
    showDetails(data.schedule);
    if (data.schedule.is_new && data.schedule.employee_id===state.user?.id) {
      const ownerId=state.user.id;
      const notice=await post('/schedules/notifications/read',{schedule_ids:[id]}).catch(()=>null);
      if (notice && state.user?.id===ownerId) {
        state.newScheduleCount=notice.count;
        syncNav();
        document.querySelectorAll(`[data-schedule-id="${id}"]`).forEach(button=>button.classList.remove('schedule-unread'));
      }
    }
  } catch (error) {
    if (currentRequest === requestId && dialog.open) body.textContent = error.message;
  }
}
