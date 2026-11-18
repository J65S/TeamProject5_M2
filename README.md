# TeamProject5_M4 — Student Workload Tracker

A command-line assistant that turns syllabus assignments and a student's time budget into a study session. Two agents analyze assignments through MCP and coach the student using a plan whose time allocations are computed in Python.

## What works

- Accepts numeric budgets such as `90 minutes`, `1.5 hours`, or `1 hour 30 minutes`.
- Validates syllabus records, rejects non-finite estimates, and warns about invalid or duplicate tasks.
- Allocates time in deadline order, with partial work and explicit remaining workload.
- Retains overdue tasks until the student explicitly confirms completion.
- Uses an Assignment Analyst with an MCP retrieval tool, then hands its findings and the authoritative plan to a Schedule Coach.
- Uses AI for the primary browser reply; reports model failures without silently substituting a canned response.
- Keeps an explicitly offline CLI for engineering checks; browser chat requires AI access.

The included syllabi are fictional demonstration data. Calendar planning uses a clearly labeled demo or a saved read-only Google Calendar snapshot; assignments are not imported from Canvas.

## Project layout

```text
TeamProject5_M4/
├── agent.py                  # CLI launcher
├── web_app.py                # Dashboard launcher
├── taskpilot/                # Python application package
│   ├── agent.py              # Agent workflow and CLI
│   ├── web_app.py            # Local HTTP server and API
│   ├── workload.py           # Retrieval and scheduling
│   ├── conversation.py       # Grounded answers and example-week data
│   ├── mcp_server.py         # MCP tool adapter
│   └── paths.py              # Shared resource paths
├── web/                      # Frontend HTML, CSS, JS, and icon
├── data/syllabi/             # Example assignment files
├── tests/                    # Planner and API tests
├── evaluation/               # Evaluation templates and local results
├── docs/                     # Milestone requirements and preparation
├── requirements.txt          # AI dependencies
└── .env                      # Local credentials (ignored by Git)
```

Run commands from the project root. The launchers keep the original commands working; Python modules also support `python3 -m taskpilot.agent` and `python3 -m taskpilot.web_app`. Default resource paths are resolved from the project location, so launchers also work when invoked by absolute path from another directory. Custom `--syllabi` paths are relative to your current directory.

## Student interview experience

```bash
python3 web_app.py
```

Open **http://127.0.0.1:8000** on the same computer. The main screen is a conversation. Students can type a question or click an example:

- “I have an hour. What should I work on?”
- “I’m overwhelmed. Where do I start?”
- “What assignments are due tomorrow?”
- “I now only have two hours instead of four.”

The app asks for missing time, accepts common written durations, remembers the last explicit budget within the current conversation, and shows deadline-first study blocks and remaining work. Zero availability produces no work. It does not infer that a planned block has actually been completed.

Vague time such as “a few hourz” gets one short AI clarification rather than a backlog dump. A short answer such as “3” is interpreted in the context of the hours question. The advisor recommends a starting task and a first step using the source deadlines. After a proposed plan, a simple “yeah, that works” immediately reuses an AI-written acknowledgment or a checked sentence from the previous answer; it does not call the models again or book anything. The cached acknowledgment is signed, expires after ten minutes, and is rejected if source data or preferences change. More substantial replies still go through AI.

When the first window is shorter than requested, a suggestion shows the next known opening. “Use another opening today” explicitly permits an updated plan across two windows on the same day, retaining the original study-time budget and including breaks. Busy gaps between the confirmed windows are outside that study-time budget; `calendar_span_minutes` records the full clock span separately. Another explicit request can add a third window. Work is proposed, not recorded as completed.

A six-assignment **fictional example week** is ready by default. Dates are relative to the conversation date; the example is reproducible using the date in the transcript. Students do not upload files, enter academic records, or check off a semester of old tasks. Expand **Your example week** to inspect the source data or switch to **Project syllabus files**. The CLI still uses the original project syllabus data by default.

Use **New conversation** between participants. Conversation and availability are held in the tab, not persisted in browser storage. **Save conversation** downloads a JSON transcript with actual questions, planner replies, assignment snapshots, timing, and AI-request outcomes. It does not assign pass/fail, collect survey answers, or establish consent. Ask participants before retaining their responses; avoid personal information. See [the short facilitator guide](docs/INTERVIEW_QUICK_START.md).

