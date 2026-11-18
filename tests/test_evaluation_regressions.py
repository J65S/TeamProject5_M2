"""Regression checks for failures in the saved first M4 evaluation.

These are engineering checks, not a replacement score for the live evaluation.
"""
from datetime import datetime
from pathlib import Path
import unittest

from taskpilot.ai_chat import prepare_plan, validate_intent
from taskpilot.calendar_planner import calendar_snapshot, preferences
from taskpilot.grounding import ground_intent, answer_facts, check_answer_facts
from taskpilot.workload import load_assignments

ROOT = Path(__file__).resolve().parents[1]


class EvaluationRegressions(unittest.TestCase):
    def setUp(self):
        self.data = load_assignments(ROOT/'evaluation/fixtures/m3_original', '2026-10-27')
        for task in self.data['assignments']:
            if task['due_date'] < self.data['today']:
                task['status'] = 'completed'
        self.calendar = calendar_snapshot('demo', datetime.fromisoformat(self.data['today']).date())
        self.raw = dict(action='plan', minutes=240, after_last_event=True,
                        not_before='2026-10-27T17:00:00-04:00', day='2026-10-28',
                        task_ids=[self.data['assignments'][-1]['id']], restrict_tasks=True)

    def intent(self, message, **kwargs):
        payload = dict(message=message, data=self.data, **kwargs)
        return validate_intent(ground_intent(self.raw, payload, self.calendar), self.data)

    def plan(self, message, **kwargs):
        intent = self.intent(message, **kwargs)
        return intent, prepare_plan(intent, self.data, 'demo', {})

    def test_tc01_no_invented_after_work_scope_or_tomorrow(self):
        intent, verified = self.plan('I have 4 hours to study today. What should I work on?')
        self.assertFalse(intent['after_last_event'])
        self.assertFalse(intent['restrict_tasks'])
        self.assertIsNone(intent['not_before'])
        self.assertEqual(intent['day'], '2026-10-27')
        blocks = verified['plan']['blocks']
        self.assertTrue(blocks[0]['start'].startswith('2026-10-27T10:30'))
        self.assertTrue(all(b['start'][:10] == '2026-10-27' for b in blocks))
        self.assertLessEqual(verified['plan']['elapsed_minutes'], 240)
        self.assertTrue(verified['plan']['shorter_window'])

    def test_tc02_breaks_fit_inside_one_hour(self):
        _, verified = self.plan('I only have 1 hour available today.')
        plan = verified['plan']
        start, end = (datetime.fromisoformat(b[k]) for b,k in [(plan['blocks'][0],'start'),(plan['blocks'][-1],'end')])
        self.assertLessEqual((end-start).total_seconds()/60, 60)
        self.assertEqual(plan['elapsed_minutes'], plan['scheduled_minutes'] + plan['break_minutes'])
        self.assertEqual(plan['scheduled_minutes'], 50)

    def test_tc04_missing_availability_reaches_ai_clarification(self):
        intent, verified = self.plan('Help me plan my assignments.')
        self.assertEqual(intent['action'], 'clarify')
        self.assertIsNone(intent['minutes'])
        self.assertIsNone(verified['plan'])
        check_answer_facts('How much time do you have available?', intent, answer_facts(intent,self.data,verified))

    def test_tc05_all_eleven_hours_remain_accounted_for(self):
        self.data = load_assignments(ROOT/'evaluation/fixtures/conflicting', '2026-10-27')
        intent, verified = self.plan('I have 3 hours today, and multiple assignments are due soon. How should I prioritize?')
        facts = answer_facts(intent, self.data, verified)
        self.assertEqual(facts['total_work_minutes'], 660)
        self.assertIn('11 hours', facts['required_answer_phrases'])
        self.assertEqual(sum(t['remaining_minutes'] for t in verified['plan']['unfinished']), 660-verified['plan']['scheduled_minutes'])
        self.assertEqual(len(verified['plan']['unfinished']), 2)
        self.assertFalse(intent['restrict_tasks'])
        self.assertEqual(verified['plan']['blocks'][0]['task'], 'Three-hour assignment')
        risks = answer_facts(intent,self.data,verified,self.calendar,preferences())['deadline_risks']
        self.assertEqual(risks[0]['optimistic_free_minutes'],630)
        self.assertEqual(risks[0]['shortfall_at_least_minutes'],30)

    def test_tc07_inventory_includes_added_poster_with_due_date(self):
        self.data = load_assignments(ROOT/'evaluation/fixtures/retrieval', '2026-10-27')
        for t in self.data['assignments']:
            if t['due_date'] < self.data['today']: t['status'] = 'completed'
        intent, verified = self.plan('I have 2 hours today. What upcoming assignments do I have?')
        self.assertEqual(intent['request_kind'], 'inventory')
        self.assertIsNone(verified['plan'])
        facts = answer_facts(intent,self.data,verified)
        self.assertIn('Prepare TaskPilot poster', facts['required_answer_phrases'])
        self.assertIn('2026-11-15', facts['required_answer_phrases'])
        with self.assertRaises(ValueError):
            check_answer_facts('Just work on trees today.', intent, facts)

    def test_tc08_new_budget_replaces_old_without_inheriting_model_constraint(self):
        initial = self.intent('I have 4 hours today.')
        intent, verified = self.plan('I now only have 2 hours instead of 4. Please plan using my new availability.',
                                     context=initial, history=[{'role':'user','content':'I have 4 hours today.'}])
        self.assertEqual(intent['minutes'], 120)
        self.assertFalse(intent['after_last_event'])
        self.assertLessEqual(verified['plan']['elapsed_minutes'],120)

    def test_tc09_total_and_remaining_are_computed_not_guessed(self):
        intent, verified = self.plan('I have 1 hour today. Can I finish all my upcoming assignments?')
        facts = answer_facts(intent, self.data, verified)
        self.assertEqual(facts['total_work_minutes'], 3780)
        self.assertEqual(facts['remaining_work_minutes'], 3730)
        self.assertFalse(facts['can_finish_all'])
        with self.assertRaises(ValueError):
            check_answer_facts('You have many more hours left.', intent, facts)
        check_answer_facts('No, you have 63 hours of estimated work. This session has 50 minutes of focus, leaving 62 hours 10 minutes of work and 10 minutes unused in your available hour.', intent, facts)

    def test_explicit_scope_keeps_global_backlog(self):
        task = next(t for t in self.data['assignments'] if t.get('status') != 'completed')
        intent, verified = self.plan(f"I have 1 hour. Only work on {task['task']}.")
        self.assertTrue(intent['restrict_tasks'])
        self.assertTrue(all(b['task_id'] == task['id'] for b in verified['plan']['blocks']))
        self.assertGreater(len(verified['plan']['unfinished']),1)

    def test_real_end_of_day_request_survives_followup(self):
        initial = self.intent('I have 1 hour today.')
        intent, verified = self.plan('Start when im done with my day', context=initial,
                                     history=[{'role':'user','content':'I have 1 hour today.'}])
        self.assertTrue(intent['after_last_event'])
        self.assertEqual(intent['minutes'],60)
        self.assertTrue(verified['plan']['blocks'][0]['start'].startswith('2026-10-27T20:15'))

    def test_after_work_anchor_comes_from_actual_event(self):
        intent, verified = self.plan('I have 1 hour after work today.')
        self.assertEqual(intent['not_before'],'2026-10-27T17:00:00-04:00')
        self.assertTrue(verified['plan']['blocks'][0]['start'].startswith('2026-10-27T17:15'))

    def test_zero_is_preserved_not_missing(self):
        intent, verified = self.plan('I have 0 hours available today.')
        self.assertEqual(intent['minutes'],0)
        self.assertFalse(verified['plan']['blocks'])

    def test_false_only_available_window_claim_is_rejected(self):
        intent, verified = self.plan('I have one hour today.')
        facts = answer_facts(intent,self.data,verified)
        reply = ' '.join(facts['required_answer_phrases']) + '. This is your only free window.'
        with self.assertRaises(ValueError): check_answer_facts(reply,intent,facts)

    def test_clarification_cannot_add_after_last_event(self):
        intent, verified = self.plan('Help me plan my assignments.')
        with self.assertRaises(ValueError):
            check_answer_facts('How many minutes can you study after your last event?',intent,answer_facts(intent,self.data,verified))

    def test_ambiguous_or_negative_update_does_not_restore_old_time(self):
        for message in ('I have 30 minutes or 2 hours available.', 'I have -1 hour.'):
            intent, verified = self.plan(message,history=[{'role':'user','content':'I have 4 hours.'}])
            self.assertEqual(intent['action'],'clarify')
            self.assertIsNone(intent['minutes'])
            self.assertIsNone(verified['plan'])

    def test_numerically_equivalent_duration_units_are_accepted(self):
        facts={'required_answer_phrases':['1 hour 5 minutes','1 hour 15 minutes','1 hour 45 minutes unused']}
        check_answer_facts('65 minutes of focus in 75 minutes, leaving 105 minutes unused.',{'action':'answer'},facts)

    def test_wrong_duration_or_unused_arithmetic_is_rejected(self):
        facts={'required_answer_phrases':['1 hour 5 minutes','1 hour 45 minutes unused']}
        with self.assertRaises(ValueError):
            check_answer_facts('65 minutes of focus, leaving 65 minutes unused.',{'action':'answer'},facts)
