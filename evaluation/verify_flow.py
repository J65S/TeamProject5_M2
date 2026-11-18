"""Capture a real guided conversation; does not rescore the ten-case suite."""
import asyncio
import json
from pathlib import Path
import time
import argparse

from taskpilot.ai_chat import run_ai_chat
from taskpilot.workload import load_assignments
from taskpilot.paths import SYLLABI_FOLDER


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('evaluation/evidence/guided_flow_2026-11-17'))
    folder=parser.parse_args().output
    folder.mkdir(exist_ok=False)
    data=load_assignments(SYLLABI_FOLDER,'2026-11-17')
    context,history={},[]
    for index,message in enumerate(['I have a few hourz today, i was wondering what work i should get done to be on time','3','Yeah that works','Use another opening today'],1):
        tick=time.monotonic()
        payload=dict(message=message,data=data,calendar_mode='demo',preferences={},context=context,history=history,capture_validation=True)
        try:
            reply=await run_ai_chat(payload)
        except Exception as exc:
            (folder/f'{index}.json').write_text(json.dumps(dict(message=message,error=str(exc),diagnostics=getattr(exc,'diagnostics',None)),indent=2))
            raise
        seconds=round(time.monotonic()-tick,3)
        (folder/f'{index}.json').write_text(json.dumps(dict(message=message,seconds=seconds,result=reply),indent=2)+'\n')
        print(f'{index}: {reply["engine"]} ({seconds}s): {reply["answer"]}\n{reply.get("follow_up", "")}',flush=True)
        if index==1: assert reply['kind']=='clarify' and len(reply['answer'].split())<=35
        if index==2: assert reply['minutes']==180 and reply['plan']['blocks']
        if index==3: assert reply['engine']=='ai_cached_confirmation' and seconds<1
        if index==4: assert reply['plan']['split_confirmed'] and reply['plan']['elapsed_minutes']<=180
        context=reply['context']
        history.extend([dict(role='user',content=message),dict(role='assistant',content=reply['answer'])])


if __name__=='__main__': asyncio.run(main())