The browser chat is **AI-first**. The Context and Calendar Analyst calls the MCP tool, interprets the request and conversation, and returns validated intent. Python checks time budgets, calendar conflicts and deadlines. The Student Study Advisor explains the recommended work naturally. The actual computed schedule is displayed by default below that explanation, with dates, clock times, assignments, durations, breaks, remaining work and deadline risks. Its display does not depend on whether the model happens to restate every block in prose. AI failure is shown explicitly; no automatic template fallback is used.

The worker uses `.venv/bin/python` when present, even if the local server was launched using system Python. Configure NRP as described below. The installed environment was verified with `gpt-oss`; optional `NRP_MODEL` overrides the model. A live two-agent smoke test correctly interpreted “Start when im done with my day,” retained a prior one-hour budget, retrieved the demo calendar, and proposed 8:15 PM after the final 8 PM event plus the buffer. This is a single smoke test, not the original M3 suite.

Model output can still be wrong. JSON shapes, budgets, task IDs, timezones, and generated study blocks are checked, but the generated prose is not guaranteed correct. The worker has a 180-second total timeout, bounded agent turns, and provider timeouts. Details and exports stay collapsed under **View study blocks & calendar details**.
```bash
python3 web_app.py --port 8080 --syllabi ./data/syllabi
```

The server listens only on your own computer. A localhost link will not work on another student's device. Use the team's laptop for in-person testing. It serves the `web/` assets and explicit API endpoints, without exposing repository files or credentials. Stop it with Ctrl+C.

## Calendar-aware planning

Choose **Interview demo** for a repeatable fictional calendar or **My Google Calendar** for the locally saved primary-calendar snapshot. Example assignments remain fictional unless you switch the assignment source to project files. Your calendar does not supply assignments or completion status.

The planner initially uses the first available window on the selected day, observes study-hour preferences and event buffers, and divides the session into focus blocks. **Availability includes breaks and elapsed time within each session.** Additional windows require an explicit request; it never silently moves today's work into tomorrow. Equal-deadline tasks use smaller remaining estimates first. “After work” is anchored to a matching work/shift event; an unknown event requires clarification.

The demo simulates 9:30 AM on the conversation date. The personal mode uses the real current time in America/New_York. A snapshot older than 24 hours or beyond its coverage is flagged; the app does not produce verified calendar windows from it. Only the primary calendar has been checked, not secondary calendars or off-calendar commitments.

Calendar data is stored in ignored `.local/calendar.json`, separate from project fixtures. The initial snapshot was retrieved read-only through your connected Google Calendar in Codex. That connector cannot be called directly by this local Python app. **This is a timestamped snapshot, not continuous live sync.** You can ask Codex to refresh it. The optional in-app refresh requires a separately supplied `GOOGLE_CALENDAR_ACCESS_TOKEN`; see [calendar setup](docs/CALENDAR_SETUP.md).

The app never creates or edits Google events. **Download calendar blocks (.ics)** explicitly exports a plan you may import into your calendar. Check current availability before importing; suggested slots are not reserved. The primary AI handoff includes calendar context and the validated plan. A successful live demo-mode run has been observed; private-calendar AI interpretation still needs broader validation.

## Setup and run

Offline planning requires Python 3.10+ and no packages:

```bash
python3 agent.py --offline --request 'I have 90 minutes'
```

For terminal or dashboard AI chat, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a local `.env` beside `agent.py` (never commit credentials):

```text
NRP_BASE_URL=YOUR_NRP_OPENAI_COMPATIBLE_BASE_URL
NRP_API_KEY=YOUR_NRP_API_KEY
```

Then run:

```bash
python agent.py
```

The terminal and dashboard both use AI to ask for missing availability and preserve recent conversation history. Invalid local configuration or missing source data exits with status 2 before inference.

Useful options:

```bash
# Reproducible date and machine-readable schedule
python3 agent.py --offline --minutes 90 --as-of 2026-11-16 --json

# Your own syllabus folder
python agent.py --minutes 120 --syllabi ./data/syllabi

# Mark tasks as complete for this run using IDs printed in the schedule
python3 agent.py --offline --minutes 60 --completed TASK_ID
```

