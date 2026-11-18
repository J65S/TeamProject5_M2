"""Read-only calendar snapshots and deterministic, deadline-aware free windows."""
from datetime import datetime, time, timedelta
import json
import re
from zoneinfo import ZoneInfo
from .paths import PROJECT_ROOT
from .workload import deadline_at, completed_ids, blocking_dependencies

CALENDAR_FILE = PROJECT_ROOT / '.local' / 'calendar.json'
ZONE = ZoneInfo('America/New_York')


def preferences(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict):
        raise ValueError('Study preferences must be an object.')
    result = dict(start_hour=8, end_hour=22, buffer=15, break_minutes=10, block_minutes=50)
    for key in result:
        if key in value:
            result[key] = value[key]
        if isinstance(result[key], bool) or not isinstance(result[key], int):
            raise ValueError('Study preferences must be whole numbers.')
    if not 0 <= result['start_hour'] < result['end_hour'] <= 24:
        raise ValueError('Choose study hours between 0 and 24, with an end after the start.')
    if not 0 <= result['buffer'] <= 120 or not 0 <= result['break_minutes'] <= 60 or not 15 <= result['block_minutes'] <= 120:
        raise ValueError('Use a 0–120 minute buffer, 0–60 minute break, and 15–120 minute focus block.')
    return result


def calendar_snapshot(mode, today=None):
    today = today or datetime.now(ZONE).date()
    if mode == 'demo':
        def event(title, day, start, end):
            d = today + timedelta(days=day)
            return dict(title=title, start=datetime.combine(d, time.fromisoformat(start), ZONE).isoformat(), end=datetime.combine(d, time.fromisoformat(end), ZONE).isoformat())
        now = datetime.combine(today, time(9, 30), ZONE)
        return dict(timezone=str(ZONE), mode='demo', simulated_now=now.isoformat(), synced_at=now.isoformat(),
                    coverage_start=datetime.combine(today, time(), ZONE).isoformat(),
                    coverage_end=datetime.combine(today+timedelta(days=7), time(), ZONE).isoformat(),
                    events=[event('Morning class', 0, '09:00', '10:15'), event('Work shift', 0, '12:00', '17:00'),
                            event('Study group', 0, '19:00', '20:00'), event('Lab', 1, '09:00', '12:00'), event('Work shift', 1, '14:00', '18:00')])
    if mode != 'personal':
        raise ValueError('Choose personal or demo calendar mode.')
    try:
        result = json.loads(CALENDAR_FILE.read_text())
        result['mode'] = 'personal'
        return result
    except (OSError, ValueError):
        return dict(mode='personal', error='No calendar snapshot yet. Ask Codex to refresh your connected Google Calendar, or use interview demo mode.')


def free_windows(calendar, prefs, now):
    zone = ZoneInfo(calendar['timezone'])
    lower = max(now, datetime.fromisoformat(calendar['coverage_start']))
    upper = min(now + timedelta(days=7), datetime.fromisoformat(calendar['coverage_end']))
    busy = []
    for e in calendar['events']:
        start, end = datetime.fromisoformat(e['start']), datetime.fromisoformat(e['end'])
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError('Calendar events need explicit timezones.')
        busy.append((start - timedelta(minutes=prefs['buffer']), end + timedelta(minutes=prefs['buffer'])))
    windows = []
    for day in range(8):
        d = lower.astimezone(zone).date() + timedelta(days=day)
        start = max(lower, datetime.combine(d, time(prefs['start_hour']), zone))
        end_of_day = datetime.combine(d + timedelta(days=1), time(), zone) if prefs['end_hour'] == 24 else datetime.combine(d, time(prefs['end_hour']), zone)
        end = min(upper, end_of_day)
        if end <= start:
            continue
        cursor = start
        for a, b in sorted(busy):
            if b <= cursor or a >= end:
                continue
            if a > cursor:
                windows.append([cursor, min(a, end)])
            cursor = max(cursor, b)
        if cursor < end:
            windows.append([cursor, end])
    return windows


