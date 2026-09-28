import sys
sys.stdout.reconfigure(encoding="utf-8")

from agents import (
    Agent,
    Runner,
    function_tool,
    set_default_openai_client,
    set_default_openai_api,
    set_trace_processors,
)
from agents.tracing import TracingProcessor
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict
import os

# Load environment variables from .env file
load_dotenv()

# Point the Agents SDK at the NRP (Nautilus) OpenAI-compatible endpoint
client = AsyncOpenAI(
    base_url=os.getenv("NRP_BASE_URL"),
    api_key=os.getenv("NRP_API_KEY"),
)
set_default_openai_client(client, use_for_tracing=False)
set_default_openai_api("chat_completions")


import asyncio
from pathlib import Path
from agents.mcp import MCPServerStdio


async def main():
    server_file = Path(__file__).with_name("mcp_server.py")

    async with MCPServerStdio(
        name="Student Assignments",
        params={
            "command": sys.executable,
            "args": [str(server_file)],
        },
    ) as server:
        agent = Agent(
            name="Student Workload Planner",
            model="gpt-oss",
            instructions=(
                "Help a student plan their assignment work. "
                "Always call get_assignments before making a plan. "
                "Use only the assignments returned by that tool. "
                "Ask how many hours the student has if they did not say. "
                "State clearly when the available time is insufficient."
            ),
            mcp_servers=[server],
        )

        result = await Runner.run(
            agent,
            input("How much time do you have, and what would you like help planning? "),
        )
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())