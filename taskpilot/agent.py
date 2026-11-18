"""TaskPilot terminal chat, using the same AI workflow as the dashboard."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

# IDE Run buttons execute this file without package context.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = 'taskpilot'

from .ai_chat import run_ai_chat, AIRequestError
from .flow import confirmation_reply
from .conversation import example_week
from .paths import SYLLABI_FOLDER
from .workload import load_assignments, make_plan, parse_minutes, render_plan


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', help='Ask one question and exit (omit for interactive chat)')
    parser.add_argument('--minutes', type=int, help='Explicit available minutes')
    parser.add_argument('--as-of', help='ISO date for repeatable demos')
    parser.add_argument('--syllabi', type=Path, default=SYLLABI_FOLDER)
    parser.add_argument('--completed', action='append', default=[], metavar='TASK_ID')
    parser.add_argument('--relative-dates', action='store_true')
    parser.add_argument('--demo', action='store_true', help='Use the small fictional example week')
    parser.add_argument('--calendar', choices=('demo', 'personal'), default='demo', help='Calendar source; demo is fictional')
    parser.add_argument('--details', action='store_true', help='Show verified blocks, full remaining work, and agent evidence')
    parser.add_argument('--offline', action='store_true', help='Explicit deterministic planning without AI')
    parser.add_argument('--json', action='store_true', help='Output structured result; use --request or --minutes')
    return parser.parse_args()


def source_data(args):
    data = example_week(args.as_of) if args.demo else load_assignments(args.syllabi, args.as_of, relative_dates=args.relative_dates)
    if 'error' in data:
        raise ValueError(data['error'])
    make_plan(data, 0, args.completed)  # Validate completion IDs without allocating work.
    for task in data['assignments']:
        if task['id'] in args.completed:
            task.update(status='completed', estimated_minutes=0)
    data['total_estimated_minutes'] = sum(t['estimated_minutes'] for t in data['assignments'])
    return data


async def run_coaching(request, data, plan, folder):
    """Compatibility entry for the old coaching API; no separate legacy worker."""
    result = await run_ai_chat(dict(message=request or 'Help me use this study time.', data=data,
        calendar_mode=data.get('calendar_context', {}).get('mode', 'demo'), preferences={},
        context={'minutes':plan['available_minutes'],'task_ids':[b['task_id'] for b in plan['blocks']],'restrict_tasks':True}, explicit_minutes=plan['available_minutes'], history=[]))
    return result['answer']


def show_reply(result, details=False):
    print('\nTaskPilot: ' + result['answer'], flush=True)
    if result.get('follow_up'):
        print(result['follow_up'], flush=True)
    if details:
        show_details(result)


def show_details(result):
    plan = result.get('plan')
    if plan:
        print('\n' + render_plan(plan, detailed=True), flush=True)
        for block in plan['blocks']:
            if block.get('start'):
                print(f"  {block['start']} to {block['end']}: {block['task']}")
    evidence = result.get('evidence', {})
    print(f"\nAI model: {result.get('model', 'unknown')} | MCP results: {evidence.get('analyst_tool_outputs', 0)} | Handoff: {evidence.get('handoff', False)}", flush=True)
    calendar = result.get('calendar') or {}
    if calendar.get('notice'):
        print(calendar['notice'], flush=True)


async def answer_with_progress(payload):
    started = time.monotonic()
    task = asyncio.create_task(run_ai_chat(payload))
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=15)
            if done:
                return task.result()
            print(f'Still waiting for the AI reply ({int(time.monotonic()-started)} seconds)…', file=sys.stderr, flush=True)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def main(args=None):
    args = args or arguments()
    data = source_data(args)
    if args.minutes is not None and (isinstance(args.minutes, bool) or not 0 <= args.minutes <= 1440):
        raise ValueError('Available time must be between 0 and 1440 minutes.')
    if args.json and args.request is None and args.minutes is None:
        raise ValueError('Use --request or --minutes with --json.')
    single = args.request is not None or args.minutes is not None
    message = args.request or (f'I have {args.minutes} minutes. What should I work on?' if args.minutes is not None else None)
    if args.offline:
        if message is None:
            message = input('How much time do you have today? ').strip()
        minutes = args.minutes if args.minutes is not None else parse_minutes(message)
        plan = make_plan(data, minutes)
        print(json.dumps(plan, indent=2) if args.json else '\nOffline plan (no AI):\n' + render_plan(plan, detailed=args.details))
        return
    history, context, last = [], {}, None
    if args.minutes is not None:
        context['minutes'] = args.minutes
    if not single:
        print('TaskPilot · AI conversation\nAsk naturally; you don’t need to enter your time until it’s relevant.\nCalendar: ' + ('fictional interview demo' if args.calendar == 'demo' else 'your saved Google Calendar snapshot') + '\nType /details for evidence, /new to start over, or /quit to finish.', flush=True)
    while True:
        if message is None:
            try:
                message = input('\nYou: ').strip()
            except EOFError:
                return
        if not message:
            message = None
            continue
        if message.lower() in ('/quit', '/exit', 'quit', 'exit'):
            return
        if message.lower() == '/new':
            history, context, last = [], {}, None
            print('A fresh conversation. What would you like help with?')
            message = None
            continue
        if message.lower() == '/details':
            show_details(last) if last else print('Ask a question first; there isn’t a plan to inspect yet.')
            message = None
            continue
        payload=dict(message=message, data=data, calendar_mode=args.calendar,
                     preferences={}, context=context, history=history[-10:], explicit_minutes=args.minutes)
        try:
            result=confirmation_reply(payload)
            if result is None:
                print('The AI agents are reading your request and checking the source data…', file=sys.stderr, flush=True)
                result = await answer_with_progress(payload)
        except (AIRequestError, asyncio.TimeoutError) as exc:
            # Keep the student's facts even when the provider/response fails.
            history.append({'role':'user','content':message[:2000]})
            error = str(exc) if isinstance(exc, AIRequestError) else 'The AI request exceeded its time limit. Please try again.'
            if args.json:
                print(json.dumps({'engine':'ai_unavailable','error':error}))
            else:
                print('\nTaskPilot could not get an AI answer: ' + error, file=sys.stderr, flush=True)
                print('No template answer was substituted. You can retry, or explicitly use --offline for a non-AI plan.', file=sys.stderr, flush=True)
            if single:
                return 1
            message = None
            continue
        context, last = result.get('context', {}), result
        history.extend([{'role':'user','content':message[:2000]}, {'role':'assistant','content':result['answer'][:2000]}])
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            show_reply(result, args.details)
        if single:
            return
        message = None


def choose_interface():
    print('Welcome to TaskPilot. Would you rather work here or in the dashboard?\n  1. Here in the terminal\n  2. Dashboard in your browser', flush=True)
    while True:
        choice = input('Choose 1 or 2 (Enter for terminal): ').strip().lower()
        if choice in ('', '1', 'terminal', 'here', 't'):
            return 'terminal'
        if choice in ('2', 'dashboard', 'browser', 'd'):
            return 'dashboard'
        print('Type 1 for the terminal or 2 for the dashboard.')


def cli():
    try:
        args = arguments()
        interactive = sys.stdin.isatty() and args.request is None and args.minutes is None and not args.offline and not args.json
        if interactive and choose_interface() == 'dashboard':
            from .web_app import launch_dashboard
            launch_dashboard(args.syllabi)
            return
        sys.exit(asyncio.run(main(args)) or 0)
    except (ValueError, OSError) as exc:
        print(f'Cannot start TaskPilot: {exc}', file=sys.stderr)
        sys.exit(2)
    except (KeyboardInterrupt, EOFError):
        print('\nSession ended.', file=sys.stderr)
        sys.exit(130)


if __name__ == '__main__':
    cli()
