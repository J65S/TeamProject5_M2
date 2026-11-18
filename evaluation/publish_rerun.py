"""Format an explicitly reviewed rerun; preserve first-run artifacts and raw data.

This publishes judgments from review.json, never grades success from exit codes.
"""
import argparse
import csv
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from taskpilot.workload import deadline_at


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--stem',required=True)
    args=parser.parse_args()
    run=args.run_dir.resolve()
    review=json.loads((run/'review.json').read_text())
    manifest=json.loads((run/'manifest.json').read_text())
    for name,digest in manifest['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise SystemExit('Application/fixture changed during the run: '+name)
    baseline=list(csv.DictReader((ROOT/'evaluation/results.csv').open()))
    assert len(baseline)==10 and len(review['cases'])==10
    csv_path=ROOT/'evaluation'/f'{args.stem}.csv'
    md_path=csv_path.with_suffix('.md')
    chart_path=ROOT/'evaluation'/f'{args.stem}_chart.svg'
    if any(p.exists() for p in (csv_path,md_path,chart_path)):
        raise SystemExit('Choose a new stem; published results will not be overwritten.')
    rows=[]
    model_settings=set()
    for old in baseline:
        case=old['case_id'];judgment=review['cases'][case]
        assert judgment['pass_fail'] in ('PASS','FAIL')
        raw=json.loads((run/f'{case}.json').read_text())
        result=raw.get('result') or {}
        plan=result.get('plan') or {}
        blocks=plan.get('blocks',[])
        clock_span=int((max(datetime.fromisoformat(b['end']) for b in blocks)-min(datetime.fromisoformat(b['start']) for b in blocks)).total_seconds()/60) if blocks else 0
        checked='N/A'
        if plan:
            tasks={t['id']:t for t in result['assignment_snapshot']['assignments']}
            assert plan['scheduled_minutes']==sum(b['minutes'] for b in blocks)
            assert plan['elapsed_minutes']==plan['scheduled_minutes']+plan['break_minutes']
            assert plan['elapsed_minutes']<=result['minutes']
            assert all(datetime.fromisoformat(b['end'])<=deadline_at(tasks[b['task_id']]) for b in blocks)
            assert all(b['start'][:10]=='2026-10-27' for b in blocks)
            assert sum(t['remaining_minutes'] for t in plan['unfinished'])==sum(t['estimated_minutes'] for t in tasks.values() if t.get('status')!='completed')-plan['scheduled_minutes']
            checked='PASS'
        seconds=raw['elapsed_seconds']
        if case=='TC08':seconds+=json.loads((run/'TC08_initial.json').read_text())['elapsed_seconds']
        if result.get('model'):
            model_settings.add((result['model'],result.get('reasoning_effort'),result.get('analyst_reasoning_effort')))
        rows.append(dict(case_id=case,case_name=old['case_name'],input=old['input'],expected_output=old['expected_output'],
                         actual_output=raw['stdout'].strip() or raw['stderr'].strip(),pass_fail=judgment['pass_fail'],previous_result=old['pass_fail'],
                         actual_summary=judgment['summary'],root_cause=judgment['root_cause'],failure_analysis=judgment['failure_analysis'],secondary_notes=judgment['secondary_notes'],
                         evidence_path=str((run/f'{case}.json').relative_to(ROOT)),run_date=manifest['run_date'],version_commit=manifest['application_head']+'+uncommitted-working-tree (see source manifest)',
                         critic_score='N/A - manual review',checked_allocation=checked,elapsed_seconds=round(seconds,3),focus_minutes=plan.get('scheduled_minutes'),
                         allocated_study_minutes=plan.get('elapsed_minutes'),clock_span_minutes=clock_span,
                         remaining_work_minutes=(result.get('answer_facts') or {}).get('remaining_work_minutes')))
    with csv_path.open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    passed=sum(r['pass_fail']=='PASS' for r in rows)
    prior=sum(r['pass_fail']=='PASS' for r in baseline)
    turns=[json.loads(p.read_text()) for p in run.glob('TC*.json') if 'input' not in p.name]
    ai_turns=[r for r in turns if (r.get('result')or{}).get('engine')=='two_agent_ai']
    durations=[r['elapsed_seconds'] for r in ai_turns]
    lines=['# Original ten-case evaluation — second live run','',f'**{passed}/10 passed ({passed*10}%).** Previous recorded run: {prior}/10 ({prior*10}%). Combined change: **+{(passed-prior)*10} percentage points**. Readiness target: 9/10; **not met**.','',
           'The checked scheduling data now fits its budgets and deadlines. Three full-response failures remain: normal-schedule narration, zero-time preparation advice, and contradictory changed-availability advice.','',
           '## Ten-case chart','', '| Case | Test | Previous | Rerun | Observed result |','|---|---|---|---|---|']
    for row in rows:lines.append(f"| {row['case_id']} | {row['case_name']} | {row['previous_result']} | **{row['pass_fail']}** | {row['actual_summary']} |")
    lines+=['',f'![Rerun chart]({chart_path.name})','', '## Method and scoring','',
            '- All ten original M3 cases executed once; TC08 includes a real initial four-hour turn and follow-up. No selective reruns or application changes occurred during this evaluation.',
            '- Same original fixture hashes, controlled October 27, 2026 planning date, explicit completion of older work, and fictional 09:30 Eastern calendar as the recorded 3/10 run. The December interview data was not substituted.',
            '- Cases 5/7 use their original special fixtures; case 10 uses a nonexistent folder instead of renaming user data. These calendar/date/file-path adaptations are inherited and disclosed.',
            '- Original success criteria were cross-checked against submitted M3 Section 4.3, pages 6–8. Checked allocations and the whole delivered response were reviewed separately. Correct JSON or a zero exit code is not by itself a case pass.',
            '- Narrow retrieval/handoff criteria can pass despite secondary prose issues; these are explicitly recorded. Retrieval analysis includes the retrieved snapshot and computed analysis facts; the report does not claim that every source field appears in the final prose.',
            '- Reviewer: coding assistant, not an independent user or critic rating. No critic scores were invented. Tool/handoff counts are instrumented evidence, not a complete SDK-native handoff trace.',
            '- Model: gpt-oss. Analyst reasoning: low. Current plan/clarification advisor reasoning: medium; inventory path: low. The first run used low effort throughout. This comparison covers the combined current implementation/settings and does not isolate any individual change.',
            '- The historical M3 PDF reported 7/10 with different execution limitations; that is not a controlled baseline. The directly preserved earlier M4 run is 3/10.',
            '- The original report, CSV, chart and raw evidence remain unchanged. These rerun artifacts use separate filenames.',
            '',f'[Full input/expected/actual CSV]({csv_path.name}) · [Source manifest](evidence/{run.name}/manifest.json) · [Recorded review](evidence/{run.name}/review.json) · [Earlier 3/10 report](results.md)','',
            '## Allocation checks and response time','',
            f'All {len(ai_turns)} actual AI turns returned responses; no provider/validation timeout occurred. Each finished within 60 seconds (mean {statistics.mean(durations):.1f}s, range {min(durations):.1f}–{max(durations):.1f}s). TC08 takes {next(r["elapsed_seconds"] for r in rows if r["case_id"]=="TC08"):.1f}s for both turns combined. TC10 returned the expected local error without AI.',
            '', 'Every returned plan passed focus-sum, elapsed-budget, same-day, deadline and remaining-work arithmetic checks. TC03 has an empty zero-minute plan; TC04/TC07 have no plan. This does **not** validate the AI narration or any extra work it suggests outside the checked blocks.',
            '', '## Actual outputs and analysis','']
    for row in rows:
        raw=json.loads((run/f"{row['case_id']}.json").read_text());result=raw.get('result') or {}
        answer=result.get('answer') or result.get('error') or raw['stderr'].strip()
        lines.extend([f"### {row['case_id']} — {row['case_name']} — {row['pass_fail']}",'', '**Input/setup:** '+row['input'],'', '**Expected:** '+row['expected_output'],'', '**Actual reply/error:**',''])
        lines.extend('> '+line if line else '>' for line in answer.splitlines())
        if result.get('follow_up'):lines+=['> '+result['follow_up']]
        lines+=['', '**Judgment:** '+row['actual_summary'],'', '**Reason:** '+row['failure_analysis'],'', '**Secondary notes:** '+row['secondary_notes'],'',
                f"**Checked allocation:** {row['checked_allocation']}; focused work: {row['focus_minutes']}; allocated elapsed study time: {row['allocated_study_minutes']}; clock span: {row['clock_span_minutes']} minutes.",'',
                f"[Full raw command/output](evidence/{run.name}/{row['case_id']}.json)",'']
    lines+=['## Remaining failures','',
            '- TC01: keep the AI narrative consistent with each block duration and the resulting remaining-work estimate.',
            '- TC03: zero availability must mean no immediate study **or preparation** task, even if the checked plan is empty.',
            '- TC08: preserve the new availability through the entire reply; do not add immediate preparation outside the plan or misstate known openings.',
            '', 'Five prior failures improved to passes (TC02, TC04, TC05, TC07, TC09). TC01 and TC08 still fail; TC03 regressed. TC06 and TC10 remain passes. No app fixes were made as part of this rerun.',
            '', 'This is one observed run, not evidence of stable reliability or benefit to real users. The five external-user sessions are still required. No PDF report, live Google Calendar test or user study was generated by this rerun.']
    md_path.write_text('\n'.join(lines)+'\n')
    # Standalone SVG, preserving the original 3/10 chart unchanged.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="630" viewBox="0 0 1100 630" role="img" aria-labelledby="title desc">',
         f'<title id="title">TaskPilot rerun: {passed} of 10 passed</title>',
         '<desc id="desc">Earlier recorded run: 3 pass, 7 fail. Current rerun: 7 pass, 3 fail. Failures: normal schedule, zero availability and changed availability. Target 9 of 10 is not met.</desc>',
         '<rect width="1100" height="630" rx="20" fill="#f7f8fc"/><g font-family="Arial, sans-serif">',
         '<text x="48" y="57" font-size="27" font-weight="700" fill="#283044">TaskPilot · ten-case rerun</text>',
         '<text x="48" y="88" font-size="15" fill="#657088">Original M3 cases · November 17, 2026 · first attempts on current code</text>',
         f'<text x="48" y="155" font-size="46" font-weight="700" fill="#283044">{passed} / 10</text>',
         f'<text x="240" y="151" font-size="23" fill="#367e69">{passed*10}% pass rate · +{(passed-prior)*10} percentage points</text>',
         '<text x="48" y="190" font-size="15" fill="#657088">Three full-response failures remain. Readiness target: 90%.</text>']
    for y,label,value,color in [(235,'Earlier M4 run',prior*10,'#8a96ac'),(295,'Current rerun',passed*10,'#367e69')]:
        svg += [f'<text x="48" y="{y+23}" font-size="16" fill="#47536a">{label}</text>',f'<rect x="210" y="{y}" width="700" height="32" rx="7" fill="#e8ebf2"/>',f'<rect x="210" y="{y}" width="{value*7}" height="32" rx="7" fill="{color}"/>',f'<text x="930" y="{y+23}" font-size="19" font-weight="700" fill="#283044">{value}%</text>']
    svg+=['<line x1="840" y1="220" x2="840" y2="337" stroke="#7359bb" stroke-width="2" stroke-dasharray="5 4"/>','<text x="808" y="363" font-size="12" fill="#7359bb">90% target</text>']
    for i,row in enumerate(rows):
        x=48+100*i;color='#367e69' if row['pass_fail']=='PASS' else '#b84f58'
        svg += [f'<rect x="{x}" y="394" width="88" height="75" rx="9" fill="{color}"/>',f'<text x="{x+44}" y="421" font-size="13" fill="white" text-anchor="middle">{escape(row["case_id"])}</text>',f'<text x="{x+44}" y="451" font-size="16" font-weight="700" fill="white" text-anchor="middle">{row["pass_fail"]}</text>']
    svg += ['<text x="48" y="510" font-size="14" fill="#47536a">Failures: TC01 normal-schedule narration · TC03 zero-time preparation · TC08 follow-up advice</text>',
            '<text x="48" y="540" font-size="13" fill="#657088">Checked allocations fit the limits; inconsistent AI prose still counts against the full response.</text>',
            '<text x="48" y="566" font-size="13" fill="#657088">One observed run. Model settings changed with the implementation; individual effects are not isolated.</text>',
            '<text x="48" y="592" font-size="13" fill="#657088">Raw evidence and manual reasoning are preserved; no failures were selectively replaced.</text>','</g></svg>']
    chart_path.write_text('\n'.join(svg)+'\n')
    print(f'Published {passed}/10. Prior results preserved. Files: {csv_path.name}, {md_path.name}, {chart_path.name}')


if __name__=='__main__': main()
