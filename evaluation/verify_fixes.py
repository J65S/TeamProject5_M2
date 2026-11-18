"""Targeted live smoke checks, separate from the ten-case evaluation and score.

Usage: .venv/bin/python -m evaluation.verify_fixes --output NEW_EMPTY_DIRECTORY
This calls NRP, saves every response/error, and never updates results.csv/md.
"""
import argparse
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path

from taskpilot.ai_chat import run_ai_chat
from taskpilot.workload import load_assignments

ROOT = Path(__file__).resolve().parents[1]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checks', nargs='+', help='Optional named subset; prior attempts remain preserved')
    args=parser.parse_args()
    output = args.output
    if output.exists() and any(output.iterdir()):
        raise SystemExit('Choose a new empty directory; prior evidence will not be overwritten.')
    output.mkdir(parents=True, exist_ok=True)
    checks = [
        ('clarification', 'm3_original', 'Can you help me plan my assignments?'),
        ('shared_deadline', 'conflicting', 'I have three hours today. How can I work toward both assignments before their shared deadline?'),
        ('complete_inventory', 'retrieval', 'I have two hours today. Please list my upcoming assignments with their due dates.'),
        ('workload_feasibility', 'm3_original', 'I only have one hour today. Can I finish all my upcoming assignments?'),
    ]
    if args.checks:
        unknown=set(args.checks)-{c[0] for c in checks}
        if unknown: raise SystemExit('Unknown checks: ' + ', '.join(sorted(unknown)))
        checks=[c for c in checks if c[0] in args.checks]
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for folder in ('taskpilot', 'evaluation/fixtures') for p in (ROOT/folder).rglob('*')
               if p.suffix in ('.py', '.txt')}
    (output/'manifest.json').write_text(json.dumps(dict(purpose='Targeted fix verification, not a ten-case score', started_at=datetime.now().isoformat(), source_sha256=sources), indent=2)+'\n')
    limit = asyncio.Semaphore(2)
    async def check(name, fixture, message):
        async with limit:
            data = load_assignments(ROOT/'evaluation/fixtures'/fixture, '2026-10-27')
            for t in data['assignments']:
                if t['due_date'] < data['today']:
                    t.update(status='completed', estimated_minutes=0)
            payload = dict(message=message, data=data, calendar_mode='demo', preferences={}, context={}, history=[],capture_validation=True)
            tick = asyncio.get_running_loop().time()
            record = dict(input=payload)
            try:
                reply = await run_ai_chat(payload)
                record['result'] = reply
                assert reply['evidence'].get('facts_checked') or reply['evidence'].get('critic_passed') or reply['kind']=='clarify'
                if name == 'clarification':
                    assert reply['kind'] == 'clarify' and reply['plan'] is None and '?' in reply['answer']
                elif name == 'complete_inventory':
                    assert 'Prepare TaskPilot poster' in reply['answer'] and reply['plan'] is None
                else:
                    plan = reply['plan']
                    assert plan['elapsed_minutes'] <= reply['minutes']
                    assert all(b['start'][:10] == data['today'] for b in plan['blocks'])
                    assert sum(t['remaining_minutes'] for t in plan['unfinished']) == reply['answer_facts']['remaining_work_minutes']
                record['smoke_check'] = 'PASS'
            except Exception as exc:
                record.update(smoke_check='FAIL', error=str(exc))
                if getattr(exc,'diagnostics',None):
                    record['validation_diagnostics']=exc.diagnostics
            record['elapsed_seconds'] = round(asyncio.get_running_loop().time()-tick, 2)
            (output/f'{name}.json').write_text(json.dumps(record, indent=2)+'\n')
            print(f"{name}: {record['smoke_check']} ({record['elapsed_seconds']}s)", flush=True)
            return record['smoke_check'] == 'PASS'
    passed = await asyncio.gather(*(check(*c) for c in checks))
    if not all(passed):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
