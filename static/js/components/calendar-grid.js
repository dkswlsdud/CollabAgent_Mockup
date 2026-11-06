import { state } from '../core/state.js';
import { calendarWeeks } from '../shared/calendar-layout.js';
import { view } from '../shared/templates.js';
import { esc } from '../shared/dom.js';

export function calendarGrid(month, schedules, today) {
  const weeks = calendarWeeks(month, schedules).map(week => view('calendar-week', {
    lanes: Math.max(week.lanes, 1),
    days: week.days.map(day => view('calendar-day', {
      column: day.column,
      outsideClass: day.outside ? 'outside' : '',
      sundayClass: day.column === 1 ? 'sunday' : '',
      todayClass: day.date === today ? 'is-today' : '',
      day: Number(day.date.slice(8)),
    })).join(''),
    events: week.segments.map(segment => {
      const schedule = segment.schedule;
      return view('calendar-event', {
        startColumn: segment.startColumn, endColumn: segment.endColumn + 1, row: segment.lane + 2,
        continuationClass: (segment.continuesBefore ? 'continues-before ' : '') + (segment.continuesAfter ? 'continues-after' : ''),
        typeClass: esc(schedule.type.toLowerCase()), unreadClass:schedule.is_new && schedule.employee_id===state.user?.id ? 'schedule-unread' : '', scheduleId: schedule.id,
        tooltip: esc(`${schedule.employee_name} · ${schedule.title}\n${schedule.start_at.replace('T', ' ')} ~ ${schedule.end_at.replace('T', ' ')}`),
        time: segment.continuesBefore ? '계속' : schedule.type === 'PERSONAL' ? '개인' : schedule.start_at.slice(11, 16),
        title: esc(schedule.title), employeeName: esc(schedule.employee_name),
      });
    }).join(''),
  })).join('');
  return view('calendar-grid', {
    weekdays: ['일', '월', '화', '수', '목', '금', '토'].map(label => view('calendar-weekday', { label })).join(''),
    cells: weeks,
    emptyMessage: schedules.length ? '' : view('empty-calendar'),
  });
}
