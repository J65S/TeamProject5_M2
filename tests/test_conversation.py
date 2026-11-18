"""Student-facing questions must stay grounded and avoid guessed availability."""
import unittest
from taskpilot.conversation import answer_question, example_week
from taskpilot.workload import make_plan, parse_minutes


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.data = example_week('2026-11-16')

    def ask(self, message, previous=None):
        return answer_question(message, self.data, previous)

    def test_demo_is_small_and_reproducible(self):
        self.assertEqual(self.data, example_week('2026-11-16'))
        self.assertEqual(len(self.data['assignments']), 6)
        self.assertFalse(any(t['overdue'] for t in self.data['assignments']))

    def test_plain_language_time(self):
        for question, expected in [('I have an hour', 60), ('I have two hours', 120),
                                   ('half an hour', 30), ('an hour and a half', 90),
                                   ('forty-five minutes', 45), ('30 mins', 30)]:
            with self.subTest(question=question):
                self.assertEqual(self.ask(question)['plan']['scheduled_minutes'], expected)

    def test_missing_availability_then_followup(self):
        result = self.ask('I’m overwhelmed. Where do I start?')
        self.assertEqual(result['kind'], 'clarification')
        self.assertIsNone(result['plan'])
        self.assertEqual(self.ask('one hour')['minutes'], 60)

    def test_remembers_explicit_time(self):
        self.assertEqual(self.ask('Can I finish all my work?', 60)['minutes'], 60)

    def test_updated_budget_not_added_to_old(self):
        self.assertEqual(self.ask('I now only have two hours instead of four hours', 240)['minutes'], 120)

    def test_due_tomorrow_factual_answer(self):
        result = self.ask('What assignments are due tomorrow?')
        self.assertEqual(result['kind'], 'overview')
        self.assertIn('Graph traversal practice', result['answer'])
        self.assertIn('Project outline', result['answer'])
        self.assertNotIn('Reading response', result['answer'])
        self.assertIsNone(result['plan'])

    def test_zero_time(self):
        result = self.ask('I have no time today')
        self.assertEqual(result['plan']['blocks'], [])
        self.assertEqual(result['plan']['scheduled_minutes'], 0)
        self.assertIn('haven’t scheduled', result['answer'])
        self.assertEqual(parse_minutes('0 hours'), 0)
        self.assertEqual(make_plan(self.data, 0)['scheduled_minutes'], 0)

    def test_ambiguous_or_negative_time_not_replaced_with_old_budget(self):
        for question in ('I have -1 hours', '1 or 2 hours', '25 hours', 'I have some hours'):
            with self.subTest(question=question):
                self.assertIsNone(self.ask(question, 60)['plan'])

    def test_future_session_is_not_scheduled_as_today(self):
        self.assertIsNone(self.ask('I have 2 hours tomorrow', 60)['plan'])

    def test_remaining_work_and_partial_blocks(self):
        result = self.ask('I have one hour. Can I finish everything?')
        plan = result['plan']
        self.assertEqual([b['minutes'] for b in plan['blocks']], [45, 15])
        self.assertEqual(sum(t['remaining_minutes'] for t in plan['unfinished']), 495)
        self.assertIn('8h 15m', result['answer'])

    def test_unrelated_question_does_not_invent_an_answer(self):
        self.assertIsNone(self.ask('Who won the baseball game?', 60)['plan'])

    def test_total_workload(self):
        result = self.ask('How much work do I have in total?')
        self.assertEqual(result['kind'], 'overview')
        self.assertIn('9h 15m', result['answer'])

    def test_bad_request_and_missing_source(self):
        for message in ('', None, 123, 'x' * 2001):
            with self.subTest(message=str(message)[:20]), self.assertRaises(ValueError):
                self.ask(message)
        with self.assertRaises(ValueError):
            self.ask('help', True)
        result = answer_question('one hour', {'error': 'missing'})
        self.assertEqual(result['kind'], 'unavailable')
        self.assertIsNone(result['plan'])
