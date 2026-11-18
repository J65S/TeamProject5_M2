"""Reproduce IDE Run commands, including a working directory outside the repo."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


class DirectLaunchTests(TestCase):
    def test_ide_entry_files_can_show_help_outside_project(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('agent.py', 'web_app.py', 'calendar_sync.py'):
                with self.subTest(name=name):
                    run = subprocess.run([sys.executable, '-u', str(ROOT/'taskpilot'/name), '--help'], cwd=folder, capture_output=True, text=True, timeout=15)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertIn('usage:', run.stdout)

    def test_direct_agent_runs_offline_not_just_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            run = subprocess.run([sys.executable, '-u', str(ROOT/'taskpilot/agent.py'), '--offline', '--demo', '--minutes', '90', '--json'], cwd=folder, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['available_minutes'], 90)

    def test_calendar_helper_default_explains_how_to_launch(self):
        run = subprocess.run([sys.executable, str(ROOT/'taskpilot/calendar_sync.py')], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('python agent.py', run.stdout)
        self.assertIn('--refresh', run.stdout)
