# To-Be Gap Analyst Agent v3 rebuild notes

## Purpose

v3 addresses two failures reproduced in Agent Builder:

1. The agent reached user agreement / a confirmed plan but stopped without automatically creating the report.
2. The agent read the registered Skills but skipped required stages, created an ad-hoc `build_gap.py`, omitted source-pack verification, and then treated a limited package as if it were formal.

## Main design change

`gap-delivery/scripts/gap_workflow.py` is now the single orchestration entry point for the integrated Agent.

### `prepare`

Run before semantic Gap analysis. It creates:

- `source-pack.txt`
- `source-index.json`
- `gap-analysis.template.json`
- `workflow-preparation.json`

The template preserves exact source-question lineage, process entity IDs, improvement IDs, and hashes of the prepared source pack/index. The agent must update this template lineage rather than reconstructing `gap-analysis.json` from summaries with an independent script.

### `calendar`

Provides a registered path for verified Japanese-business-day calculations. This avoids guessing a standalone Skill path and falling back to hand calculation after a path lookup failure.

### `draft`

May create an in-progress package, but it is never formal or verified-final output.

### `final`

Requires the prepared source pack and a completed analysis. It calls the registered generator internally and creates a formal ZIP only when every gate passes.

## Final gate

Formal generation now fails and does not create the final ZIP when, among other checks:

- `--pack` is missing.
- The analysis was not derived from `gap_workflow.py@3 prepare`.
- Prepared source-pack or source-index hashes do not match.
- Dialogue is not completed or confirmation source is missing.
- GAP / ACT / Q / Next Action sets are incomplete for final delivery.
- Internal priority values are not `critical/high/medium/low`.
- Analysis dimensions are placeholders or overly repetitive.
- Gap decision-context fields are missing/thin or heavily templated across all gaps.
- Structured source evidence is missing.
- Semantic mappings remain `unmapped`, use invalid shapes, omit semantic differences, duplicate source IDs, or fail full source-entity coverage.
- A source ID common to As-Is and To-Be is not compared in one semantic mapping.
- Improvement IDs from `improvement-analysis.yaml` are not classified in `coverage.improvement_lineage`.
- Source-question lineage does not exactly match the source pack.
- Dependencies, IDs, execution sequence, renderer output, derivative ID/count consistency, or HTML re-render reproducibility fail.

Only `overall_status=pass` and `formal_verified=true` is a formal result.

## Conversation completion behavior

Agent Instructions now distinguish dialogue completion from Agent-task completion. When the user approves the current scope/plan, the agent must in the same response flow:

1. update the canonical analysis,
2. set the dialogue completion data,
3. run `gap_workflow.py final`,
4. return the formal report/package when the final gate passes.

The agent must not stop at a "confirmed plan" summary, ask the user to request the report again, or ask whether it should create the report.

## Files changed

- Agent Instructions v3 / `declarativeAgent_0.json`
- `gap-delivery/SKILL.md`
- `gap-delivery/references/output-contract.md`
- `gap-delivery/scripts/gap_workflow.py` (new)
- `gap-delivery/scripts/generate_delivery.py`
- `gap-delivery/scripts/inspect_sources.py`
- matching `bpr-gap-analysis/scripts/inspect_sources.py`
- integration notes in `bpr-gap-analysis`, `gap-planning`, `gap-business-calendar`, and `gap-report-format`
- package versions: declarative agent `v1.9`, Teams manifest `1.0.20`

## Local validation

Validated locally:

- all Python files compile;
- all five Skill instructions are below 20,000 characters;
- `prepare` creates source pack, index, template, and preparation manifest;
- `final` with a source-verified synthetic analysis returns exit code 0, `overall_status=pass`, `formal_verified=true`, and a final ZIP;
- the final ZIP contains all seven runtime scripts including `gap_workflow.py`;
- `final` without a source pack returns non-zero and creates no final ZIP;
- invalid internal priority (`最優先候補`) returns non-zero and creates no final ZIP;
- registered renderer reproducibility and formal manifest checks pass in the positive test.

These are local script/package tests. They do not prove how consistently the preview Agent Builder runtime will follow the workflow; the purpose of v3 is to make skipped stages fail mechanically when the formal workflow is invoked.
