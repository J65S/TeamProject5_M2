# TeamProject5_M3
## AI Student Workload Tracker
**Team 5 — Milestone 3**

A command-line multi-agent prototype that helps students prioritize assignments and plan their available study time.

The system uses the OpenAI Agents SDK with the `gpt-oss` model through an NRP OpenAI-compatible endpoint. A local MCP server retrieves assignment information from two fictional syllabus files.

## What the Prototype Does

- Accepts a student's available time and planning request.
- Retrieves upcoming assignments from syllabus files.
- Identifies approaching deadlines and estimated workloads.
- Passes assignment analysis to a separate planning agent.
- Generates a study plan and explains unfinished work.
- Displays tool calls, retrieved data, and the handoff in the terminal.

The prototype uses demonstration data. It does not connect to Canvas, calendars, or student accounts.

## Multi-Agent Workflow

1. **Assignment Analyst:** Calls `get_assignments`, summarizes upcoming work, and identifies approaching deadlines.
2. **Handoff:** After the analyst finishes, Python passes its text output and the student's original request to the Schedule Planner.
3. **Schedule Planner:** Uses that information to recommend how the student should spend their available time.

This is a sequential workflow coordinated by Python, rather than an SDK-native handoff.

### Reasoning and Knowledge Layer

The analyst follows a ReAct-style tool-use sequence: call the assignment tool, observe its result, and analyze the retrieved workload before passing findings to the planner.

The knowledge layer uses date-based retrieval from local syllabus files. Retrieved assignment records provide context for the generated recommendation. It does not use embeddings or a vector database.

The server uses the computer's current date. Assignments due before today are assumed completed; assignments due today or later are returned in deadline order. Actual submission status is not checked.

## Repository Files

| File | Purpose |
|---|---|
| `agent.py` | Configures NRP, runs both agents, displays tool activity, and coordinates the handoff. |
| `mcp_server.py` | Reads syllabus files and exposes the `get_assignments` tool. |
| `syllabi/algorithms.txt` | Fictional Algorithms course assignments. |
| `syllabi/software_engineering.txt` | Fictional AI Agent Workflows course assignments. |
| `requirements.txt` | Project dependencies. |
| `.gitignore` | Excludes credentials, virtual environments, and cache files. |

## Requirements

- Python 3.14 was used for the demonstrated M3 runs.
- Internet access to the NRP endpoint.
- Authorized NRP credentials and access to `gpt-oss`.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/J65S/TeamProject5_M3.git
cd TeamProject5_M3
```

### 2. Create the environment and install dependencies

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Add credentials

Create `.env` beside `agent.py`:

```text
NRP_BASE_URL=YOUR_NRP_OPENAI_COMPATIBLE_BASE_URL
NRP_API_KEY=YOUR_NRP_API_KEY
```

Use your authorized endpoint and key. Do not commit `.env`.

## Run

macOS / Linux, with the environment activated:

```bash
python agent.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe agent.py
```

When prompted, enter:

```text
I have 3 hours and don't know where to start.
```

The script handles one request per run. Follow-up questions in the generated response cannot be answered within the same session.

## Syllabus Format

Place `.txt` files in the lowercase `syllabi` folder. Use these exact labels:

```text
COURSE: Example Course

Task: Complete project outline
Due: 2026-11-04
Estimated hours: 2
```

The parser expects this format; it does not extract assignments from arbitrary syllabi or PDFs. Missing fields, invalid dates, and invalid estimated hours produce warnings.

## Testing and Limitations

An observed three-hour run retrieved 13 upcoming assignments from both syllabi, identified 11 estimated hours of work due the next day, and produced one three-hour plan through the two-agent workflow.

Observed limitations include:

- Incorrect date calculations and inconsistent workload estimates.
- Occasional empty analyst responses or tool-call text instead of a usable analysis.
- A tendency to favor tasks that fit the available time.
- Suggested work blocks that may fall after deadlines.

The code stops on an empty analyst response or the specific malformed tool-call text previously observed. It does not independently validate the final schedule's arithmetic or deadlines.

Progress and conversation history are not saved. Students must review recommendations. These observations do not mean the full evaluation suite has passed.

## CHANGES Since M2

- Replaced one planning agent with an analyst and a planner.
- Added an explicit handoff containing the request and analyst findings.
- Replaced two hard-coded assignments with semester assignment files.
- Added current-date filtering and syllabus validation warnings.
- Added visible tool activity and a basic analyst-output check.
- Disabled OpenAI trace export for the NRP setup.

## Milestone Deliverables

The repository contains the running system and setup documentation.

The architecture diagram, 10-case evaluation plan, operational cost model, sustainability analysis, and user testing plan are submitted separately in `TeamProject5_M3.pdf`, alongside a two-minute screen recording.
