"""Ground AI intent and answer requirements in user statements and source facts.

These checks constrain scheduling and arithmetic; the two AI agents still
interpret the question, retrieve its sources, and write the student-facing answer.
"""
from datetime import datetime, timedelta
from copy import deepcopy
import re

from .calendar_planner import ZONE, free_windows
from .conversation import normalize_time
from .workload import completed_ids, deadline_at, format_duration, parse_minutes


def request_text(message):
    """Normalize common typing slips for routing; retain the original request."""
    aliases={'haev':'have','hvae':'have','havve':'have','hourz':'hours','tommorrow':'tomorrow'}
    return re.sub(r'\b(?:'+ '|'.join(aliases)+r')\b',lambda m:aliases[m[0].lower()],message,flags=re.I)


def availability(message):
    text = normalize_time(request_text(message))
    if re.search(r'\b(?:i .*?have|available|free|can spare)\b', text) and re.search(r'\b(?:hours?|minutes?|hrs?|mins?)\b', text):
        # "Can you help me or no?" is not an alternative duration.
        alternative=r'\d+(?:\.\d+)?\s*(?:(?:hours?|hrs?|minutes?|mins?)\s*)?\bor\b\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\b'
        if re.search(alternative, text) or re.search(r'(?<!\w)-\s*\d', text):
            raise ValueError('Choose one nonnegative time budget.')
    # Do not mistake an assignment's estimate for the student's availability.
    match = re.search(r'(?:\bi\s+(?:(?:now|only|currently|just)\s+)*(?:have|have got|can study for|can work for)\s+(?:(?:only|just)\s+)?|^\s*)(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b(?:\s+(?:and\s+)?\d+\s*(?:minutes?|mins?|m)\b)?)', text)
    if not match:
        match = re.search(r'(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b)\s+(?:available|free|to study)', text)
    if match:
        return parse_minutes(match[1])
    return None


def quoted_availability(parsed, messages):
    """Allow the AI to recognize unfamiliar phrasing with a checkable quote."""
    quote=parsed.get('availability_quote')
    minutes=parsed.get('minutes')
    if not isinstance(quote,str) or not quote.strip() or type(minutes) is not int:
        return None
    if not any(quote.casefold() in message.casefold() for message in messages):
        return None
    # A quote of an assignment estimate alone is not evidence of availability.
    duration_only=re.fullmatch(r'\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)(?:\s+(?:and\s+)?\d+\s*(?:minutes?|mins?|m))?\s*[.!]?\s*',normalize_time(request_text(quote)),re.I)
    if not re.search(r'\b(?:i|we|my|our|available|free|spare)\b',quote,re.I) and not duration_only:
        return None
    durations=re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b',normalize_time(request_text(quote)))
    try:
        return minutes if durations and parse_minutes(' '.join(durations))==minutes else None
    except ValueError:
        return None


def with_user_progress(data, ids):
    """Apply reported completions to this conversation, without editing files."""
    result=deepcopy(data)
    ids=set(ids)
    for task in result['assignments']:
        if task['id'] in ids:
            task.update(status='completed',estimated_minutes=0,progress_source='user report in conversation')
    result['total_estimated_minutes']=sum(t['estimated_minutes'] for t in result['assignments'])
    return result


def vague_hours(payload):
    """A fuzzy duration needs a short AI question, not a full planning cycle."""
    fuzzy=bool(re.search(r'\b(?:a\s+)?(?:few|couple|some|several)\s+hour[sz]?\b',payload['message'],re.I))
    if not fuzzy or payload.get('explicit_minutes') is not None:
        return False
    try:
        return availability(payload['message']) is None
    except ValueError:
        return False


