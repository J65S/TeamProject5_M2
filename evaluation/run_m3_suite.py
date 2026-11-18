"""Capture one live execution per M3 case, without modifying application code.
Run: python3 evaluation/run_m3_suite.py --run-dir evaluation/evidence/RUN_ID
Results require manual review; failures are never automatically rerun.
"""
import argparse
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from taskpilot.workload import load_assignments

AS_OF='2026-10-27'
PROMPTS={
'TC01': 'I have 4 hours to study today. What should I work on?',
'TC02': 'I only have 1 hour available today.',
'TC03': 'I have 0 hours available today.',
'TC04': 'Help me plan my assignments.',
'TC05': 'I have 3 hours today, and multiple assignments are due soon. How should I prioritize?',
'TC06': 'I have 2 hours today. Check my upcoming assignments and make a study plan.',
'TC07': 'I have 2 hours today. What upcoming assignments do I have?',
'TC08': 'I now only have 2 hours instead of 4. Please plan using my new availability.',
'TC09': 'I have 1 hour today. Can I finish all my upcoming assignments?',
'TC10': 'I have 3 hours today. What assignments should I work on?',
}

async def command(cmd,path):
    started=datetime.now(ZoneInfo('America/New_York')).isoformat()
    tick=time.monotonic()
    p=await asyncio.create_subprocess_exec(*cmd,cwd=str(ROOT),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    timed_out=False
    try:
        stdout,stderr=await asyncio.wait_for(p.communicate(),timeout=205)
    except asyncio.TimeoutError:
        timed_out=True;p.kill();stdout,stderr=await p.communicate()
    raw=stdout.decode(errors='replace')
    try: parsed=json.loads(raw)
    except ValueError: parsed=None
    record=dict(started_at=started,elapsed_seconds=round(time.monotonic()-tick,3),exit_code=p.returncode,outer_timeout=timed_out,command=cmd,stdout=raw,stderr=stderr.decode(errors='replace'),result=parsed)
    path.write_text(json.dumps(record,indent=2)+'\n')
    return record

async def execute(case,run_dir,limit):
    async with limit:
        print(f'{case} starting',flush=True)
        fixture=ROOT/'evaluation/fixtures'/('conflicting' if case=='TC05' else 'm3_original')
        if case=='TC07': fixture=ROOT/'evaluation/fixtures/retrieval'
        if case=='TC10': fixture=run_dir/'missing_syllabi'
        data=load_assignments(fixture,AS_OF)
        # M3 assumed older work completed; make that assumption explicit for this rerun.
        completed=[t['id'] for t in data.get('assignments',[]) if t['due_date']<AS_OF]
        common=[str(ROOT/'.venv/bin/python'),str(ROOT/'agent.py'),'--syllabi',str(fixture),'--as-of',AS_OF,'--calendar','demo','--json']
        for task_id in completed: common += ['--completed',task_id]
        if case=='TC08':
            initial=await command(common+['--request',PROMPTS['TC01']],run_dir/'TC08_initial.json')
            previous=initial.get('result') or {}
            # Exercise an actual follow-up with the previous AI context and history, not a new isolated prompt.
            payload=dict(message=PROMPTS[case],data=previous.get('assignment_snapshot') or data,calendar_mode='demo',preferences={},context=previous.get('context') or {},history=[dict(role='user',content=PROMPTS['TC01']),dict(role='assistant',content=previous.get('answer',''))])
            if 'assignment_snapshot' not in previous:
                for t in payload['data'].get('assignments',[]):
                    if t['id'] in completed: t.update(status='completed',estimated_minutes=0)
            input_path=run_dir/'TC08_followup_input.json';input_path.write_text(json.dumps(payload,indent=2))
            worker=[str(ROOT/'.venv/bin/python'),'-m','evaluation.suite_followup',str(input_path)]
            final=await command(worker,run_dir/'TC08.json')
            final['initial_turn_succeeded']=initial['exit_code']==0 and previous.get('engine')=='two_agent_ai'
            (run_dir/'TC08.json').write_text(json.dumps(final,indent=2)+'\n')
        else:
            final=await command(common+['--request',PROMPTS[case]],run_dir/f'{case}.json')
        print(f"{case} captured: exit={final['exit_code']}, elapsed={final['elapsed_seconds']}s",flush=True)

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-dir',type=Path,required=True);args=parser.parse_args()
    run_dir=args.run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()): raise SystemExit('Choose a new empty run directory; evidence will not be overwritten.')
    run_dir.mkdir(parents=True,exist_ok=True)
    retrieval=ROOT/'evaluation/fixtures/retrieval';retrieval.mkdir(exist_ok=True)
    for path in (ROOT/'evaluation/fixtures/m3_original').glob('*.txt'):
        (retrieval/path.name).write_bytes(path.read_bytes())
    with (retrieval/'software_engineering.txt').open('a') as f:
        f.write('\n\nTask: Prepare TaskPilot poster\nDue: 2026-11-15\nEstimated hours: 2\n')
    files={}
    for folder in ('taskpilot','evaluation/fixtures'):
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and p.suffix in ('.py','.txt'):
                files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    metadata=dict(run_date=datetime.now(ZoneInfo('America/New_York')).isoformat(),as_of=AS_OF,fixture_git_revision='30461f1',application_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),working_tree_modified=True,model='gpt-oss unless NRP_MODEL override (actual returned model recorded)',calendar='fictional demo at 09:30 Eastern',concurrency=2,scoring='Manual against M3 case criteria; first execution only; no selective reruns',source_sha256=files)
    (run_dir/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    limit=asyncio.Semaphore(2)
    await asyncio.gather(*(execute(case,run_dir,limit) for case in PROMPTS))

if __name__=='__main__': asyncio.run(main())
