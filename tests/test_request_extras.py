import io
from copy import deepcopy
import sys
from pathlib import Path
import unittest
from unittest.mock import patch,MagicMock
from werkzeug.datastructures import FileStorage
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import create_app
from app.services import attachment_service
from app.repositories import attachment_repository,negotiation_repository,notice_repository
from app.shared.errors import AppError
from app.shared.notices import request_version,checked_version


class RequestExtrasTests(unittest.TestCase):
    def test_safe_upload_keeps_korean_filename_and_bytes(self):
        values=attachment_service.prepare_uploads([FileStorage(stream=io.BytesIO(b'%PDF-test'),filename='질문지.pdf')])
        self.assertEqual(values[0][0],'질문지.pdf')
        self.assertEqual(values[0][2],b'%PDF-test')

    def test_unsupported_empty_and_excess_files_are_rejected(self):
        for files in [[FileStorage(stream=io.BytesIO(b'x'),filename='run.exe')],
                      [FileStorage(stream=io.BytesIO(),filename='empty.pdf')],
                      [FileStorage(stream=io.BytesIO(b'x'),filename='a.txt') for _ in range(6)]]:
            with self.assertRaises(AppError):attachment_service.prepare_uploads(files)

    def test_download_denies_unrelated_employee(self):
        with patch.object(attachment_service,'transaction'),patch.object(attachment_repository,'find',return_value=dict(request_id=1,requester_id=1,assignee_id=2)),patch.object(attachment_repository,'authorized_rounds',return_value=[]):
            with self.assertRaises(AppError) as error:attachment_service.download(1,{'id':3})
            self.assertEqual(error.exception.status,403)

    def test_multipart_request_is_allowed_and_passes_files_to_service(self):
        app=create_app()
        client=app.test_client()
        client.set_cookie('collab_session','test')
        with patch('app.services.auth_service.session_user',return_value={'id':1}),patch('app.services.request_service.create_request',return_value={'id':10}) as create:
            response=client.post('/api/requests',data={'payload':'{"task_content":"직접 작성"}','attachments':(io.BytesIO(b'%PDF-test'),'질문지.pdf')})
            self.assertEqual(response.status_code,201)
            self.assertEqual(create.call_args.args[0]['task_content'],'직접 작성')
            self.assertEqual(create.call_args.args[2][0].filename,'질문지.pdf')

    def test_notice_changes_on_new_round_or_consent_response(self):
        row={'id':1,'status':'NEGOTIATING'}
        before=request_version(row,[{'id':1,'consents_json':[]}],None)
        after=request_version(row,[{'id':1,'consents_json':[{'status':'APPROVED'}]}],None)
        self.assertNotEqual(before,after)
        self.assertEqual(checked_version({'version':after}),after)
        with self.assertRaises(AppError):checked_version({'version':'invalid'})

    def test_notice_acknowledgement_is_per_account_and_kind(self):
        cur=MagicMock()
        notice_repository.acknowledge(cur,4,10,'CONSENT','a'*64)
        self.assertEqual(cur.execute.call_args.args[1],(4,10,'CONSENT','a'*64))

    def test_draft_selection_does_not_create_new_notice_but_completion_does(self):
        row={'id':1,'status':'NEGOTIATING'}
        for side,other in [('a','b'),('b','a')]:
            with self.subTest(side=side):
                history=[{'id':1,'alternatives_json':[{'id':1},{'id':2}]}]
                original=deepcopy(history)
                before=request_version(row,history,None)
                self.assertEqual(history,original)
                alternatives=history[0]['alternatives_json']
                alternatives[0][f'{side}_selected']=True
                for alt in alternatives:
                    alt[f'{side}_selection_completed']=False
                self.assertEqual(before,request_version(row,history,None))
                alternatives[0][f'{side}_selected']=False
                alternatives[1][f'{side}_selected']=True
                self.assertEqual(before,request_version(row,history,None))
                for alt in alternatives:
                    alt[f'{side}_selection_completed']=True
                completed=request_version(row,history,None)
                self.assertNotEqual(before,completed)
                alternatives[0][f'{other}_selected']=True
                self.assertEqual(completed,request_version(row,history,None))
                for alt in alternatives:
                    alt[f'{other}_selection_completed']=True
                self.assertNotEqual(completed,request_version(row,history,None))


