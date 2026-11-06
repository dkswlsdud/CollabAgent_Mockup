"""Authored scenario relationships and negotiation snapshots must be internally consistent."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from app.maintenance.seed_request_scenarios import build_scenarios


class DemoScenarioTests(unittest.TestCase):
    def setUp(self):
        people = [dict(id=i+1,name=name,department=team) for i,(name,team) in enumerate([
            ('김민지','마케팅팀'),('이서준','디자인팀'),('박지훈','콘텐츠팀'),('정하은','디자인팀'),('최유진','마케팅팀')])]
        self.scenarios = build_scenarios(people)

    def test_five_distinct_scenarios_have_expected_initial_states(self):
        self.assertEqual(len({s['title'] for s in self.scenarios}),5)
        self.assertEqual([s['status'] for s in self.scenarios],['PENDING','REJECTED','NEGOTIATING','NEGOTIATING','NEGOTIATING'])
        self.assertTrue(all(s['requester_id'] != s['assignee_id'] for s in self.scenarios))

    def test_split_preserves_hard_quantity_and_changes_soft_deadline(self):
        split = self.scenarios[2]
        self.assertEqual(split['conditions_json'][0]['constraint'],'SOFT')
        for option in split['alternatives']:
            self.assertEqual(sum(i['quantity'] for i in option['plan_json']['items']),8)
        self.assertEqual(len(split['alternatives'][0]['plan_json']['items']),2)

    def test_shared_plan_has_real_pending_consent_for_selected_alternative(self):
        shared = self.scenarios[3]
        selected = next(a for a in shared['alternatives'] if a['id']==shared['selected'])
        self.assertTrue(selected['a_selected'] and selected['b_selected'])
        self.assertEqual(sum(i['quantity'] for i in selected['plan_json']['items']),12)
        extra_people = {i['assignee_id'] for i in selected['plan_json']['items']} - {shared['assignee_id']}
        self.assertEqual(extra_people,{c['employee_id'] for c in shared['consents'] if c['alternative_id']==shared['selected']})
        self.assertTrue(all(c['status']=='PENDING' for c in shared['consents']))

    def test_retry_keeps_disjoint_selections_and_fresh_second_round(self):
        retry = self.scenarios[4]
        self.assertTrue(retry['history']['requester_feedback'])
        self.assertTrue(retry['history']['assignee_feedback'])
        self.assertFalse(any(a['a_selected'] and a['b_selected'] for a in retry['history']['alternatives']))
        self.assertTrue(all(not a['a_selected'] and not a['b_selected'] for a in retry['alternatives']))


if __name__ == '__main__': unittest.main()
