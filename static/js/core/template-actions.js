import { openMyCalendarDialog } from '../components/my-calendar-dialog.js';
// Compatibility boundary for inline actions in HTML templates.
import { act } from '../pages/request-detail.js';
import { cancelRequest, resubmitRequest } from '../pages/request-detail.js';
import { answerConsent, loadConsentDetail, configureConsentCalendar } from '../pages/inbox.js';
import { fillDemo } from '../pages/auth.js';
import { navigate } from '../core/router.js';
import { openDetail } from '../pages/request-detail.js';
import { openNew } from '../pages/requests.js';
import { openRenegotiate } from '../pages/request-detail.js';
import { openScheduleForm } from '../pages/calendar.js';
import { refreshData } from '../core/router.js';
import { renderCalendar } from '../pages/calendar.js';
import { respond, toggleAlternative, restartAfterRejection, toggleAllUnavailable, completeSelection } from '../pages/request-detail.js';
import { setFilter } from '../pages/inbox.js';
import { setMonth } from '../pages/calendar.js';
import { shiftMonth } from '../pages/calendar.js';
import { submitFeedback } from '../pages/request-detail.js';
import { todayMonth } from '../pages/calendar.js';

Object.assign(window, { openMyCalendarDialog, act, cancelRequest, resubmitRequest, answerConsent, loadConsentDetail, configureConsentCalendar, fillDemo, navigate, openDetail, openNew, openRenegotiate, openScheduleForm, refreshData, renderCalendar, respond, toggleAlternative, restartAfterRejection, toggleAllUnavailable, completeSelection, setFilter, setMonth, shiftMonth, submitFeedback, todayMonth });
