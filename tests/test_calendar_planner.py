from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from taskpilot.calendar_planner import ZONE, calendar_snapshot, enrich_answer, free_windows, preferences
from taskpilot.conversation import answer_question, example_week


class CalendarPlannerTests(TestCase):
    def setUp(self):
        self.data=example_week('2026-11-16')
        self.cal=calendar_snapshot('demo', datetime(2026,11,16).date())
        self.now=datetime.fromisoformat(self.cal['simulated_now'])

    def answer(self, question='I have two hours'):
        return enrich_answer(answer_question(question,self.data),self.data,'demo')

    def test_busy_reason_and_next_window(self):
        result=self.answer()
        self.assertIn('Morning class',result['answer'])
        self.assertTrue(result['plan']['blocks'][0]['start'].startswith('2026-11-16T10:30'))
        self.assertTrue(result['follow_up'])
        self.assertEqual(len(result['suggestions']),3)

    def test_no_overlap_with_events_or_buffer(self):
        for block in self.answer('I have four hours')['plan']['blocks']:
            a,b=datetime.fromisoformat(block['start']),datetime.fromisoformat(block['end'])
            for event in self.cal['events']:
                busy_start=datetime.fromisoformat(event['start'])-timedelta(minutes=15)
                busy_end=datetime.fromisoformat(event['end'])+timedelta(minutes=15)
                self.assertTrue(b<=busy_start or a>=busy_end)

    def test_budget_breaks_and_focus_limit(self):
        result=self.answer('I have four hours')['plan']
        self.assertLessEqual(result['scheduled_minutes'],240)
        self.assertEqual(result['scheduled_minutes'],sum(b['minutes'] for b in result['blocks']))
        ordered=sorted(result['blocks'],key=lambda b:b['start'])
        for block in ordered:
            self.assertLessEqual(block['minutes'],50)
        for a,b in zip(ordered,ordered[1:]):
            self.assertGreaterEqual(datetime.fromisoformat(b['start'])-datetime.fromisoformat(a['end']),timedelta(minutes=10))

    def test_no_blocks_after_deadline_and_hours(self):
        for b in self.answer('I have ten hours')['plan']['blocks']:
            end=datetime.fromisoformat(b['end'])
            self.assertLessEqual(end.date().isoformat(),b['due_date'])
            self.assertGreaterEqual(datetime.fromisoformat(b['start']).hour,8)
            self.assertLessEqual(end.hour,22)

    def test_zero_does_not_schedule(self):
        self.assertEqual(self.answer('I have zero hours')['plan']['blocks'],[])

    def test_clarification_has_no_invented_budget(self):
        result=self.answer('When can I study?')
        self.assertIsNone(result['plan'])
        self.assertIsNone(result['minutes'])

    def test_stale_snapshot_does_not_offer_windows(self):
        cal={**self.cal,'mode':'personal','synced_at':'2026-11-14T09:30:00-05:00'}
        with patch('taskpilot.calendar_planner.calendar_snapshot',return_value=cal):
            result=enrich_answer(answer_question('one hour',self.data),self.data,'personal',now=self.now)
        self.assertIn('stale',result['calendar']['notice'])
        self.assertNotIn('windows',result['calendar'])

    def test_all_day_busy_blocks_entire_day(self):
        cal={**self.cal,'events':[dict(title='Busy',start='2026-11-16T00:00:00-05:00',end='2026-11-17T00:00:00-05:00')]}
        windows=free_windows(cal,preferences(),self.now)
        self.assertTrue(all(a.date().isoformat()>'2026-11-16' for a,b in windows))

    def test_after_work_respects_requested_anchor(self):
        result=enrich_answer(answer_question('one hour',self.data),self.data,'demo',message='I have one hour after work')
        self.assertTrue(result['plan']['blocks'][0]['start'].startswith('2026-11-16T17:15'))
        self.assertIn('Work shift',result['answer'])

    def test_unknown_work_event_is_not_inferred(self):
        cal={**self.cal,'events':[]}
        with patch('taskpilot.calendar_planner.calendar_snapshot',return_value=cal):
            result=enrich_answer(answer_question('one hour',self.data),self.data,'demo',message='after work')
        self.assertIsNone(result['plan'])
        self.assertEqual(result['kind'],'clarification')

    def test_invalid_preferences(self):
        for prefs in ({'start_hour':22,'end_hour':8},{'buffer':-1},{'block_minutes':True},{'break_minutes':100}):
            with self.subTest(prefs=prefs),self.assertRaises(ValueError):
                preferences(prefs)

    def test_demo_is_independent_of_private_calendar(self):
        with patch('pathlib.Path.read_text',side_effect=AssertionError('must not read personal data')):
            self.assertEqual(calendar_snapshot('demo',self.now.date())['events'][0]['title'],'Morning class')