def ground_intent(parsed, payload, calendar):
    """Remove model-added constraints; missing availability becomes a question."""
    intent = dict(parsed)
    message = request_text(payload['message'])
    history = [h.get('content', '') for h in payload.get('history', []) if h.get('role') == 'user']
    prior = payload.get('context') or {}
    minutes = payload.get('explicit_minutes')
    ambiguous = False
    if minutes is None:
        try:
            minutes = availability(message)
            if minutes is None and prior.get('awaiting') == 'hours' and re.fullmatch(r'\s*(?:\d+(?:\.\d+)?|one|two|three|four|five|six)\s*[.!]?\s*', message, re.I):
                minutes = availability('I have ' + message.strip().rstrip('.!') + ' hours')
        except ValueError:
            ambiguous = True
    if minutes is None and not ambiguous:
        minutes=quoted_availability(parsed,[payload['message']])
    current_availability=minutes is not None
    if minutes is None and not ambiguous:
        for old in reversed(history):
            try:
                minutes = availability(old)
            except ValueError:
                continue
            if minutes is not None:
                break
        if minutes is None and prior.get('_grounded') and type(prior.get('minutes')) is int and 0 <= prior['minutes'] <= 1440:
            minutes=prior['minutes']
        if minutes is None:
            minutes=quoted_availability(parsed,[payload['message'],*history])
    intent['minutes'] = minutes
    next_free=bool(re.search(r'\bwhenever\b|\bearliest\b|\bnext\s+(?:free|available)\b|\bas soon as\b|\bwhen(?:ever)?\b.*\b(?:free|time next)\b',message,re.I))
    # Facts requested alongside availability must still be answered as facts.
    planning = bool(re.search(r'\b(?:work.*?(?:get done|work on)|work on|prioriti[sz]e|study plan|plan|figure\b.*\bout|you (?:choose|pick|decide)|move (?:this|it)|reschedule)\b', message, re.I))
    inventory = bool(re.search(r'\b(?:what|which|list|show)\b.*\b(?:assignments|tasks|deadlines)\b', message, re.I)) and not planning
    feasibility = bool(re.search(r'\b(?:can|could)\s+i\s+(?:finish|complete)\b', message, re.I))
    intent['request_kind'] = 'inventory' if inventory else 'feasibility' if feasibility else 'plan' if intent.get('action') == 'plan' else 'answer'
    if inventory:
        intent['action'] = 'answer'
    elif planning:
        intent['action'] = 'plan' if minutes is not None else 'clarify'
    elif feasibility:
        intent['action'] = 'plan' if minutes is not None else 'answer'
    elif not inventory and (current_availability or next_free or (minutes is not None and re.search(r'\b(?:help|study|work|have)\b',message,re.I))):
        intent['action']='plan' if minutes is not None else 'clarify'
    elif minutes is None and intent.get('action') == 'plan':
        intent['action'] = 'clarify'
    if minutes is None and not inventory and re.search(r'\bplan\b', message, re.I):
        intent['action'] = 'clarify'
    if ambiguous:
        intent['action'] = 'clarify'
        intent['clarification_reason'] = 'Choose one nonnegative available time budget.'
    split_requested = bool(re.search(r'\b(?:another|additional|next)\s+(?:opening|window|session)|\b(?:split|spread)\b.*\b(?:today|windows|sessions|openings)\b|\bplan the rest\b',message,re.I))
    prior_windows=prior.get('max_windows',1)
    prior_windows=prior_windows if type(prior_windows) is int else 1
    intent['max_windows'] = min(3, max(1, prior_windows) + 1) if split_requested else 1
    if split_requested:
        intent['action']='plan' if minutes is not None else 'clarify'

    # Carry constraints only from our grounded prior turn, never assistant prose.
    carried = prior if prior.get('_grounded') else {}
    timing = message if re.search(r'\b(?:after|start|tomorrow|today|done with|finished with)\b', message, re.I) else ''
    intent['day'] = carried.get('day')
    date = re.search(r'\b\d{4}-\d{2}-\d{2}\b', message)
    if date:
        intent['day'] = date[0]
    elif re.search(r'\btoday\b', message, re.I):
        intent['day'] = payload['data']['today']
    elif re.search(r'\btomorrow\b', message, re.I):
        intent['day'] = (datetime.fromisoformat(payload['data']['today']) + timedelta(days=1)).date().isoformat()
    elif intent.get('day') is None:
        # Accept an explicit ISO date; other date language requires clarification.
        intent['day'] = payload['data']['today']
    intent['after_last_event'] = carried.get('after_last_event', False)
    intent['not_before'] = carried.get('not_before')
    if timing and re.search(r'\b(?:after|start|done with|finished with)\b', timing, re.I):
        intent['after_last_event'] = False
        intent['not_before'] = None
        if re.search(r'(?:done|finished)\s+with\s+(?:my\s+)?day|after\s+(?:my\s+)?(?:last event|last commitment|day ends)', timing, re.I):
            intent['after_last_event'] = True
        else:
            event = re.search(r'\bafter\s+(?:my\s+)?(work|shift|class)\b', timing, re.I)
            clock = re.search(r'\b(?:after|start(?:\s+at)?)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', timing, re.I)
            if event:
                pattern = 'class' if event[1].lower() == 'class' else 'work|shift'
                matches = [e for e in calendar.get('events', []) if re.search(pattern, e['title'], re.I) and datetime.fromisoformat(e['end']).astimezone(ZONE).date().isoformat() == intent['day']]
                if matches:
                    intent['not_before'] = max(e['end'] for e in matches)
                else:
                    intent['action'] = 'clarify'
                    intent['clarification_reason'] = 'Which calendar event is your work or class commitment?'
            elif clock:
                hour, minute = int(clock[1]), int(clock[2] or 0)
                if not 1 <= hour <= 12 or minute > 59:
                    intent['action'] = 'clarify'
                else:
                    stamp = datetime.fromisoformat(intent['day']).replace(tzinfo=ZONE, hour=hour % 12 + (12 if clock[3].lower() == 'pm' else 0), minute=minute)
                    intent['not_before'] = stamp.isoformat()
            else:
                intent['action'] = 'clarify'
                intent['clarification_reason'] = 'What time or calendar event should this session start after?'
    # A changed day invalidates an old timestamp unless restated by the user.
    if intent.get('not_before') and datetime.fromisoformat(intent['not_before']).astimezone(ZONE).date().isoformat() != intent['day']:
        intent['not_before'] = None
    if next_free:
        intent.update(action='plan' if minutes is not None else 'clarify',after_last_event=False,not_before=None,max_windows=1)

    named = [t['id'] for t in payload['data']['assignments'] if t['task'].casefold() in message.casefold() or t['course'].casefold() in message.casefold()]
    carried_scope=carried.get('task_ids',[]) if carried.get('restrict_tasks') else []
    if re.search(r'\b(?:all (?:my )?assignments|anything|you (?:choose|pick|decide)|figure.*out)\b',message,re.I):
        carried_scope=[]
    intent['restrict_tasks'] = bool(named and intent.get('restrict_tasks') is True) or bool(carried_scope and not named)
    intent['task_ids'] = named if named and intent['restrict_tasks'] else carried_scope if intent['restrict_tasks'] else []
    known={t['id'] for t in payload['data']['assignments']}
    completed=[i for i in carried.get('completed_task_ids',[]) if i in known]
    reported_done=bool(re.search(r'\bi\s+(?:(?:have|already|just)\s+)*(?:finished|completed|submitted|am done with)\b|\bi[’\x27]ve\s+(?:already\s+)?(?:finished|completed|submitted)\b',message,re.I))
    reported_done=reported_done and not re.search(r"\b(?:not|almost|half|part|partly|some)\b|n[’']t\b",message,re.I)
    if reported_done:
        done=named or ([carried['focus_task_id']] if re.search(r'\b(?:that|it)\b',message,re.I) and carried.get('focus_task_id') in known else parsed.get('task_ids',[]))
        if not named and re.search(r'\b(?:that|it|this)\b',message,re.I) and carried.get('focus_task_id') not in known:
            done=[]  # An unresolved pronoun is not evidence for a guessed ID.
        if done and all(i in known for i in done):
            completed=list(dict.fromkeys([*completed,*done]))
            intent['action']='plan' if minutes is not None else 'clarify'
            if intent['task_ids'] and set(intent['task_ids']) <= set(completed):
                intent.update(restrict_tasks=False,task_ids=[])
        else:
            intent.update(action='clarify',clarification_reason='Which assignment did you finish?')
    intent['completed_task_ids']=completed
    intent['focus_task_id']=carried.get('focus_task_id')
    if intent['action']=='clarify' and minutes is None and not intent.get('clarification_reason'):
        intent['clarification_reason']='How much study time do you have available? I can choose the assignment from the deadlines.'
    if intent['action']=='plan' and intent['request_kind'] != 'feasibility':
        intent['request_kind']='plan'
    intent['_grounded'] = True
    return intent


