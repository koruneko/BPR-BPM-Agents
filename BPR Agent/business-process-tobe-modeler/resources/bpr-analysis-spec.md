# BPR Analysis Specification v1.9

## Purpose

This specification defines the machine-readable analysis produced by the BPR Agent from an As-Is `process.yaml`.

The As-Is process definition is evidence. The analysis is an evaluation/proposal layer and MUST NOT overwrite the As-Is YAML.

## Core principles

1. Evaluate whether work should continue before evaluating automation.
2. Keep facts, assumptions, unknowns, and proposals distinguishable.
3. A proposal may have any number of recommendation classifications; do not impose an arbitrary maximum.
4. Do not generate a To-Be process until the user explicitly approves or conditionally approves one or more improvement IDs.
5. Product capability claims that can change over time should be verified using current sources when web search is available.
6. For Microsoft 365 / Power Platform implementation ideas, prefer Microsoft Learn and other Microsoft first-party sources.
7. Web research is used to assess feasibility, constraints, support status, and implementation options. It MUST NOT rewrite organization-specific As-Is facts.
8. First define the business change, then propose implementation options. Do not let a product or feature dictate the BPR conclusion.
9. Do not silently remove, bypass, or alter an existing Task or business rule unless the proposal explicitly classifies and explains that change.
10. If an As-Is route or rule is unresolved, keep the proposal conditional instead of inventing the missing behavior.

## Improvement classifications

`recommendations` is a list and may contain any number of the following values:

- `eliminate`: remove the work if its purpose can be removed or absorbed elsewhere.
- `simplify`: reduce steps, checks, inputs, handoffs, or complexity while preserving required outcomes.
- `consolidate`: combine duplicated or closely related work with another task/process step.
- `standardize`: make rules, inputs, outputs, templates, or execution patterns consistent.
- `relocate`: move responsibility, timing, system, or execution location to a more appropriate place.
- `automate`: execute meaningful portions of the task automatically.
- `assist`: use AI or other tooling to support a human while keeping the human as the primary decision/execution actor.
- `retain`: explicitly keep the task/process behavior because it remains necessary.

Do not combine `retain` and `eliminate` on the same proposal. Other combinations are allowed when the rationale explains the relationship, for example `eliminate + automate` when a human task is removed and replaced by a deterministic system action.

## Automation levels

When automation is evaluated, use:

- `full`: the main work can be executed automatically, with humans handling only exceptions or governance where needed.
- `partial`: meaningful parts are automated but human execution remains inside the task.
- `assist`: the system or AI prepares, summarizes, recommends, validates, or highlights information while the human remains the primary actor for the task.

`automation.candidate` is tri-state:

- `true`: a meaningful automation/assistance opportunity was identified.
- `false`: the task was evaluated and is not currently an automation candidate.
- omitted/null: evidence is insufficient to decide.

If `recommendations` contains `assist`, `automation.candidate` should normally be `true` and `automation.level` should be `assist`.
If `recommendations` contains `automate`, `automation.candidate` should normally be `true` and the level should normally be `full` or `partial`.

## Priority dimensions

Every improvement should be assessed independently on four qualitative dimensions:

- `impact`: `high | medium | low`
- `effort`: `high | medium | low`
- `risk`: `high | medium | low`
- `confidence`: `high | medium | low`

Do not invent an overall numeric score or rank unless the user explicitly asks for one. Explain uncertainty in `rationale`, `prerequisites`, or `unresolved_questions`.

`unresolved_questions` MUST be atomic enough to resolve independently at a later Human Gate. Do not combine a topology/approval/threshold/exception rule with product implementation details such as API method, licensing, retention, or naming into one question.

## Improvement dependencies

Use `dependencies` when the value or feasibility of one proposal depends on another proposal.

Supported dependency types:

- `requires`: use only when this improvement itself cannot be validly reflected in To-Be unless all listed improvements are approved or conditionally approved.
- `any_of`: use only when this improvement itself requires at least one listed improvement to be approved or conditionally approved.
- `enhances`: use when the improvement is independently valid, and the listed improvements only increase value, control, observability, or completeness.

