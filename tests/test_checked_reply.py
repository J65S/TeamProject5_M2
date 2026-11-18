from datetime import datetime
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from taskpilot.ai_chat import prepare_plan, validate_intent, safe_error, record_failure
from taskpilot.calendar_planner import calendar_snapshot
from taskpilot.checked_reply import ReplyValidationError, validate_guidance, compose_reply
from taskpilot.conversation import example_week
from taskpilot.grounding import availability, ground_intent, answer_facts


class CheckedReplyTests(TestCase):
    def setUp(self):
        self.data=example_week('2026-11-17')
        self.cal=calendar_snapshot('demo',datetime(2026,11,17).date())

    def planned(self,message,**kwargs):
        payload=dict(message=message,data=self.data,**kwargs)
        intent=validate_intent(ground_intent({'action':'clarify','minutes':None},payload,self.cal),self.data)
        verified=prepare_plan(intent,self.data,'demo',{})
        return intent,verified,answer_facts(intent,self.data,verified)

    def test_or_no_is_not_an_alternative_duration(self):
        self.assertEqual(availability('I have 3 hours can you help me or no?'),180)
        for bad in ('I have 30 minutes or 2 hours','I have 1 or 2 hours'):
            with self.assertRaises(ValueError): availability(bad)

    def test_exact_user_request_selects_next_slot_without_more_questions(self):
        intent,verified,_=self.planned('I have 3 hours can you help me or no?')
        self.assertEqual(intent['action'],'plan')
        self.assertEqual(intent['minutes'],180)
        self.assertTrue(verified['plan']['blocks'][0]['start'].startswith('2026-11-17T10:30'))

    def test_next_free_overrides_model_and_previous_after_work_constraint(self):
        intent,verified,_=self.planned('Whenever i havve time next',
            context={'_grounded':True,'minutes':180,'after_last_event':True,'not_before':'2026-11-17T17:00:00-05:00'},
            history=[{'role':'user','content':'I have 3 hours can you help me or no?'}])
        self.assertEqual(intent['action'],'plan')
        self.assertFalse(intent['after_last_event'])
        self.assertIsNone(intent['not_before'])
        self.assertTrue(verified['plan']['blocks'][0]['start'].startswith('2026-11-17T10:30'))

    def test_failed_user_request_history_still_supplies_availability(self):
        intent,verified,_=self.planned('Whenever i havve time next',history=[{'role':'user','content':'I have 3 hours can you help me or no?'}])
        self.assertEqual(intent['minutes'],180)
        self.assertTrue(verified['plan']['blocks'])

    def test_ai_reply_is_preserved_and_plan_facts_remain_available(self):
        intent,verified,facts=self.planned('I have 3 hours can you help me or no?')
        block=verified['plan']['blocks'][0]
        guidance={'task_id':block['task_id'],'guidance':'Start with the reading response. Read the prompt and outline your main point.'}
        validate_guidance(guidance,intent,verified)
        text=compose_reply(guidance['guidance'],intent,verified,facts)
        self.assertTrue(text.startswith(guidance['guidance']))
        self.assertIn('Study schedule (America/New_York)',text)
        self.assertIn('Tue, Nov 17 2026 · 10:30 AM',text)
        self.assertTrue(verified['plan']['blocks'])
        self.assertEqual(verified['plan']['unused_minutes'],105)

    def test_unknown_task_reference_is_rejected(self):
        intent,verified,_=self.planned('I have three hours. Plan my work.')
        with self.assertRaises(ReplyValidationError): validate_guidance({'task_id':'bad','guidance':'Start here.'},intent,verified)

    def test_questions_and_numbers_do_not_block_ai_response(self):
        intent,verified,facts=self.planned('I have three hours. Plan my work.')
        target=verified['plan']['blocks'][0]['task_id']
        for text in ('Start at 10:30 AM. Does that sound good?', 'Spend 45 minutes on the first task, then take a break.', 'Does kicking off with that comparison sound good to you?'):
            validate_guidance({'task_id':target,'guidance':text},intent,verified)
            self.assertTrue(compose_reply(text,intent,verified,facts).startswith(text))

    def test_both_actual_rejected_drafts_can_be_delivered(self):
        intent,verified,_=self.planned('I have 3 hours help me plan')
        target=verified['plan']['blocks'][0]['task_id']
        drafts=[
            'Starting with the Trees and heaps quiz prep is a solid move since it’s upcoming and you’ve got a clear first step. Beginning by comparing a binary search tree with a binary heap will get your mind into the right shape for the rest of the review. How many minutes do you think you can set aside for that first comparison?',
            'The Trees and heaps quiz prep is a great place to begin—you have a clear first step and the deadline is coming up. Starting by comparing a binary search tree with a binary heap will warm you up for the rest of the material. Does kicking off with that comparison sound good to you?']
        for draft in drafts: validate_guidance({'task_id':target,'guidance':draft},intent,verified)

    def test_failure_explains_its_check_and_local_log_excludes_provider_secrets(self):
        error=ReplyValidationError('wrong_task','internal issue')
        self.assertIn('Check: wrong_task',safe_error(error,'answer validation'))
        with tempfile.TemporaryDirectory() as folder,patch('taskpilot.ai_chat.PROJECT_ROOT',Path(folder)):
            name=record_failure({'_phase':'AI study guidance','message':'Help me plan'},RuntimeError('secret token in provider body'))
            text=Path(name).read_text()
            self.assertNotIn('secret token',text)
            self.assertEqual(Path(name).stat().st_mode & 0o777,0o600)
            self.assertIn('AI study guidance',json.loads(text)['phase'])
