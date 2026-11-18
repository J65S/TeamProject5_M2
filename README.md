# TeamProject5_M4 — TaskPilot Student Workload Tracker

TaskPilot turns a student's available time and syllabus assignments into a study plan. Two AI agents retrieve assignment data through MCP, interpret the request, and explain the plan. Python computes the schedule and checks deadlines, available time, and calendar conflicts. TaskPilot runs locally as a browser dashboard or terminal chat, with an offline CLI for deterministic checks.

## Quick start

Run these commands from the project root. Python 3.10+ is required. To try scheduling without model credentials or dependencies:

```bash
python3 agent.py --offline --request "I have 90 minutes"
```

For AI chat, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a local `.env` beside `agent.py` and keep it out of Git:

```dotenv
NRP_BASE_URL=YOUR_NRP_OPENAI_COMPATIBLE_BASE_URL
NRP_API_KEY=YOUR_NRP_API_KEY
```

The recorded live checks used `gpt-oss` through NRP. Set `NRP_MODEL` to override the model or `NRP_REASONING_EFFORT` to change the default of `low`.

- **Dashboard:** Run `python3 web_app.py` and open [http://127.0.0.1:8000](http://127.0.0.1:8000) on the same computer. Use `--port 8080` for a different port. The server binds to localhost. Press Ctrl+C to stop it.
- **Terminal:** Run `python agent.py` and choose terminal chat or the dashboard. Use `/details` to inspect the checked schedule and tool evidence, `/new` to reset the conversation, and `/quit` to exit.
- **Scripted runs:** Use `--request` for a single turn, `--json` for structured output, or `--help` for all options. The launchers also work as `python3 -m taskpilot.agent` and `python3 -m taskpilot.web_app`. Custom `--syllabi` paths are relative to the working directory.

```bash
python agent.py --request "I have 90 minutes. What should I work on?" --details
python agent.py --demo --calendar demo --as-of 2026-12-01
python3 agent.py --offline --minutes 90 --as-of 2026-12-01 --json
python3 -m unittest discover -s tests -v
```

## Using TaskPilot

Ask “I have an hour. What should I work on?” or “What assignments are due tomorrow?” After a plan, try “I only have 30 minutes now” or “Start when I’m done with my day.” TaskPilot accepts common written and numeric durations and asks a short follow-up when availability is unclear. It retains the last explicit budget and timing preferences within the conversation. Zero available minutes produces an empty schedule.

The dashboard shows the checked study blocks below the AI reply, including clock times, breaks, remaining work, and deadline risks. Overdue assignments stay visible until the student explicitly reports completion. A proposed study block or a simple acknowledgment leaves completion status alone. Explicit completion applies to the current conversation. In scripted CLI runs, repeat `--completed TASK_ID` to report multiple completed tasks.

### Assignments and calendar

| Source | What it provides |
|---|---|
| Dashboard example week | Six fictional assignments with dates relative to the conversation date. |
| Project syllabus files | 24 fictional assignments with fixed dates of December 1–7, 2026. This is the default CLI assignment source. Choose the relative-date option in the dashboard or pass `--relative-dates` in the CLI to re-anchor the demo. |
| Interview demo calendar | A repeatable fictional calendar that simulates 9:30 AM on the conversation date. |
| My Google Calendar | A read-only snapshot of the primary calendar in `.local/calendar.json`. Planning uses its coverage and rejects verified-window planning when the snapshot is older than 24 hours or outside its coverage. |

Assignment files support stable IDs, remaining effort, exact due times and timezones, status, prerequisites, split rules, and suggested first steps. Older files with task names, dates, and estimated hours still load. The supplied assignments are demonstration data. See [the assignment format](data/README.md).

The planner starts with the first eligible window on the selected day. It respects study hours, buffers, and known deadline cutoffs. Breaks count against the study-time budget. Add another window through an explicit request, such as “Use another opening today.” Busy gaps between windows count toward the clock span and are excluded from the study-time budget.

Google Calendar supplies availability from a saved snapshot. Refreshing from the app requires a separate Google access token. TaskPilot proposes calendar blocks and can export an `.ics` file for manual import. Calendar events and Canvas assignments are outside the app's write and import workflows. See [calendar setup](docs/CALENDAR_SETUP.md).

### Interview mode

Use the dashboard's fictional assignment week and **Interview demo** calendar for a repeatable session. Start a **New conversation** between participants. With consent, **Save conversation** downloads the questions, replies, assignment snapshots, timing, and AI request outcomes as JSON. Record ratings and observations separately. See the [facilitator guide](docs/INTERVIEW_QUICK_START.md).

## Architecture

| Component | Responsibility |
|---|---|
| `agent.py`, `web_app.py`, `web/` | CLI and local dashboard entry points and frontend. |
| `taskpilot/ai_chat.py`, `taskpilot/mcp_server.py` | The analyst retrieves the assignment snapshot via MCP and interprets the request. The study advisor receives the checked plan and explains it. |
| `taskpilot/grounding.py`, `taskpilot/workload.py`, `taskpilot/calendar_planner.py` | Ground requests in the conversation, validate assignments, and allocate study time in deadline order subject to remaining effort, prerequisites, and calendar constraints. |
| `taskpilot/checked_reply.py` | Presents the AI explanation with the computed schedule. |
| `tests/`, `evaluation/`, `docs/` | Automated checks, evaluation evidence, and milestone documentation. |

Normal terminal and dashboard chat share the AI workflow. Provider or validation failures are reported explicitly. The offline CLI is an explicit mode that allocates relative session minutes without calendar or model calls. Schedule checks cover computed plan data. AI explanations can still contradict that data. Conversation history and progress are session-scoped.

## Critical changes since M3

| Change | Why it mattered | Evaluation evidence |
|---|---|---|
| Moved scheduling and workload validation into Python, and displayed the computed blocks directly. | Prompt-based scheduling could misstate duration, deadlines, or unfinished work. The app now computes allocations, surfaces deadline risks, and retains overdue work until completion is confirmed. | Local checks cover budget, overlaps, deadlines, and remaining work. The second targeted live run completed all six scheduling checks. |
| Made follow-ups retain the student's time, selected day, and explicit completion reports. Added clarification for vague availability and tolerance for common typos. | Students could lose their schedule after a typo, a shorter time budget, or a follow-up. | Targeted live checks covered typos, less time, tomorrow, completion, and a deadline-capacity shortfall. The first attempt exposed a completion-validation failure that was corrected before the second run. |
| Unified terminal and dashboard chat around the two-agent MCP workflow, with explicit failure reporting. | Both interfaces needed the same assignment data and plan. Visible failures and transcript evidence make the workflow easier to evaluate. | Live NRP checks recorded MCP retrieval and the agent handoff. The full-suite rerun still found narration errors in three cases. |
| Added calendar-aware planning and a repeatable dashboard interview flow. | Students can plan around commitments and try the planner using fictional data. | A live demo selected 8:15 PM after an 8:00 PM event and its buffer. In one documented external interview, the participant completed all five scenarios independently and asked for larger text. Broader private-calendar validation remains open. |

The evidence in each row shows the behavior checked for that change. The project measured the full-suite improvement across the combined changes. Individual pass-rate effects were not isolated, and advisor reasoning settings also changed between the recorded runs.

## M4 evaluation and readiness

| Evidence | Recorded result |
|---|---|
| Original ten-case M3 suite, first recorded live run | **3/10 (30%)**. [Baseline results](evaluation/results.md) |
| Same ten-case suite, second recorded live run | **7/10 (70%)**, up **40 percentage points**. TC01, TC03, and TC08 failed because the AI explanation conflicted with the checked plan or added preparation or continuation work. [Rerun summary](evaluation/results_run2.md) · [Case-level results](evaluation/results_run2.csv) |
| Local regression and targeted live checks | **128 local tests passed**. A later targeted run completed all **6 scheduling checks**. [Local regression results](evaluation/local_regression_results.md) · [Targeted run evidence](evaluation/evidence/schedule_restoration_2026-11-17_run2/) |
| External usability interviews | Interviews have begun. In the documented session summarized here, the participant rated realism and prioritization **5/5**, and ease of understanding, schedule clarity, and trust **4/5**. The five-session evidence set remains unconfirmed. |

The latest recorded full-suite result is **7/10**, below the **9/10 readiness threshold**. The later targeted run confirms the scheduling fixes it exercised. A comparable full-suite run on the final implementation and a complete five-session evidence set are still needed for the final readiness decision. Narrow-screen behavior and transcript downloads also lack recorded interactive verification.

The **7/10 checkpoint** is associated with branch `taskpilot-m4-7of10` and tag `taskpilot-m4-7of10-checkpoint`. Use the post-M3 commit history and execution-time manifests to trace the implementation and evidence. See the [M4 readiness requirements](docs/M4_READINESS.md).