Do not use `requires` or `any_of` merely because two improvements work better together. If the proposal still makes business sense and can be implemented independently, use `enhances`.

Example:

```yaml
dependencies:
  - type: any_of
    improvement_ids: [IMP-005, IMP-006]
    note: 少なくとも一方の自動化方式が確定すると状態管理の効果が高まる。
```

## Implementation options

An improvement may contain zero or more `implementation_options`.

These are implementation candidates, not business decisions. Generate the BPR proposal first, then describe possible Microsoft 365 / Power Platform capabilities or other services that could implement it.

A `primary` implementation option is still only a candidate. Human Gate approval of an improvement MUST NOT automatically select the product/service. If the user explicitly selects a candidate, the matching decision entry MAY include `selected_implementation_options: [<exact product_or_service>]`. Without that explicit selection, candidate-only product names must not be fixed into To-Be `system`/participant fields.

```yaml
implementation_options:
  - product_or_service: Power Automate
    capability: SharePoint connector - Create file
    role: エビデンスを規定ライブラリへ自動保存する
    fit: primary          # primary | complementary | alternative
    confidence: high     # high | medium | low
    prerequisites:
      - 保存先ライブラリと命名規則が確定している
    source_refs:
      - SRC-001
```

Rules:

- Prefer 1-3 useful options rather than producing a catalog.
- Use `primary` only when the current evidence supports it as the main option.
- Use `complementary` when a candidate adds a capability alongside the main option rather than replacing it. A complementary option should normally coexist with at least one `primary` option.
- Use `alternative` for a substitute implementation approach or when a candidate is being considered without a confirmed main option.
- If the product, app type, connector, API, license, or tenant constraint is unknown, lower `confidence` and record the prerequisite/question.
- Current product capabilities should be verified against current first-party documentation when web search is available.
- Do not present a specific service as mandatory unless the user's environment or requirements establish that constraint.
- If `implementation_options` is empty, `implementation_options_reason` is REQUIRED and MUST explain why no concrete product/service candidate is shown. Do not emit only a bare `具体候補なし`.
- Report presentation MUST order implementation options as `primary`, `complementary`, then `alternative`. Within the same `fit`, order `confidence` as `high`, `medium`, `low`, then preserve original YAML order.
- The report SHOULD visually distinguish `primary` from `complementary` / `alternative` without making the page visually noisy. `complementary` is shown as `補完候補`.
- If an improvement has one or more `alternative` options but no `primary` option, the report MUST display those options as `検討候補` rather than `代替候補`. Keep the YAML `fit: alternative`; this is presentation-only and signals that no main option has been established.
- Use a consistent user-facing name for the same product/service within one artifact. Prefer the name commonly used in current first-party documentation, but do not mechanically add or remove vendor prefixes such as `Microsoft`. Preserve clear user/As-Is naming when it is unambiguous. Do not mix forms such as `Microsoft Power Apps` and `Power Apps` for the same product without a reason. Preserve source titles, quotations, plan/SKU names, and feature names as written by the source.
- Preserve the As-Is business vocabulary where practical. If the As-Is uses `エビデンス` for generic supporting material, use `エビデンス` in the BPR analysis; use `領収書` only when specifically referring to receipts. Do not mechanically replace generic `エビデンス` with `証憑`.
- Avoid the user-facing term `正本`. For a process-state storage location, prefer a descriptive phrase such as `基準となるデータストア` or `一元管理するデータストア`; for YAML, use `基準となる定義` when that is the intended meaning.

## As-Is open-question coverage

The number of improvements is not a contract. Do not force a fixed count.

Every source-process `metadata.open_questions` entry MUST be represented in `as_is_open_question_coverage`. This prevents an important unknown from disappearing when proposals are merged or split.

```yaml
as_is_open_question_coverage:
  - question: 再申請後にも不備が残る場合の再差し戻し率または最大再申請回数は未確認である。
    improvement_ids:
      - IMP-002
    carried_forward: true
    note: 再申請上限・エスカレーションの標準化対象に含め、具体値は未確認のまま引き継ぐ。
```

