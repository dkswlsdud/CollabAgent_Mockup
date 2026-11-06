import { view } from './templates.js';
import { statusNames, tagClass } from './constants.js';
import { esc } from './dom.js';

export function heading(kicker, title, sub, button = '') {
  return view('page-heading', {
    kicker: kicker,
    title: title,
    subtitle: sub,
    button: button,
  });
}

export function displayStatus(status, resultStatus) {
  return status === 'PENDING'
    ? 'SUBMITTED'
    : status === 'ACCEPTED'
      ? 'AGREED'
      : status === 'NEGOTIATING' && resultStatus === 'PENDING_CONFIRMATION'
        ? 'AWAITING_CONFIRMATION'
        : status;
}

export function tag(r) {
  return view('status-tag', {
    className: r.needs_recoordination ? 'rejected recoordination-badge' : tagClass[r.status] || 'submitted',
    label: r.needs_recoordination ? '재조정 필요' : r.awaiting_calendar_settings ? '일정 등록 대기' : r.awaiting_related_consent ? '관계자 동의 대기' : r.status === 'AWAITING_CONFIRMATION' ? '양측 최종 확인' : statusNames[r.status] || esc(r.status),
  });
}

export function requestTitle(request) {
  const title = request.task_content || '작성 중인 요청';
  if (!/^\[시연\s*\d+\]/.test(title) && !/^\[시연\s*\d+\]/.test(request.original_text || '')) return title;
  return title.replace(/^\[시연\s*\d+\]\s*/, '').replace(/\s*·\s*(응답 대기|수락 완료|대안 선택|.+ 동의 대기|.+ 거부 후 재조정|.+ 일정 변경 동의)$/, '');
}


export function dateTime(value) {
  return value ? value.replace('T', ' ').slice(0, 16) : '미정';
}
