# TeamProject5_M2
AI Student Workload Tracker: A prototype agent that helps students prioritize assignments and plan their available study time.

# AI Student Workload Tracker
### Team 5 — Milestone 2

A command-line agent that helps students decide what assignment work to prioritize based on their available study time.

The prototype uses the OpenAI Agents SDK with an NRP OpenAI-compatible model endpoint. It retrieves sample assignment information through a local Model Context Protocol (MCP) server and generates a study recommendation.

## What the Prototype Does

- Accepts a student's request through the terminal.
- Retrieves sample assignments using the `get_assignments` MCP tool.
- Recommends how to use the student's available study time.
- Identifies when available time is insufficient.
- Asks for available study time when it is missing from the request.

This is an early prototype. It uses sample assignments and does not connect to Canvas, a calendar, or a student's actual course account.

## Repository Files

| File | Purpose |
|------|---------|
| `agent.py` | Configures the NRP model connection, connects to the MCP server, and runs the planning agent. |
| `mcp_server.py` | Exposes the `get_assignments` MCP tool and its sample assignment data. |
| `requirements.txt` | Lists the Python dependencies needed to install the prototype. |
| `.gitignore` | Excludes local credentials, virtual environments, and Python cache files. |
| `README.md` | Documents setup, usage, test expectations, and limitations. |

## Requirements

- Python 3.12, which was used for local testing
- Internet access to the NRP model endpoint
- Valid NRP API credentials
- A model that supports tool calling; this prototype is configured to use `gpt-oss`

Each user must supply their own authorized credentials. API keys are not included in the repository.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/J65S/TeamProject5_M2.git
cd TeamProject5_M2
```

### 2. Create a virtual environment

**macOS / Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
```

Activation is optional when using the explicit Python paths shown below.

### 3. Install dependencies

**macOS / Linux:**

```bash
./.venv/bin/python -m pip install -r requirements.txt
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Configure NRP credentials

Create a file named `.env` in the same folder as `agent.py`:

```dotenv
NRP_BASE_URL=YOUR_NRP_OPENAI_COMPATIBLE_BASE_URL
NRP_API_KEY=YOUR_NRP_API_KEY
```

Replace the placeholders with your authorized endpoint and API key. The endpoint must be the OpenAI-compatible API base URL supplied by your NRP configuration.

The `.env` file must remain excluded from Git. Do not commit or share API keys.

## Run the Agent

Run the following command from the repository folder.

**macOS / Linux:**

```bash
./.venv/bin/python agent.py
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\python.exe agent.py
```

When the prompt appears, enter a request and press Enter:

```text
I have 3 hours to study. What should I work on first?
```

Wait for the model to respond. The script handles one request per run; run it again to try another input.

## MCP Integration

The agent launches `mcp_server.py` as a local subprocess using `MCPServerStdio`. The agent and server communicate through standard input and output.

The server exposes one tool:

### `get_assignments`

**Input:** No arguments.

**Output:** A list of sample assignments containing:

- Course name
- Task description
- Due date
- Estimated work time in hours

The agent instructions require it to call this tool before creating a recommendation. Assignment data comes from the MCP server; the model interprets the student's request and produces the plan.


## Sample Assignment Data

| Course | Task | Due Date | Estimated Hours |
|--------|------|----------|-----------------|
| Algorithms | Study for sorting quiz | 2026-10-01 | 2 |
| Senior Project | Write interview summary | 2026-10-04 | 4 |

These assignments are demonstration data stored in `mcp_server.py`.

## Manual Test Cases

These cases evaluate expected behavior rather than exact wording because model responses may vary.

| Test | Input | Expected Output |
|------|-------|-----------------|
| 1 — Limited time | “I have 1 hour to study. What should I work on?” | Prioritizes the earlier Algorithms task, recommends no more than 1 hour of work, and acknowledges that unfinished work remains. |
| 2 — No available time | “I have 0 hours available today. What should I do?” | Acknowledges that no work can be scheduled today and suggests a future work block without assigning study or preparation today. |
| 3 — Sufficient time | “I have 6 hours to study. How should I divide my time?” | Recommends 2 hours for Algorithms and 4 hours for the Senior Project task, totaling no more than 6 hours. |

### Testing Observations

A three-hour run retrieved both sample assignments and recommended two hours for Algorithms and one hour to begin the interview summary.

A zero-hour run acknowledged insufficient time but also suggested gathering materials, which would still require time. This exposed a prompt limitation. Instructions were proposed to explicitly prohibit work or preparation when availability is zero. That behavior must be retested after the prompt change.

The cases above describe expected behavior. They should not be interpreted as a claim that all cases have passed.

## Limitations

- Assignment data is hardcoded and must be updated manually.
- Estimated task durations are supplied as sample values.
- The prototype does not account for class schedules, work shifts, breaks, or existing calendar events.
- The prompt does not explicitly provide the current date, so deadline handling is limited.
- Recommendations are generated by the model; the code does not independently enforce time allocations or verify every statement.
- The agent does not save plans, update assignments, or retain conversation history between runs.
- NRP availability, model access, and network conditions can affect execution.
- Students must review recommendations before relying on them.


## Milestone Deliverables

This repository contains the agent prototype and its supporting documentation.

The architecture diagram, market research, competitive landscape, TAM/SAM assessment, and draft Business Model Canvas belong in the separate report, `TeamProject5_M2.pdf`.