Rules:

- `question` MUST exactly match one source `metadata.open_questions` entry.
- Every source open question MUST have exactly one coverage entry.
- `improvement_ids` contains proposals that explicitly address or depend on the unknown.
- `carried_forward: true` means the uncertainty remains unresolved and must not be silently treated as decided.
- At least one of `improvement_ids` being non-empty or `carried_forward: true` is required.
- `note` explains how the analysis preserves the issue.
- Coverage is traceability, not permission to invent an answer.

## Proposal / unresolved consistency

Do not state one business rule as the chosen `proposed_change` and simultaneously list the same rule as unresolved. If the proposal itself deliberately chooses a new rule, Human Gate adoption is the decision on that proposed rule and the unresolved list should contain only remaining details. If the rule is genuinely unknown, keep the proposal neutral/conditional instead of asserting one outcome.

## Improvement decision granularity

Improvements are Human Gate decisions, not merely analysis paragraphs. Split changes when a user could reasonably approve, defer, or phase them independently. Do not bundle a cross-process control improvement with a task-specific data/output standardization improvement when either can stand on its own. For example, `parallel completion/failure control` and `transfer input/result-record standardization` should be separate proposals when one can be adopted without the other. Do not split changes that are inseparable solely to increase proposal count.

## Cross-process pattern coverage

Every analysis MUST explicitly evaluate these four patterns, regardless of how many improvements are proposed:

- `loop`: rework / return / resubmission cycles.
- `handoff`: work moving between participants or organizational roles.
- `duplicate_entry`: the same business data being re-entered or copied between steps/systems.
- `parallel_dependency`: parallel work, completion waits, one-sided failure, or synchronization dependencies.

Record the result in `process_pattern_coverage`. This is a coverage contract, not a requirement to create one improvement per pattern. If a pattern is present but no separate improvement is proposed, `note` MUST explain why it is already covered by other improvements or why no change is justified.

```yaml
process_pattern_coverage:
  - pattern: loop
    present: true
    related_tasks: [manager_review, return_application, revise_resubmit]
    improvement_ids: [IMP-001, IMP-002]
    note: 申請時予防と差し戻しルール標準化で扱うため、独立したループ改善案には分けない。
  - pattern: handoff
    present: true
    related_tasks: [return_application, revise_resubmit]
    improvement_ids: [IMP-002]
    note: 差し戻し時の情報受け渡しをIMP-002で標準化する。
  - pattern: duplicate_entry
    present: true
    related_tasks: [accounting_registration]
    improvement_ids: [IMP-005]
    note: Power Appsから会計システムへの再入力をIMP-005で扱う。
  - pattern: parallel_dependency
    present: true
    related_tasks: [accounting_registration, store_evidence, execute_transfer]
    improvement_ids: [IMP-008]
    note: 並行処理の完了待ち・片側失敗・滞留を横断状態管理の対象にする。
```

Rules:

- Exactly one entry is required for each of the four pattern values.
- `present` is boolean. Structurally obvious loops, participant handoffs, and parallel gateways must not be marked false.
- `related_tasks` contains As-Is task IDs relevant to the pattern.
- `improvement_ids` contains proposals that address the pattern. It may be empty when no separate change is justified.
- `note` is always required and MUST explain the analysis result, especially when a present pattern has no linked improvement.
- Do not create filler improvements merely to satisfy coverage.

## Temporal/process-order consistency

Proposal text must remain consistent with the As-Is sequence and gateway semantics unless the improvement explicitly changes that sequence.

- Do not use a state that only exists later in the process as an input/trigger for an earlier step.
- Do not invent one universal completion event if some As-Is branches do not contain that event.
- If timing or sequence changes, classify and explain it as an improvement.
- Prefer wording tied to actual As-Is events or merge points.

## Analysis structure

