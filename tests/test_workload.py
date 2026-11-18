"""Local regression checks, distinct from the unavailable M3 committed suite."""
import tempfile
import unittest
from pathlib import Path
from taskpilot.workload import load_assignments, make_plan, parse_minutes


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def data(self, text):
        (self.folder / 'course.txt').write_text(text)
        return load_assignments(self.folder, '2026-11-16')

    def task(self, name='Essay', due='2026-11-18', hours='2'):
        return f'COURSE: Demo\nTask: {name}\nDue: {due}\nEstimated hours: {hours}\n'

    def test_compound_budget(self):
        self.assertEqual(parse_minutes('I have 1 hour 30 minutes'), 90)
        self.assertEqual(parse_minutes('I have 1.5 hours'), 90)

    def test_ambiguous_and_invalid_budgets(self):
        for text in ('help me', '-2 hours', '25 hours', '1 or 2 hours',
                     '2 hours tomorrow', '1 hour then 2 hours', '0.001 minutes'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_minutes(text)

    def test_invalid_syllabus_records(self):
        data = self.data('Task: Missing fields\n' + self.task(hours='nan') + self.task(hours='inf') + self.task(due='wrong'))
        self.assertEqual(data['assignments'], [])
        self.assertEqual(len(data['warnings']), 4)

    def test_missing_files(self):
        self.assertIn('error', load_assignments(self.folder, '2026-11-16'))

    def test_overdue_retained(self):
        data = self.data(self.task(due='2026-11-15'))
        self.assertTrue(data['assignments'][0]['overdue'])
        self.assertEqual(len(make_plan(data, 60)['blocks']), 1)

    def test_deadline_order_not_shortest_first(self):
        data = self.data(self.task('Small', '2026-11-20', '0.5') + self.task('Urgent', '2026-11-17', '3'))
        plan = make_plan(data, 60)
        self.assertEqual(plan['blocks'][0]['task'], 'Urgent')
        self.assertEqual(plan['unfinished'][0]['remaining_minutes'], 120)

    def test_no_overbooking_or_overlap(self):
        data = self.data(self.task('A', hours='0.5') + self.task('B', hours='2'))
        plan = make_plan(data, 90)
        self.assertEqual([b['minutes'] for b in plan['blocks']], [30, 60])
        self.assertEqual([b['start_minute'] for b in plan['blocks']], [0, 30])
        self.assertEqual(plan['scheduled_minutes'], 90)
        self.assertEqual(plan['unfinished'][0]['remaining_minutes'], 60)

    def test_unused_time_and_empty_workload(self):
        data = self.data(self.task(hours='0.5'))
        plan = make_plan(data, 90)
        self.assertEqual(plan['unused_minutes'], 60)
        data['assignments'] = []
        self.assertEqual(make_plan(data, 90)['blocks'], [])

    def test_completed_status(self):
        data = self.data(self.task())
        task_id = data['assignments'][0]['id']
        self.assertEqual(make_plan(data, 60, [task_id])['blocks'], [])
        with self.assertRaises(ValueError):
            make_plan(data, 60, ['unknown'])

    def test_duplicates_and_stable_ids(self):
        data = self.data(self.task() + self.task())
        self.assertEqual(len(data['assignments']), 1)
        self.assertEqual(len(data['warnings']), 1)
        self.assertEqual(data['assignments'][0]['id'], self.data(self.task())['assignments'][0]['id'])


if __name__ == '__main__':
    unittest.main()