Running `python agent.py` interactively first asks whether you prefer the terminal or dashboard. Choose **1** (or press Enter) to chat here, or **2** to start/open the dashboard. Keep the terminal open when it starts a new dashboard server; Ctrl+C stops that server. It reuses a compatible running dashboard when possible, otherwise safely selects a free port if 8000 is occupied. If automatic browser opening is unavailable, it prints the link. Scripted requests, JSON output, and offline runs skip the menu.

IDE Run buttons may also run `taskpilot/agent.py` or `taskpilot/web_app.py` directly, including from a different working directory. `taskpilot/calendar_sync.py` is a helper: running it displays usage; `--refresh` explicitly requests a calendar refresh and requires the separate Google access token.

Normal terminal use is now a real conversation through **the same `run_ai_chat` workflow as the dashboard**:

```bash
python agent.py
# Choose 1 (terminal) or 2 (dashboard opens in your browser).
# In the terminal, ask: I have 90 minutes what do you think I should work on
# Follow up: Start when I am done with my day
# Type /details for checked blocks and model/MCP/handoff evidence
# Type /new to clear conversation context, or /quit to exit
```

For a single response or machine-readable evaluation output:

```bash
python agent.py --request "I have 90 minutes. What should I work on?" --details
python agent.py --request "I have 90 minutes. What should I work on?" --json
python agent.py --demo --calendar demo --as-of 2026-12-01
```

Without `--demo`, the CLI uses the enriched December text files. The calendar defaults to the clearly identified fictional interview schedule; choose `--calendar personal` for the saved Google snapshot. `--minutes` supplies an explicit budget; otherwise the AI interprets the request or asks for availability. Interactive replies preserve recent history and structured timing constraints. Waiting messages report actual elapsed time, not simulated reasoning stages.

The normal command does not print a template plan before inference. AI failure is reported with a safe stage/category diagnostic; one-shot failures return a nonzero exit code. There is no automatic fallback. Explicit `--offline` still produces a deterministic plan with no model calls, and `--offline --json` returns that structured plan. Both modes support `--details`, completion IDs, fixed dates, and explicit relative-date mode. The older separate terminal coaching worker has been removed. AI responses use native structured output schemas; the analyst is required to call the MCP tool before returning intent. `NRP_REASONING_EFFORT` defaults to `low` for this bounded task; `medium`, `high`, or `default` can be configured. All settings still call the real model. The analyst gets one bounded correction attempt if its JSON/intent fails validation; remaining failures are reported, not hidden.

Repeat `--completed` for multiple tasks. Unknown IDs are rejected. Completion flags are not saved between runs. Because the sample files cover a semester, confirm older work as completed before using them to plan current work. `--minutes` overrides any time mentioned in `--request`. Use `--help` for all options.

## Assignment text files

The two files in `data/syllabi/` now contain **24 fictional records with fixed due dates in December 1–7, 2026**. December 1–7 is the interpretation of the requested December week. These dates, progress values, descriptions and dependencies are demonstration data; they are not the course guide’s actual submission deadlines. Existing task names, including Prepare TaskPilot poster, remain present.

Each task uses a readable, one-line-per-field format:

```text
COURSE: Example Course
Task: Project outline
ID: EX-01
Description: Explain the project goals, workflow, and evidence needed.
Due: 2026-12-04
Due time: 23:59
Timezone: America/New_York
Estimated hours: 2
Remaining minutes: 60
Status: In progress
Can split: Yes
Dependencies: None
First step: Read the brief and write three bullets describing the goal.
Demo offset days: 3
```

`Remaining minutes` is the current workload, not the original total estimate. Status is Not started, In progress, or Completed. Completed records must have zero remaining minutes; legacy records without status remain unconfirmed/not started. `Dependencies` contains comma-separated task IDs and must be confirmed completed before dependent work is scheduled. Unknown prerequisites remain visible and blocked. `Can split: No` prevents partial allocation. Exact due times require an IANA timezone and are enforced by the calendar planner. Older files with only Task, Due and Estimated hours still work, with an unknown time-of-day cutoff. Descriptions and first steps are retrieved for the agents and shown with plan details.

Fixed dates never advance automatically. To explicitly re-anchor the text-file demo offsets:

```bash
python3 agent.py --offline --minutes 90 --relative-dates --as-of 2026-12-01
```

