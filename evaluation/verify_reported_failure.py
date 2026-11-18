"""Reproduce the reported 'or no?' and 'Whenever i havve time next' flow."""
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
    sources={str(p.relative_to(PROJECT_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (PROJECT_ROOT/'taskpilot').glob('*.py')}
    (folder/'manifest.json').write_text(json.dumps(dict(purpose='Exact reported failure regression, not ten-case evaluation',source_sha256=sources),indent=2))
    data=load_assignments(SYLLABI_FOLDER,'2026-11-17')
    first='I have 3 hours can you help me or no?'
    next_free='Whenever i havve time next'
    async def call(name,message,context=None,history=None):
        payload=dict(message=message,data=data,calendar_mode='demo',preferences={},context=context or {},history=history or [],capture_validation=True)
        tick=time.monotonic()
        try:
            result=await run_ai_chat(payload)
            record=dict(input=payload,result=result,seconds=round(time.monotonic()-tick,3))
            (folder/f'{name}.json').write_text(json.dumps(record,indent=2)+'\n')
            assert result['kind']=='plan' and result['minutes']==180
            assert result['plan']['blocks'][0]['start'].startswith('2026-11-17T10:30')
            assert result['evidence']['facts_checked'] and result['evidence']['critic_reviews']==0
            assert result['evidence']['analyst_tool_outputs']>=1 and result['evidence']['handoff']
            assert result['answer'].strip()==result['ai_guidance'].strip()
            print(f"{name}: PASS ({record['seconds']}s)\n{result['answer']}\n",flush=True)
            return result
        except Exception as exc:
            (folder/f'{name}_failure.json').write_text(json.dumps(dict(input=payload,error=str(exc),diagnostics=getattr(exc,'diagnostics',None)),indent=2)+'\n')
            raise
    async def conversation():
        reply=await call('initial',first)
        await call('next_free',next_free,reply['context'],[dict(role='user',content=first),dict(role='assistant',content=reply['answer'])])
    await asyncio.gather(conversation(),call('after_failed_turn',next_free,history=[dict(role='user',content=first)]))


if __name__=='__main__': asyncio.run(main())
