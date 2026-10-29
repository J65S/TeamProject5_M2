# TeamProject5_M3
## TaskPilot — AI Student Workload Tracker
**Team 5 — Milestone 3**

A command-line multi-agent prototype that helps students prioritize assignments and plan their available study time.

TaskPilot uses the OpenAI Agents SDK with `gpt-oss` through an NRP OpenAI-compatible endpoint. A local MCP server retrieves assignment information from fictional syllabus files.

## What the Prototype Does

- Accepts a student's available time and planning request.
- Retrieves upcoming assignments from syllabus files.
- Identifies approaching deadlines and estimated workloads.
- Passes assignment analysis to a separate planning agent.
- Generates a study recommendation and identifies unfinished work.
- Displays tool calls, retrieved data, and the handoff in the terminal.

The prototype uses demonstration data. It does not connect to Canvas, calendars, or student accounts.

## Multi-Agent Workflow

1. **Assignment Analyst:** Calls `get_assignments`, summarizes upcoming work, and identifies approaching deadlines.
2. **Handoff:** After the analyst finishes and passes a basic output check, Python passes its findings and the student's original request to the Schedule Planner.
3. **Schedule Planner:** Uses that information to recommend how the student should spend their available time.

The handoff is coordinated by Python rather than the SDK's built-in handoff feature.

### Reasoning Pattern

The analyst uses a simple ReAct-style tool-use sequence: call the assignment tool, observe its result, and analyze the retrieved workload. The terminal displays the actual tool call and response. This is a retrieval-and-analysis sequence, not a repeated loop involving multiple tools.

### Knowledge Layer

TaskPilot uses simple file-based retrieval-augmented generation (RAG). The MCP tool retrieves upcoming assignment records from local syllabus files, and the agents use those records to generate recommendations. Retrieval is date-based; it does not use embeddings or a vector database.

The server uses the computer's current date. Assignments due before today are assumed completed, while assignments due today or later are returned in deadline order. Actual submission status is not checked.

## Repository Files

| File | Purpose |
|---|---|
| `agent.py` | Configures NRP, runs both agents, displays tool activity, and coordinates the handoff. |
| `mcp_server.py` | Reads syllabus files and exposes `get_assignments`. |
| `syllabi/algorithms.txt` | Fictional Algorithms assignments. |
| `syllabi/software_engineering.txt` | Fictional AI Agent Workflows assignments. |
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

### 2. Create a virtual environment and install dependencies

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

### 3. Configure credentials

Create `.env` beside `agent.py`:

```text
NRP_BASE_URL=YOUR_NRP_OPENAI_COMPATIBLE_BASE_URL
NRP_API_KEY=YOUR_NRP_API_KEY
```

Replace the placeholders with your authorized endpoint and key. Do not commit `.env`.

## Run

macOS / Linux, with the environment activated:

```bash
python agent.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe agent.py
```

When prompted, enter a request:

```text
I have 3 hours and don't know where to start.
```

The script handles one request per run. It does not accept follow-up answers within the same session.

## Syllabus Format

Place `.txt` files in the lowercase `syllabi` folder. Use these exact labels:

```text
COURSE: Example Course

Task: Complete project outline
Due: 2026-11-04
Estimated hours: 2
```

The parser expects this format and does not process arbitrary syllabi or PDFs. Invalid assignment records are skipped with warnings. Missing folders or files produce an error message.

## Testing and Limitations

Preliminary testing demonstrated assignment retrieval, the two-agent handoff, recognition of missing availability, and handling of missing syllabus files. Adding a new assignment to a syllabus also made it available during the next run without changing the agent code.

Observed limitations include:

- Incorrect workload totals and remaining-time calculations.
- Suggested schedules that exceed availability or extend beyond deadlines.
- A tendency to favor assignments that fit the current time window.
- Occasional empty analyst responses or tool-call text instead of usable analysis.
- No saved progress, submission tracking, or conversation history.

The code stops on empty analyst output or the specific malformed tool-call text previously observed. It does not independently verify schedule arithmetic or deadline compliance.

Instructions discourage invented assignments and unrealistic schedules, but these constraints are not fully enforced by Python. Students must review recommendations before relying on them. General recovery from network or MCP server failures has not been implemented.

## CHANGES Since M2

- **Added separate analyst and planner agents** to separate assignment analysis from schedule generation.
- **Added an explicit handoff** so the planner receives the student's request and analyst findings.
- **Replaced hard-coded assignments with syllabus files** to support semester-wide assignment data.
- **Added current-date filtering** to focus retrieval on upcoming assignments.
- **Added field validation and warnings** to identify invalid syllabus records.
- **Added visible tool activity** to make retrieval and agent coordination easier to demonstrate.
- **Added a basic analyst-output check** to stop empty or specific malformed responses from reaching the planner.
- **Disabled OpenAI trace export** because the prototype uses the NRP endpoint.

## Milestone Deliverables

This repository contains the running system and setup documentation.

The architecture diagram, ten-case evaluation plan, operational cost model, sustainability analysis, user testing plan, and contribution evidence are included in the separate report, `TeamProject5_M3.pdf`. A screen recording accompanies the submission to demonstrate the workflow and explain an imperfect moment.
