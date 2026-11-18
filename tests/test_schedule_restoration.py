from copy import deepcopy
from datetime import datetime
import json
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from taskpilot.ai_chat import validate_intent, prepare_plan
from taskpilot.calendar_planner import calendar_snapshot, preferences
from taskpilot.checked_reply import compose_reply
from taskpilot.conversation import example_week
from taskpilot.grounding import availability, ground_intent, with_user_progress, answer_facts


class ScheduleRestorationTests(TestCase):
    def setUp(self):
        self.data=example_week('2026-11-17')
        self.calendar=calendar_snapshot('demo',datetime(2026,11,17).date())

    def turn(self,message,context=None,analyst=None):
        context=context or {}
        data=with_user_progress(self.data,context.get('completed_task_ids',[]))
        parsed=analyst or {'action':'clarify','minutes':None}
        intent=validate_intent(ground_intent(parsed,dict(message=message,data=data,context=context),self.calendar),data)
        data=with_user_progress(data,intent['completed_task_ids'])
        verified=prepare_plan(intent,data,'demo',{})
        if (verified.get('plan') or {}).get('blocks'):
            intent['focus_task_id']=verified['plan']['blocks'][0]['task_id']
        return intent,data,verified

    def test_typo_request_generates_same_real_schedule_as_normal_request(self):
        normal,_,a=self.turn('I have 3 hours today. What should I work on?')
        typo,_,b=self.turn('I haev 3 hourz today what should i work on')
        self.assertEqual(normal['minutes'],180)
        self.assertEqual(typo['minutes'],180)
        self.assertEqual(a['plan']['blocks'],b['plan']['blocks'])
        self.assertTrue(b['plan']['blocks'])
        self.assertLessEqual(b['plan']['elapsed_minutes'],typo['minutes'])

    def test_quote_supports_unfamiliar_availability_but_not_invented_time(self):
        message="I've got ninety minutes to spare"
        intent,_,verified=self.turn(message,analyst=dict(action='plan',minutes=90,availability_quote=message))
        self.assertEqual(intent['minutes'],90)
        self.assertTrue(verified['plan']['blocks'])
        for quote in ('I have 4 hours', 'ninety minutes'):
            intent,_,_=self.turn(message,analyst=dict(action='plan',minutes=240,availability_quote=quote))
            self.assertEqual(intent['action'],'clarify')
        previous,_,_=self.turn('I have 3 hours today')
        updated,_,_=self.turn(message,previous,dict(action='clarify',minutes=90,availability_quote=message))
        self.assertEqual(updated['minutes'],90)
        self.assertEqual(updated['action'],'plan')
        intent,_,_=self.turn('This assignment takes 90 minutes',analyst=dict(action='plan',minutes=90,availability_quote='This assignment takes 90 minutes'))
        self.assertIsNone(intent['minutes'])

    def test_time_and_day_followups_preserve_budget_and_assignments(self):
        first,_,_=self.turn('I haev 3 hours today what should i work on')
        shorter,_,second=self.turn('I only have two hours',first)
        self.assertEqual(shorter['minutes'],120)
        tomorrow,_,third=self.turn('move this to tomorrow',shorter)
        self.assertEqual(tomorrow['minutes'],120)
        self.assertEqual(tomorrow['day'],'2026-11-18')
        self.assertTrue(all(b['start'].startswith('2026-11-18') for b in third['plan']['blocks']))
        self.assertLessEqual(second['plan']['elapsed_minutes'],120)
        self.assertLessEqual(third['plan']['elapsed_minutes'],120)
        self.assertEqual(self.data['assignments'][0]['due_date'],'2026-11-17')

    def test_completed_focus_is_removed_only_after_explicit_report(self):
        original=deepcopy(self.data)
        first,_,_=self.turn('I have 3 hours, help me plan')
        done,data,verified=self.turn('I already finished that',first)
        self.assertIn(first['focus_task_id'],done['completed_task_ids'])
        self.assertTrue(all(b['task_id']!=first['focus_task_id'] for b in verified['plan']['blocks']))
        updated,_,next_plan=self.turn('I only have two hours',done)
        self.assertIn(first['focus_task_id'],updated['completed_task_ids'])
        self.assertTrue(all(b['task_id']!=first['focus_task_id'] for b in next_plan['plan']['blocks']))
        self.assertEqual(self.data,original)
        self.assertEqual(next(t for t in data['assignments'] if t['id']==first['focus_task_id'])['progress_source'],'user report in conversation')

    def test_negated_or_partial_completion_is_not_marked_complete(self):
        first,_,_=self.turn('I have 3 hours, help me plan')
        for message in ('I have not finished that','I almost finished that','I finished half of that'):
            intent,_,_=self.turn(message,first)
            self.assertFalse(intent['completed_task_ids'])

    def test_unknown_completion_asks_a_focused_question(self):
        intent,_,result=self.turn('I already finished that')
        self.assertEqual(intent['action'],'clarify')
        self.assertEqual(intent['clarification_reason'],'Which assignment did you finish?')
        self.assertIsNone(result['plan'])
        intent,_,_=self.turn('I already finished that',analyst=dict(action='plan',minutes=None,task_ids=['demo-1']))
        self.assertEqual(intent['action'],'clarify')
        self.assertFalse(intent['completed_task_ids'])

    def test_actual_schedule_is_visible_even_with_a_conversational_question(self):
        intent,data,verified=self.turn('I have 3 hours today')
        facts=answer_facts(intent,data,verified)
        answer=compose_reply('Start with the reading response. Does that sound good?',intent,verified,facts)
        self.assertIn('Study schedule (America/New_York)',answer)
        self.assertIn('Tue, Nov 17 2026 · 10:30 AM',answer)
        self.assertIn('Reading response (45 minutes)',answer)
        self.assertIn('Break (10 minutes)',answer)
        self.assertIn('1 hour 45 minutes',answer)

    def test_deadline_shortfall_is_flagged_and_never_scheduled_late(self):
        self.data['assignments']=self.data['assignments'][:1]
        task=self.data['assignments'][0]
        task.update(estimated_minutes=120,due_at='2026-11-17T10:45:00-05:00')
        intent,data,verified=self.turn('I have three hours, help me plan')
        facts=answer_facts(intent,data,verified,self.calendar,preferences())
        self.assertEqual(verified['plan']['scheduled_minutes'],15)
        self.assertEqual(facts['deadline_risks'][0]['shortfall_at_least_minutes'],105)
        self.assertTrue(all(b['end']<=task['due_at'] for b in verified['plan']['blocks']))
        self.assertIn('Deadline risk:',compose_reply('Start with your reading.',intent,verified,facts))

    def test_dashboard_response_keeps_conversation_progress_snapshot(self):
        from tests import test_web_app
        harness=test_web_app.WebAPITests();harness.setUp()
        snapshot=with_user_progress(self.data,['demo-1'])
        try:
            with patch('taskpilot.web_app.run_ai_chat',AsyncMock(return_value=dict(answer='Updated schedule',context={'completed_task_ids':['demo-1']},assignment_snapshot=snapshot))):
                status,body,_=harness.request('/api/chat',{'message':'I already finished that','source':'demo'})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['assignment_snapshot']['assignments'][0]['status'],'completed')
        finally:
            harness.doCleanups()
