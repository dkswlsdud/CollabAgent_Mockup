"""Schedule mutations must be owned, valid and preserve the existing identity."""
from contextlib import ExitStack
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import schedule_service as service
from app.repositories import schedule_repository as repo
from app.shared.errors import AppError


class ScheduleEditTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(service,'transaction'))
        self.stack.enter_context(patch('app.repositories.employee_repository.lock_employee'))
        self.lookup = self.stack.enter_context(patch.object(repo,'lock_schedule',return_value={'id':3,'employee_id':1,'status':'SCHEDULED'}))
        self.update = self.stack.enter_context(patch.object(repo,'update_schedule'))
        self.delete = self.stack.enter_context(patch.object(repo,'delete_schedule'))
        self.data = dict(title='수정된 일정',type='WORK',start_at='2026-11-04T09:00',end_at='2026-11-06T18:00',priority='HIGH',workload='LOW',status='IN_PROGRESS',memo='변경 메모')

    def test_owner_can_update_multiple_day_schedule(self):
        result = service.update_schedule(3,self.data,{'id':1})
        self.assertEqual(result,{'ok':True,'id':3})
        values = self.update.call_args.args[1]
        self.assertEqual(values[0],'수정된 일정')
        self.assertEqual(values[-2:],('IN_PROGRESS',3))
        self.assertEqual(values[2].day,4)
        self.assertEqual(values[3].day,6)

    def test_owner_can_delete(self):
        self.assertEqual(service.delete_schedule(3,{'id':1}),{'ok':True})
        self.assertEqual(self.delete.call_args.args[1],3)

    def test_other_employee_cannot_edit_or_delete(self):
        for operation in [lambda:service.update_schedule(3,self.data,{'id':2}),lambda:service.delete_schedule(3,{'id':2})]:
            with self.assertRaises(AppError) as error: operation()
            self.assertEqual(error.exception.status,403)
        self.update.assert_not_called()
        self.delete.assert_not_called()

    def test_missing_schedule_returns_not_found(self):
        self.lookup.return_value = None
        with self.assertRaises(AppError) as error: service.delete_schedule(999,{'id':1})
        self.assertEqual(error.exception.status,404)

    def test_invalid_period_and_status_do_not_write(self):
        for changes in [{'end_at':self.data['start_at']},{'status':'INVALID'}]:
            with self.assertRaises(AppError): service.update_schedule(3,{**self.data,**changes},{'id':1})
        self.update.assert_not_called()
