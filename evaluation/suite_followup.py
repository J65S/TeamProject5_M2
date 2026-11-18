"""Invoke the same AI engine with recorded prior-turn context for evaluation."""
import asyncio
import json
from pathlib import Path
import sys
from taskpilot.ai_chat import run_ai_chat, AIRequestError

async def main():
    try:
        result=await run_ai_chat(json.loads(Path(sys.argv[1]).read_text()))
        print(json.dumps(result))
    except AIRequestError as exc:
        print(json.dumps(dict(engine='ai_unavailable',error=str(exc))))
        return 1

if __name__=='__main__': sys.exit(asyncio.run(main()) or 0)
