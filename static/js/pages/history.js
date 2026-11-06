import { state } from '../core/state.js';
import { $, esc } from '../shared/dom.js';
import { view } from '../shared/templates.js';
import { dateTime, heading, tag, requestTitle } from '../shared/presentation.js';

export function renderHistory() {
  const rows = state.requests.filter((collaborationRequest) =>
    ['AGREED', 'REJECTED', 'CANCELLED'].includes(collaborationRequest.status),
  );
  $('#app').innerHTML = view('history-page', {
    heading: heading(
      'AGREEMENT ARCHIVE',
      '함께 정한 결과를 남겨요',
      '합의와 거절 내역을 확인하고 요청 상세에서 회차별 기록을 살펴보세요.',
    ),
    count: rows.length,
    cards:
      rows
        .map((collaborationRequest) =>
          view('history-card', {
            requestId: collaborationRequest.id,
            keyboardRequestId: collaborationRequest.id,
            statusTag: tag(collaborationRequest),
            updatedAt: dateTime(collaborationRequest.updated_at),
            title: esc(requestTitle(collaborationRequest)),
            requesterName: esc(collaborationRequest.requester_name),
            assigneeName: esc(collaborationRequest.assignee_name),
          }),
        )
        .join('') || view('empty-history'),
  });
}