```yaml
analysis_version: '1.5'
source_analysis_id: bpr-a-0123456789abcdef
source_process:
  id: expense_reimbursement_as_is
  name: 経費精算業務（As-Is）
  version: '1.0'

research_sources:
  - id: SRC-001
    title: <source title>
    publisher: Microsoft Learn
    url: https://learn.microsoft.com/...
    note: <what this source supports>

improvements:
  - id: IMP-001
    title: <short human-readable title>
    scope: task              # task | process
    target_tasks:
      - check_amount
    recommendations:
      - eliminate
      - automate
    rationale: >
      Why this change is being proposed and what As-Is evidence supports it.
    proposed_change: >
      What should change if the user approves this proposal.
    expected_effect:
      impact: medium
      notes: >
        Expected qualitative or quantitative effect. Keep assumptions explicit.
    priority:
      effort: low
      risk: low
      confidence: high
    automation:
      candidate: true
      level: full
      notes: >
        What is automated, what remains human, and important constraints.
    dependencies: []
    implementation_options:
      - product_or_service: Power Automate
        capability: Condition in a cloud flow
        role: 固定閾値で後続経路を分岐する
        fit: primary
        confidence: high
        prerequisites:
          - 判定に使う金額が構造化データとして取得できる
        source_refs:
          - SRC-001
    prerequisites:
      - <condition that must be true>
    unresolved_questions:
      - <question that affects feasibility or design>
    as_is_evidence:
      - task_id: check_amount
        note: <specific fact from the As-Is model>
    source_refs:
      - SRC-001

as_is_open_question_coverage:
  - question: <exact string from source metadata.open_questions>
    improvement_ids:
      - IMP-001
    carried_forward: true
    note: <how the unknown is preserved or addressed>

process_pattern_coverage:
  - pattern: loop
    present: true
    related_tasks: [manager_review, return_application, revise_resubmit]
    improvement_ids: [IMP-001, IMP-002]
    note: <how the pattern is addressed, or why no separate proposal is needed>
  - pattern: handoff
    present: true
    related_tasks: [return_application, revise_resubmit]
    improvement_ids: [IMP-002]
    note: <coverage note>
  - pattern: duplicate_entry
    present: true
    related_tasks: [accounting_registration]
    improvement_ids: [IMP-005]
    note: <coverage note>
  - pattern: parallel_dependency
    present: true
    related_tasks: [accounting_registration, store_evidence, execute_transfer]
    improvement_ids: [IMP-008]
    note: <coverage note>

analysis_open_questions:
  - <cross-cutting unresolved question>
```

## Improvement IDs

- Use stable IDs such as `IMP-001`, `IMP-002`, ... within one analysis.
- The report and Human Gate use these IDs.
- If an analysis is revised conversationally, keep IDs stable for unchanged proposals.
- New proposals receive new IDs; do not recycle rejected/removed IDs for a different proposal.

## Evidence and research

- `as_is_evidence` refers to facts from the source process. Prefer task IDs and concise factual notes.
- `research_sources` records external sources that materially support product feasibility or constraints.
- `source_refs` references `research_sources[].id`.
- `implementation_options[].source_refs` uses the same source registry.
- Improvement-level `source_refs` MUST directly support the main proposal or rationale. Do not attach a source that only supports an ancillary capability and then present it as evidence for the entire improvement.
- A concrete product/service implementation option SHOULD have one or more `source_refs` when current first-party evidence is available. The validator emits a warning when a product/service option has no source reference; this does not block analysis.
- A source reference MUST directly support the capability claimed by that implementation option. Do not use evidence for one capability (for example, input validation) as evidence for a broader or different capability (for example, workflow routing) unless the source actually covers both. Split the capability, omit unsupported source references, or research an additional primary source.
- Do not fabricate URLs or source titles. If current product capability was not verified, state that in `unresolved_questions` and reduce `confidence` as appropriate.
- Organization-specific facts from the As-Is YAML take precedence over generic external guidance.

## Analysis artifact identity

