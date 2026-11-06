"""Team member filtering must keep the department boundary and work with demo data."""
import sys
from pathlib import Path
from datetime import date, datetime
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services import schedule_service
from app.repositories import schedule_repository
from app.maintenance.reset_schedule_demo import build_rows
from app.shared.errors import AppError


class TeamFilterTests(unittest.TestCase):
    def setUp(self):
        self.user = dict(id=1,department='마케팅팀')
        self.people = [dict(id=1,name='김민지',department='마케팅팀'),dict(id=5,name='최유진',department='마케팅팀'),dict(id=2,name='이서준',department='디자인팀')]

    def test_team_member_is_forwarded_to_query(self):
        with patch.object(schedule_service,'transaction'), patch.object(schedule_repository,'list_schedules',return_value=[]) as query, patch('app.repositories.employee_repository.list_active_employees',return_value=self.people):
            schedule_service.schedules({'scope':'team','month':'2026-11','employee_id':'5'},self.user)
            self.assertEqual(query.call_args.args[-1],5)
            self.assertEqual(query.call_args.args[-2],'마케팅팀')

    def test_outside_department_is_rejected(self):
        with patch.object(schedule_service,'transaction'), patch('app.repositories.employee_repository.list_active_employees',return_value=self.people):
            with self.assertRaises(AppError) as error:
                schedule_service.schedules({'scope':'team','employee_id':'2'},self.user)
            self.assertEqual(error.exception.status,403)

    def test_selected_department_and_member_are_allowed(self):
        with patch.object(schedule_service,'transaction'), patch.object(schedule_repository,'list_schedules',return_value=[]) as query, patch('app.repositories.employee_repository.list_active_employees',return_value=self.people):
            schedule_service.schedules({'scope':'team','department':'디자인팀','employee_id':'2'},self.user)
            self.assertEqual(query.call_args.args[-2:], ('디자인팀', 2))

    def test_mismatched_selected_department_and_member_are_rejected(self):
        with patch.object(schedule_service,'transaction'), patch('app.repositories.employee_repository.list_active_employees',return_value=self.people):
            with self.assertRaises(AppError):
                schedule_service.schedules({'scope':'team','department':'디자인팀','employee_id':'5'},self.user)

    def test_unknown_department_is_rejected(self):
        with patch.object(schedule_service,'transaction'), patch('app.repositories.employee_repository.list_active_employees',return_value=self.people):
            with self.assertRaises(AppError):
                schedule_service.schedules({'scope':'team','department':'없는팀'},self.user)

    def test_invalid_member_filter_is_rejected(self):
        with self.assertRaises(AppError):
            schedule_service.schedules({'scope':'all'},self.user)
        for value in ['abc','0','-1']:
            with self.assertRaises(AppError):
                schedule_service.schedules({'scope':'team','employee_id':value},self.user)

    def test_query_combines_department_and_member(self):
        cur = MagicMock()
        schedule_repository.list_schedules(cur,datetime(2026,12,1),datetime(2026,11,1),'team',1,'마케팅팀',5)
        sql,args = cur.execute.call_args.args
        self.assertIn('e.department=%s',sql)
        self.assertIn('s.employee_id=%s',sql)
        self.assertEqual(args[-2:],['마케팅팀',5])


class ScheduleFixtureTests(unittest.TestCase):
    def test_schedule_registration_only_requires_start_and_end(self):
        with patch.object(schedule_service,'transaction'), patch('app.repositories.employee_repository.lock_employee'), patch.object(schedule_repository,'insert_schedule',return_value=42) as insert:
            result = schedule_service.create_schedule({'title':'회의','type':'MEETING','start_at':'2030-11-04T10:00','end_at':'2030-11-04T11:00'}, {'id':1})
            self.assertEqual(result,{'id':42})
            values = insert.call_args.args[1]
            self.assertEqual(values[3:5], (datetime(2030,11,4,10),datetime(2030,11,4,11)))
            self.assertEqual(len(values),8)

    def test_fixture_has_varied_metadata_and_preserves_employee_ids(self):
        employees = [dict(id=i+1,name=name) for i,name in enumerate(['김민지','최유진','이서준','정하은','박지훈'])]
        rows = build_rows(employees,date(2026,11,2))
        self.assertEqual(len(rows),28)
        self.assertEqual({r[0] for r in rows},{e['id'] for e in employees})
        self.assertEqual({r[7] for r in rows},{'HIGH','MEDIUM','LOW'})
        self.assertEqual({r[8] for r in rows},{'SCHEDULED','IN_PROGRESS','COMPLETED','CANCELLED'})
        self.assertEqual({r[9] for r in rows},{'HIGH','MEDIUM','LOW'})
        self.assertTrue(all(r[4] < r[5] for r in rows))
        self.assertEqual(sum(r[4].date()!=r[5].date() for r in rows),19)
        self.assertEqual(sum(r[3]=='WORK' and r[4].date()==r[5].date() for r in rows),2)
        self.assertTrue(all(r[4].date()==r[5].date() for r in rows if r[3] in {'MEETING','PERSONAL'}))


if __name__ == '__main__': unittest.main()