In the browser, expand the assignment panel and choose **December 1–7 text files (fictional)** or **Text-file interview week (relative dates)**. The separate small example week also remains relative to the conversation date. As-of date, source notes, original fixed dates, stable IDs, and date mode are preserved in snapshots/transcripts for reproducibility. See [data format and date modes](data/README.md).

Normal AI chat in both interfaces uses checked clock-time blocks. Explicit `--offline` allocates relative session minutes without a calendar. Unknown exact deadlines are not invented.

## Architecture and guardrails

`taskpilot/ai_chat.py` runs the shared two-agent workflow. The analyst retrieves the authoritative snapshot through MCP. `taskpilot/grounding.py` checks timing and scope against user statements, preserves availability and computes workload facts. An explicit duration with a help request selects a plan; “whenever I have time next” selects the earliest verified slot without requiring another start-time choice. Failed terminal turns stay in history so availability is not lost.

For plans and clarification, the advisor returns its explanation; the scheduler already owns the assignment IDs, so the model does not need to repeat an ID merely to authorize displaying a valid plan. `taskpilot/checked_reply.py` retains the AI explanation and appends the computed schedule. Common typing slips are normalized for routing, and other recognized availability can be grounded in an exact user quote rather than discarded. Time-budget changes, moving the session to tomorrow and explicit completion reports update conversation state. “I already finished that” refers to the previously recommended assignment; an unresolved reference asks which assignment. Completion reports affect the conversation snapshot, not syllabus files, and are labeled as user reports. Evidence records MCP retrieval, the handoff and checked plan facts; `facts_checked` refers to scheduler data, not a guarantee that every prose claim is correct. Both agents still use `gpt-oss` through NRP. Tracing export remains disabled.

`taskpilot/workload.py` and `taskpilot/calendar_planner.py` enforce arithmetic, deadline dates, buffers, and study hours. `taskpilot/mcp_server.py` supports the installed MCP 2 API, with a compatibility import for MCP 1. `taskpilot/agent.py` now calls that same engine for normal terminal use; only explicit `--offline` uses the deterministic planner directly.

`/api/chat` requires the real AI worker. `/api/offline-chat` is a separate, explicitly labeled engineering endpoint; the frontend never calls it. Successful AI replies include the model name, tool-output count, handoff flag, advisor-return flag, and validated context. Transcripts retain that evidence and failed requests, rather than claiming every response succeeded.

## Verification and M4 evidence status

```bash
python3 -m unittest discover -s tests -v
```

128 local tests pass across planning, conversational questions, and the HTTP boundary. The scheduling-restoration checks additionally exercised the real CLI/NRP/MCP path with normal and typo requests, then reduced time, tomorrow, completion, and a deadline-capacity shortfall. The first live attempt exposed a redundant model-ID failure on completion; that evidence is retained. The second run completed all six scheduling checks. These are targeted checks, not a replacement ten-case score. See [local regression results](evaluation/local_regression_results.md).

These checks are **not a replacement for the ten committed M3 evaluation cases**. The [second full live run](evaluation/results_run2.md) passed **7/10 (70%)**, compared with **3/10 (30%)** in the [preserved first run](evaluation/results.md): a combined improvement of **40 percentage points**. TC01, TC03 and TC08 still fail because AI narration conflicts with the checked plan or adds preparation/continuation work. The 9/10 readiness threshold is not met. Individual change effects were not isolated; advisor reasoning settings also changed with the implementation. All ten inputs, expected/actual outputs and judgments are in [the rerun CSV](evaluation/results_run2.csv). Five external-user sessions are still needed.

The current two-agent browser path completed a live NRP/MCP demo-mode smoke test; that single run does not establish general reliability. Offline CLI behavior, scheduling constraints, Python compilation, and HTTP handlers have been checked. The frontend has been visually reviewed in Chrome; assignment loading, a generated plan, and unavailable-coaching recovery were observed. The current chat flow was checked in Chrome for clarification, a one-hour answer, a two-hour update, zero availability, and reset. Narrow-screen layouts and transcript downloads have not been interactively browser-verified. The current Git remote still references the M2 repository; this README title does not rename or publish the repository.

## CHANGES Since M3

