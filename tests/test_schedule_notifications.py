"""New calendar state is persisted per schedule and acknowledged only by its owner."""
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.repositories import schedule_repository as repository
from app.services import schedule_service as service
from app.shared.errors import AppError


class ScheduleNotificationTests(unittest.TestCase):
    def test_count_is_scoped_to_current_employee(self):
        with patch.object(service, 'transaction'), patch.object(repository, 'schedule_notification_count', return_value={'count': 2}) as query:
            self.assertEqual(service.schedule_notifications({'id': 4}), {'count': 2})
            self.assertEqual(query.call_args.args[-1], 4)

    def test_acknowledgement_uses_owner_and_displayed_ids(self):
        cur = MagicMock()
        repository.read_schedule_notifications(cur, 4, [7, 9])
        sql, values = cur.execute.call_args.args
        self.assertIn('employee_id=%s', sql)
        self.assertEqual(values, [4, 7, 9])

    def test_empty_acknowledgement_does_not_update_all_schedules(self):
        cur = MagicMock()
        repository.read_schedule_notifications(cur, 4, [])
        cur.execute.assert_not_called()

    def test_invalid_acknowledgements_are_rejected(self):
        for ids in [None, 'all', [True], [-1], ['3']]:
            with self.assertRaises(AppError): service.read_schedule_notifications({'schedule_ids': ids}, {'id': 4})

    def test_new_automatic_schedule_sets_unread_flag(self):
        cur = MagicMock()
        repository.insert_result_schedule(cur, (4, 1, 2, 'work', 'title', '2026-12-01T09:00', '2026-12-01T10:00','HIGH','LOW'))
        self.assertIn('is_new', cur.execute.call_args.args[0])
        self.assertIn('TRUE', cur.execute.call_args.args[0])

    def test_overview_does_not_block_available_work_time(self):
        cur = MagicMock()
        repository.list_workload_schedules(cur, (1, '2026-12-01', '2026-12-02'))
        self.assertIn("NOT LIKE 'overview:%%'", cur.execute.call_args.args[0])
