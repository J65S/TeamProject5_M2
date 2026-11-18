import asyncio
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from taskpilot.agent import main
from taskpilot.ai_chat import AIRequestError, safe_error


class TerminalChatTests(TestCase):
    def run_main(self,args, replies, inputs=None):
        out,err=StringIO(),StringIO()
        mock=AsyncMock(side_effect=replies)
        with patch('sys.argv',['agent.py',*args]), patch('taskpilot.agent.run_ai_chat',mock), redirect_stdout(out),redirect_stderr(err):
            if inputs is None:
                result=asyncio.run(main())
            else:
                with patch('builtins.input',side_effect=inputs):
                    result=asyncio.run(main())
        return result,out.getvalue(),err.getvalue(),mock

    def reply(self,answer='What time do you have available?',context=None):
        return dict(answer=answer,follow_up='',plan=None,context=context or {},model='gpt-oss',engine='two_agent_ai')

    def test_natural_request_goes_to_ai_without_time_regex(self):
        _,out,_,mock=self.run_main(['--request','I feel overwhelmed'],[self.reply()])
        self.assertEqual(mock.call_args.args[0]['message'],'I feel overwhelmed')
        self.assertIn('What time do you have available?',out)
        self.assertNotIn('Here’s a possible way',out)

    def test_followup_carries_context_and_history(self):
        first=self.reply('When would you like to start?',{'minutes':90})
        _,out,_,mock=self.run_main([],[first,self.reply('After your last event.')],['I have 90 minutes','After my day','/quit'])
        second=mock.call_args_list[1].args[0]
        self.assertEqual(second['context']['minutes'],90)
        self.assertEqual(second['history'][0]['content'],'I have 90 minutes')
        self.assertEqual(second['message'],'After my day')

    def test_failure_is_visible_and_not_a_successful_fallback(self):
        code,out,err,_=self.run_main(['--request','I have an hour'],[AIRequestError('NRP timed out at analyst stage')])
        self.assertEqual(code,1)
        self.assertNotIn('Here’s a possible way',out)
        self.assertIn('analyst stage',err)
        self.assertIn('No template answer',err)

    def test_structured_result_is_ai_result(self):
        _,out,_,_=self.run_main(['--request','help','--json'],[self.reply()])
        import json
        self.assertEqual(json.loads(out)['engine'],'two_agent_ai')

    def test_diagnostic_excludes_exception_body(self):
        error=safe_error(ValueError('secret private provider request'),'answer validation')
        self.assertNotIn('secret',error)
        self.assertIn('answer validation',error)

    def test_failed_turn_remains_in_history_for_the_next_request(self):
        _,_,_,mock=self.run_main([],[AIRequestError('provider failed'),self.reply('Here is your next opening.')],
                                ['I have 3 hours can you help me or no?','Whenever i havve time next','/quit'])
        self.assertEqual(mock.call_args_list[1].args[0]['history'][0]['content'],'I have 3 hours can you help me or no?')
