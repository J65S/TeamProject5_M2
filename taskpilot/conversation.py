"""Grounded conversational answers for a low-effort student testing experience."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import re

from .workload import make_plan, parse_minutes, render_plan


DEMO_TASKS = (
    ('Reading response', 'English Composition', 0, 45),
    ('Graph traversal practice', 'Algorithms', 1, 90),
    ('Project outline', 'Software Engineering', 1, 120),
    ('Statistics problem set', 'Statistics', 2, 60),
    ('Team project draft', 'Software Engineering', 4, 180),
    ('Quiz preparation', 'Algorithms', 5, 60),
)


def example_week(as_of=None):
    today = date.fromisoformat(as_of) if as_of else date.today()
    details = (
        ('Write a short response connecting the reading to one course theme.', 'Read the prompt and highlight one passage to discuss.'),
        ('Practice breadth-first and depth-first searches on example graphs.', 'Draw one graph and trace the first BFS queue.'),
        ('Outline the project goals, workflow, and a small implementation plan.', 'Write three bullets explaining what the project should do.'),
        ('Solve practice questions and show the calculation steps.', 'Read the first problem and identify the required formula.'),
        ('Combine the team’s evidence and implementation into a coherent draft.', 'List which sections already have supporting evidence.'),
        ('Review weak topics using a short set of practice questions.', 'Attempt one practice question without notes.'),
    )
    assignments = []
    for i, (task, course, days, minutes) in enumerate(DEMO_TASKS):
        due = today + timedelta(days=days)
        assignments.append(dict(id=f'demo-{i + 1}', task=task, course=course,
            due_date=due.isoformat(), due_time='23:59', timezone='America/New_York',
            due_at=datetime.combine(due,time(23,59),ZoneInfo('America/New_York')).isoformat(),
            estimated_hours=minutes/60, estimated_minutes=minutes,
            source_file='example-week', overdue=False, status='not_started',
            description=details[i][0], first_step=details[i][1],
            can_split=True, dependencies=[], demo_offset_days=days, date_mode='relative_demo'))
    return dict(today=today.isoformat(), assignments=assignments, warnings=[],
                total_estimated_minutes=sum(t['estimated_minutes'] for t in assignments),
                assumption='Fictional example week. Estimates are remaining work; confirm real course deadlines. Demo cutoffs are 23:59 America/New_York, not real course deadlines.')


def duration(minutes):
    hours, mins = divmod(minutes, 60)
    return ' '.join(p for p in (f'{hours}h' if hours else '', f'{mins}m' if mins else '') if p) or '0m'


def normalize_time(message):
    text = message.lower().replace('’', "'")
    # An update names the new budget first; the old window is context, not extra time.
    text = re.split(r'\binstead of\b', text, maxsplit=1)[0]
    text = re.sub(r'\b(?:no|zero) time\b', '0 minutes', text)
    text = re.sub(r'\b(?:an|one) hour and a half\b', '1 hour 30 minutes', text)
    text = re.sub(r'\bhalf (?:an? |of an? )?hour\b', '30 minutes', text)
    text = re.sub(r'\b(?:an?|one)\s+(hours?|minutes?)\b', r'1 \1', text)
    numbers = {'zero': 0, 'no': 0, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
               'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
               'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty-five': 45,
               'forty five': 45, 'sixty': 60, 'ninety': 90}
    for word in sorted(numbers, key=len, reverse=True):
        number = numbers[word]
        text = re.sub(r'\b' + re.escape(word) + r'\b(?=\s*(?:hours?|hrs?|minutes?|mins?)\b)', str(number), text)
    return text


def answer_question(message, data, previous_minutes=None):
    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
        raise ValueError('Ask a question of 1–2000 characters.')
    if previous_minutes is not None and (isinstance(previous_minutes, bool) or not isinstance(previous_minutes, int) or not 0 <= previous_minutes <= 1440):
        raise ValueError('Previous availability must be between 0 and 1440 minutes.')
    if 'error' in data:
        return dict(kind='unavailable', answer='I couldn’t read the assignments. Please ask your facilitator to check the syllabus files. I haven’t made a plan.', minutes=None, plan=None)
    tasks = [t for t in data['assignments'] if t.get('status') != 'completed']
    text = normalize_time(message)
    has_time = bool(re.search(r'(?:\d|\b(?:a|one|several|some))\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b', text))
    if not has_time and re.search(r'\b(total|workload|how much work|how many hours)\b', text):
        total = sum(t['estimated_minutes'] for t in tasks)
        return dict(kind='overview', answer=f"There are {len(tasks)} assignments with {duration(total)} of estimated work in total. Tell me your available time and I’ll help you choose a manageable part.", minutes=previous_minutes, plan=None)
    # A request for a factual deadline list doesn't need a study budget.
    if not has_time and re.search(r'\b(due|deadlines|assignments)\b', text) and re.search(r'\b(what|show|list|which)\b', text) and not re.search(r'\b(prioriti[sz]e|work on|start|plan|finish)\b', text):
        selected = tasks
        if 'tomorrow' in text:
            tomorrow = (date.fromisoformat(data['today']) + timedelta(days=1)).isoformat()
            selected = [t for t in tasks if t['due_date'] == tomorrow]
        elif 'today' in text:
            selected = [t for t in tasks if t['due_date'] == data['today']]
        elif re.search(r'\b(?:this|next) week\b', text):
            end = (date.fromisoformat(data['today']) + timedelta(days=7)).isoformat()
            selected = [t for t in tasks if data['today'] <= t['due_date'] <= end]
        lines = [f"{t['task']} ({t['course']}) — due {t['due_date']}, about {duration(t['estimated_minutes'])}." for t in selected]
        answer = 'Here’s what’s on your list:\n\n' + '\n'.join(lines) if lines else 'There are no assignments listed for that time window.'
        return dict(kind='overview', answer=answer, minutes=previous_minutes, plan=None)
    if not has_time and not re.search(r'\b(work|study|studying|plan|planning|assignments?|prioriti[sz]e|deadlines?|due|finish|start|overwhelmed|stress|help|time|why|available)\b', text):
        return dict(kind='clarification', answer='I can help with your assignment list and study time. Try “What’s due tomorrow?” or “I have an hour. What should I work on?”', minutes=previous_minutes, plan=None)
    if re.search(r'\b(tomorrow|next week|every day|daily)\b', text):
        return dict(kind='clarification', answer='I can plan one study session for today. How much time do you have today?', minutes=None, plan=None)
    if has_time:
        try:
            minutes = parse_minutes(text)
        except ValueError:
            return dict(kind='clarification', answer='How much time do you have for one session today? Try “one hour” or “90 minutes.”', minutes=None, plan=None)
    elif re.search(r'\b(?:hours?|minutes?|hrs?|mins?)\b', text):
        return dict(kind='clarification', answer='Please give one clear time budget, such as “one hour” or “90 minutes.”', minutes=None, plan=None)
    elif previous_minutes is not None:
        minutes = previous_minutes
    else:
        return dict(kind='clarification', answer='I can help you choose where to start. How much time do you have today? You can just reply “one hour” or “30 minutes.”', minutes=None, plan=None)
    plan = make_plan(data, minutes)
    if minutes == 0:
        answer = 'No study time today? That’s okay. I haven’t scheduled any work. Your assignments are still on the list. When you have some time, tell me how many minutes or hours you can spare.'
    elif not plan['blocks']:
        answer = 'There are no valid assignments available to plan. Check the assignment list and any source warnings first.'
    else:
        first = plan['blocks'][0]
        answer = f"Start with {first['task']}. Its listed due date is {first['due_date']}. Here’s how to use your {duration(minutes)}:"
        if first['overdue']:
            answer += ' This task is past due; confirm it still needs doing.'
        if re.search(r'\b(overwhelm|stress|anxious|lost|don.t know)\b', text):
            answer = 'Let’s make this smaller: focus on one block at a time. ' + answer
        remaining = sum(t['remaining_minutes'] for t in plan['unfinished'])
        if remaining:
            answer += f'\n\nYou won’t finish everything in this session: {duration(remaining)} of estimated work will remain. Partial blocks are progress, not completed assignments.'
        else:
            answer += '\n\nThat covers the estimated work on your list.'
        if plan['unused_minutes']:
            answer += f" You have {duration(plan['unused_minutes'])} unallocated."
    return dict(kind='plan', answer=answer, minutes=minutes, plan=plan, text=render_plan(plan))
