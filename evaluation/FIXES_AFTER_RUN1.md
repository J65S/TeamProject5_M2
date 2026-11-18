# Fixes after the 3/10 evaluation

The November 17 first live evaluation remains unchanged in `results.csv`, `results.md`, `results_chart.svg` and `evidence/m4_2026-11-17_run1/`. This document records subsequent engineering work, not a revised score.

| Failed cases | Observed cause | Implemented fix |
|---|---|---|
| TC01, TC08 | Invented after-work/end-of-day constraints, tomorrow scheduling, availability update inherited false restrictions | Ground timing in user statements and the verified conversation context; recompute event anchors from the calendar; replace the prior duration when the user changes it; keep the session on the selected day |
| TC01, TC02, TC05, TC08 | Focus minutes fit the budget but breaks and busy gaps exceeded elapsed availability | Use one contiguous free window with a clock-time end capped by the budget, including inter-block breaks; report a shorter session and unused time instead of adding another window |
| TC04 | A plan without availability raised an error before the writer | Route missing/ambiguous availability to the actual AI advisor for a question; preserve zero as a valid value |
| TC05 | Unrequested task restriction erased the eight-hour assignment and its remaining work | Restrict scope only when the user names a task/course; retain the full global unfinished list even for explicit focus requests; compute combined demand and optimistic deadline-capacity risks; use smaller estimates to break equal-deadline ties |
| TC07 | Correctly retrieved poster was absent from an irrelevant planning reply | Treat an explicit assignment-list question as inventory; require every active title, course and due date in the AI answer |
| TC02, TC05, TC09 | Missing numeric workload or unsupported timing claims in prose | Supply exact total, focus, elapsed, unused and overall/task-level remaining-work facts; validate coverage and unsupported timing claims; have the analyst review the advisor's claims; allow two bounded writer corrections, then show a failure instead of substituting a template |

Both the normal terminal and `/api/chat` dashboard use these shared changes. Explicit `--offline` remains a separate calendar-free engineering mode. Suggested work never automatically changes completion status.

## Verification

- `.venv/bin/python -m unittest discover -s tests`: 94 tests passed, including 16 new regression tests linked to the observed failures. Two existing expectations were updated to count breaks inside elapsed availability.
- `python -m evaluation.verify_fixes --output NEW_EMPTY_DIRECTORY`: four targeted live NRP smoke requests exercise clarification, a shared deadline, full inventory and feasibility. These are distinct from the ten-case suite and do not produce an M4 pass rate.
- First smoke outputs are preserved in `evidence/fix_verification_2026-11-17_run1/`. Automated smoke assertions passed, but manual review found an unrequested “after your last event” clarification and incorrect unused-time arithmetic in the shared-deadline answer. These prompted additional guards; the first outputs were not erased.
- Run 2: two checks passed and two failed answer validation. Run 3 repeated only the two failing checks; both automated checks passed, but manual review caught a false task-level remainder and a date-only deadline described as an official cutoff. This led to a third workflow stage: the same analyst reviews the advisor against the checked facts.
- Run 4: three checks passed; the shared-deadline check failed because the validator rejected mathematically equivalent units (65 minutes versus 1 hour 5 minutes; 75 minutes versus 1 hour 15 minutes). The validation now accepts equivalent numeric durations while still rejecting incorrect unused-time arithmetic. All failed attempts and diagnostic answers are retained.
- Final targeted verification is in `evidence/fix_verification_2026-11-17_run5/`: **4/4 smoke checks passed**, and each delivered answer records analyst factual-review approval. The shared-deadline response needed one bounded writer correction; the earlier draft and issue are retained. Every run has its own source manifest. These iterations are debugging evidence, not selectively substituted M3 results.

## Next evaluation

Run `.venv/bin/python evaluation/run_m3_suite.py --run-dir evaluation/evidence/m4_2026-11-17_run2` when ready for the full retry. Review all ten actual responses manually, including elapsed time, retrieved coverage, arithmetic, handoff evidence and remaining-work explanations. Keep the first run as the comparison baseline and disclose the existing calendar/date adaptations. Do not silently rescore the original run.

Combined full-suite improvement: **not yet measured**. Individual change effects: **not isolated**. External-user usefulness: **not yet established**. Changes remain uncommitted pending genuine team review and ownership.