| Change | Why | Evaluation impact |
|---|---|---|
| Restore typo-tolerant scheduling and quote-backed availability; show the computed dated schedule by default; retain session date, budget, scope and explicit completion reports; preserve updated snapshots through the dashboard API | Strict extraction discarded “I haev 3 hours”; conversational replies hid valid allocations; follow-up completion state was absent and redundant model task-ID checks could prevent display | 9 restoration regression checks; 128 local checks pass. Six real scheduling cases completed in `evaluation/evidence/schedule_restoration_2026-11-17_run2/`, including deadline-risk flags and no budget/calendar/deadline violations. Full M3-suite improvement remains unmeasured |
| Remove prose-style rejection rules and generated plan paragraphs; pass clear proposed-session facts to the AI and deliver its whole answer unchanged; avoid duplicate application questions | The saved failure showed useful recommendations rejected solely for ending in a question; the extra controls made the interaction brittle | Both actual rejected drafts pass regression checks; 119 local checks pass. Repeated live replies were delivered, but manual review still found factual/continuation errors; no new full-suite improvement is claimed |
| Scope alternative-duration parsing to actual numeric alternatives; preserve failed requests in history; route explicit help/time and next-free requests to a plan; replace repeated plan arithmetic reviews with AI guidance plus Python-checked facts; add specific diagnostics | “Or no?” was mistaken for alternative budgets; failed requests lost their availability; the extra AI reviewer could contradict Python and block a valid plan | 8 new regression checks; 116 total local checks pass. Three real reproductions of the reported messages succeeded on their first executions in 9.2–17.0 seconds, with MCP retrieval and a two-agent handoff. Full ten-case improvement remains unmeasured |
| Add short AI clarification for vague hours, contextual numeric replies, checked AI confirmations without new inference, guided next-opening suggestions and explicitly requested additional windows | Stop delegating prioritization back to the student, repeating the backlog, and replanning after a simple acceptance | 11 new flow tests; 108 total local checks pass. A real four-turn conversation passed all targeted assertions; clarification took 4.7 seconds, confirmation under 1 ms, first plan 15.7 seconds, additional-window plan 77.4 seconds. Original ten-case impact remains unmeasured |
| Support direct IDE launches of package entry files; give the calendar helper explicit usage and a `--refresh` command | IDE Run executed files without package context and raised relative-import errors | 3 new subprocess checks pass, including execution outside the project and a real offline plan; 97 total local checks pass; full-suite impact not measured |
| Ground timing/scope in user messages; route missing time to AI clarification; enforce one elapsed-time session on the selected day; retain the global backlog; require complete inventory and computed workload facts in AI replies; add analyst factual review and bounded writer correction | Address TC01, TC02, TC04, TC05, TC07, TC08 and TC09 from the real 3/10 run | 94 local checks pass, including 16 new regression checks; targeted live verification is recorded separately; full-suite and individual pass-rate effects remain unmeasured |
| Unify normal CLI and dashboard AI chat, preserve terminal follow-ups, replace the separate coaching worker, add stage-specific safe errors and explicit offline mode | Fix the terminal path that printed a deterministic plan then failed with opaque RuntimeError/TimeoutError | 73 local checks pass; a live NRP terminal response with MCP retrieval and handoff completed; original-suite improvement not measured |
| Enrich assignment text files and move their fictional fixed dates to December 1–7, with opt-in relative offsets, status, remaining effort, precise cutoffs, dependencies, split rules and first steps | Give agents useful context and stop completed demonstration work from overwhelming current plans | 66 local checks pass, including exact cutoff/status/dependency/date-mode cases; changed fixtures are not an original M3 evaluation rerun and have no measured original-suite improvement |
| Add a shared supportive voice and concise terminal summaries, with full backlog/IDs available through `--details` | Reduce overwhelming, directive wording while keeping uncertain completion status and remaining work visible | Existing checks pass; summary/detail and unchanged JSON checks verified; user-perceived improvement and original-suite impact not measured |
| Make two-agent AI interpretation and writing the primary browser path, preserve structured conversational constraints, collapse details, and remove silent template fallback | Correct the failure to understand “done with my day” and keep student-facing replies focused | 54 local checks pass; live NRP + MCP + two-agent demo smoke test selected 8:15 PM after the final event; original-suite improvement not measured |
| Add read-only calendar snapshot planning, an isolated interview calendar, preferences, richer replies, next-question buttons, and explicit calendar-file export | Suggest usable study windows after commitments with less participant effort | 47 local checks pass; real and demo calendar replies verified in Chrome; no measured original-suite/user-study improvement yet |
| Replace the dashboard with a question-first interview flow, conversational time handling, a small example week, and transcript download | Reduce participant setup and expose a natural planning interaction | 33 local tests pass; core conversation flow browser-verified; real-user and original M3-suite impact not yet measured |
| Allow zero availability without scheduling work | Match the committed M3 behavior instead of rejecting a valid student situation | Zero-time parser, plan, and conversational checks pass; M3-suite rerun still needed |
| Supply the same canonical snapshot to the MCP analyst for example-week and file modes | Keep AI retrieval aligned with the assignments used for planning | Syntax checked; live two-agent provider behavior remains unverified |
| Organize Python code into `taskpilot/`, example data into `data/syllabi/`, and centralize resource paths | Keep code, data, frontend, and evidence easy to find while preserving launcher commands | Planner/API tests and cross-directory startup checks pass; behavioral evaluation improvement not measured |
| Add TaskPilot frontend and local HTTP API | Let students review assignments, persist browser completion choices, create and export plans, and request coaching without a terminal workflow | Eight HTTP/API tests pass; desktop browser review completed; M3-suite and real-user improvement not measured |
| Move scheduling arithmetic and deadline priority to `taskpilot/workload.py` | Prompt instructions alone did not enforce time limits or ordering | New budget/overlap, urgency, and unfinished-work checks pass; M3-suite improvement not measured |
| Validate numeric time before model calls; clarify interactive missing input | Avoid guessing availability or spending API calls on invalid requests | Valid compound time and eight invalid/ambiguous examples pass regression checks; M3-suite improvement not measured |
| Retain overdue work; add explicit completion IDs | Past due does not imply submitted | Overdue and completion regression checks pass; M3-suite improvement not measured |
| Reject NaN/infinite estimates, warn on invalid records, deduplicate, retain stable IDs | Invalid numeric data and duplicate tasks undermine plans | Invalid-record and duplicate regression checks pass; M3-suite improvement not measured |
| Replace MCP adapter with FastMCP and pass custom syllabus folder to its environment | Use the installed SDK's tool-decorator API and keep retrieval consistent with CLI data | Syntax checked; live MCP integration not yet verified; improvement not measured |
| Hand verified plan to coaching agent; add bounded turns, a timeout-isolated coaching subprocess, output checks, and offline mode | Make model failures recoverable and keep the plan inspectable | Offline CLI smoke checks pass; missing-dependency recovery passes; live provider recovery not yet verified; improvement not measured |
| Lazy-load model dependencies and configure credentials at runtime | Support credential-free offline use and testing | Offline execution works without installed SDK packages; M3-suite improvement not measured |

