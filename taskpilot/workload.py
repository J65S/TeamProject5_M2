"""Credential-free assignment retrieval and scheduling constraints."""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .paths import SYLLABI_FOLDER


def load_assignments(folder=SYLLABI_FOLDER, as_of=None, relative_dates=False):
    today = date.fromisoformat(as_of) if as_of else date.today()
    files = sorted(Path(folder).glob('*.txt'))
    if not files:
        return {'error': f'No .txt syllabus files found in {folder}.'}
    tasks, warnings, source_notes = [], [], []
    for path in files:
        course, current = path.stem, {}

        def save():
            if not current:
                return
            try:
                task = current['Task'].strip()
                due = date.fromisoformat(current['Due'])
                status = current.get('Status', 'Not started').strip().lower().replace(' ', '_')
                if status not in ('not_started', 'in_progress', 'completed'):
                    raise ValueError('invalid status')
                if 'Remaining minutes' in current:
                    minutes = int(current['Remaining minutes'])
                    hours = float(current.get('Estimated hours', minutes / 60))
                else:
                    hours = float(current['Estimated hours'])
                    minutes = math.ceil(hours * 60)
                if not task or not math.isfinite(hours) or hours < 0 or not 0 <= minutes <= 1_000_000:
                    raise ValueError('invalid estimate')
                if status == 'completed':
                    if 'Remaining minutes' in current and minutes != 0:
                        raise ValueError('completed task has remaining work')
                    minutes = 0
                elif minutes <= 0:
                    raise ValueError('unfinished task needs positive remaining work')
                offset = int(current['Demo offset days']) if 'Demo offset days' in current else None
                if relative_dates:
                    if offset is None or offset < 0:
                        raise ValueError('relative demo needs a nonnegative Demo offset days')
                    due = today + timedelta(days=offset)
                due_time = current.get('Due time')
                zone = current.get('Timezone')
                due_at = None
                if due_time:
                    if not zone:
                        raise ValueError('due time needs timezone')
                    due_at = datetime.combine(due, time.fromisoformat(due_time), ZoneInfo(zone)).isoformat()
                elif zone:
                    ZoneInfo(zone)
                split = current.get('Can split', 'Yes').lower()
                if split not in ('yes', 'no'):
                    raise ValueError('Can split must be Yes or No')
                dependencies = [value.strip() for value in current.get('Dependencies', '').split(',') if value.strip() and value.strip().lower() != 'none']
            except (KeyError, ValueError, OverflowError, ZoneInfoNotFoundError):
                warnings.append(f"{path.name}: skipped incomplete or invalid task {current.get('Task', '(unnamed)')!r}.")
                return
            identity = f'{path.name}|{course}|{task}|{due.isoformat()}'
            task_id = current.get('ID') or sha256(identity.encode()).hexdigest()[:12]
            if any(t['id'] == task_id for t in tasks):
                warnings.append(f'{path.name}: skipped duplicate task {task!r}.')
                return
            tasks.append(dict(id=task_id, course=course, task=task,
                              due_date=due.isoformat(), estimated_hours=hours,
                              estimated_minutes=minutes, source_file=path.name,
                              overdue=status != 'completed' and due < today,
                              description=current.get('Description', ''), status=status,
                              due_time=due_time, timezone=zone, due_at=due_at,
                              can_split=split == 'yes', dependencies=dependencies,
                              first_step=current.get('First step', ''), demo_offset_days=offset,
                              fixed_due_date=current['Due'], date_mode='relative_demo' if relative_dates else 'fixed'))

        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeError):
            warnings.append(f'{path.name}: could not read syllabus.')
            continue
        for line in lines:
            key, sep, value = line.strip().partition(':')
            if not sep:
                continue
            if key in ('DATA TYPE', 'DATE NOTE', 'STATUS NOTE', 'DEMO NOTE'):
                source_notes.append(f'{path.name}: {value.strip()}')
            if key in ('COURSE', 'Task'):
                save()
                current = {}
            if key == 'COURSE':
                course = value.strip() or path.stem
            elif key in ('ID', 'Task', 'Due', 'Estimated hours', 'Remaining minutes', 'Status', 'Description', 'Due time', 'Timezone', 'Can split', 'Dependencies', 'First step', 'Demo offset days'):
                current[key] = value.strip()
        save()
    tasks.sort(key=lambda t: (deadline_at(t).timestamp(), t['source_file'], t['task'], t['id']))
    return dict(today=today.isoformat(), assignments=tasks, warnings=warnings,
                total_estimated_minutes=sum(t['estimated_minutes'] for t in tasks),
                source_notes=source_notes, date_mode='relative_demo' if relative_dates else 'fixed', assumption='Completion and remaining effort come from the source records, not a submission system. Exact due times are used when provided; date-only records have an unknown cutoff. Relative dates are an explicit demo mode, never an automatic change to real deadlines.')


def parse_minutes(text):
    """Accept explicit numeric hours/minutes; ask for clarification otherwise."""
    matches = list(re.finditer(r'(?<![\w.])(-?\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b', text, re.I))
    if not matches:
        raise ValueError('Enter your available time, for example 90 minutes or 1.5 hours.')
    # Reject alternative windows or future-day requests rather than adding them together.
    if re.search(r'\b(or|tomorrow|week|next|daily|every)\b', text, re.I):
        raise ValueError('Provide one study session for today, with a single time budget.')
    units = ['h' if m[2].lower().startswith('h') else 'm' for m in matches]
    if len(set(units)) != len(units):
        raise ValueError('Provide one time budget, such as 1 hour 30 minutes.')
    total = 0.0
    for match in matches:
        amount = float(match[1])
        if amount < 0:
            raise ValueError('Available time cannot be negative.')
        total += amount * (60 if match[2].lower().startswith('h') else 1)
    if not math.isfinite(total) or not 0 <= total <= 1440 or 0 < total < 1:
        raise ValueError('Choose zero time or a session between 1 minute and 24 hours.')
    return math.floor(total)


