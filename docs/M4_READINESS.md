# Team 5 M4 submission preparation

This is a submission-preparation checklist, not a completed report. Two full ten-case evaluations are complete: 3/10 in the first run and 7/10 in the rerun. The 9/10 readiness target is not met.

## Current evidence

- The README identifies the working project as TeamProject5_M4. Terminal and dashboard use the same MCP-grounded analyst and AI advisor.
- It says the committed 10-case evaluation and user-testing plans are in a separately submitted `TeamProject5_M3.pdf`. The submitted M3 PDF has now been supplied and reviewed from the Downloads folder. It contains the original ten cases and a preliminary 7/10 baseline (including a handoff case supported by another run), plus a plan for ten participants. The supplied course guide has also been reviewed; M4 requirements are on pages 11–13.
- The first real M4 evaluation on November 17 passed 3/10; its artifacts remain preserved. The full rerun passed 7/10, with TC01, TC03 and TC08 still failing. See `evaluation/results_run2.csv`, `evaluation/results_run2.md` and `evaluation/results_run2_chart.svg`. Raw first-attempt outputs, source hashes and manual judgments are in `evaluation/evidence/m4_2026-11-17_run2/`. This is a combined +40 percentage-point change; individual effects are not isolated. No completed external-user session notes are present.
- The configured GitHub remote is `https://github.com/J65S/TeamProject5_M2.git`. An M4 repository URL has not been verified.
- The working tree already contained an edit to `syllabi/software_engineering.txt`. Its contents were preserved when the data was moved to `data/syllabi/software_engineering.txt`.

## Evidence collection

1. Use the supplied M3 PDF and course guide. Copy the original ten cases, acceptance criteria, and user-testing procedure without silently replacing them. Document any necessary deviations.
2. Identify the actual M3 submission commit and submission date. Run those ten cases on that baseline and preserve inputs, raw outputs, model/SDK configuration, date, syllabus snapshot, and commit identifier. If a historical result is unavailable, label a new baseline run as a retrospective rerun.
3. Implement refinements based on observed failures. Record each change's reason and its affected cases. Re-run the same cases under comparable conditions; preserve failures as well as successes.
4. Preserve the completed 3/10 run. Capture the next full run in a new empty evidence directory and review every result against the original criteria. Do not count engineering checks or targeted smoke checks as a new evaluation pass rate.
5. Test with five people outside the team using the M3 procedure. Use participant codes P01–P05 and obtain consent before collecting notes. Record tasks attempted, observed outcomes, difficulties, feedback, and changes suggested. Exclude personal identifiers from committed evidence.
6. Both team backgrounds should contribute to evaluation, sessions, synthesis, the decision, and the Business Model Canvas. Document actual roles and review contributions. Each person should commit their own work; do not fabricate authorship or backdate commits.

## Reporting calculations

- Final suite pass rate: passing cases / 10. Report executed cases and missing or blocked cases alongside it.
- Change in pass rate: final percentage minus baseline percentage, expressed in percentage points.
- Attribute an improvement to a specific change only when before/after evidence isolates that change. Otherwise report the combined improvement and state that individual effects were not measured.
- A single run describes that run; report repetitions and variability when collected.
- Separate deterministic parser checks from full two-agent evaluation. Unit checks alone do not establish that the system helps people.

## Proposed 12-page report structure

This structure covers the guide’s M4 sections (pages 11–13); page allocation is a planning suggestion. The synthesis must be 500–700 words and the decision document 300–400 words.

| Page | Content |
|---|---|
| 1 | Title, team, repository URL, project purpose, evidence status |
| 2 | M3 commitments, evaluation method, deviations, reproducibility |
| 3 | Ten-case results, pass rate, baseline comparison |
| 4 | Failure analysis with concrete observed outputs |
| 5 | Agent refinements and measured effects; limitations of attribution |
| 6 | User-testing method and summaries for P01–P02 |
| 7 | Session summaries for P03–P05 |
| 8 | Cross-session synthesis and evidence of usefulness |
| 9 | Proceed, pivot, or scope-down decision and supporting evidence |
| 10 | Updated Business Model Canvas: all nine blocks |
| 11 | Canvas rationale, assumptions, and next validation steps |
| 12 | Contributions, limitations, references, evidence links |

Each session summary should state the participant's relevant context, task, observed success or failure, friction, feedback, and implication. Distinguish observed behavior from participant opinions and team interpretation. Do not invent quotations.

The Business Model Canvas must address customer segments, value propositions, channels, customer relationships, revenue streams, key resources, key activities, key partnerships, and cost structure. Mark unvalidated business assumptions explicitly.

## Final submission checklist

- [ ] Course guide checked section by section (requirements mapped below); verify completed deliverables against it before submission.
- [ ] Original M3 plans recovered; execute them and disclose deviations.
- [ ] Refined agent verified through the original ten cases.
- [ ] Results file contains all ten inputs, expectations, actual outputs, and outcomes.
- [ ] Five external-user sessions completed and synthesized.
- [ ] Decision follows the collected evidence, including failures.
- [ ] Updated Business Model Canvas includes all nine blocks.
- [ ] README has a `CHANGES Since M3` section with reasons and measured effects, or explicitly states when an effect was not measured.
- [ ] Real post-M3 commits demonstrate both contributors' ownership.
- [ ] GitHub repository is named `TeamProject5_M4`; published URL verified.
- [ ] Report exported and visually checked at 10–14 pages as `TeamProject5_M4.pdf`.
- [ ] Submit the repository link, PDF, and evaluation results file once for the team.

## Confirmed course-guide requirements

M4 is due Wednesday, November 18, 2026, at 11:59 PM. The guide lists 14 points and 20% of the project grade. Submit one repository link, a 10–14 page PDF, and the evaluation results file per team. The LMS assignment supplied in this conversation specifies the `TeamProject5_M4` repository and PDF names.

| Guide section | Required evidence | Rubric points |
|---|---|---|
| 1.1 Evaluation | Execute all ten M3 cases; ID, input, expected and actual output, pass/fail, critic score where applicable; pass rate; root cause for every failure (prompt, retrieval, reasoning, or other) | 3 |
| 1.2 Improvements | README CHANGES lists every post-M3 agent change, reason, and measured evaluation impact; genuine commits after M3 submission | 2 |
| 2.1 Sessions | Five completed templates from real external testers, including stuck and surprise moments | 3 |
| 2.2 Synthesis | 500–700 words: pattern supported by at least three testers; strongest specific validation moment; most important unexpected failure; top three prioritized changes before the final presentation, with rationale | 3 |
| 3.1 Decision | 300–400 words: proceed, pivot, or scope down; cite both evaluation and user-testing evidence | 2 |
| 3.2 Updated BMC | All nine blocks; identify significant changes from M2 in bold or notes; explain each change and trace it to M4 findings | 1 |

The guide requires exactly three team members, at least one from CS and one from entrepreneurship. Both backgrounds contribute across milestones. Record genuine contributions from all members; earlier commits alone do not demonstrate shared ownership of new M4 work.

### Required session summary template (repeat for P01–P05)

- Tester: role and context, without full name.
- Date and format: in person, video, or asynchronous.
- Task given: what the tester was asked to do with the agent.
- What they did: what actually happened, step by step.
- Where they got stuck: specific confusion, hesitation, or failure.
- What surprised the team: an unexpected action or comment.
- Would they use the agent again, and what would make them more likely to?

Also preserve the quantitative and qualitative responses committed to in the M3 user-testing plan. The guide's M3 plan requires at least two quantitative and three qualitative questions; recovering that plan is necessary to establish what this team committed to.
