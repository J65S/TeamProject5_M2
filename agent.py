import sys
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_disabled,
)
from agents.mcp import MCPServerStdio


# Load settings from the .env file
load_dotenv()

# Configure the NRP OpenAI-compatible endpoint
client = AsyncOpenAI(
    base_url=os.getenv("NRP_BASE_URL"),
    api_key=os.getenv("NRP_API_KEY"),
)

set_default_openai_client(client, use_for_tracing=False)
set_default_openai_api("chat_completions")

# Use NRP without exporting traces to OpenAI
set_tracing_disabled(True)


async def main():
    server_file = Path(__file__).with_name("mcp_server.py")

    async with MCPServerStdio(
        name="Student Assignments",
        params={
            "command": sys.executable,
            "args": [str(server_file)],
        },
    ) as server:

        # Agent 1: retrieve and analyze assignments
        assignment_analyst = Agent(
            name="Assignment Analyst",
            model="gpt-oss",
            instructions=(
                "You analyze a student's assignments before a schedule is made. "
                "Always call the get_assignments tool. "
                "Use only assignments returned by the tool. "
                "For each assignment, report the course, task, due date, "
                "and estimated hours. "
                "Calculate the total estimated hours. "
                "Include the student's available time if they provided it. "
                "After receiving the tool result, briefly explain which "
                "assignments have the closest deadlines and note their "
                "estimated workloads. "
                "Do not create the final study schedule."
            ),
            mcp_servers=[server],
        )

        # Agent 2: create a plan using the analyst's findings
        schedule_planner = Agent(
            name="Schedule Planner",
            model="gpt-oss",
            instructions=(
                "Create a realistic study plan using the assignment analysis "
                "and the student's request. "
                "Do not invent assignments or deadlines. "
                "Do not schedule more time than the student has available. "
                "If there is not enough time to complete everything, "
                "explain what remains and recommend a next step. "
                "If the student did not provide their available hours, "
                "ask them for that information instead of guessing."
            ),
        )

        student_request = input(
            "How much time do you have, and what would you like help planning? "
        )

        print("\n--- Assignment Analyst is working ---\n")

        analyst_result = await Runner.run(
            assignment_analyst,
            student_request,
        )

        # Display the actual tool activity from the analyst's run.
        print("\n--- Assignment Analyst tool activity ---")

        for item in analyst_result.new_items:
            if item.type == "tool_call_item":
                print("\nAction: Assignment Analyst called a tool.")
                print(item.raw_item)

            elif item.type == "tool_call_output_item":
                print("\nTool result:")
                print(item.output)

        # Everything below is outside the loop, so it only runs once.
        analysis = str(analyst_result.final_output or "").strip()

        if not analysis or analysis.startswith('{"tool"'):
            print(
                "\nThe Assignment Analyst did not return assignment details. "
                "Please run the program again."
            )
            return

        # Explicit handoff to the Schedule Planner
        handoff_payload = (
            f"Student's original request:\n{student_request}\n\n"
            f"Assignment Analyst's findings:\n{analysis}"
        )

        print("\n--- Handoff to Schedule Planner ---")
        print(handoff_payload)

        print("\n--- Schedule Planner is working ---\n")

        planner_result = await Runner.run(
            schedule_planner,
            handoff_payload,
        )

        print("\n--- Final study plan ---\n")
        print(planner_result.final_output)


if __name__ == "__main__":
    asyncio.run(main())