def completed_ids(data, completed=()):
    return set(completed) | {t['id'] for t in data['assignments'] if t.get('status') == 'completed'}


def blocking_dependencies(task, data, completed=()):
    return [dep for dep in task.get('dependencies', []) if dep not in completed_ids(data, completed)]


def deadline_at(task):
    if task.get('due_at'):
        return datetime.fromisoformat(task['due_at'])
    return datetime.combine(date.fromisoformat(task['due_date']) + timedelta(days=1), time(), ZoneInfo(task.get('timezone') or 'America/New_York'))


def make_plan(data, minutes, completed=()):
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 <= minutes <= 1440:
        raise ValueError('Session must be an integer between 0 and 1440 minutes.')
    if 'error' in data:
        raise ValueError(data['error'])
    unknown = set(completed) - {task['id'] for task in data['assignments']}
    if unknown:
        raise ValueError('Unknown completed task IDs: ' + ', '.join(sorted(unknown)))
    remaining, elapsed, blocks, unfinished = minutes, 0, [], []
    blocked = []
    for task in data['assignments']:
        if task['id'] in completed_ids(data, completed):
            continue
        deps = blocking_dependencies(task, data, completed)
        if deps:
            blocked.append(dict(task_id=task['id'], task=task['task'], dependencies=deps))
        allocated = 0 if deps else min(remaining, task['estimated_minutes'])
        if not task.get('can_split', True) and allocated < task['estimated_minutes']:
            allocated = 0
        if allocated:
            blocks.append(dict(task_id=task['id'], start_minute=elapsed,
                               minutes=allocated, course=task['course'], task=task['task'],
                               due_date=task['due_date'], overdue=task['overdue'], due_at=task.get('due_at'), timezone=task.get('timezone'), first_step=task.get('first_step', '')))
            elapsed += allocated
            remaining -= allocated
        if allocated < task['estimated_minutes']:
            unfinished.append(dict(task_id=task['id'], task=task['task'],
                                   remaining_minutes=task['estimated_minutes'] - allocated))
    return dict(as_of=data['today'], available_minutes=minutes, scheduled_minutes=elapsed,
                unused_minutes=remaining, blocks=blocks, unfinished=unfinished,
                warnings=data['warnings'], assumption=data['assumption'], blocked=blocked)


def format_duration(minutes):
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if mins or not parts:
        parts.append(f"{mins} {'minute' if mins == 1 else 'minutes'}")
    return ' '.join(parts)


def render_plan(plan, detailed=False):
    """Show a manageable starting point; keep full audit detail opt-in."""
    lines = [f"Here’s a possible way to use your {format_duration(plan['available_minutes'])} ({plan['as_of']})."]
    if not plan['available_minutes']:
        lines.append('No study time today? I haven’t scheduled any work. Your list can wait for another session.')
    elif not plan['blocks']:
        lines.append('There’s no available work to plan from this data. Check the assignment source and any notes below.')
    for b in plan['blocks']:
        lines.append(f"  {b['start_minute']}–{b['start_minute'] + b['minutes']} min: {b['task']} ({b['course']})")
        due_note = f"Listed deadline: {b.get('due_at') or b['due_date']}."
        if b['overdue']:
            due_note += ' That date has passed; this may already be finished.'
        lines.append('    ' + due_note)
        remaining = next((t['remaining_minutes'] for t in plan['unfinished'] if t['task_id'] == b['task_id']), 0)
        if remaining:
            lines.append(f"    This is a start; about {format_duration(remaining)} would still be needed afterward.")
        if b.get('first_step'):
            lines.append('    A first step: ' + b['first_step'])
        if detailed:
            lines.append(f"    Task ID: {b['task_id']}")
    scheduled_ids = {b['task_id'] for b in plan['blocks']}
    other_work = [t for t in plan['unfinished'] if t['task_id'] not in scheduled_ids]
    if detailed and plan['unfinished']:
        lines.append('Full remaining-work list:')
        lines.extend(f"  {t['task']}: {format_duration(t['remaining_minutes'])} remaining [{t['task_id']}]" for t in plan['unfinished'])
    elif other_work:
        lines.append('Other assignments are still on your list. We can take them one session at a time.')
    if plan['unused_minutes']:
        lines.append(f"You have {format_duration(plan['unused_minutes'])} left unallocated.")
    lines.extend('Source note: ' + w for w in plan['warnings'])
    if any(b['overdue'] for b in plan['blocks']):
        lines.append('Before you start: is this older work still unfinished? I can’t check submission status.')
    if plan.get('blocked'):
        lines.append('Some work depends on unfinished prerequisites; check the full details before starting it.')
        if detailed:
            lines.extend(f"  {t['task']}: waiting on {', '.join(t['dependencies'])}" for t in plan['blocked'])
    lines.append('Timing note: confirm source deadlines; date-only records do not specify a cutoff time.')
    if detailed:
        lines.append(plan['assumption'])
    return '\n'.join(lines)