`analysis_id` is a required content-derived identifier generated by the Analyst script in the form `bpr-a-<16 hex>`. It identifies the exact improvement-analysis artifact, not only the schema/process version. Human Gate copied output and `improvement-decisions.yaml` MUST preserve it as `source_analysis_id`. To-Be generation MUST stop when the IDs do not exactly match.

## Human Gate decision structure

```yaml
decision_version: '1.3'
source_analysis_version: '1.5'
analysis_id: bpr-a-0123456789abcdef
source_process:
  id: expense_reimbursement_as_is
  version: '1.0'
decisions:
  - improvement_id: IMP-002
    decision: conditional_approved  # approved | conditional_approved | hold | rejected
    note: 業務責任者が再申請回数の上限とエスカレーションルールを確定すること
```

Meanings:

- `approved`: adopted for To-Be.
- `conditional_approved`: adopted for To-Be as a conditional target design. `note` is mandatory and the condition must remain traceable in To-Be metadata.
- `hold`: not reflected in To-Be.
- `rejected`: not reflected in To-Be.
- no decision / UI `undecided`: not reflected in To-Be and should be visibly shown as needing human judgment.

The agent may create the decision YAML from natural-language user choices. Ambiguous choices must be clarified before To-Be generation. For every `conditional_approved` decision, verify that the condition semantically belongs to the same improvement by comparing it with that improvement's title, `proposed_change`, `prerequisites`, and `unresolved_questions`. If the condition appears to belong to another improvement or the binding is ambiguous, stop before To-Be generation and ask the user to confirm/correct the improvement ID and condition. The validator includes a conservative lexical guardrail for obvious cross-improvement misbinding, but this does not replace semantic review by the agent.

The agent MUST NOT recommend which Human Gate decision the user should make. It may explain decision conditions, prerequisites, risk, confidence, and unresolved questions, but should not label proposals as `推奨判断: 条件付き採用`, `先行採用候補`, `採用しやすい候補`, or similar decision recommendations. This restriction is about improvement adoption. In the later Material Business Rule Gate, the agent may recommend one concrete option when source facts or conservative design principles support it, while clearly leaving the final choice to the user; otherwise it should state that there is no defensible recommendation.

### Material business-rule decisions

Adopting an improvement does not resolve every unresolved business rule inside that improvement. Before Final To-Be generation, require confirmation only when leaving the item open prevents one unambiguous product-neutral Control Flow from being modeled (for example route after a limit is reached, amount basis for a branch, non-approval route, or whether failure blocks downstream work). Numeric/timing parameters such as a retry-count value or SLA, escalation timing/target, product/API choice, naming, and retention details are normally non-blocking when the abstract flow can still be modeled. Record confirmed blocking rules in the same decision artifact:

```yaml
business_rule_resolutions:
  - question: 部門長が承認しない場合は却下か差し戻しか、どこへ戻すか
    source: IMP-004
    resolution: 非承認時は申請者へ差し戻し、再申請後に上長確認からやり直す
```

`question` must exactly copy the unresolved question from the analysis/As-Is. `source` is the source improvement ID (`IMP-xxx`) or `as_is` / `analysis` for questions originating outside an active improvement. `resolution` must preserve the user's decision without adding unstated detail. If one user answer resolves multiple existing questions, create one resolution entry per exact question rather than binding the whole answer to only one question. The validator conservatively detects common flow-blocking questions; the agent must also perform semantic review. Product implementation details and parameters that do not prevent a product-neutral logical flow may remain non-blocking.

## To-Be traceability requirements

The To-Be process is a NEW process definition. Do not overwrite the As-Is file.

The To-Be `process.id` should differ from the As-Is process ID. Unchanged As-Is node/edge IDs should remain stable. New elements receive new IDs.

The To-Be MUST also include `metadata.bpr.open_question_disposition`. Every unresolved question relevant to the To-Be must be classified exactly once as `resolved`, `carried_forward`, or `not_applicable`. Each entry includes `source`, `question`, `status`, `materiality`, `note`, and, when resolved, `resolution`. `materiality` is `blocking` or `non_blocking`. Questions carried forward must appear exactly in top-level `metadata.open_questions`; resolved/not-applicable questions must not. A `materiality: blocking` question cannot be carried forward in a Final To-Be.

