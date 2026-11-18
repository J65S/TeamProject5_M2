from datetime import datetime
import json
import unittest
from unittest.mock import AsyncMock, patch
from taskpilot.ai_chat import validate_intent, prepare_plan, check_time_ranges
from taskpilot.conversation import example_week
from tests import test_web_app


class AIContractTests(unittest.TestCase):
    def setUp(self):
        self.data=example_week('2026-11-16')
        self.intent=dict(action='plan',minutes=60,after_last_event=True,not_before=None,day=None,task_ids=[],summary='Start after the last event today')

    def test_end_of_day_is_after_last_event_not_first_gap(self):
        plan=prepare_plan(validate_intent(self.intent,self.data),self.data,'demo',{})['plan']
        self.assertTrue(plan['blocks'][0]['start'].startswith('2026-11-16T20:15'))
        self.assertEqual(plan['scheduled_minutes'],50)
        self.assertEqual(plan['elapsed_minutes'],60)
        self.assertEqual(plan['break_minutes'],10)

    def test_task_suggestion_does_not_silently_restrict_budget(self):
        intent={**self.intent,'after_last_event':False,'task_ids':['demo-1']}
        intent=validate_intent(intent,self.data)
        plan=prepare_plan(intent,self.data,'demo',{})['plan']
        self.assertEqual(plan['scheduled_minutes'],50)
        self.assertEqual(plan['elapsed_minutes'],60)
        self.assertEqual(len({b['task_id'] for b in plan['blocks']}),2)
        intent['restrict_tasks']=True
        limited=prepare_plan(intent,self.data,'demo',{})['plan']
        self.assertEqual(limited['scheduled_minutes'],45)

    def test_optional_boolean_representations_are_normalized_safely(self):
        for raw,expected in [(None,False),('false',False),('False',False),('true',True),('',False)]:
            with self.subTest(raw=raw):
                intent=validate_intent({**self.intent,'after_last_event':raw,'restrict_tasks':None},self.data)
                self.assertIs(intent['after_last_event'],expected)
                self.assertIs(intent['restrict_tasks'],False)
        for raw in ('tomorrow',[],1):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                validate_intent({**self.intent,'after_last_event':raw},self.data)

    def test_explicit_time_constraint(self):
        self.intent.update(after_last_event=False,not_before='2026-11-16T21:00:00-05:00')
        plan=prepare_plan(self.intent,self.data,'demo',{})['plan']
        self.assertTrue(all(datetime.fromisoformat(b['start'])>=datetime.fromisoformat('2026-11-16T21:00:00-05:00') for b in plan['blocks']))

    def test_unknown_task_and_missing_budget_are_rejected(self):
        for update in ({'task_ids':['invented']},{'minutes':None},{'minutes':True},{'not_before':'2026-11-16T20:00:00'}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                validate_intent({**self.intent,**update},self.data)

    def test_hallucinated_event_range_is_rejected(self):
        snapshot={'calendar': {'events':[{'start':'2026-11-16T19:00:00-05:00','end':'2026-11-16T20:00:00-05:00'}]}}
        with self.assertRaises(ValueError):
            check_time_ranges('After the 8:00‑9:00 PM study group',snapshot,{})
        check_time_ranges('After the 7:00–8:00 PM study group',snapshot,{})

    def test_clarification_does_not_create_plan(self):
        self.intent.update(action='clarify',minutes=None)
        self.assertIsNone(prepare_plan(self.intent,self.data,'demo',{})['plan'])

    def test_ai_endpoint_calls_agents_with_history(self):
        harness=test_web_app.WebAPITests(); harness.setUp()
        try:
            reply={'answer':'An actual model answer','minutes':60,'context':self.intent,'plan':None,'engine':'two_agent_ai'}
            mock=AsyncMock(return_value=reply)
            history=[{'role':'user','content':'I have an hour'}]
            with patch('taskpilot.web_app.run_ai_chat',mock):
                status,body,_=harness.request('/api/chat',{'message':'after my day','context':{'minutes':60},'history':history})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['engine'],'two_agent_ai')
            self.assertEqual(mock.call_args.args[0]['history'],history)
            self.assertEqual(mock.call_args.args[0]['context']['minutes'],60)
        finally:
            harness.doCleanups()

    def test_ai_failure_has_no_template_fallback(self):
        harness=test_web_app.WebAPITests(); harness.setUp()
        try:
            with patch('taskpilot.web_app.run_ai_chat',AsyncMock(side_effect=RuntimeError('provider failed'))):
                status,body,_=harness.request('/api/chat',{'message':'I have an hour'})
            self.assertEqual(status,503)
            result=json.loads(body)
            self.assertEqual(result['engine'],'ai_unavailable')
            self.assertNotIn('plan',result)
            self.assertNotIn('answer',result)
        finally:
            harness.doCleanups()
