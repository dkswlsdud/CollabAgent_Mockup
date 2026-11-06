"""Behavior checks for proposals, conflicts, Hard conditions and third-party consent."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import planning_service as planner, schedule_service, intake_service
from app.shared.errors import AppError

TODAY = datetime(2026, 11, 2, 8)
PEOPLE = [dict(id=1, name='김민지', department='마케팅팀'), dict(id=2, name='이서준', department='디자인팀'), dict(id=3, name='정하은', department='디자인팀')]


def request(quantity=5):
    return dict(id=10, requester_id=1, assignee_id=2, due_at='2026-11-06T18:00:00', task_content='배너 제작',
                conditions_json=[dict(key='deadline', label='마감', constraint='HARD'),
                                 dict(key='quantity', label='수량', value=quantity, constraint='SOFT'),
                                 dict(key='specification', label='규격', value='1200×600px', constraint='HARD')])


def schedule(id=1, person=2, start='2026-11-02T09:00', end='2026-11-06T18:00', **kw):
    return dict(id=id, employee_id=person, requester_id=1, result_id=None, title='기존 업무', type='WORK',
                status='SCHEDULED', priority=kw.get('priority', 'MEDIUM'), workload='MEDIUM', start_at=start, end_at=end, due_at=end)


def ai_proposal(start='2026-11-02T09:00:00', quantity=5, person=2, specification='1200×600px'):
    begin = datetime.fromisoformat(start)
    return dict(title='빈 시간 작업', description='기존 업무와 겹치지 않는 시간에 작업합니다.',
                reflects_feedback=True,feedback_explanation='의견에서 제안한 조건으로 작업을 배치합니다.',warnings=[],
                specification=specification, condition_values=[], schedule_changes=[],
                items=[dict(assignee_id=person, quantity=quantity, start_at=start,
                            end_at=begin.replace(hour=begin.hour+1).isoformat(), due_at='2026-11-06T18:00:00')])


class PlanningTests(unittest.TestCase):
    def test_consent_rejection_regenerates_fixed_demo_without_ai(self):
        negotiation=dict(requester_feedback='관계자 거부 후 재생성',request_snapshot_json={
            'related_party_rejections':[dict(employee_id=3,employee_name='정하은',reason='분담 불가')]})
        with patch('app.services.ai_planning_service.generate_proposals',side_effect=AssertionError('No AI for rejected-consent demos')):
            alternatives,consents=planner.generate(None,request(),negotiation)
        self.assertEqual([a['title'] for a in alternatives],['대안1-재생성','대안2-재생성','대안3-재생성'])
        self.assertTrue(all(a['validation']=='DEMO' for a in alternatives))

    def test_revision_feedback_regenerates_fixed_demo_without_ai(self):
        for side in ['requester_feedback','assignee_feedback']:
            with self.subTest(side=side), patch('app.services.ai_service.urlopen',side_effect=AssertionError('No AI for regeneration')):
                alternatives,_=planner.generate(None,request(),{side:'대안을 다시 생성해주세요.'})
                self.assertEqual([a['title'] for a in alternatives],['대안1-재생성','대안2-재생성','대안3-재생성'])
                self.assertTrue(all(a['validation']=='DEMO' for a in alternatives))

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.schedules = []
        self.stack.enter_context(patch.object(planner, 'now', return_value=TODAY))
        self.stack.enter_context(patch.object(schedule_service, 'now', return_value=TODAY))
        self.stack.enter_context(patch('app.repositories.employee_repository.list_active_employees', return_value=PEOPLE))
        self.stack.enter_context(patch('app.repositories.schedule_repository.list_workload_schedules', side_effect=self.workload))
        self.stack.enter_context(patch('app.repositories.schedule_repository.find_schedule', side_effect=lambda cur, params: next((s for s in self.schedules if s['id'] == params[0]), None)))

    def workload(self, cur, parameters):
        person, start, end = parameters
        return [s for s in self.schedules if s['employee_id'] == person and s['status'] not in {'COMPLETED','CANCELLED'} and datetime.fromisoformat(s['start_at']) < end and datetime.fromisoformat(s['end_at']) > start]

    def test_free_slots_exclude_weekend_and_leave(self):
        self.schedules = [schedule(start='2026-11-06T09:00', end='2026-11-06T18:00')]
        slots = planner.free_slots(self.schedules, datetime(2026,11,6,9), datetime(2026,11,10,18))
        self.assertTrue(slots)
        self.assertTrue(all(s.weekday() == 0 or s.day == 10 for s, e in slots))

    def ai(self, alternatives):
        if len(alternatives) == 1:
            base = alternatives[0]
            alternatives = [deepcopy(base) for _ in range(3)]
            for index, proposal in enumerate(alternatives):
                for item in proposal['items']:
                    for key in ['start_at', 'end_at']:
                        value = datetime.fromisoformat(item[key])
                        item[key] = value.replace(day=value.day+index).isoformat()
        return self.stack.enter_context(patch.object(planner, 'generate_proposals', return_value=dict(alternatives=alternatives, reason='')))

    def test_ai_receives_conditions_feedback_and_only_relevant_team(self):
        provider = self.ai([ai_proposal()])
        self.schedules = [schedule(start='2026-11-03T10:00', end='2026-11-03T11:00')]
        proposals, _ = planner.generate(None, request(), dict(assignee_comment='마감 유지', requester_feedback='분담 없이 진행', accepted_condition_key='deadline'))
        payload = provider.call_args.args[0]
        self.assertEqual({p['id'] for p in payload['employees']}, {2, 3})
        self.assertEqual(payload['accepted_condition_keys'],['deadline'])
        self.assertEqual(payload['feedback']['requester_feedback'],'분담 없이 진행')
        self.assertEqual(payload['request']['conditions_json'][0]['constraint'],'HARD')
        self.assertEqual(payload['feedback']['assignee_comment'], '마감 유지')
        self.assertTrue(payload['schedules'])
        self.assertEqual(proposals[0]['plan_json']['method'], 'MOCK')
        self.assertEqual(len(proposals), 3)

    def test_ai_errors_do_not_fall_back_to_rules(self):
        with patch.object(planner, 'generate_proposals', side_effect=AppError('AI 연결 실패', 502)):
            with self.assertRaises(AppError) as error: planner.generate(None, request(), {})
            self.assertEqual(error.exception.status, 502)

    def test_partial_ai_result_does_not_save_fewer_than_three(self):
        self.schedules = [schedule(start='2026-11-02T09:00', end='2026-11-02T10:00')]
        self.ai([ai_proposal(), ai_proposal(start='2026-11-03T09:00:00')])
        with self.assertRaises(AppError) as error: planner.generate(None, request(), {})
        self.assertIn('3개', error.exception.message)








    def test_no_feasible_ai_plan_is_rejected(self):
        self.ai([])
        with self.assertRaises(AppError): planner.generate(None, request(), {})

    def test_duplicates_and_malformed_candidates_are_not_saved(self):
        self.ai([{}, ai_proposal(), ai_proposal()])
        with self.assertRaises(AppError): planner.generate(None, request(), {})

    def test_unknown_employee_is_rejected(self):
        self.ai([ai_proposal(person=999)])
        with self.assertRaises(AppError): planner.generate(None, request(), {})

    def test_ai_cannot_move_high_priority_or_forge_schedule_owner(self):
        self.schedules = [schedule(start='2026-11-04T09:00', end='2026-11-04T10:00', priority='HIGH')]
        proposal = ai_proposal()
        proposal['schedule_changes'] = [dict(schedule_id=1, start_at='2026-11-10T09:00', end_at='2026-11-10T10:00')]
        self.ai([proposal])
        with self.assertRaises(AppError): planner.generate(None, request(), {})

    def test_shared_work_requires_real_consent(self):
        self.ai([ai_proposal(person=3)])
        proposals, consents = planner.generate(None, request(), {})
        self.assertEqual(consents[0]['employee_id'], 3)
        self.assertEqual(consents[0]['status'], 'PENDING')

    def test_latest_conflict_blocks_confirmation(self):
        self.ai([ai_proposal()])
        proposals, _ = planner.generate(None, request(), {})
        plan = proposals[0]['plan_json']
        item = plan['items'][0]
        self.schedules = [schedule(start=item['start_at'], end=item['end_at'])]
        with self.assertRaises(AppError): schedule_service.validate_plan(None, request(), plan)

    def test_recommendation_is_fixed_regardless_of_availability(self):
        row = request(45)
        self.assertEqual(schedule_service.analysis_for(None, 2, datetime(2026,11,6,18), row)['recommended_response'], 'CONDITIONAL_ACCEPT')
        self.schedules=[schedule(start='2026-11-02T09:00',end='2026-11-02T18:00')]
        self.assertEqual(schedule_service.analysis_for(None,2,datetime(2026,11,6,18),row)['recommended_response'],'CONDITIONAL_ACCEPT')
        self.schedules=[schedule()]
        self.assertEqual(schedule_service.analysis_for(None,2,datetime(2026,11,6,18),row)['recommended_response'],'CONDITIONAL_ACCEPT')

    def test_restored_hard_deadline_rejects_extension(self):
        proposal=ai_proposal(start='2026-11-10T09:00:00')
        proposal['items'][0]['due_at']='2026-11-12T18:00:00'
        self.ai([proposal])
        with self.assertRaises(AppError):planner.generate(None,request(),{})

    def test_restored_soft_deadline_can_be_extended(self):
        row=request()
        row['conditions_json'][0]['constraint']='SOFT'
        proposal=ai_proposal(start='2026-11-10T09:00:00')
        proposal['items'][0]['due_at']='2026-11-12T18:00:00'
        self.ai([proposal])
        proposals,_=planner.generate(None,row,{})
        self.assertEqual(len(proposals),3)

    def test_restored_hard_quantity_cannot_change(self):
        row=request()
        row['conditions_json'][1]['constraint']='HARD'
        self.ai([ai_proposal(quantity=2)])
        with self.assertRaises(AppError):planner.generate(None,row,{})

    def test_restored_accepted_soft_condition_is_kept(self):
        self.ai([ai_proposal(quantity=2)])
        with self.assertRaises(AppError):planner.generate(None,request(),{'accepted_condition_keys_json':['quantity']})

    def test_fixed_alternatives_are_offline_and_third_always_needs_consent(self):
        from app.services.mock_planning_service import generate_proposals
        with patch.object(planner,'generate_proposals',side_effect=generate_proposals),patch('app.services.ai_service.urlopen',side_effect=AssertionError('No AI for alternatives')):
            for quantity in [1,5]:
                row=request(quantity)
                row['conditions_json'][1]['constraint']='HARD'
                alternatives,consents=planner.generate(None,row,{'accepted_condition_keys_json':['quantity']})
                self.assertEqual([a['title'] for a in alternatives],['대안1','대안2','대안3(관계자 필요)'])
                self.assertEqual({c['alternative_id'] for c in consents},{3})
                self.assertEqual({c['employee_id'] for c in consents},{3})
                self.assertTrue(all(a['plan_json']['method']=='MOCK' for a in alternatives))
                self.assertTrue(all(sum(i['quantity'] for i in a['plan_json']['items'])==quantity for a in alternatives))

    def test_fixed_demo_still_generates_when_busy_and_hard_deadline_has_passed(self):
        from app.services.mock_planning_service import generate_proposals
        self.schedules=[schedule(end='2026-11-20T18:00')]
        row=request()
        row['due_at']='2026-11-01T18:00:00'
        before=deepcopy(row)
        with patch.object(planner,'generate_proposals',side_effect=generate_proposals),patch.object(schedule_service,'validate_plan',side_effect=AssertionError('No feasibility gate when displaying fixed demos')):
            alternatives,consents=planner.generate(None,row,{})
        self.assertEqual([a['title'] for a in alternatives],['대안1','대안2','대안3(관계자 필요)'])
        self.assertTrue(all(a['validation']=='DEMO' for a in alternatives))
        self.assertEqual({c['alternative_id'] for c in consents},{3})
        self.assertEqual(row,before)

    def test_demo_uses_consent_reviewer_when_assignee_has_no_other_teammate(self):
        from app.services.mock_planning_service import generate_proposals
        row=request()
        row.update(requester_id=2,assignee_id=1)
        with patch.object(planner,'generate_proposals',side_effect=generate_proposals):
            alternatives,consents=planner.generate(None,row,{})
        self.assertEqual(len(alternatives),3)
        self.assertEqual(consents[0]['employee_id'],3)
        self.assertEqual(consents[0]['alternative_id'],3)
        self.assertEqual(alternatives[2]['plan_json']['related_employee_ids'],[3])
        self.assertTrue(all(i['assignee_id']==1 for i in alternatives[2]['plan_json']['items']))



class IntakeTests(unittest.TestCase):
    def test_ai_suggested_requirements_have_reasons_and_missing_questions(self):
        extracted = dict(task_content='배너 제작',due_at='2026-11-06T18:00',assignee_id=3,questions=[],conditions_json=[
            dict(key='specification',label='배너 규격',value='1200x600px',unit='',origin='SUGGESTED',reason='게재 영역에 맞게 제작하려면 크기를 확인해야 합니다.',question='배너 크기는 얼마인가요?'),
            dict(key='format',label='파일 형식',value='',unit='',origin='SUGGESTED',reason='최종 결과물을 전달할 형식이 필요합니다.',question='PNG와 JPG 중 어떤 형식인가요?')])
        with patch.object(intake_service,'transaction'),patch.object(intake_service,'extract_request',side_effect=lambda _:deepcopy(extracted)),patch('app.repositories.employee_repository.list_active_employees',return_value=PEOPLE):
            draft=intake_service.analyze({'original_text':'배너 만들어줘'}, {'id':1})
            self.assertEqual(len(draft['conditions_json']),2)
            self.assertEqual(draft['conditions_json'][0]['value'],'')
            self.assertIn('게재 영역',draft['conditions_json'][0]['reason'])
            self.assertEqual({q['key'] for q in draft['questions']},{'specification','format'})
            completed=intake_service.analyze({'original_text':'배너 만들어줘','answers':{'specification':'600x300px','format':'PNG'}},{'id':1})
            self.assertTrue(completed['ready'])
            self.assertEqual(completed['conditions_json'][0]['value'],'600x300px')

    def test_reanalysis_preserves_manual_conditions_and_respects_deletions(self):
        extracted=dict(task_content='배너 제작',due_at='2026-11-06T18:00',assignee_id=3,questions=[],conditions_json=[dict(key='format',label='파일 형식',value='',unit='',origin='SUGGESTED',reason='전달 형식 확인',question='파일 형식은 무엇인가요?')])
        manual=dict(key='custom_review',label='검수 담당',value='김민지',unit='',constraint='HARD',origin='MANUAL')
        with patch.object(intake_service,'transaction'),patch.object(intake_service,'extract_request',return_value=extracted),patch('app.repositories.employee_repository.list_active_employees',return_value=PEOPLE):
            draft=intake_service.analyze({'original_text':'배너 제작','previous_conditions':[manual],'removed_condition_keys':['format']},{'id':1})
            self.assertEqual([c['key'] for c in draft['conditions_json']],['custom_review'])
            self.assertEqual(draft['conditions_json'][0]['constraint'],'HARD')
            self.assertTrue(draft['ready'])

    def test_deleted_ai_clarification_does_not_return_on_reanalysis(self):
        extracted=dict(task_content='질문지 검토',due_at='2026-11-10T18:00',assignee_id=3,conditions_json=[],questions=['어떤 고객을 인터뷰하나요?'])
        with patch.object(intake_service,'transaction'),patch.object(intake_service,'extract_request',return_value=extracted),patch('app.repositories.employee_repository.list_active_employees',return_value=PEOPLE):
            first=intake_service.analyze({'original_text':'질문지 검토'}, {'id':1})
            key=first['questions'][0]['key']
            second=intake_service.analyze({'original_text':'질문지 검토','removed_condition_keys':[key]}, {'id':1})
            self.assertEqual(second['questions'],[])
            self.assertTrue(second['ready'])

    def test_korean_relative_and_explicit_dates(self):
        self.assertEqual(intake_service.extract_date('다음 주 금요일까지', TODAY), '2026-11-13T18:00')
        self.assertEqual(intake_service.extract_date('11월 6일 오후 3시', TODAY), '2026-11-06T15:00')
        self.assertEqual(intake_service.extract_date('내일', TODAY), '2026-11-03T18:00')

    def test_missing_questions_and_answer_completion(self):
        extracted = dict(task_content='배너 제작',due_at=None,assignee_id=3,conditions_json=[dict(key='quantity',label='수량',value='5',unit='개'),dict(key='specification',label='규격',value='',unit='')],questions=[])
        with patch.object(intake_service, 'transaction') as tx, patch.object(intake_service, 'extract_request', side_effect=lambda _:deepcopy(extracted)), patch('app.repositories.employee_repository.list_active_employees', return_value=PEOPLE), patch.object(intake_service, 'now', return_value=TODAY):
            tx.return_value.__enter__.return_value = None
            draft = intake_service.analyze({'original_text':'정하은에게 배너 5개'}, {'id':1})
            self.assertEqual({q['key'] for q in draft['questions']}, {'due_at','specification'})
            draft = intake_service.analyze({'original_text':'정하은에게 배너 5개', 'answers':{'due_at':'2026-11-06T18:00', 'specification':'1200×600px'}}, {'id':1})
            self.assertTrue(draft['ready'])
        self.assertEqual(draft['method'], 'LLM')

    def test_ai_failure_does_not_produce_a_draft(self):
        with patch.object(intake_service,'transaction'), patch('app.repositories.employee_repository.list_active_employees', return_value=PEOPLE), patch.object(intake_service,'extract_request',side_effect=AppError('AI 연결 실패',502)):
            with self.assertRaises(AppError):
                intake_service.analyze({'original_text':'정하은에게 11월 6일까지 배너 5개'}, {'id':1})


if __name__ == '__main__': unittest.main()
