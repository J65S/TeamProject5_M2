from contextlib import redirect_stdout
from io import StringIO
import errno
from unittest import TestCase
from unittest.mock import patch, MagicMock
from taskpilot.agent import choose_interface, cli
from taskpilot.web_app import launch_dashboard, serve_dashboard, open_dashboard_browser


class StartupChoiceTests(TestCase):
    def test_choice_accepts_plain_words_and_reprompts(self):
        for inputs,expected in [(['2'],'dashboard'),(['here'],'terminal'),([''],'terminal'),(['what','dashboard'],'dashboard')]:
            with self.subTest(inputs=inputs),patch('builtins.input',side_effect=inputs),redirect_stdout(StringIO()):
                self.assertEqual(choose_interface(),expected)

    def test_dashboard_selection_does_not_start_ai_chat(self):
        with patch('sys.argv',['agent.py']),patch('sys.stdin.isatty',return_value=True),patch('taskpilot.agent.choose_interface',return_value='dashboard'),patch('taskpilot.web_app.launch_dashboard') as launch,patch('taskpilot.agent.main') as chat:
            cli()
            launch.assert_called_once()
            chat.assert_not_called()

    def test_existing_dashboard_is_reused(self):
        with patch('taskpilot.web_app.dashboard_is_running',return_value=True),patch('taskpilot.web_app.open_dashboard_browser') as open_tab,patch('taskpilot.web_app.serve_dashboard') as serve,redirect_stdout(StringIO()):
            launch_dashboard()
            open_tab.assert_called_once_with('http://127.0.0.1:8000')
            serve.assert_not_called()

    def test_busy_port_uses_actual_assigned_url_and_closes(self):
        server=MagicMock();server.server_port=9123
        with patch('taskpilot.web_app.ThreadingHTTPServer',side_effect=[OSError(errno.EADDRINUSE,'occupied'),server]) as factory,patch('taskpilot.web_app.open_dashboard_browser') as open_tab,redirect_stdout(StringIO()):
            serve_dashboard(open_browser=True)
            self.assertEqual(factory.call_args_list[1].args[0],('127.0.0.1',0))
            open_tab.assert_called_once_with('http://127.0.0.1:9123')
            server.server_close.assert_called_once()

    def test_browser_unavailable_still_gives_manual_link(self):
        out=StringIO()
        with patch('taskpilot.web_app.webbrowser.open',return_value=False),redirect_stdout(out):
            open_dashboard_browser('http://127.0.0.1:8000')
        self.assertIn('Open this link: http://127.0.0.1:8000',out.getvalue())
