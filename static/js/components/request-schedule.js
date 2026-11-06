import { esc } from '../shared/dom.js';
import { dateTime } from '../shared/presentation.js';
import { typeNames } from '../shared/constants.js';
import { scheduleBadges } from '../shared/schedule-details.js';
import { timelineEntries } from '../shared/schedule-timeline.js';
import { view } from '../shared/templates.js';

function shortDate(value) {
  const [year,month,day] = value.slice(0,10).split('-').map(Number);
  return `${month}/${day} (${'일월화수목금토'[new Date(Date.UTC(year,month-1,day)).getUTCDay()]})`;
}

export function requestSchedule(timeline,request) {
  const entries = timelineEntries(timeline);
  const today = timeline.start_at.slice(0,10);
  const cards = entries.map(schedule => {
    const badges = scheduleBadges(schedule);
    const startsBefore = schedule.start_at.slice(0,10)<today;
    const startLabel = shortDate(schedule.start_at);
    const endLabel = shortDate(schedule.end_at);
    return `<li class="request-schedule-item">
      <div class="schedule-period-label"><b>${esc(startLabel)}</b>${schedule.start_at.slice(0,10)!==schedule.end_at.slice(0,10) ? `<span>~ ${esc(endLabel)}</span>` : ''}${startsBefore ? '<small>이전부터 이어지는 일정</small>' : ''}</div>
      <div class="request-schedule-card">
        <div class="request-schedule-top"><span class="schedule-type schedule-type-${esc(schedule.type.toLowerCase())}">${esc(typeNames[schedule.type] || schedule.type)}</span>${badges.status}</div>
        <h4>${esc(schedule.title)}</h4>
        <p class="schedule-period-text">${esc(dateTime(schedule.start_at))} ~ ${esc(dateTime(schedule.end_at))}</p>
        <div class="request-schedule-meta"><span>우선순위 ${badges.priority}</span><span>작업량 ${badges.workload}</span></div>
      </div></li>`;
  }).join('');
  return view('request-analysis', {
    assigneeName:esc(request.assignee_name),
    periodStart:esc(shortDate(timeline.start_at)),periodEnd:esc(dateTime(timeline.end_at)),
    count:entries.length,
    schedules:cards ? `<ol class="request-schedule-list">${cards}</ol>` : '<div class="request-schedule-empty">이 기간에 등록된 일정이 없습니다.</div>',
  });
}