The To-Be YAML must include traceability metadata:

```yaml
metadata:
  bpr:
    source_process:
      id: expense_reimbursement_as_is
      version: '1.0'
    source_analysis_version: '1.5'
    source_analysis_id: bpr-a-0123456789abcdef
    applied_improvements:
      - IMP-001
    conditional_improvements:
      - improvement_id: IMP-001
        condition: 会計システムにAPIまたはCSV連携があること
    issue_disposition:
      accounting_registration:
        - source_issue: Power Appsに登録済みの内容を会計システムへ再入力している。
          status: remaining       # resolved | remaining | changed
          note: 条件付き採用の連携方式が未確定のため、現時点では人手登録を維持する。
        - source_issue: 会計システムへの再入力には転記ミスのリスクがある。
          status: remaining
          note: 人手登録を維持する間は転記ミスリスクも残る。
    change_log:
      - improvement_id: IMP-001
        title: 金額確認Taskの廃止と閾値分岐の自動化
        action: remove_and_replace
        summary: 金額確認の人手Taskを廃止し、閾値判定を自動化
        expected_effect:
          impact: medium
          notes: 200分/月の定型作業削減が期待される。実績値は運用後に確認する。
        confidence: high
        condition: null
        source_node_ids: [check_amount]
        target_node_ids: [amount_decision]
        source_edge_ids: []
        target_edge_ids: []
```

Only `approved` and `conditional_approved` improvements may appear in `applied_improvements` or `change_log`.

Each `change_log` entry MUST copy `title`, `expected_effect`, and `priority.confidence` from the approved analysis without rewriting them. Use `condition` to preserve the exact conditional-approval note; use `null` for an unconditional approval. This snapshot lets a To-Be artifact explain why a node changed without re-reading the analysis file.

When a conditional approval still permits multiple implementation modes that would change `task_type`, participant, system, or control flow, do not select one mode by inference. Preserve the condition and keep the process model conservative until the implementation mode is confirmed. Cross-cutting state/monitoring automation must not, by itself, turn every touched Task into an automation candidate or be appended to each Task's `automation.notes`; keep it in BPR traceability. To-Be task nodes do not carry `duration` / `frequency`; these are As-Is baseline measurements, not post-implementation actuals.

For an automated To-Be `service` / `script` Task, separate the execution actor from the human exception owner. The Task `participant` should reference a `type: system` participant. When the execution product is not selected, a product-neutral participant such as `automation_system` / `自動処理` may be introduced. Keep the destination/application in `system`, and record the human/organizational participant responsible for failed or exceptional cases in `automation.exception_owner`. Do not place an automated normal-flow Service Task in a human lane merely because that team handles exceptions.

When an adopted improvement has `automation.level: full`, removes a human decision/preparation Task, and replaces that work with a deterministic `gateway_exclusive`, that Gateway is the automated decision executor and should also use a `type: system` participant. This is a narrow rule for explicit full-automation replacements; do not move human judgment gateways to a system lane.

To-Be top-level `metadata.assumptions` contains only assumptions required for the future target design. Do not copy As-Is workload calculations, measured frequencies, durations, or observed rates into To-Be assumptions. Those baselines belong in `metadata.bpr.source_node_context` and `metadata.bpr.performance_targets`. If an As-Is business rule or system placement remains an explicit premise of the To-Be (for example, high-value requests still require department-head approval, or SharePoint remains the evidence repository), restate that premise as a future-design assumption rather than copying the As-Is measurement calculation.



### To-Be performance targets

A To-Be process is a proposal/target design, not a post-implementation measurement. Preserve As-Is `duration` / `frequency` only in `metadata.bpr.source_node_context`; do not copy them into To-Be task nodes. Express intended outcomes with `metadata.bpr.performance_targets`.

