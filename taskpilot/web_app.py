"""Local TaskPilot frontend and API. Start with: python3 web_app.py"""
import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import importlib.util
import os
from pathlib import Path
import threading
import webbrowser
import errno
from http.client import HTTPConnection, HTTPException
from urllib.parse import urlsplit
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = 'taskpilot'

from .workload import load_assignments, make_plan, render_plan

from .paths import WEB_ROOT, SYLLABI_FOLDER, ENV_FILE
from .conversation import example_week, answer_question
from .calendar_planner import enrich_answer, preferences
from .ai_chat import run_ai_chat
COACH_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Request bodies (which can contain student information) are never logged.
        pass

    def send_content(self, status, content, content_type='application/json; charset=utf-8'):
        if isinstance(content, dict):
            content = json.dumps(content).encode()
        elif isinstance(content, str):
            content = content.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(content)

    def valid_host(self):
        # This server is for the user's own machine; reject DNS rebinding hosts.
        return self.headers.get('Host') in {
            f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'
        }

    def do_GET(self):
        if not self.valid_host():
            self.send_content(403, {'error': 'Use the localhost URL printed by the server.'})
            return
        path = urlsplit(self.path).path
        if path == '/api/health':
            self.send_content(200, {'application':'taskpilot', 'ready':True, 'syllabus_folder':str(self.server.syllabus_folder.resolve())})
            return
        if path == '/api/workspace':
            ai_configured = bool(importlib.util.find_spec('agents') and importlib.util.find_spec('dotenv') and
                                 (ENV_FILE.exists() or (os.getenv('NRP_API_KEY') and os.getenv('NRP_BASE_URL'))))
            self.send_content(200, {'data': example_week(), 'ai_configured': ai_configured})
            return
        if path in ('/api/assignments', '/api/assignments-relative'):
            data = load_assignments(self.server.syllabus_folder, relative_dates=path.endswith('-relative'))
            self.send_content(422 if 'error' in data else 200, data)
            return
        files = {
            '/': ('index.html', 'text/html; charset=utf-8'),
            '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
            '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
            '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
        }
        if path not in files:
            self.send_content(404, {'error': 'Not found.'})
            return
        filename, kind = files[path]
        self.send_content(200, (WEB_ROOT / filename).read_bytes(), kind)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or (origin and origin != f'http://{self.headers.get("Host")}'):
            self.send_content(403, {'error': 'Requests must come from this local app.'})
            return
        if urlsplit(self.path).path not in ('/api/plan', '/api/coach', '/api/chat', '/api/offline-chat', '/api/calendar/refresh'):
            self.send_content(404, {'error': 'Not found.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send_content(415, {'error': 'Send application/json.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32768:
                raise ValueError('Request must be between 1 and 32768 bytes.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
            if urlsplit(self.path).path == '/api/calendar/refresh':
                from .calendar_sync import refresh_calendar
                try:
                    refreshed = refresh_calendar()
                except ValueError as exc:
                    self.send_content(400, {'error': str(exc)})
                except Exception:
                    self.send_content(503, {'error': 'Google refresh failed. Check your read-only access token. The previous snapshot was kept.'})
                else:
                    self.send_content(200, refreshed)
                return
            if urlsplit(self.path).path in ('/api/chat', '/api/offline-chat'):
                source = body.get('source', 'demo')
                if source not in ('demo', 'syllabi', 'syllabi-relative'):
                    raise ValueError('Choose demo, syllabi, or syllabi-relative as the assignment source.')
                as_of = body.get('as_of')
                if as_of is not None and not isinstance(as_of, str):
                    raise ValueError('Conversation date must be an ISO date.')
                data = example_week(as_of) if source == 'demo' else load_assignments(self.server.syllabus_folder, as_of, relative_dates=source == 'syllabi-relative')
                message = body.get('message')
                if not isinstance(message,str) or not message.strip() or len(message)>2000:
                    raise ValueError('Ask a question of 1–2000 characters.')
                previous = body.get('previous_minutes')
                if previous is not None and (isinstance(previous,bool) or not isinstance(previous,int) or not 0 <= previous <= 1440):
                    raise ValueError('Invalid previous availability.')
                prefs = preferences(body.get('preferences'))
                if urlsplit(self.path).path == '/api/chat':
                    mode=body.get('calendar_mode','demo')
                    if mode not in ('demo','personal'):
                        raise ValueError('Choose demo or personal calendar mode.')
                    history=body.get('history',[])
                    context=body.get('context',{})
                    if not isinstance(context,dict) or not isinstance(history,list) or len(history)>12 or any(not isinstance(h,dict) or h.get('role') not in ('user','assistant') or not isinstance(h.get('content'),str) or len(h['content'])>2000 for h in history):
                        raise ValueError('Invalid conversation history.')
                    if 'error' in data:
                        raise ValueError(data['error'])
                    if not COACH_LOCK.acquire(blocking=False):
                        self.send_content(429, {'error':'An AI request is already running. Please wait for it to finish.'})
                        return
                    try:
                        result=asyncio.run(run_ai_chat(dict(message=message,data=data,calendar_mode=mode,preferences=prefs,history=history,context=context or {'minutes':previous})))
                    except Exception as exc:
                        self.send_content(503, {'error':'The AI could not answer. Check the NRP connection and model access, then retry. No automatic template answer was substituted.', 'engine':'ai_unavailable'})
                    else:
                        result.update(source=source,as_of=data.get('today'),warnings=data.get('warnings',[]))
                        result.setdefault('assignment_snapshot',data)
                        self.send_content(200,result)
                    finally:
                        COACH_LOCK.release()
                    return
                result = answer_question(message, data, previous)
                if body.get('calendar_mode') is not None:
                    result = enrich_answer(result, data, body['calendar_mode'], body.get('preferences'), message=body.get('message',''))
                result.update(source=source, as_of=data.get('today'), warnings=data.get('warnings', []), engine='offline_verified_planner', assignment_snapshot=data)
                self.send_content(200, result)
                return
            completed = body.get('completed', [])
            request = body.get('request', '')
            if not isinstance(completed, list) or not all(isinstance(i, str) for i in completed):
                raise ValueError('Completed tasks must be a list of task IDs.')
            if not isinstance(request, str) or len(request) > 2000:
                raise ValueError('Notes must be at most 2000 characters.')
            source = body.get('source', 'syllabi')
            if source not in ('demo', 'syllabi', 'syllabi-relative'):
                raise ValueError('Choose demo, syllabi, or syllabi-relative as the assignment source.')
            as_of = body.get('as_of')
            if as_of is not None and not isinstance(as_of, str):
                raise ValueError('Conversation date must be an ISO date.')
            data = example_week(as_of) if source == 'demo' else load_assignments(self.server.syllabus_folder, as_of, relative_dates=source == 'syllabi-relative')
            plan = make_plan(data, body.get('minutes'), completed)
            if urlsplit(self.path).path == '/api/coach' and body.get('calendar_mode') is not None:
                enriched = enrich_answer(dict(plan=plan, minutes=body.get('minutes'), kind='plan'), data, body['calendar_mode'], body.get('preferences'), message=request)
                plan = enriched.get('plan')
                if plan is None or enriched.get('calendar', {}).get('notice'):
                    raise ValueError('Refresh calendar availability before requesting calendar coaching.')
                data = {**data, 'calendar_context': enriched['calendar']}
        except (ValueError, TypeError, UnicodeError) as exc:
            self.send_content(400, {'error': str(exc)})
            return
        if urlsplit(self.path).path == '/api/plan':
            self.send_content(200, {'plan': plan, 'text': render_plan(plan)})
            return
        if not plan['blocks']:
            self.send_content(400, {'error': 'There is no work to coach on. Add assignments or review completed tasks.'})
            return
        if not COACH_LOCK.acquire(blocking=False):
            self.send_content(429, {'error': 'A coaching request is already running. Try again when it finishes.'})
            return
        try:
            from .agent import run_coaching
            coaching = asyncio.run(run_coaching(request, data, plan, self.server.syllabus_folder))
            self.send_content(200, {'coaching': coaching})
        except Exception:
            self.send_content(503, {'error': 'AI coaching is unavailable. Your verified study plan is ready to use. Your facilitator can check the AI connection later.'})
        finally:
            COACH_LOCK.release()


def dashboard_is_running(port=8000):
    connection = HTTPConnection('127.0.0.1', port, timeout=1)
    try:
        connection.request('GET', '/api/health')
        response = connection.getresponse()
        data = json.loads(response.read(2048))
        return response.status == 200 and data.get('application') == 'taskpilot' and data.get('ready') is True and data.get('syllabus_folder') == str(SYLLABI_FOLDER.resolve())
    except (OSError, ValueError, AttributeError, HTTPException):
        return False
    finally:
        connection.close()


def open_dashboard_browser(url):
    try:
        opened = webbrowser.open(url, new=2)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(f'Your browser could not open automatically. Open this link: {url}', flush=True)


def serve_dashboard(syllabus_folder=SYLLABI_FOLDER, port=8000, open_browser=False):
    try:
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    except OSError as exc:
        if not open_browser or exc.errno not in (errno.EADDRINUSE, 10048):
            raise
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.syllabus_folder = syllabus_folder
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'TaskPilot is ready at {url}\nKeep this terminal open. Press Ctrl+C to stop the dashboard.', flush=True)
    try:
        if open_browser:
            open_dashboard_browser(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nTaskPilot stopped.')
    finally:
        server.server_close()


def launch_dashboard(syllabus_folder=SYLLABI_FOLDER):
    if syllabus_folder.resolve() == SYLLABI_FOLDER.resolve() and dashboard_is_running():
        url = 'http://127.0.0.1:8000'
        print(f'Opening the running TaskPilot dashboard: {url}', flush=True)
        open_dashboard_browser(url)
        return
    serve_dashboard(syllabus_folder, open_browser=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--syllabi', type=Path, default=SYLLABI_FOLDER)
    args = parser.parse_args()
    serve_dashboard(args.syllabi, args.port)


if __name__ == '__main__':
    main()