The pre-dashboard checkpoint uses branch `taskpilot-m4-7of10` and tag `taskpilot-m4-7of10-checkpoint` in the existing repository. It preserves the current scheduling implementation, dashboard and observed 7/10 evaluation, including the three failures. Evaluation manifests retain their original execution-time commit and uncommitted-state records. Real contributors should review and commit their own work after M3; do not manufacture authorship.
Earlier rows record checks available at the time of each change, not independent measurements of its effect. The preserved first live run is the current ten-case result. Only a fresh comparable evaluation can establish the combined improvement.

## Earlier M3 changes since M2

M3 introduced two sequential agents and an explicit handoff, semester syllabus files, date-based retrieval, validation warnings, visible tool activity, basic analyst-output checks, and disabled trace export. M3 reported date and workload errors, occasional empty analyst outputs, preference for tasks fitting the time budget, and potentially late suggested blocks. Those historical observations were not a full ten-case evaluation.

## Known limits and next evidence

- Deadline-first allocation respects study hours, buffers, breaks, dependency status and split rules; it does not model student energy or guarantee optimal prioritization.
- The chat does not persist completed work, partial progress, or conversation history across reloads. The CLI accepts completion IDs for one run. Calendar planning is limited to the known snapshot coverage, recorded exact deadlines where supplied, and source-reported progress.
- All unfinished estimates remain full estimates unless a task is marked complete; partial progress is not persisted.
- Five external-user sessions and the original M3 suite must still establish usefulness and justify the proceed/pivot/scope-down decision.
- See [M4 preparation requirements](docs/M4_READINESS.md) before preparing the final PDF.
