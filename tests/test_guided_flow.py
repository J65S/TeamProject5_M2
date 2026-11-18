import asyncio
import copy
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from taskpilot.ai_chat import prepare_plan, run_ai_chat, validate_intent
from taskpilot.calendar_planner import calendar_snapshot
from taskpilot.conversation import example_week
from taskpilot.flow import remember_confirmation, confirmation_reply
from taskpilot.grounding import ground_intent, answer_facts, check_answer_facts, vague_hours


class GuidedFlowTests(TestCase):
    def setUp(self):
        self.data=example_week('2026-11-17')
        self.payload=dict(message='I have 3 hours today',data=self.data,calendar_mode='demo',preferences={},context={},history=[])
        self.calendar=calendar_snapshot('demo',datetime.fromisoformat(self.data['today']).date())

    def intent(self,message,**context):
        return validate_intent(ground_intent(dict(action='answer',minutes=None),{**self.payload,'message':message,'context':context},self.calendar),self.data)

    def remembered(self):
        result=dict(answer='Start at 10:30.',model='gpt-oss',plan={'blocks':[{'task':'Reading response'}]},
                    acceptance_text='Sounds good—start with the reading response, one paragraph at a time.',
                    context={'minutes':180},evidence={'critic_passed':True})
        return remember_confirmation(result,self.payload)

    def test_vague_hours_with_typo_asks_for_precision(self):
        self.assertTrue(vague_hours({**self.payload,'message':'I have a few hourz today, what work should I get done?'}))
        self.assertFalse(vague_hours(self.payload))
        self.assertEqual(self.intent('I have a few hourz today, what work should I get done?')['action'],'clarify')

    def test_bare_answer_to_hours_question_and_followup_guidance(self):
        self.assertEqual(self.intent('three',awaiting='hours')['minutes'],180)
        self.assertEqual(self.intent('Can you help me figure that out')['action'],'clarify')
        self.assertEqual(self.intent('I have 3 hours figure it out')['action'],'plan')

    def test_confirmation_uses_reviewed_ai_text_without_worker(self):
        result=self.remembered()
        payload={**self.payload,'message':'Yeah that works','context':result['context']}
        with patch('taskpilot.ai_chat.asyncio.create_subprocess_exec',side_effect=AssertionError('No new planning cycle')):
            accepted=asyncio.run(run_ai_chat(payload))
        self.assertEqual(accepted['answer'],result['acceptance_text'])
        self.assertFalse(accepted['evidence']['new_inference'])
        self.assertNotIn('confirmation',accepted['context'])

    def test_edited_or_stale_or_changed_source_confirmation_is_rejected(self):
        result=self.remembered()
        for variation in ('edited','expired','source','new_request'):
            payload=copy.deepcopy({**self.payload,'message':'yes','context':result['context']})
            if variation=='edited': payload['context']['confirmation']['text']='Invented reply'
            if variation=='expired':
                with patch('taskpilot.flow.time.time',return_value=10**12): self.assertIsNone(confirmation_reply(payload))
                continue
            if variation=='source': payload['data']['assignments'][0]['estimated_minutes']=999
            if variation=='new_request': payload['message']='yes but start after work'
            self.assertIsNone(confirmation_reply(payload))

    def test_next_opening_is_offered_from_verified_calendar(self):
        intent=self.intent('I have three hours. What should I work on?')
        verified=prepare_plan(intent,self.data,'demo',{})
        self.assertTrue(answer_facts(intent,self.data,verified)['next_opening']['start'].startswith('2026-11-17T17:15'))

    def test_explicit_another_opening_updates_same_day_plan_with_breaks(self):
        intent=self.intent('Use another opening today',max_windows=1)
        # Retain the actual availability from prior user history.
        payload={**self.payload,'message':'Use another opening today','history':[{'role':'user','content':'I have 3 hours today'}]}
        intent=validate_intent(ground_intent({'action':'plan'},payload,self.calendar),self.data)
        plan=prepare_plan(intent,self.data,'demo',{})['plan']
        self.assertTrue(plan['split_confirmed'])
        self.assertEqual(intent['max_windows'],2)
        self.assertLessEqual(plan['elapsed_minutes'],180)
        self.assertEqual(plan['elapsed_minutes'],plan['scheduled_minutes']+plan['break_minutes'])
        self.assertGreater(plan['calendar_span_minutes'],plan['elapsed_minutes'])
        self.assertTrue(all(b['start'][:10]=='2026-11-17' for b in plan['blocks']))

    def test_clarification_cannot_dump_backlog_or_delegate_priority(self):
        intent={'action':'clarify','minutes':None}
        facts={'required_answer_phrases':[]}
        for reply in ('You have hours of work. Which assignment seems most urgent?', 'many '*60+'How many minutes?'):
            with self.assertRaises(ValueError): check_answer_facts(reply,intent,facts)

    def test_hour_reply_budget_survives_later_opening_request(self):
        intent=self.intent('Use another opening today',minutes=180,_grounded=True)
        self.assertEqual(intent['minutes'],180)
        self.assertEqual(intent['action'],'plan')

    def test_missing_ai_greeting_reuses_checked_instruction(self):
        result=self.remembered()
        result['context'].pop('confirmation')
        result.update(acceptance_text='',answer='Start with Reading response. Take it one paragraph at a time.')
        result=remember_confirmation(result,self.payload)
        accepted=confirmation_reply({**self.payload,'message':'yes','context':result['context']})
        self.assertEqual(accepted['answer'],'Sounds good. Start with Reading response.')

    def test_confirmation_does_not_claim_agent_will_do_student_work(self):
        result=self.remembered()
        result.update(acceptance_text='Got it, I’ll start studying.',answer='Start with Reading response.')
        result=remember_confirmation(result,self.payload)
        accepted=confirmation_reply({**self.payload,'message':'yes','context':result['context']})
        self.assertNotIn('I’ll',accepted['answer'])

    def test_invalid_precise_budget_is_not_misrouted_to_fuzzy_question(self):
        self.assertFalse(vague_hours({**self.payload,'message':'I have -1 hour'}))
        self.assertFalse(vague_hours({**self.payload,'message':'I have 3 hours, not a few hours'}))

    def test_ai_followup_question_is_preserved_without_app_duplicate(self):
        result=self.remembered()
        result['answer']='Start with Reading response at 10:30. Does that sound good?'
        result=remember_confirmation(result,self.payload)
        self.assertEqual(result['answer'],'Start with Reading response at 10:30. Does that sound good?')
        self.assertEqual(result['follow_up'],'')
