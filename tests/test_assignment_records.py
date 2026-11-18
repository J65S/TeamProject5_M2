from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from taskpilot.workload import load_assignments, make_plan
from taskpilot.calendar_planner import enrich_answer
from taskpilot.paths import SYLLABI_FOLDER


class AssignmentRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)

    def load(self, text, as_of='2026-12-01', relative=False):
        (self.folder/'tasks.txt').write_text(text)
        return load_assignments(self.folder,as_of,relative_dates=relative)

    def record(self, extras='', name='Outline', id='A'):
        return f'COURSE: Test\nTask: {name}\nID: {id}\nDue: 2026-12-03\nRemaining minutes: 60\n{extras}\n'

    def test_all_fixed_fixture_dates_in_requested_week(self):
        data=load_assignments(SYLLABI_FOLDER,'2026-11-16')
        self.assertEqual(len(data['assignments']),24)
        self.assertEqual(data['warnings'],[])
        for task in data['assignments']:
            self.assertTrue('2026-12-01'<=task['due_date']<='2026-12-07')
            self.assertTrue(task['description'] and task['first_step'] and task['due_at'])

    def test_rich_record_fields(self):
        data=self.load(self.record('Description: Create an outline.\nFirst step: Read the brief.\nDue time: 18:00\nTimezone: America/New_York\nStatus: In progress\nCan split: No'))
        task=data['assignments'][0]
        self.assertEqual(task['status'],'in_progress')
        self.assertFalse(task['can_split'])
        self.assertEqual(task['due_at'],'2026-12-03T18:00:00-05:00')
        self.assertEqual(task['first_step'],'Read the brief.')

    def test_relative_mode_is_explicit_and_reproducible(self):
        text=self.record('Demo offset days: 2\nDue time: 18:00\nTimezone: America/New_York')
        fixed=self.load(text,as_of='2026-11-16')['assignments'][0]
        relative=self.load(text,as_of='2026-11-16',relative=True)['assignments'][0]
        self.assertEqual(fixed['due_date'],'2026-12-03')
        self.assertEqual(relative['due_date'],'2026-11-18')
        self.assertEqual(relative['fixed_due_date'],'2026-12-03')
        self.assertEqual(relative['id'],fixed['id'])
        self.assertEqual(relative,self.load(text,as_of='2026-11-16',relative=True)['assignments'][0])

    def test_relative_due_time_observes_timezone(self):
        task=self.load(self.record('Demo offset days: 0\nDue time: 18:00\nTimezone: America/New_York'),as_of='2026-07-01',relative=True)['assignments'][0]
        self.assertTrue(task['due_at'].endswith('-04:00'))

    def test_completed_is_not_scheduled(self):
        data=self.load(self.record('Status: Completed').replace('Remaining minutes: 60','Remaining minutes: 0'))
        self.assertEqual(make_plan(data,90)['blocks'],[])
        self.assertEqual(data['assignments'][0]['status'],'completed')

    def test_prerequisite_blocks_until_confirmed_complete(self):
        data=self.load(self.record() + self.record('Dependencies: A',name='Draft',id='B'))
        plan=make_plan(data,120)
        self.assertEqual([b['task_id'] for b in plan['blocks']],['A'])
        self.assertEqual(plan['blocked'][0]['task_id'],'B')
        self.assertEqual(make_plan(data,120,completed=['A'])['blocks'][0]['task_id'],'B')

    def test_non_splittable_task_is_not_partially_allocated(self):
        data=self.load(self.record('Can split: No'))
        self.assertEqual(make_plan(data,30)['blocks'],[])
        self.assertEqual(make_plan(data,60)['blocks'][0]['minutes'],60)

    def test_invalid_extended_fields_are_reported(self):
        for extra in ('Due time: 30:00\nTimezone: America/New_York','Due time: 18:00',
                      'Timezone: No/Such_Zone','Status: Unknown','Can split: Maybe'):
            with self.subTest(extra=extra):
                data=self.load(self.record(extra))
                self.assertEqual(data['assignments'],[])
                self.assertEqual(len(data['warnings']),1)

    def test_calendar_respects_exact_time_not_end_of_date(self):
        text=self.record('Due time: 10:45\nTimezone: America/New_York').replace('2026-12-03','2026-12-01')
        data=self.load(text)
        result=enrich_answer(dict(kind='plan',minutes=60,plan=make_plan(data,60)),data,'demo')
        plan=result['plan']
        self.assertEqual(plan['scheduled_minutes'],15)
        self.assertEqual(plan['unfinished'][0]['remaining_minutes'],45)
        self.assertTrue(all(datetime.fromisoformat(b['end'])<=datetime.fromisoformat(data['assignments'][0]['due_at']) for b in plan['blocks']))

    def test_calendar_does_not_split_unsplittable_task(self):
        data=self.load(self.record('Can split: No'))
        result=enrich_answer(dict(kind='plan',minutes=30,plan=make_plan(data,30)),data,'demo')
        self.assertEqual(result['plan']['blocks'],[])

    def test_unknown_dependency_stays_visible_and_blocked(self):
        data=self.load(self.record('Dependencies: missing-id'))
        plan=make_plan(data,60)
        self.assertEqual(plan['blocks'],[])
        self.assertEqual(plan['blocked'][0]['dependencies'],['missing-id'])

    def test_relative_files_require_offset(self):
        data=self.load(self.record(),relative=True)
        self.assertEqual(data['assignments'],[])
        self.assertEqual(len(data['warnings']),1)