def answer_facts(intent, data, verified, calendar=None, prefs=None):
    active = [t for t in data['assignments'] if t['id'] not in completed_ids(data)]
    total = sum(t['estimated_minutes'] for t in active)
    plan = verified.get('plan') or {}
    focus = plan.get('scheduled_minutes', 0)
    remaining = total-focus
    inventory = [dict(task=t['task'], course=t['course'], due=t.get('due_at') or t['due_date'], estimated_minutes=t['estimated_minutes']) for t in active]
    progress = []
    for t in active:
        allocated = sum(b['minutes'] for b in plan.get('blocks', []) if b['task_id'] == t['id'])
        progress.append(dict(task=t['task'], before_minutes=t['estimated_minutes'], proposed_focus_minutes=allocated,
                             after_minutes=t['estimated_minutes']-allocated,
                             after=format_duration(t['estimated_minutes']-allocated)))
    risks = []
    if calendar and 'events' in calendar and not verified.get('calendar', {}).get('notice'):
        now = datetime.fromisoformat(verified.get('calendar',{}).get('planning_start') or calendar.get('simulated_now') or datetime.now(ZONE).isoformat())
        windows = free_windows(calendar, prefs, now)
        coverage_end = datetime.fromisoformat(calendar['coverage_end'])
        for cutoff in sorted({deadline_at(t) for t in active}):
            if cutoff <= now:
                due=[t for t in active if deadline_at(t)==cutoff]
                risks.append(dict(through=cutoff.isoformat(),task_names=[t['task'] for t in due],
                                  work_minutes=sum(t['estimated_minutes'] for t in due),optimistic_free_minutes=0,
                                  note='The listed deadline precedes the requested session; completion is unconfirmed.'))
                continue
            if cutoff > coverage_end:
                continue  # Unknown later calendar coverage is not evidence of a shortage.
            due = [t for t in active if deadline_at(t) <= cutoff]
            demand = sum(t['estimated_minutes'] for t in due)
            capacity = sum(max(0, int((min(b, cutoff)-a).total_seconds()//60)) for a,b in windows if a < cutoff)
            if demand > capacity:
                risks.append(dict(through=cutoff.isoformat(), task_names=[t['task'] for t in due],
                                  work_minutes=demand, optimistic_free_minutes=capacity,
                                  shortfall_at_least_minutes=demand-capacity,
                                  note='Upper bound ignores breaks; date-only deadlines use end of listed date, not a verified cutoff.'))
    required = []
    next_opening = None
    if plan.get('blocks') and plan.get('unused_minutes'):
        last_end=max(b['end'] for b in plan['blocks'])
        next_opening=next((w for w in verified.get('calendar',{}).get('windows',[]) if w['start'] >= last_end),None)
    if intent['action'] == 'clarify':
        required = []
    elif intent.get('request_kind') == 'inventory':
        required = [str(t[k]) for t in inventory for k in ('task', 'course', 'due')]
    elif plan or intent.get('request_kind') == 'feasibility':
        required = [format_duration(total), format_duration(remaining)]
        if plan.get('blocks'):
            required += [format_duration(focus), format_duration(plan['elapsed_minutes'])]
        if plan.get('shorter_window'):
            required += ['shorter']
        if plan.get('unused_minutes'):
            required += [format_duration(plan['unused_minutes']) + ' unused']
        if risks:
            required += ['at risk']
    return dict(total_work_minutes=total, total_work=format_duration(total), focus_minutes=focus,
                remaining_work_minutes=remaining, remaining_work=format_duration(remaining),
                inventory=inventory, required_answer_phrases=list(dict.fromkeys(required)),
                task_progress=progress,
                next_opening=next_opening,
                deadline_risks=risks,
                can_finish_all=total <= focus,
                session_elapsed_minutes=plan.get('elapsed_minutes', 0),
                session_break_minutes=plan.get('break_minutes', 0),
                requested_elapsed_minutes=intent.get('minutes'))


def check_answer_facts(answer, intent, facts):
    # Accept numerically equivalent units (65 minutes == 1 hour 5 minutes).
    # Requiring both wordings made accurate answers fail formatting checks.
    normalized = ' '.join(answer.casefold().split())
    pattern = r'(?<![\w.])(\d+(?:\.\d+)?)\s*[-‑–]?\s*(hours?|hrs?|minutes?|mins?)(?:\s+(?:and\s+)?(\d+(?:\.\d+)?)\s*[-‑–]?\s*(minutes?|mins?))?\b'
    def amount(match):
        return float(match[1])*(60 if match[2].startswith('h') else 1) + float(match[3] or 0)
    claims = list(re.finditer(pattern, normalized))
    def present(phrase):
        phrase = phrase.casefold()
        unused = phrase.endswith(' unused')
        duration = re.fullmatch(pattern, phrase.removesuffix(' unused'))
        if duration:
            return any(amount(m) == amount(duration) and (not unused or normalized[m.end():].lstrip().startswith('unused')) for m in claims)
        return phrase in normalized
    missing = [p for p in facts['required_answer_phrases'] if not present(p)]
    if missing:
        raise ValueError('Include these source facts verbatim: ' + '; '.join(missing))
    if intent['action'] == 'clarify' and '?' not in answer:
        raise ValueError('Ask a specific clarification question before planning.')
    if intent['action'] == 'clarify' and intent.get('minutes') is None and not re.search(r'\b(?:time|minutes|hours|long)\b', answer, re.I):
        raise ValueError('Ask how much time the student has available.')
    if intent['action'] == 'clarify' and len(answer.split()) > 55:
        raise ValueError('Ask one short clarification question, at most 55 words; do not list the backlog.')
    if intent['action'] in ('plan','clarify') and re.search(r'(?:which|what).*?(?:seems? (?:most )?urgent|(?:want|like|prefer) to (?:tackle|work on))',answer,re.I):
        raise ValueError('Recommend a task from the deadlines instead of asking the student to prioritize for you.')
    if not intent.get('after_last_event') and re.search(r'(?:after|once).*?(?:your|the)\s+(?:last|final)\s+(?:event|commitment)|(?:done|finished)\s+with\s+your\s+day', answer, re.I):
        raise ValueError('Remove the unrequested after-last-event constraint. Ask only about missing availability.')
    if re.search(r'\bonly (?:free |available )?(?:slot|window|opening)\b', answer, re.I):
        raise ValueError('Do not claim this is the only free window; describe the chosen session.')
    if intent.get('request_kind') == 'feasibility' and not facts['can_finish_all'] and not re.search(r'\b(?:no|cannot|can’t|can\x27t|won’t|won\x27t|not enough|wouldn’t|wouldn\x27t)\b', answer, re.I):
        raise ValueError('Clearly say the available session cannot finish all the work.')
