"""Exercise business services together through a complete multi-user agreement."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import json
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import negotiation_service as actions, consent_service, request_service, schedule_service, planning_service
from app.repositories import negotiation_repository as nr, request_repository as rr, result_repository as result_repo, response_repository as response_repo, employee_repository as er, schedule_repository as sr
from app.shared.errors import AppError
from app.shared.conditions import condition_keys
from app.repositories import notice_repository,attachment_repository
from test_planning import TODAY, PEOPLE, request, schedule


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.row = request()
        self.row['status'] = 'PENDING'
        self.rounds, self.result, self.response, self.saved, self.schedules = [], None, None, [], []
        self.stack.enter_context(patch.object(notice_repository,'reads',return_value={}))
        self.stack.enter_context(patch.object(attachment_repository,'metadata',return_value=[]))
        self.serial = 0
        self.overviews = []
        @contextmanager
        def transaction(): yield object()
        for module in [actions, consent_service, request_service]:
            self.stack.enter_context(patch.object(module, 'transaction', transaction))
        for module in [actions, request_service, schedule_service, planning_service]:
            self.stack.enter_context(patch.object(module, 'now', return_value=TODAY))
        self.stack.enter_context(patch.object(planning_service, 'generate_proposals', side_effect=self.ai_proposals))
        def insert_round(cur, p):
            self.serial += 1
            self.rounds.insert(0, dict(id=self.serial, request_id=p[0], round_no=p[1], request_snapshot_json=p[2], analysis_json=p[3], alternatives_json=[], consents_json=[], status='IN_PROGRESS', accepted_condition_key=None, assignee_comment=None, selected_alternative_key=None))
            return self.serial
        def update_round(key, value): self.rounds[0][key] = value
        def pending(cur, p):
            self.result = dict(id=30, request_id=p[0], negotiation_id=p[1], agreed_terms_json=p[2], status='PENDING_CONFIRMATION', a_confirmed_at=None, b_confirmed_at=None)
            return 30
        def direct(cur, p):
            self.result = dict(id=30, request_id=p[0], status=p[1], agreed_terms_json=p[2], reason=p[3], a_confirmed_at=p[4], b_confirmed_at=p[5], finalized_at=p[6])
            return 30
        def clear_result(*_): self.result = None
        def response(cur, p): self.response = dict(request_id=p[0], decision=p[1], reject_reason=p[2])
        def clear_response(*_): self.response = None
        def close(cur, p, column):
            self.rounds[0].update({column:p[0], 'status':'FAILED','closed_at':p[1]})
        def cancel_rounds(*_):
            for n in self.rounds:
                if n['status'] == 'IN_PROGRESS': n['status'] = 'CANCELLED'
        patches = [
            (rr, dict(find_request=lambda *_:deepcopy(self.row), find_request_detail=lambda *_:deepcopy(self.row), lock_request=lambda *_:None,
                      mark_negotiating=lambda *_:self.row.update(status='NEGOTIATING'), mark_accepted=lambda *_:self.row.update(status='ACCEPTED'),
                      update_request_status=lambda cur,p:self.row.update(status=p[0]), resubmit=lambda cur,p:self.row.update(status='PENDING',due_at=p[0],conditions_json=p[1]))),
            (nr, dict(archive_round_snapshot=lambda cur,p:update_round('request_snapshot_json',p[0]),find_consent_round=lambda *_:deepcopy(self.rounds[0]) if self.rounds else None,insert_round=insert_round, lock_latest_round=lambda *_:deepcopy(self.rounds[0]) if self.rounds else None,
                      list_request_rounds=lambda *_:deepcopy(self.rounds), update_response_conditions=lambda cur,p:self.rounds[0].update(accepted_condition_key=(condition_keys(p[0]) or [None])[0],accepted_condition_keys_json=condition_keys(p[0]),assignee_comment=p[1]),
                      update_feedback=lambda cur,p,column:update_round(column,p[0]), close_failed_round=close,
                      update_alternatives=lambda cur,p:update_round('alternatives_json',p[0]), update_consents=lambda cur,p:update_round('consents_json',p[0]),
                      clear_selected_alternative=lambda *_:update_round('selected_alternative_key',None), update_selected_alternative=lambda cur,p:update_round('selected_alternative_key',p[0]),
                      finalize_round=lambda *_:update_round('status','AGREED'), cancel_open_rounds=cancel_rounds,
                      list_open_round_consents=lambda *_:[dict(deepcopy(n),request_title=self.row['task_content'],a_confirmed_at=(self.result or {}).get('a_confirmed_at'),b_confirmed_at=(self.result or {}).get('b_confirmed_at')) for n in self.rounds if n['status']=='IN_PROGRESS'],
                      find_round_request=lambda *_:dict(request_id=10), lock_round_consents=lambda *_:deepcopy(self.rounds[0]))),
            (result_repo, dict(update_agreed_terms=lambda cur,p:self.result.update(agreed_terms_json=p[0]),lock_request_result=lambda *_:deepcopy(self.result), find_result=lambda *_:deepcopy(self.result), insert_pending_result=pending,
                               insert_direct_result=direct, delete_result=clear_result, confirm_result=lambda cur,p,column:self.result.update({column:p[0]}),
                               finalize_result=lambda *_:self.result.update(status='ACCEPTED'))),
            (response_repo, dict(insert_response=response, delete_response=clear_response, find_response=lambda *_:deepcopy(self.response))),
            (er, dict(list_active_employees=lambda *_:PEOPLE, lock_employee=lambda *_:None)),
            (sr, dict(list_workload_schedules=lambda cur,p:[s for s in self.schedules if s['employee_id']==p[0]],list_period_schedules=lambda cur,p:[s for s in self.schedules if s['employee_id']==p[0]], find_schedule=lambda cur,p:next((s for s in self.schedules if s['id']==p[0]),None),
                      delete_result_schedules=lambda cur,result_id:(self.saved.clear(),self.overviews.clear()),
                      lock_schedule=lambda cur,key:next((s for s in self.schedules if s['id']==key),None),
                      reschedule=lambda cur,c:next(s for s in self.schedules if s['id']==c['schedule_id']).update(start_at=c['start_at'],end_at=c['end_at']),
                      insert_result_schedule=lambda cur,p:self.saved.append(p), insert_result_overview=lambda cur,p:self.overviews.append(p))),
        ]
        for module, values in patches: self.stack.enter_context(patch.multiple(module, **values))

    def ai_proposals(self, payload):
        # Fixed provider responses exercise consent/finalization without external API calls.
        from test_planning import ai_proposal
        proposal = ai_proposal()
        if self.row['conditions_json'][1]['value'] == 45:
            proposal['items'] = [dict(assignee_id=2, quantity=1, start_at=f'2026-11-{day:02}T{hour:02}:00:00',
                end_at=f'2026-11-{day:02}T{hour+1:02}:00:00', due_at=self.row['due_at']) for day in range(2,7) for hour in range(9,18)]
            proposal['schedule_changes'] = [dict(schedule_id=1,start_at='2026-11-09T09:00:00',end_at='2026-11-09T10:00:00')]
        else:
            proposal['items'] = [dict(assignee_id=2 if index<3 else 3, quantity=1,
                start_at=f'2026-11-02T{9+index:02}:00:00', end_at=f'2026-11-02T{10+index:02}:00:00',
                due_at=self.row['due_at']) for index in range(5)]
        alternatives = [deepcopy(proposal) for _ in range(3)]
        for index, alternative in enumerate(alternatives):
            if alternative['schedule_changes']:
                for change in alternative['schedule_changes']:
                    change['start_at'] = f'2026-11-{9+index:02}T09:00:00'
                    change['end_at'] = f'2026-11-{9+index:02}T10:00:00'
            else:
                for item in alternative['items']:
                    item['start_at'] = item['start_at'].replace('2026-11-02', f'2026-11-{2+index:02}')
                    item['end_at'] = item['end_at'].replace('2026-11-02', f'2026-11-{2+index:02}')
        return dict(alternatives=alternatives,reason='')

    def action(self, person, action, **data):
        if action=='confirm' or (action=='respond' and data.get('decision')=='ACCEPT'):
            data.setdefault('schedule_priority','MEDIUM')
            data.setdefault('schedule_workload','MEDIUM')
        return actions.request_action(10, dict(action=action, **data), {'id':person})

    def configure_all(self,consent_id):
        self.action(2,'calendar_settings',schedule_priority='LOW',schedule_workload='HIGH')
        return consent_service.consent_calendar_settings(consent_id,dict(schedule_priority='HIGH',schedule_workload='MEDIUM'),{'id':3})

    def test_all_unavailable_ends_negotiation_without_registering_schedules(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='일정 조율 필요')
        self.action(1,'generate')
        with self.assertRaises(AppError):
            self.action(1,'reject_all')
        self.action(2,'reject_all')
        self.assertEqual(self.row['status'],'REJECTED')
        self.assertEqual(self.rounds[0]['status'],'FAILED')
        self.assertEqual(self.result['status'],'REJECTED')
        self.assertIn('재조정 의견을 남기지 않아',self.result['reason'])
        self.assertFalse(self.saved)
        with self.assertRaises(AppError):
            self.action(2,'reject_all')

    def test_all_unavailable_feedback_starts_new_round_instead_of_ending(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='일정 조율 필요')
        self.action(1,'generate')
        self.action(2,'renegotiate',feedback='분담 없이 다시 진행해주세요.')
        self.assertEqual(self.row['status'],'NEGOTIATING')
        self.assertEqual(self.rounds[0]['assignee_feedback'],'분담 없이 다시 진행해주세요.')
        self.assertEqual(self.rounds[0]['round_no'],2)
        self.action(2,'generate')
        self.assertEqual(len(json.loads(self.rounds[0]['alternatives_json'])),3)

    def prepare_shared(self, confirm=True):
        self.action(2, 'respond', decision='CONDITIONAL_ACCEPT', accepted_condition_key='deadline', comment='3개 가능')
        self.action(1, 'generate')
        detail = request_service.request_detail(10, {'id':1})
        shared = next(a for a in detail['alternatives'] if any(i['assignee_id']==3 for i in a['plan_json']['items']))
        key = shared['id']
        self.action(1, 'select', alternative_id=key, selected=True)
        self.action(2, 'select', alternative_id=key, selected=True)
        self.action(1, 'complete_selection')
        self.action(2, 'complete_selection')
        self.action(1, 'choose', alternative_id=key)
        if confirm:
            self.action(1, 'confirm', alternative_id=key)
            self.action(2, 'confirm', alternative_id=key)
        return key

    def test_consents_are_sent_only_after_both_final_confirmations(self):
        key = self.prepare_shared(confirm=False)
        self.assertFalse(consent_service.my_consents({'id':3})['consents'])
        selected = next(c for c in json.loads(self.rounds[0]['consents_json']) if c['alternative_id'] == key)
        consent_id = f"{self.rounds[0]['id']}_{selected['id']}"
        with self.assertRaises(AppError): consent_service.answer_consent(consent_id, {'status':'APPROVED','schedule_priority':'LOW','schedule_workload':'LOW'}, {'id':3})
        self.action(1,'confirm',alternative_id=key)
        self.assertFalse(consent_service.my_consents({'id':3})['consents'])
        self.action(2,'confirm',alternative_id=key)
        consents = consent_service.my_consents({'id':3})['consents']
        self.assertEqual(len(consents),1)
        self.assertEqual(consents[0]['request_title'],self.row['task_content'])
        self.assertEqual(consents[0]['alternative_id'],key)
        self.assertEqual(consents[0]['status'],'PENDING')
        self.assertTrue(consents[0]['requested_at'])
        consent_service.answer_consent(consent_id, {'status':'APPROVED'}, {'id':3})
        self.configure_all(consent_id)
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertFalse(consent_service.my_consents({'id':3})['consents'])
        with self.assertRaises(AppError): self.action(2,'confirm',alternative_id=key)

    def test_no_third_party_required_completes_on_second_confirmation(self):
        from test_planning import ai_proposal
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='일정 조정')
        proposals = [ai_proposal(start=f'2026-11-{day:02}T09:00:00') for day in [2,3,4]]
        with patch.object(planning_service,'generate_proposals',return_value=dict(alternatives=proposals,reason='')):
            self.action(1,'generate')
        for person in [1,2]:
            self.action(person,'select',alternative_id=1,selected=True)
            self.action(person,'complete_selection')
        self.action(1,'choose',alternative_id=1)
        self.action(1,'confirm',alternative_id=1)
        self.assertEqual(self.row['status'],'NEGOTIATING')
        self.assertFalse(self.saved)
        self.action(2,'confirm',alternative_id=1)
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertEqual({p[0] for p in self.saved+self.overviews},{2})

    def test_requester_never_needs_calendar_settings_after_related_approval(self):
        self.prepare_shared()
        consent=consent_service.my_consents({'id':3})['consents'][0]
        consent_service.answer_consent(consent['id'],dict(status='APPROVED',schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})
        self.assertFalse(request_service.request_detail(10,{'id':1})['needs_calendar_settings'])
        with self.assertRaises(AppError):self.action(1,'calendar_settings',schedule_priority='HIGH',schedule_workload='LOW')
        self.action(2,'calendar_settings',schedule_priority='MEDIUM',schedule_workload='MEDIUM')
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertNotIn(1,{p[0] for p in self.saved+self.overviews})

    def test_fixed_third_alternative_delivers_real_consent_after_confirmation(self):
        from app.services.mock_planning_service import generate_proposals
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='대안3 관계자 동의 시연')
        with patch.object(planning_service,'generate_proposals',side_effect=generate_proposals),patch('app.services.ai_service.urlopen',side_effect=AssertionError('No AI for alternatives')):
            self.action(1,'generate')
        self.assertFalse(consent_service.my_consents({'id':3})['consents'])
        for actor in [1,2]:
            self.action(actor,'select',alternative_id=3,selected=True)
            self.action(actor,'complete_selection')
        self.action(1,'choose',alternative_id=3)
        self.action(1,'confirm',alternative_id=3)
        self.assertFalse(consent_service.my_consents({'id':3})['consents'])
        self.action(2,'confirm',alternative_id=3)
        consents=consent_service.my_consents({'id':3})['consents']
        self.assertEqual(len(consents),1)
        self.assertEqual(consents[0]['alternative_id'],3)
        self.assertEqual(consents[0]['status'],'PENDING')
        consent_service.answer_consent(consents[0]['id'],{'status':'APPROVED'},{'id':3})
        self.configure_all(consents[0]['id'])
        self.assertEqual(self.row['status'],'ACCEPTED')

    def test_mock_final_confirmation_ignores_busy_time_and_expired_hard_deadline(self):
        from app.services.mock_planning_service import generate_proposals
        self.row['due_at']='2026-11-01T18:00:00'
        self.schedules=[schedule(start='2026-11-02T09:00',end='2026-11-20T18:00')]
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='목업 진행')
        with patch.object(planning_service,'generate_proposals',side_effect=generate_proposals):
            self.action(1,'generate')
        for actor in [1,2]:
            self.action(actor,'select',alternative_id=1,selected=True)
            self.action(actor,'complete_selection')
        self.action(1,'choose',alternative_id=1)
        self.action(1,'confirm',alternative_id=1)
        self.action(2,'confirm',alternative_id=1)
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertTrue(self.saved)

    def test_related_person_can_register_mock_schedule_despite_conflicting_work(self):
        self.prepare_shared()
        consent=consent_service.my_consents({'id':3})['consents'][0]
        self.schedules=[schedule(person=3,start='2026-11-02T09:00',end='2026-11-20T18:00')]
        result=consent_service.answer_consent(consent['id'],dict(status='APPROVED',schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})
        self.assertTrue(result['schedule_registered'])
        self.assertTrue(self.saved)
        self.assertEqual({item[0] for item in self.saved},{3})

    def test_related_person_registers_without_waiting_for_other_consent_and_is_not_duplicated(self):
        self.prepare_shared()
        consents=json.loads(self.rounds[0]['consents_json'])
        selected=next(c for c in consents if c['alternative_id']==1)
        consents.append(dict(selected,id=99,employee_id=4,employee_name='추가 관계자'))
        self.rounds[0]['consents_json']=json.dumps(consents)
        nid=self.rounds[0]['id']
        reply=consent_service.answer_consent(f"{nid}_{selected['id']}",dict(status='APPROVED',schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})
        self.assertFalse(reply['completed'])
        self.assertTrue(reply['schedule_registered'])
        self.assertEqual({p[0] for p in self.saved},{3})
        self.assertFalse(self.overviews)
        self.assertEqual(next(c for c in json.loads(self.rounds[0]['consents_json']) if c['id']==99)['status'],'PENDING')
        detail=consent_service.consent_detail(f"{nid}_{selected['id']}",{'id':3})
        self.assertFalse(detail['needs_calendar_settings'])
        self.assertTrue(detail['calendar_registered'])
        early_count=len(self.saved)
        consent_service.consent_calendar_settings(f"{nid}_{selected['id']}",dict(schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})
        self.assertEqual(len(self.saved),early_count)
        # Actual workload queries include the rows created by the first approval.
        for index,p in enumerate(self.saved):
            self.schedules.append(dict(id=800+index,employee_id=p[0],result_id=30,type='WORK',status='SCHEDULED',priority='HIGH',workload='LOW',title='이미 등록한 협업',start_at=p[5],end_at=p[6]))
        consent_service.answer_consent(f'{nid}_99',dict(status='APPROVED',schedule_priority='LOW',schedule_workload='MEDIUM'),{'id':4})
        self.action(2,'calendar_settings',schedule_priority='LOW',schedule_workload='HIGH')
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertEqual(len([p for p in self.saved if p[0]==3]),early_count)
        self.assertEqual({p[0] for p in self.saved+self.overviews},{2,3,4})

    def test_other_consent_refusal_cleans_up_early_registered_schedules(self):
        self.prepare_shared()
        consents=json.loads(self.rounds[0]['consents_json'])
        selected=next(c for c in consents if c['alternative_id']==1)
        consents.append(dict(selected,id=99,employee_id=4,employee_name='추가 관계자'))
        self.rounds[0]['consents_json']=json.dumps(consents)
        nid=self.rounds[0]['id']
        consent_service.answer_consent(f"{nid}_{selected['id']}",dict(status='APPROVED',schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})
        self.assertTrue(self.saved)
        consent_service.answer_consent(f'{nid}_99',dict(status='REJECTED',reason='분담이 어렵습니다.'),{'id':4})
        self.assertFalse(self.saved)
        self.assertFalse(json.loads(self.result['agreed_terms_json'])['calendar_registered_employee_ids'])
        with self.assertRaises(AppError):
            consent_service.consent_calendar_settings(f"{nid}_{selected['id']}",dict(schedule_priority='HIGH',schedule_workload='LOW'),{'id':3})



    def test_partial_or_rejected_consent_does_not_complete_collaboration(self):
        self.prepare_shared()
        consents = json.loads(self.rounds[0]['consents_json'])
        selected = next(c for c in consents if c['alternative_id']==1)
        extra = dict(selected,id=99,employee_id=4,employee_name='추가 관계자')
        consents.append(extra)
        self.rounds[0]['consents_json'] = json.dumps(consents)
        nid = self.rounds[0]['id']
        reply = consent_service.answer_consent(f"{nid}_{selected['id']}",{'status':'APPROVED','schedule_priority':'LOW','schedule_workload':'LOW'},{'id':3})
        self.assertFalse(reply['completed'])
        self.assertEqual(self.row['status'],'NEGOTIATING')
        reply = consent_service.answer_consent(f'{nid}_99',{'status':'REJECTED','reason':'업무량이 많아 분담이 어렵습니다.'},{'id':4})
        self.assertFalse(reply['completed'])
        self.assertEqual(self.row['status'],'NEGOTIATING')
        self.assertFalse(self.saved)
        self.assertFalse(self.overviews)

    def test_related_party_can_read_confirmed_collaboration_details(self):
        key = self.prepare_shared()
        consent = next(c for c in consent_service.my_consents({'id':3})['consents'] if c['alternative_id']==key)
        detail = consent_service.consent_detail(consent['id'],{'id':3})
        self.assertEqual(detail['request']['id'],10)
        self.assertEqual(detail['alternative']['id'],key)
        self.assertTrue(detail['confirmation']['a_confirmed_at'])
        self.assertTrue(detail['confirmation']['b_confirmed_at'])
        self.assertEqual(detail['consent']['employee_id'],3)
        self.assertNotIn('rounds',detail)
        for outsider in [1,2,999]:
            with self.assertRaises(AppError) as error: consent_service.consent_detail(consent['id'],{'id':outsider})
            self.assertEqual(error.exception.status,403)

    def test_unissued_unselected_and_revoked_consent_details_are_blocked(self):
        key = self.prepare_shared(confirm=False)
        current = next(c for c in json.loads(self.rounds[0]['consents_json']) if c['alternative_id']==key)
        consent_id = f"{self.rounds[0]['id']}_{current['id']}"
        with self.assertRaises(AppError) as error: consent_service.consent_detail(consent_id,{'id':3})
        self.assertEqual(error.exception.status,409)
        self.action(1,'confirm',alternative_id=key)
        self.action(2,'confirm',alternative_id=key)
        other = next(c for c in json.loads(self.rounds[0]['consents_json']) if c['alternative_id']!=key)
        with self.assertRaises(AppError): consent_service.consent_detail(f"{self.rounds[0]['id']}_{other['id']}",{'id':3})
        self.action(1,'renegotiate',feedback='다른 일정으로 다시 조율해주세요.')
        with self.assertRaises(AppError): consent_service.consent_detail(consent_id,{'id':3})

    def test_invalid_or_missing_consent_detail_is_rejected(self):
        with self.assertRaises(AppError) as error: consent_service.consent_detail('invalid',{'id':3})
        self.assertEqual(error.exception.status,400)
        with self.assertRaises(AppError) as error: consent_service.consent_detail('999_1',{'id':3})
        self.assertEqual(error.exception.status,404)

    def test_related_party_refusal_requires_reason_and_notifies_both_participants(self):
        self.prepare_shared()
        consent = consent_service.my_consents({'id':3})['consents'][0]
        for reason in ['', '   ', None, 'x'*2001]:
            with self.assertRaises(AppError):
                consent_service.answer_consent(consent['id'],{'status':'REJECTED','reason':reason},{'id':3})
        reply = consent_service.answer_consent(consent['id'],{'status':'REJECTED','reason':'업무량이 많아 분담이 어렵습니다.'},{'id':3})
        self.assertFalse(reply['completed'])
        for person in [1,2]:
            detail = request_service.request_detail(10,{'id':person})
            self.assertTrue(detail['request']['needs_recoordination'])
            self.assertEqual(detail['request']['consent_rejections'][0]['reason'],'업무량이 많아 분담이 어렵습니다.')
        with patch.object(rr,'list_user_requests',return_value=[dict(self.row,latest_consents_json=self.rounds[0]['consents_json'],latest_selected_key='1')]):
            for person in [1,2]:
                inbox=request_service.requests_list({'id':person})['requests'][0]
                self.assertTrue(inbox['needs_recoordination'])
                self.assertIn('업무량',inbox['consent_rejections'][0]['reason'])
        self.assertFalse(self.saved)
        self.assertFalse(self.overviews)
        for action in ['select','choose','confirm','complete_selection','generate','finalize']:
            with self.assertRaises(AppError): self.action(1,action,alternative_id=1,selected=False)

    def test_restart_archives_confirmation_and_passes_refusal_to_ai(self):
        self.prepare_shared()
        consent = consent_service.my_consents({'id':3})['consents'][0]
        consent_service.answer_consent(consent['id'],{'status':'REJECTED','reason':'현재 업무량이 많아 분담할 수 없습니다.'},{'id':3})
        old_id = self.rounds[0]['id']
        self.action(2,'restart_after_rejection',source_round_id=old_id)
        self.assertEqual(self.rounds[1]['status'],'FAILED')
        self.assertIsNone(self.result)
        archived = json.loads(self.rounds[1]['request_snapshot_json'])
        self.assertTrue(archived['final_result']['a_confirmed_at'])
        self.assertTrue(archived['final_result']['b_confirmed_at'])
        self.assertTrue(json.loads(self.rounds[1]['alternatives_json']))
        snapshot = json.loads(self.rounds[0]['request_snapshot_json'])
        self.assertEqual(snapshot['related_party_rejections'][0]['employee_id'],3)
        self.assertIn('분담할 수 없습니다',snapshot['related_party_rejections'][0]['reason'])
        self.assertTrue(snapshot['related_party_rejections'][0]['declined_items'])
        with self.assertRaises(AppError): self.action(1,'restart_after_rejection',source_round_id=old_id)
        with patch.object(planning_service,'generate_proposals',side_effect=self.ai_proposals) as provider:
            self.action(2,'generate')
        payload = provider.call_args.args[0]
        self.assertEqual(payload['related_party_rejections'][0]['reason'],snapshot['related_party_rejections'][0]['reason'])
        for alternative in json.loads(self.rounds[0]['alternatives_json']):
            self.assertFalse(alternative['a_selected'])
            self.assertFalse(alternative['b_selected'])
        detail=request_service.request_detail(10,{'id':1})
        self.assertFalse(detail['request']['needs_recoordination'])

    def test_refusal_stops_other_pending_requests_for_the_same_alternative(self):
        self.prepare_shared()
        consents = json.loads(self.rounds[0]['consents_json'])
        selected = next(c for c in consents if c['alternative_id']==1)
        consents.append(dict(selected,id=99,employee_id=4,employee_name='추가 관계자'))
        self.rounds[0]['consents_json'] = json.dumps(consents)
        nid=self.rounds[0]['id']
        consent_service.answer_consent(f"{nid}_{selected['id']}",{'status':'REJECTED','reason':'분담이 어렵습니다.'},{'id':3})
        rows = json.loads(self.rounds[0]['consents_json'])
        self.assertEqual(next(c for c in rows if c['id']==99)['status'],'CANCELLED')
        with self.assertRaises(AppError): consent_service.answer_consent(f'{nid}_99',{'status':'APPROVED','schedule_priority':'LOW','schedule_workload':'LOW'},{'id':4})

    def test_each_participant_selects_settings_only_after_all_consents(self):
        key=self.prepare_shared(confirm=False)
        self.action(1,'confirm',alternative_id=key)
        self.action(2,'confirm',alternative_id=key)
        self.assertFalse(json.loads(self.result['agreed_terms_json'])['calendar_preferences'])
        with self.assertRaises(AppError): self.action(1,'calendar_settings',schedule_priority='HIGH',schedule_workload='LOW')
        consent=consent_service.my_consents({'id':3})['consents'][0]
        result=consent_service.answer_consent(consent['id'],{'status':'APPROVED'},{'id':3})
        self.assertTrue(result['needs_calendar_settings'])
        self.assertFalse(self.saved)
        self.configure_all(consent['id'])
        self.assertEqual({tuple(p[-2:]) for p in self.saved if p[0]==2},{('LOW','HIGH')})
        self.assertEqual({tuple(p[-2:]) for p in self.saved if p[0]==3},{('HIGH','MEDIUM')})
        self.assertFalse(self.overviews)
        self.assertEqual(self.row['status'],'ACCEPTED')

    def test_direct_acceptance_requires_explicit_valid_preferences(self):
        for priority,workload in [(None,None),('HIGH',None),('URGENT','LOW')]:
            with self.assertRaises(AppError): actions.request_action(10,dict(action='respond',decision='ACCEPT',schedule_priority=priority,schedule_workload=workload),{'id':2})
        self.action(2,'respond',decision='ACCEPT',schedule_priority='HIGH',schedule_workload='LOW')
        self.assertEqual(tuple(self.saved[0][-2:]),('HIGH','LOW'))


    def test_unselected_consent_cannot_be_answered(self):
        key = self.prepare_shared()
        other = next(c for c in json.loads(self.rounds[0]['consents_json']) if c['alternative_id'] != key)
        consent_id = f"{self.rounds[0]['id']}_{other['id']}"
        with self.assertRaises(AppError): consent_service.answer_consent(consent_id, {'status':'APPROVED','schedule_priority':'LOW','schedule_workload':'LOW'}, {'id':3})

    def test_selection_completion_locks_changes_without_revoking_consents(self):
        key=self.prepare_shared()
        previous=deepcopy(self.result)
        for person in [1,2]:
            with self.assertRaises(AppError): self.action(person,'select',alternative_id=key,selected=False)
            with self.assertRaises(AppError): self.action(person,'select',alternative_id=2,selected=True)
        self.assertEqual(self.result,previous)
        self.assertTrue(consent_service.my_consents({'id':3})['consents'])
        self.assertTrue(all(a['a_selection_completed'] and a['b_selection_completed'] for a in json.loads(self.rounds[0]['alternatives_json'])))

    def test_each_participant_is_locked_only_after_their_completion(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='일정 조율')
        self.action(1,'generate')
        self.action(1,'select',alternative_id=1,selected=True)
        self.action(1,'complete_selection')
        with self.assertRaises(AppError): self.action(1,'select',alternative_id=2,selected=True)
        self.action(2,'select',alternative_id=1,selected=True)
        self.action(2,'select',alternative_id=2,selected=True)
        self.action(2,'complete_selection')
        with self.assertRaises(AppError): self.action(2,'select',alternative_id=2,selected=False)
        self.action(1,'choose',alternative_id=1)
        self.assertEqual(self.result['status'],'PENDING_CONFIRMATION')

    def test_selection_completion_is_required_before_choosing_final_plan(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='분담 요청')
        self.action(1,'generate')
        with self.assertRaises(AppError): self.action(1,'complete_selection')
        self.action(1,'select',alternative_id=1,selected=True)
        self.action(2,'select',alternative_id=1,selected=True)
        with self.assertRaises(AppError): self.action(1,'choose',alternative_id=1)
        self.action(1,'complete_selection')
        with self.assertRaises(AppError): self.action(1,'choose',alternative_id=1)
        self.action(2,'complete_selection')
        self.action(1,'choose',alternative_id=1)
        self.assertEqual(self.result['status'],'PENDING_CONFIRMATION')

    def test_agreement_waits_for_real_third_party_consent_then_registers_all_items(self):
        self.prepare_shared()
        with self.assertRaises(AppError): self.action(1, 'finalize')
        consents = consent_service.my_consents({'id':3})['consents']
        self.assertTrue(consents)
        consent_service.answer_consent(consents[0]['id'], {'status':'APPROVED'}, {'id':3})
        self.configure_all(consents[0]['id'])
        self.assertEqual(self.row['status'],'ACCEPTED')
        saved_count = len(self.saved)+len(self.overviews)
        self.action(1, 'finalize')
        self.assertEqual(saved_count,len(self.saved)+len(self.overviews))
        self.assertEqual(self.rounds[0]['status'],'AGREED')
        self.assertEqual({p[0] for p in self.saved+self.overviews},{2,3})
        self.assertEqual(len(self.overviews),0)
        self.assertEqual(len(self.saved),5)

    def test_direct_acceptance_registers_period_even_when_existing_schedule_is_full(self):
        self.schedules = [schedule()]
        self.action(2, 'respond', decision='ACCEPT')
        self.assertEqual(self.row['status'], 'ACCEPTED')
        self.assertEqual(len(self.saved), 1)
        self.assertEqual(self.saved[0][0], 2)
        self.assertEqual(self.saved[0][1], 1)
        self.assertEqual(self.saved[0][5], TODAY)
        self.assertEqual(self.saved[0][6].isoformat(), self.row['due_at'])
        self.assertEqual(json.loads(self.result['agreed_terms_json'])['method'], 'DIRECT_ACCEPTANCE')
        with self.assertRaises(AppError):
            self.action(2, 'respond', decision='ACCEPT')
        self.assertEqual(len(self.saved), 1)

    def test_direct_acceptance_of_expired_request_registers_a_mock_period(self):
        self.row['due_at'] = '2026-11-01T18:00:00'
        self.action(2, 'respond', decision='ACCEPT')
        self.assertTrue(self.saved)
        self.assertEqual(self.row['status'],'ACCEPTED')
        self.assertGreater(self.saved[0][6],self.saved[0][5])

    def test_generation_does_not_save_a_partial_set_of_alternatives(self):
        from test_planning import ai_proposal
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',comment='마감은 유지합니다.')
        with patch.object(planning_service,'generate_proposals',return_value=dict(alternatives=[ai_proposal()],reason='')):
            with self.assertRaises(AppError): self.action(2,'generate')
        self.assertEqual(self.rounds[0]['alternatives_json'], [])
        self.assertEqual(self.saved, [])

    def test_only_assignee_can_respond_and_only_requester_can_cancel(self):
        with self.assertRaises(AppError): self.action(1,'respond',decision='ACCEPT')
        with self.assertRaises(AppError): self.action(2,'cancel')
        self.action(1,'cancel')
        self.assertEqual(self.row['status'],'CANCELLED')
        with self.assertRaises(AppError): self.action(2,'respond',decision='ACCEPT')

    def test_rejection_can_be_resubmitted_with_history(self):
        self.action(2,'respond',decision='REJECT',comment='일정이 어렵습니다.')
        self.action(1,'resubmit',due_at='2026-11-13T18:00',feedback='마감을 일주일 늦춰 다시 요청합니다.')
        self.assertEqual(self.row['status'],'PENDING')
        self.assertIsNone(self.response)
        self.assertIsNone(self.result)
        self.assertIn('previous_response',self.rounds[0]['request_snapshot_json'])
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',accepted_condition_key='quantity',comment='규격은 유지')
        self.assertEqual(self.rounds[0]['round_no'],2)

    def test_renegotiation_preserves_assignee_constraints_and_feedback(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',accepted_condition_key='quantity',comment='마감을 조정해주세요.')
        self.action(1,'renegotiate',feedback='분담 불가, 순연 불가')
        self.assertEqual(self.rounds[0]['accepted_condition_key'],'quantity')
        self.assertEqual(self.rounds[0]['assignee_comment'],'마감을 조정해주세요.')
        self.assertEqual(self.rounds[1]['status'],'FAILED')
        self.assertEqual(self.rounds[0]['round_no'],2)

    def test_multiple_accepted_conditions_survive_renegotiation(self):
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',accepted_condition_keys=['deadline','quantity','specification'],comment='세 조건은 유지할 수 있습니다.')
        self.assertEqual(self.rounds[0]['accepted_condition_keys_json'],['deadline','quantity','specification'])
        self.action(1,'renegotiate',feedback='일정을 다시 조정해주세요.')
        self.assertEqual(self.rounds[0]['accepted_condition_keys_json'],['deadline','quantity','specification'])

    def test_invalid_accepted_condition_is_rejected(self):
        with self.assertRaises(AppError):
            self.action(2,'respond',decision='CONDITIONAL_ACCEPT',accepted_condition_keys=['deadline','unknown'])

    def test_locked_selection_preserves_both_final_confirmations(self):
        key=self.prepare_shared()
        with self.assertRaises(AppError): self.action(2,'select',alternative_id=key,selected=False)
        self.assertTrue(self.result['a_confirmed_at'])
        self.assertTrue(self.result['b_confirmed_at'])
        with self.assertRaises(AppError): self.action(1,'finalize')

    def test_initial_detail_contains_analysis_before_any_response(self):
        detail = request_service.request_detail(10,{'id':2})
        self.assertEqual(detail['rounds'],[])
        self.assertEqual(detail['analysis']['recommended_response'],'CONDITIONAL_ACCEPT')
        self.assertEqual(detail['schedule_timeline']['start_at'],'2026-11-02T00:00:00')
        self.assertEqual(detail['schedule_timeline']['end_at'],'2026-11-06T18:00:00')

    def prepare_reschedule(self, approve=True):
        self.row = request(45)
        self.row['status'] = 'PENDING'
        self.schedules = [schedule(start='2026-11-06T17:00',end='2026-11-06T18:00',priority='LOW')]
        self.schedules[0]['requester_id'] = 3
        self.action(2,'respond',decision='CONDITIONAL_ACCEPT',accepted_condition_key='quantity',comment='낮은 우선순위 업무를 순연해주세요.')
        self.action(1,'generate')
        detail = request_service.request_detail(10,{'id':1})
        proposal = next(a for a in detail['alternatives'] if a['plan_json']['schedule_changes'])
        key = proposal['id']
        self.action(1,'select',alternative_id=key,selected=True)
        self.action(2,'select',alternative_id=key,selected=True)
        self.action(1,'complete_selection')
        self.action(2,'complete_selection')
        self.action(1,'choose',alternative_id=key)
        self.action(1,'confirm',alternative_id=key)
        self.action(2,'confirm',alternative_id=key)
        consent = next(c for c in consent_service.my_consents({'id':3})['consents'] if c['alternative_id']==key)
        if approve:
            consent_service.answer_consent(consent['id'],{'status':'APPROVED'},{'id':3})
            self.configure_all(consent['id'])
        return consent

    def test_reschedule_and_delivery_are_applied_together(self):
        self.prepare_reschedule()
        self.action(1,'finalize')
        self.assertGreater(self.schedules[0]['start_at'],'2026-11-06T18:00')
        self.assertEqual(len(self.saved),45)
        self.assertEqual({p[0] for p in self.overviews},{3})
        self.assertEqual(tuple(next(p for p in self.overviews if p[0]==3)[-2:]),('HIGH','MEDIUM'))
        self.assertNotIn(1,{p[0] for p in self.saved+self.overviews})

    def test_changed_original_schedule_requires_new_consent_round(self):
        consent = self.prepare_reschedule(approve=False)
        self.schedules[0]['end_at'] = '2026-11-06T17:30'
        consent_service.answer_consent(consent['id'],{'status':'APPROVED'},{'id':3})
        with self.assertRaises(AppError): self.configure_all(consent['id'])
        self.assertEqual(self.saved,[])
        self.assertEqual(self.row['status'],'NEGOTIATING')


if __name__ == '__main__': unittest.main()