```yaml
metadata:
  bpr:
    performance_targets:
      - metric: 上長確認時間
        baseline: 8分/件
        target: null
        direction: decrease   # decrease | increase | maintain
        note: 申請時の不備予防により確認負荷低減を期待。目標値は未設定で、導入後に測定する。
        related_improvements: [IMP-001]
        source_node_ids: [manager_review]
        target_node_ids: [manager_review]
      - metric: 金額確認の人手作業量
        baseline: 200分/月
        target: 0分/月
        direction: decrease
        note: 金額確認Taskを廃止するため、定常的な人手確認は設計上0になる。
        related_improvements: [IMP-003]
        source_node_ids: [check_amount]
        target_node_ids: [amount_decision]
```

Rules:

- `metric` is the business/KPI measure the adopted improvement intends to change. It is not limited to time or volume; rework rate, error rate, exception rate, lead time, SLA, manual workload, reprocessing, control/audit metrics, etc. are valid.
- `baseline` is an As-Is fact when known; use `null` when not measured.
- `target` is a concrete target only when explicitly supplied by the user/business rule or deterministically implied by the adopted design (for example, an eliminated manual task can have a target manual workload of zero). Otherwise use `null`. Never invent a percentage or time reduction.
- `direction` is `decrease`, `increase`, or `maintain`.
- `note` explains the intended outcome and, when target is null, why the target value is not yet set.
- `related_improvements` contains only approved/conditionally approved improvement IDs.
- `source_node_ids` and `target_node_ids` provide traceability. A removed source task may point to its replacement/next target node.
- These are targets/expectations, not actual To-Be performance results. Actual results belong to post-implementation measurement.

### As-Is issue disposition in To-Be

`source_node_context.issues` is historical As-Is evidence. `nodes[].issues` describes issues that still apply to the To-Be task. Do not copy As-Is issues into To-Be merely to preserve history.

For every surviving As-Is task that had one or more source issues and is either structurally changed **or targeted by an approved/conditionally approved improvement**, `metadata.bpr.issue_disposition.<node_id>` MUST classify every source issue exactly once:

- `resolved`: the As-Is issue is no longer true in the modeled To-Be; the exact source issue must not remain in `nodes[].issues`.
- `remaining`: the issue still applies in To-Be; the exact source issue remains in `nodes[].issues`.
- `changed`: the old issue is no longer an accurate statement. Use exactly one of: (a) `to_be_issue` when a related issue still exists in the To-Be and must appear in `nodes[].issues`; or (b) `performance_target_metric` when the old issue is being treated as a Baseline/KPI and should move to `performance_targets` instead of remaining as a To-Be issue. `performance_target_metric` must exactly match a linked `performance_targets[].metric` for that node.

Every disposition entry requires a concise `note`. For `changed`, do not set both `to_be_issue` and `performance_target_metric`. When `performance_target_metric` is used, the original As-Is issue must not remain verbatim in `nodes[].issues`. New To-Be-specific issues that did not exist in As-Is may also be added directly to `nodes[].issues`.

Example of moving an As-Is observation into a To-Be KPI instead of preserving it as a future issue:

```yaml
issue_disposition:
  manager_review:
    - source_issue: 初回確認の20%が差し戻しとなっている。
      status: changed
      performance_target_metric: 初回確認の差し戻し率
      note: As-Is実績20%はBaselineとしてperformance_targetsへ移し、To-Beでは導入後値を測定する。
```

## Analysis sequence

For each relevant task and cross-process pattern, reason in this order:

1. Is the work still necessary for the business outcome, control, legal/compliance requirement, or user value?
2. If it remains necessary, can it be simplified?
3. Can duplicate or adjacent work be consolidated?
4. Can rules, inputs, outputs, or execution patterns be standardized?
5. Would responsibility, timing, or system placement be better elsewhere?
6. What meaningful work can be automated?
7. What remaining human work can be assisted by AI or other tooling?
8. Only after the business change is clear, which products/features/services are plausible implementation options?

Do not jump directly from As-Is pain points to automation if elimination or simplification can remove the work itself.
