"""Final request wording comes from AI while the user's original remains intact."""
from pathlib import Path
from datetime import datetime
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import request_service as service
from app.shared.errors import AppError


class RequestMessageTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(service,'transaction'))
        stack.enter_context(patch.object(service,'now',return_value=datetime(2026,11,2)))
        stack.enter_context(patch('app.repositories.employee_repository.list_active_employees',return_value=[dict(id=2,name='이서준',department='디자인팀')]))
        stack.enter_context(patch('app.repositories.employee_repository.find_active_employee',return_value={'id':2}))
        self.insert=stack.enter_context(patch('app.repositories.request_repository.insert_request',return_value=123))
        self.save=stack.enter_context(patch('app.repositories.request_repository.save_request_message'))
        self.compose=stack.enter_context(patch.object(service,'compose_request',return_value='이서준 님, 배너 제작을 부탁드립니다.'))
        self.data=dict(original_text='서준이한테 배너 만들어 달라고 해줘',task_content='배너 제작',assignee_id=2,assignee_department='디자인팀',due_at='2026-11-06T18:00',conditions_json=[dict(key='deadline',label='마감',constraint='HARD')])

    def test_original_and_polite_message_are_saved_separately(self):
        self.assertEqual(service.create_request(self.data,{'id':1,'name':'김민지','department':'마케팅팀'}),{'id':123})
        self.assertEqual(self.insert.call_args.args[1][2],self.data['original_text'])
        self.assertEqual(self.save.call_args.args[1],('이서준 님, 배너 제작을 부탁드립니다.',123))
        self.assertEqual(self.compose.call_args.args[0]['assignee']['name'],'이서준')

    def test_team_member_mismatch_does_not_call_ai_or_save(self):
        self.data['assignee_department']='콘텐츠팀'
        with self.assertRaises(AppError): service.create_request(self.data,{'id':1})
        self.compose.assert_not_called()
        self.insert.assert_not_called()

    def test_ai_failure_does_not_send_raw_original(self):
        self.compose.side_effect=AppError('AI 연결 실패',502)
        with self.assertRaises(AppError): service.create_request(self.data,{'id':1})
        self.insert.assert_not_called()


if __name__=='__main__': unittest.main()
