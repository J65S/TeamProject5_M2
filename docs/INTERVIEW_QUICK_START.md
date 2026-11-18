# TaskPilot: quick interview setup

## Before the student arrives

1. From the project root, run `python3 web_app.py` and open `http://127.0.0.1:8000` on the team's computer. Browser replies now require the two-agent AI workflow. Install the requirements in `.venv`, set the NRP credentials, and verify a real reply before the student arrives; the server automatically uses `.venv/bin/python` for AI workers.
2. Leave the source on **Example week**. Six fictional assignments are ready; no participant setup is required. The dates are relative to today and are included in downloaded transcripts.
3. Click **New conversation**. Explain that the data is fictional, the prototype may make mistakes, and you are testing the app rather than the participant. Ask permission to take anonymous notes and save the conversation. Recording needs separate permission.

## What the student does

Say: “Ask TaskPilot what you should work on. Say what you're thinking as you go.”

Give the five scenarios from the M3 plan one at a time:

| Scenario | Participant task |
|---|---|
| Normal scheduling | “You have four hours to study today. Ask for a plan.” |
| Limited availability | “Now you only have one hour. Ask again.” |
| Prioritization | “Find out what assignments are due soon and what to prioritize.” |
| Missing information | Click **New conversation**, then: “Ask for help planning without saying how much time you have.” Observe the follow-up; do not supply the answer for them. |
| Adjustment | “Tell it you now have two hours instead of four.” |

There are no forms or files for the participant to prepare. One-click suggestions are available, but note when they use a suggestion instead of writing their own request. Plans replace the budget; they do not record work as actually completed.

## What the facilitator records

For each scenario: independent/assisted/failed, what happened, stuck moments, exact help supplied, surprising behavior, and relevant quotes. Ask the ten feedback questions committed in M3 afterward, plus the additional qualitative follow-up in the interview script. Do not replace the survey with transcript timing.

Click **Save conversation** before starting the next participant. The JSON includes observed inputs, outputs, the source snapshot, date, planner response duration, and attempted AI-review outcomes. Save it under a participant code such as P01, not their name. A transcript saved while AI review is pending will label it requested, not completed; save again afterward if you need the final outcome. Reloading or clicking New conversation clears the in-tab transcript, so export first.

An unavailable AI reply is a failure to record, not a successful multi-agent run. Browser chat will not substitute an offline planner answer. The offline CLI/engineering endpoint can still be tested separately, but must not be presented as AI user testing.

## Report the adaptation honestly

M3 Section 7 committed to ten participants and five typed-prompt scenarios. M4 requires at least five outside-team participants. Aim for ten; explain any shortfall. This UI preserves a typed-question interaction but uses a smaller, clearly fictional, date-relative example week for convenience. Document that fixture change and use the same setup for each participant. It does not replace the original ten-case technical evaluation. This guide is preparation, not evidence of completed sessions.
