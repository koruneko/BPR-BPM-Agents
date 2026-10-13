# v3 planning-quality follow-up (2026-10-14)

This change is a continuation of PR #4. It does not alter BPM/BPR source files, CORE Agent definitions, or the approved improvement decisions.

## Why

A user-provided local demonstration (not committed to this public repository) completed the v3 workflow with a formally verified ZIP, but exposed semantic planning weaknesses: identical `priority_reason` across all GAP/ACT entries; 19 required/start dependencies using the same generic reason and unresolved inputs; a task mixing API investigation and implementation; generic fabricated deliverables; one resource role treated as one worker with concurrency one; and a serial schedule that did not follow its declared execution sequence. Several genuine analysis fields were missing from human-readable derivatives because the renderer read obsolete keys.

## Changed behavior

- `gap-planning` gives per-item prioritization, work-stage decomposition, concrete dependency gating and owner/skill separation guidance. It does not force a specific count of dependencies or split all actions mechanically.
- `gap-business-calendar` treats resource assumptions as `scenario` unless the single-person/concurrency constraint was separately confirmed. Estimates can be proposed without assuming capacity or a confirmed date.
- `gap-delivery` rejects mass-copied priority rationales, generic required/start dependencies, identical boilerplate dependency explanations, unsupported investigation+implementation tasks with no split rationale, and generic deliverables. It also checks the consistency of a declared serial schedule and its execution sequence.
- The renderer and derivative writers now honor `actions[].deliverables`, `roadmap[].start_condition`, and `roadmap[].transition_condition` (with backward-compatible legacy key reads). Derived HTML, Markdown, roadmap and CSV expose the corresponding business content. A missing HTML/Markdown source value fails derivative verification.
- Agent Instructions and the output contract document these distinctions and the limits of a formal verification claim.

## Validation and limitations

- Nine independent synthetic regression tests cover both rejection cases and legitimate exceptions. Test files contain **no user business source or generated customer analysis**.
- The previously generated demonstration is deliberately **not** republished as a corrected formal analysis. It would fail the stronger final gate until an agent revises each plan rationale, separates work stages and reconsiders dependency/resource assumptions with the human user.
- Formal structure and traceability verification do not constitute a business owner sign-off, a permission grant for external integrations, or a verified delivery-time commitment.
