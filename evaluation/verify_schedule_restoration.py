"""Run real CLI requests and stateful follow-ups, preserving every first attempt."""
import argparse
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time

from taskpilot.ai_chat import run_ai_chat
from taskpilot.calendar_planner import calendar_snapshot, preferences, ZONE
from taskpilot.paths import PROJECT_ROOT, SYLLABI_FOLDER
from taskpilot.workload import deadline_at, load_assignments


def verify(result, data, minutes, day, completed=None):
    assert result['kind']=='plan',result.get('answer')
    assert result['minutes']==minutes
    plan=result['plan']
    assert plan and plan['blocks']
    assert plan['elapsed_minutes']<=minutes
    assert plan['scheduled_minutes']+plan['break_minutes']==plan['elapsed_minutes']
    assert sum(b['minutes'] for b in plan['blocks'])==plan['scheduled_minutes']
    assert 'Study schedule (' in result['answer']
    tasks={t['id']:t for t in data['assignments']}
    calendar=calendar_snapshot('demo',datetime.fromisoformat(data['today']).date())
    for b in plan['blocks']:
        start,end=datetime.fromisoformat(b['start']),datetime.fromisoformat(b['end'])
        assert start.astimezone(ZONE).date().isoformat()==day
        assert end<=deadline_at(tasks[b['task_id']])
        assert b['task_id'] not in (completed or [])
        for event in calendar['events']:
            from datetime import timedelta
            assert end<=datetime.fromisoformat(event['start'])-timedelta(minutes=15) or start>=datetime.fromisoformat(event['end'])+timedelta(minutes=15)
    assert result['evidence']['analyst_tool_outputs']>=1 and result['evidence']['handoff']


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    folder=parser.parse_args().output
    folder.mkdir(parents=True,exist_ok=False)
    source_files=[* (PROJECT_ROOT/'taskpilot').glob('*.py'),*SYLLABI_FOLDER.glob('*.txt')]
    sources={str(p.relative_to(PROJECT_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    (folder/'manifest.json').write_text(json.dumps(dict(purpose='Scheduling restoration, targeted real execution; not a ten-case score',source_sha256=sources),indent=2))
    data=load_assignments(SYLLABI_FOLDER,'2026-11-17')
    async def cli(name,message):
        tick=time.monotonic()
        command=[str(PROJECT_ROOT/'.venv/bin/python'),str(PROJECT_ROOT/'agent.py'),'--request',message,'--calendar','demo','--as-of',data['today'],'--json']
        process=await asyncio.create_subprocess_exec(*command,cwd=PROJECT_ROOT,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err=await asyncio.wait_for(process.communicate(),205)
        record=dict(command=command,stdout=out.decode(),stderr=err.decode(),exit_code=process.returncode,seconds=round(time.monotonic()-tick,2))
        (folder/f'{name}.json').write_text(json.dumps(record,indent=2)+'\n')
        assert process.returncode==0,record
        result=json.loads(out)
        verify(result,data,180,data['today'])
        print(f'{name}: scheduling checks passed ({record["seconds"]}s)',flush=True)
        return result
    normal_message='I have three hours today. What should I work on?'
    typo_message='I haev 3 hours today what should i work on'
    normal,typo=await asyncio.gather(cli('normal',normal_message),cli('typo',typo_message))
    assert normal['plan']['blocks']==typo['plan']['blocks']
    context=typo['context']
    history=[dict(role='user',content=typo_message),dict(role='assistant',content=typo['answer'][:2000])]
    for name,message,day in [('shorter','I only have two hours','2026-11-17'),('tomorrow','move this to tomorrow','2026-11-18'),('completed','I already finished that','2026-11-18')]:
        tick=time.monotonic()
        previous_focus=context['focus_task_id']
        payload=dict(message=message,data=data,calendar_mode='demo',preferences={},context=context,history=history,capture_validation=True)
        try:
            result=await run_ai_chat(payload)
        except Exception as exc:
            (folder/f'{name}_failure.json').write_text(json.dumps(dict(input=payload,error=str(exc),diagnostics=getattr(exc,'diagnostics',None)),indent=2))
            raise
        record=dict(input=payload,result=result,seconds=round(time.monotonic()-tick,2))
        (folder/f'{name}.json').write_text(json.dumps(record,indent=2)+'\n')
        verify(result,data,120,day,[previous_focus] if name=='completed' else [])
        if name=='completed':
            assert previous_focus in result['context']['completed_task_ids']
            assert next(t for t in result['assignment_snapshot']['assignments'] if t['id']==previous_focus)['status']=='completed'
        context=result['context']
        history.extend([dict(role='user',content=message),dict(role='assistant',content=result['answer'][:2000])])
        print(f'{name}: scheduling checks passed ({record["seconds"]}s)',flush=True)
    # Original conflict fixture: 11 hours due against at most 10.5 known free hours.
    conflict=load_assignments(PROJECT_ROOT/'evaluation/fixtures/conflicting','2026-10-27')
    result=await run_ai_chat(dict(message='I have three hours today. Prioritize my work.',data=conflict,calendar_mode='demo',preferences={},context={},history=[],capture_validation=True))
    (folder/'deadline_shortfall.json').write_text(json.dumps(result,indent=2)+'\n')
    verify(result,conflict,180,'2026-10-27')
    assert result['answer_facts']['deadline_risks']
    assert 'Deadline risk:' in result['answer']
    print('deadline_shortfall: scheduling checks passed',flush=True)


if __name__=='__main__': asyncio.run(main())
