"""Exercise the HTTP boundary without network access or model calls."""
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from taskpilot.web_app import Handler


class MemorySocket:
    def __init__(self, request):
        self.input = BytesIO(request)
        self.output = bytearray()

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output.extend(data)


class WebAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'course.txt').write_text(
            'COURSE: Test Course\nTask: Example\nDue: 2099-12-01\nEstimated hours: 2\n'
        )

    def request(self, path, payload=None, host='127.0.0.1:8000', origin=None, raw=None, content_type='application/json'):
        method = 'GET' if payload is None and raw is None else 'POST'
        body = json.dumps(payload).encode() if raw is None and payload is not None else raw or b''
        headers = [f'{method} {path} HTTP/1.0', f'Host: {host}', f'Content-Length: {len(body)}', f'Content-Type: {content_type}']
        if origin:
            headers.append(f'Origin: {origin}')
        sock = MemorySocket(('\r\n'.join(headers) + '\r\n\r\n').encode() + body)
        Handler(sock, ('127.0.0.1', 12345), SimpleNamespace(server_port=8000, syllabus_folder=self.folder))
        head, response = bytes(sock.output).split(b'\r\n\r\n', 1)
        status = int(head.split(b' ')[1])
        return status, response, head

    def test_assignments_endpoint(self):
        status, body, _ = self.request('/api/assignments')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['assignments'][0]['task'], 'Example')

    def test_plan_and_completion(self):
        status, body, _ = self.request('/api/plan', {'minutes': 90})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['plan']['scheduled_minutes'], 90)
        self.assertEqual(data['plan']['unfinished'][0]['remaining_minutes'], 30)
        task_id = data['plan']['blocks'][0]['task_id']
        status, body, _ = self.request('/api/plan', {'minutes': 90, 'completed': [task_id]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['plan']['blocks'], [])

    def test_invalid_budget(self):
        for minutes in (None, -1, 1441, True, '90', 1.5):
            with self.subTest(minutes=minutes):
                self.assertEqual(self.request('/api/plan', {'minutes': minutes})[0], 400)

    def test_invalid_payload(self):
        for raw in (b'not JSON', b'[]', b'{"minutes":60,"completed":{}}', b'{"minutes":60,"completed":[1]}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request('/api/plan', raw=raw)[0], 400)
        self.assertEqual(self.request('/api/plan', {'minutes': 60}, content_type='text/plain')[0], 415)

    def test_unknown_completion(self):
        self.assertEqual(self.request('/api/plan', {'minutes': 60, 'completed': ['nonexistent']})[0], 400)

    def test_no_private_file_routes(self):
        for path in ('/.env', '/agent.py', '/../.env', '/web/../.env'):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_host_and_origin(self):
        self.assertEqual(self.request('/api/assignments', host='untrusted.example:8000')[0], 403)
        self.assertEqual(self.request('/api/plan', {'minutes': 60}, origin='https://other.example')[0], 403)
        self.assertEqual(self.request('/api/plan', {'minutes': 60}, origin='http://127.0.0.1:8000')[0], 200)

    def test_chat_question_followup_and_budget_update(self):
        status, body, _ = self.request('/api/offline-chat', {'message': 'Help me plan my assignments', 'as_of': '2026-11-16'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['kind'], 'clarification')
        status, body, _ = self.request('/api/offline-chat', {'message': 'an hour', 'as_of': '2026-11-16'})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result['minutes'], 60)
        self.assertEqual(result['source'], 'demo')
        self.assertEqual(result['plan']['scheduled_minutes'], 60)
        status, body, _ = self.request('/api/offline-chat', {'message': 'two hours instead of four hours', 'previous_minutes': 240})
        self.assertEqual(json.loads(body)['minutes'], 120)

    def test_chat_validation_and_syllabus_source(self):
        for payload in ({'message': ''}, {'message': 'help', 'previous_minutes': True},
                        {'message': 'help', 'source': 'unknown'}, {'message': 'help', 'as_of': []}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request('/api/offline-chat', payload)[0], 400)
        status, body, _ = self.request('/api/offline-chat', {'message': 'one hour', 'source': 'syllabi'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['plan']['blocks'][0]['task'], 'Example')

    def test_calendar_chat_and_preferences(self):
        status, body, _ = self.request('/api/offline-chat', {'message':'one hour','calendar_mode':'demo','as_of':'2026-11-16'})
        result=json.loads(body)
        self.assertEqual(status,200)
        self.assertEqual(result['calendar']['mode'],'demo')
        self.assertTrue(result['plan']['blocks'][0]['start'].startswith('2026-11-16T10:30'))
        self.assertTrue(result['follow_up'])
        self.assertTrue(result['suggestions'])
        self.assertEqual(self.request('/api/offline-chat', {'message':'one hour','calendar_mode':'demo','preferences':{'buffer':-1}})[0],400)

    def test_private_calendar_not_served(self):
        self.assertEqual(self.request('/.local/calendar.json')[0],404)

    def test_frontend_and_headers(self):
        for path in ('/', '/app.js', '/styles.css', '/favicon.svg'):
            with self.subTest(path=path):
                status, body, headers = self.request(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertIn(b'X-Content-Type-Options: nosniff', headers)
                self.assertIn(b"frame-ancestors 'none'", headers)


if __name__ == '__main__':
    unittest.main()
