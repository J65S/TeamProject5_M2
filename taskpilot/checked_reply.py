"""Check response structure and task references without policing AI wording."""
from datetime import datetime
from .workload import format_duration


class ReplyValidationError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code=code


def validate_guidance(reply, intent, verified):
    text=reply.get('guidance')
    if not isinstance(text,str) or not text.strip() or len(text)>5000:
        raise ReplyValidationError('empty_guidance','The AI returned empty or unreadable coaching.')
    blocks=(verified.get('plan') or {}).get('blocks',[])
    target=blocks[0]['task_id'] if blocks else None
    if 'task_id' in reply and reply['task_id'] != target:
        raise ReplyValidationError('wrong_task','The AI recommendation referenced a different assignment from the checked plan.')


def compose_reply(guidance, intent, verified, facts):
    """Show the real allocation by default, alongside natural AI guidance."""
    plan=verified.get('plan')
    if not plan:
        notice=verified.get('calendar',{}).get('notice')
        return guidance.strip()+ ('\n\n'+notice if notice else '')
    zone=verified.get('calendar',{}).get('timezone','America/New_York')
    lines=[guidance.strip(),f'\nStudy schedule ({zone}):']
    if not plan['blocks']:
        lines.append('No blocks scheduled.' if not intent['minutes'] else 'No eligible work fits before its listed deadline in the available opening.')
    previous=None
    for block in plan['blocks']:
        start,end=datetime.fromisoformat(block['start']),datetime.fromisoformat(block['end'])
        same_window=previous and any(datetime.fromisoformat(w['start'])<=previous<start<=datetime.fromisoformat(w['end']) for w in verified.get('calendar',{}).get('windows',[]))
        if same_window:
            lines.append(f"  {previous.strftime('%I:%M %p')}–{start.strftime('%I:%M %p')} | Break ({int((start-previous).total_seconds()//60)} minutes)")
        lines.append(f"  {start.strftime('%a, %b %d %Y · %I:%M %p')}–{end.strftime('%I:%M %p')} | {block['task']} ({format_duration(block['minutes'])}); due {block.get('due_at') or block['due_date']}")
        previous=end
    lines.append(f"Study time: {format_duration(plan['elapsed_minutes'])} including breaks, of {format_duration(intent['minutes'])} available. Unallocated: {format_duration(plan['unused_minutes'])}.")
    lines.append(f"Estimated work remaining after this proposed session: {facts['remaining_work']}.")
    for risk in facts.get('deadline_risks',[]):
        lines.append('Deadline risk: '+', '.join(risk['task_names'])+' — the known free time cannot cover the estimated work before the listed deadline. Confirm date-only cutoff times.')
    if plan.get('split_confirmed'):
        lines.append('The study windows are separate; intervening calendar commitments are outside the study-time budget.')
    if plan.get('blocked'):
        lines.append('Some remaining work has unfinished prerequisites and was not scheduled.')
    return '\n'.join(lines)