def enrich_answer(result, data, mode='demo', prefs=None, now=None, message='', freshness_now=None, max_windows=1):
    prefs = preferences(prefs)
    calendar = calendar_snapshot(mode, datetime.fromisoformat(data['today']).date())
    result['suggestions'] = ['What’s due tomorrow?', 'I have 30 minutes. Help me start small.', 'I have two hours. Can I finish everything?']
    result['follow_up'] = 'Would a shorter session or a longer study window work better for you?'
    result['calendar'] = {k: calendar[k] for k in ('mode', 'synced_at', 'timezone', 'simulated_now') if k in calendar}
    if 'error' in calendar:
        result['calendar']['notice'] = calendar['error']
        return result
    now = now or (datetime.fromisoformat(calendar['simulated_now']) if mode == 'demo' else datetime.now(ZONE))
    if mode == 'personal' and ((freshness_now or now) - datetime.fromisoformat(calendar['synced_at']) > timedelta(hours=24) or now >= datetime.fromisoformat(calendar['coverage_end'])):
        result['calendar']['notice'] = 'Calendar snapshot is stale. Refresh it before relying on free-time suggestions.'
        return result
    anchor_reason = ''
    if re.search(r'\bafter\s+(?:my\s+)?(?:work|class|shift|last event)\b', message, re.I):
        phrase = re.search(r'\bafter\s+(?:my\s+)?(work|class|shift|last event)\b', message, re.I)[1].lower()
        matching = [e for e in calendar['events'] if datetime.fromisoformat(e['end']).astimezone(ZONE).date() == now.astimezone(ZONE).date() and
                    (phrase == 'last event' or re.search('class' if phrase == 'class' else 'work|shift', e['title'], re.I))]
        if not matching:
            result.update(kind='clarification', plan=None, answer='Which event on your calendar is your work or class commitment? I won’t guess from an unfamiliar event title. You can also set your earliest study hour below.', follow_up='What hour are you free after that commitment?')
            return result
        event = max(matching, key=lambda e:e['end'])
        now = max(now, datetime.fromisoformat(event['end']))
        anchor_reason = f"You asked to study after {event['title']}, which ends at {datetime.fromisoformat(event['end']).strftime('%I:%M %p')}. "
    # A stated availability is one elapsed-time session on the selected day.
    # Do not silently carry a "today" request into tomorrow or across busy gaps.
    windows = [(a, b) for a, b in free_windows(calendar, prefs, now)
               if a.astimezone(ZONE).date() == now.astimezone(ZONE).date()]
    result['calendar']['windows'] = [dict(start=a.isoformat(), end=b.isoformat()) for a,b in windows[:3]]
    current = [e for e in calendar['events'] if datetime.fromisoformat(e['start']) <= now < datetime.fromisoformat(e['end'])]
    context = anchor_reason or (f"You’re currently busy with {current[0]['title']}. " if current else 'I checked the calendar’s busy windows. ')
    result['calendar']['explanation'] = context + f"I leave {prefs['buffer']} minutes around events and keep study time between {prefs['start_hour']:02}:00 and {prefs['end_hour']:02}:00."
    if not result.get('plan') or not result.get('minutes'):
        if result.get('kind') == 'clarification':
            result['answer'] += '\n\n' + result['calendar']['explanation']
            result['follow_up'] = 'How long would you like your study session to be?'
        return result
    plan = result['plan']
    blocks, remaining, budget, elapsed = [], [], result['minutes'], 0
    session_start = windows[0][0] if windows else None
    session_end = min(windows[0][1], session_start + timedelta(minutes=budget)) if windows else None
    slots = [[a, min(b, a+timedelta(minutes=budget)), False] for a,b in windows[:max_windows]]
    elapsed_clock = 0
    blocked = []
    # Within the same deadline, start with the smaller estimate so tie ordering
    # does not depend on an assignment's alphabetical name.
    for task in sorted(data['assignments'], key=lambda t: (deadline_at(t), t['estimated_minutes'], t['id'])):
        if task['id'] in completed_ids(data):
            continue
        deps = blocking_dependencies(task, data)
        if deps:
            blocked.append(dict(task_id=task['id'], task=task['task'], dependencies=deps))
            remaining.append(dict(task_id=task['id'], task=task['task'], remaining_minutes=task['estimated_minutes']))
            continue
        needed = task['estimated_minutes']
        deadline = deadline_at(task)
        for slot in slots:
            while needed and elapsed_clock < budget:
                pause = prefs['break_minutes'] if slot[2] else 0
                start = slot[0] + timedelta(minutes=pause)
                available = int((min(slot[1], deadline)-start).total_seconds()//60)
                allocated = min(needed, prefs['block_minutes'], available, budget-elapsed_clock-pause)
                if allocated < 1 or (not task.get('can_split', True) and allocated < needed):
                    break
                end = start + timedelta(minutes=allocated)
                blocks.append(dict(task_id=task['id'], task=task['task'], course=task['course'], due_date=task['due_date'], overdue=task['overdue'], start_minute=elapsed_clock+pause, minutes=allocated, start=start.isoformat(), end=end.isoformat(), due_at=task.get('due_at'), timezone=task.get('timezone'), first_step=task.get('first_step', '')))
                slot[0], slot[2] = end, True
                needed -= allocated
                elapsed += allocated
                elapsed_clock += allocated+pause
        if needed:
            remaining.append(dict(task_id=task['id'], task=task['task'], remaining_minutes=needed))
    blocks.sort(key=lambda b:b['start'])
    split = sum(bool(slot[2]) for slot in slots) > 1
    plan.update(blocks=blocks, unfinished=remaining, scheduled_minutes=elapsed,
                elapsed_minutes=elapsed_clock, break_minutes=elapsed_clock-elapsed,
                unused_minutes=budget-elapsed_clock, blocked=blocked,
                session_limit_start=session_start.isoformat() if session_start else None,
                session_limit_end=session_end.isoformat() if session_end else None,
                shorter_window=sum(int((b-a).total_seconds()//60) for a,b in windows[:max_windows]) < budget,
                split_confirmed=split,
                calendar_span_minutes=int((datetime.fromisoformat(blocks[-1]['end'])-datetime.fromisoformat(blocks[0]['start'])).total_seconds()//60) if blocks else 0)
    if blocks:
        first = blocks[0]
        result['answer'] = (f"{context}Your next study block is {first['task']}. Start {datetime.fromisoformat(first['start']).strftime('%a, %b %d at %I:%M %p')} ({calendar['timezone']}).\n\n"
                            f"This uses {elapsed_clock} minutes including {elapsed_clock-elapsed} minutes of breaks, with {elapsed} minutes of focused work. Work is ordered by deadline, with no suggested block after its listed due date.\n\n"
                            f"There are {sum(t['remaining_minutes'] for t in remaining) // 60}h {sum(t['remaining_minutes'] for t in remaining) % 60}m of estimated work still unfinished. A partial block means progress, not a finished assignment.")
        if plan['unused_minutes']:
            result['answer'] += f" {plan['unused_minutes']} requested minutes are unused in this single session; I haven’t added another window without asking."
        result['suggestions'] = ['I have 30 minutes. Find a smaller window.', 'I have two hours. Plan a longer session.', 'What assignments are due tomorrow?']
        result['follow_up'] = 'Does this start time work, or would you prefer to change your study hours below?'
    else:
        result['answer'] = 'I couldn’t fit study time before the listed deadlines within your preferred hours and known calendar coverage. I haven’t scheduled work after a deadline. Review overdue tasks, widen your study hours, or refresh your calendar.'
        result['follow_up'] = 'Could you widen your study hours, or check whether any overdue work is already complete?'
    from .workload import render_plan
    result['text'] = render_plan(plan) + '\n\nCalendar blocks:\n' + '\n'.join(f"{b['start']} to {b['end']}: {b['task']}" for b in blocks)
    return result
