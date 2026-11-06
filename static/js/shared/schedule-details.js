import { esc } from './dom.js';
import { dateTime } from './presentation.js';
import { typeNames } from './constants.js';
import { view } from './templates.js';

function badge(value, choices) {
  const [label, tone] = choices[value] || ['미지정', 'neutral'];
  return `<span class="schedule-badge schedule-badge--${tone}">${esc(label)}</span>`;
}

export function scheduleBadges(schedule) {
  return {
    priority: badge(schedule.priority, { HIGH: ['높음', 'high'], MEDIUM: ['보통', 'medium'], LOW: ['낮음', 'low'] }),
    workload: badge(schedule.workload, { HIGH: ['많음', 'high'], MEDIUM: ['보통', 'medium'], LOW: ['적음', 'low'] }),
    status: badge(schedule.status, { SCHEDULED: ['예정', 'scheduled'], IN_PROGRESS: ['진행 중', 'progress'], COMPLETED: ['완료', 'completed'], CANCELLED: ['취소', 'neutral'] }),
  };
}

export function scheduleDetails(schedule) {
  return view('schedule-detail-content', {
    type: esc(typeNames[schedule.type] || schedule.type),
    title: esc(schedule.title),
    employeeName: esc(schedule.employee_name),
    department: esc(schedule.department),
    startAt: esc(dateTime(schedule.start_at)),
    endAt: esc(dateTime(schedule.end_at)),
    ...scheduleBadges(schedule),
    requesterName: esc(schedule.requester_name || '직접 등록'),
    memo: esc(schedule.memo || '없음'),
  });
}
