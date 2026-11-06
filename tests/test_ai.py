"""Live AI paths are tested with mocked HTTP responses, never real employee data."""
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services import ai_service
from app.shared.errors import AppError


class AiTests(unittest.TestCase):
    def response(self,value):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(dict(status='completed',output=[dict(content=[dict(type='output_text',text=json.dumps(value))])])).encode()
        return response

    def test_live_extraction_uses_configured_model_and_strict_schema(self):
        value=dict(task_content='질문지 검토',due_at='2026-11-10T12:00',assignee_id=2,conditions_json=[],questions=[])
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'configured-model'}),patch.object(ai_service,'urlopen',return_value=self.response(value)) as transport:
            self.assertEqual(ai_service.extract_request({'original_text':'질문지 검토'}),value)
            request=transport.call_args.args[0]
            body=json.loads(request.data)
            self.assertEqual(body['model'],'configured-model')
            self.assertFalse(body['store'])
            self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(body['text']['format']['name'],'collaboration_request')
            self.assertNotIn('test-key',body['input'])
            self.assertEqual(transport.call_args.kwargs['timeout'],20)

    def test_composition_really_calls_ai(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'configured-model'}),patch.object(ai_service,'urlopen',return_value=self.response({'request_message':'김민지 님, 질문지 검토를 부탁드립니다.'})) as transport:
            self.assertIn('부탁드립니다',ai_service.compose_request({'task_content':'질문지 검토'}))
            self.assertEqual(json.loads(transport.call_args.args[0].data)['text']['format']['name'],'polite_collaboration_message')

    def test_missing_configuration_never_returns_mock_data(self):
        with patch.dict('os.environ',{},clear=True),patch.object(ai_service,'urlopen') as transport:
            with self.assertRaises(AppError) as error:ai_service.extract_request({})
            self.assertEqual(error.exception.status,503)
            transport.assert_not_called()

    def test_timeout_is_an_explicit_error(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'configured-model'}),patch.object(ai_service,'urlopen',side_effect=TimeoutError):
            with self.assertRaises(AppError) as error:ai_service.compose_request({})
            self.assertEqual(error.exception.status,504)

    def test_invalid_ai_extraction_is_rejected(self):
        with patch.object(ai_service,'request_json',return_value={'conditions_json':[],'questions':[]}):
            with self.assertRaises(AppError):ai_service.extract_request({})

