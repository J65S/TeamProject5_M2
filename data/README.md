# Assignment data

`syllabi/algorithms.txt` and `syllabi/software_engineering.txt` are fictional planning fixtures. All 24 fixed dates are December 1–7, 2026. They do not change any actual course deadline. Progress values are example states, not claims that team members submitted work. TaskPilot can read source status but cannot independently verify it.

## Edit a task

Start each block with `Task:`. Each following field occupies one line. Leave a blank line between tasks for readability. Use stable, unique `ID` values so dependency references and transcript comparisons keep working.

| Field | Meaning |
|---|---|
| Task / Description | Short name and what the student needs to accomplish |
| Due | Fixed YYYY-MM-DD date; never advanced automatically |
| Due time / Timezone | Explicit cutoff and IANA timezone; both are needed for an exact timestamp |
| Estimated hours | Original whole-task estimate; legacy parser compatibility |
| Remaining minutes | Current effort still needed; used for allocations |
| Status | Not started, In progress, or Completed; completed tasks need zero remaining minutes |
| Can split | Yes permits partial blocks; No requires one fitting block |
| Dependencies | Comma-separated IDs, or None; prerequisite completion must be confirmed in the source or CLI completion flags |
| First step | A specific action the agent can suggest without inventing instructions |
| Demo offset days | Optional nonnegative offset for explicit relative-date demo mode |

Dependencies are not automatically completed because a plan allocated time to them. A task with an unknown or incomplete dependency remains blocked; edit the source after actual completion is confirmed. For a CLI run you can also use `--completed ID`. These are local prototype records, not a live progress system. Completed work is retained in the source for context and traceability but not scheduled.

## Date modes

**Fixed:** default for text files. The requested December dates remain the same on every run.

**Relative demo:** opt in using `--relative-dates` in the CLI or the browser's Text-file interview week source. Each task's Demo offset days is added to the run's explicit as-of date (or local today). This is a simulation, not an extension of a real deadline. Missing offsets are reported as invalid records rather than guessed. The original fixed date is retained as `fixed_due_date`.

**Small example week:** the browser’s original six-task example is still a separate relative fixture, now also carrying descriptions, first steps and explicit 23:59 Eastern cutoffs. Its durations and task IDs are unchanged for existing engineering checks.

For repeatable interviews, use one source, calendar mode, as-of date and fixture version consistently, and record them in the session summary/transcript. Calendar demo time is 9:30 AM on that date. A fixed December assignment date does not imply that a real November calendar snapshot covers December; personal calendar suggestions remain bounded by imported coverage.

The original M3 case setups and historical results must be kept distinct from this revised demonstration dataset. Recover the baseline from the submitted report and original Git version when running comparisons.
