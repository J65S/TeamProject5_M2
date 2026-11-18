"""Repeat the actual failed request with natural AI prose enabled.

This records first attempts and never edits the ten-case evaluation score.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time

from taskpilot.ai_chat import run_ai_chat
from taskpilot.workload import load_assignments
from taskpilot.paths import PROJECT_ROOT, SYLLABI_FOLDER


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    folder=parser.parse_args().output
    folder.mkdir(parents=True,exist_ok=False)
    data=load_assignments(SYLLABI_FOLDER,'2026-11-17')
    sources={str(p.relative_to(PROJECT_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (PROJECT_ROOT/'taskpilot').glob('*.py')}
    (folder/'manifest.json').write_text(json.dumps(dict(purpose='Repeated reported request with wording gates removed',source_sha256=sources),indent=2))
    limit=asyncio.Semaphore(2)
    async def run(index):
        async with limit:
            payload=dict(message='I have 3 hours help me plan',data=data,calendar_mode='demo',preferences={},context={},history=[],capture_validation=True)
            tick=time.monotonic()
            try:
                result=await run_ai_chat(payload)
                record=dict(input=payload,result=result,seconds=round(time.monotonic()-tick,3))
                assert result['kind']=='plan' and result['minutes']==180
                assert result['plan']['blocks'][0]['start'].startswith('2026-11-17T10:30')
                assert result['answer']==result['ai_guidance'].strip()
                record['checks']='PASS'
            except Exception as exc:
                record=dict(input=payload,error=str(exc),diagnostics=getattr(exc,'diagnostics',None),checks='FAIL')
            (folder/f'attempt_{index}.json').write_text(json.dumps(record,indent=2)+'\n')
            print(f"Attempt {index}: {record['checks']} ({record.get('seconds','?')}s)\n{record.get('result',{}).get('answer',record.get('error'))}\n",flush=True)
            return record['checks']=='PASS'
    passed=await asyncio.gather(*(run(i) for i in range(1,4)))
    if not all(passed): raise SystemExit(1)


if __name__=='__main__': asyncio.run(main())
