# Business Process YAML Specification

This specification defines the YAML model used by the business-process skills.
BPMN, PlantUML, and HTML are generated from the same YAML definition.

## Root structure

```yaml
schema_version: "1.0"
process:
  id: expense_request
  name: 備品購入申請
  description: 社員による備品購入申請から発注までの業務プロセス
  owner: 総務部  # optional; do not infer only from task ownership
  version: "1.0"
  scope:
    start: 申請者が購入申請を開始する
    end: 購買担当が発注を完了する
participants: []
nodes: []
edges: []
metadata:
  assumptions: []
  open_questions: []
  inferences: []
```

## Required fields

- `schema_version`
- `process.id`
- `process.name`
- `participants`
- `nodes`
- `edges`
- Every participant: `id`, `name`
- Every node: `id`, `type`, `name`
- Every edge: `id`, `from`, `to`

## Node types

- `start`: start event
- `end`: end event
- `task`: business activity
- `gateway_exclusive`: exclusive decision or exclusive merge gateway
- `gateway_parallel`: parallel split or parallel join gateway

For `task`, `task_type` may be one of:

- `generic`
- `user`
- `manual`
- `service`
- `business_rule`
- `send`
- `receive`
- `script`

## Participant types

`type` is informational and may be one of `role`, `department`, `system`, `external`.

## Optional analysis fields on task nodes

- `description`
- `system`
- `inputs`: list of business-object or information names
- `outputs`: list of business-object or information names
- `duration`
- `frequency`
- `issues`
- `automation.candidate`
- `automation.notes`

Reasonable context-based inference is allowed for `description`, `inputs`, `outputs`, and `system`. Do not infer new business rules such as unconfirmed approval thresholds, owners, exceptions, durations, frequencies, or regulatory requirements. `process.owner` is optional and should not be inferred merely because one department performs downstream work.

### Modeling quality expectations

- For AI-generated models, populate `description` for every Task when the activity is understandable from context. Keep it concise and factual.
- Set `participant` on Tasks whenever the actor is known. Also set `participant` on Start/End/Gateway nodes when the responsible lane is clear from the surrounding flow. For example, a decision gateway immediately following an upper-manager review belongs in the manager lane; an End after an accounting transfer belongs in the accounting lane.
- A control node may omit `participant` only when assigning a lane would be genuinely ambiguous. Publisher may infer a display-only lane defensively, but the YAML should contain the participant when business context makes it clear.
- `task_type: user` means a person works with a software application. If no supporting application/system is established, prefer `generic` unless the user-task semantics are otherwise explicit.
- Do not invent a new output merely because an action could theoretically create one. For example, `エビデンスを保管` does not by itself imply a distinct `保管記録`; create that object only when the business description actually indicates such a record is produced.

## Task type semantics

Use specialized BPMN task types conservatively because they carry execution semantics.

- `user`: a person performs the task with the assistance of a software application.
- `generic`: use when the activity is known but its execution mode is not sufficiently established.
- `manual`: use only when a person performs the work without application/process-engine assistance.
- `business_rule`: use only when the task evaluates rules through a rules engine or equivalent automated rule service; do not use it merely because a person checks an amount or criterion.
- `send` / `receive`: use only when the activity itself is BPMN message sending/receiving, not merely because the task name says return, notify, or request.
- `service` / `script`: use only when automated execution is established.

## Terminology

When a generic name is needed for receipts, attachments, or supporting materials, prefer `エビデンス`. If the user provides a specific formal artifact name such as `領収書` or `請求書`, preserve that specific name.

## Business-object continuity

`inputs` and `outputs` describe business objects or information transferred through tasks. They are not a place to encode every process state.

1. If the same business object continues through review, approval, rejection/return, correction, resubmission, registration, or another state transition, keep the same object name unless it has actually become a distinct artifact.
2. Prefer `経費申請 -> 経費申請 -> 経費申請` over artificial variants such as `不備のない経費申請`, `金額確認済み経費申請`, or `部門長承認済み経費申請` when they refer to the same application.
3. Express state and control semantics with task names, `description`, gateways, edge labels, and edge conditions.
4. When an upstream output and downstream input refer to the same object, use exactly the same wording.
5. Every downstream input should have a plausible provenance: it was produced/attached/received by an upstream task, or is an explicit external input. If a task description says that it reviews or uses an object, include that object in the task `inputs`. Do not require unrelated intermediate tasks to carry an object in their I/O solely to keep a synthetic chain.
6. A task that outputs the same object after review, update, return, approval, or storage should keep the same object name. Do not rename `エビデンス` to `保管されたエビデンス` merely to encode state; represent that state in the task name or `description`. Create a separate `保管記録` only if a distinct record is actually produced.
7. Do not model pure completion/control states such as `確認完了`, `保管完了`, or `承認完了` as data objects unless a downstream task actually consumes that information as data.
8. Add a new object name only when a genuinely distinct artifact, record, message, report, external record, or other information object is created.

Example:

```yaml
- id: submit_expense
  type: task
  name: 経費精算を申請
  inputs: [経費情報, エビデンス]
  outputs: [経費申請, エビデンス]

- id: manager_review
  type: task
  name: 申請内容を確認
  inputs: [経費申請, エビデンス]
  outputs: [経費申請]

- id: revise_resubmit
  type: task
  name: 内容を修正して再申請
  inputs: [経費申請]
  outputs: [経費申請]

- id: store_evidence
  type: task
  name: エビデンスを保管
  inputs: [経費申請, エビデンス]
  outputs: [エビデンス]
```

## Edge semantics

- `name`: user-facing branch label
- `condition`: machine-readable or human-readable condition expression
- `default: true`: default route from an exclusive gateway

A default route MUST NOT also contain `condition`.

For an Exclusive Gateway used as a split, every outgoing route should have a user-facing `name`, including a default route. `default: true` means "otherwise" for execution semantics; it does not replace labels such as `不備なし` or `5万円未満` that the user explicitly stated.

## Gateway modeling rules

1. Use `gateway_exclusive` for mutually exclusive alternatives and for merging those alternatives again.
2. Use `gateway_parallel` only when multiple tokens really run in parallel or when waiting for all of those parallel tokens.
3. Do not connect mutually exclusive branches directly into a Parallel Gateway. Merge them first with a separate `gateway_exclusive`.
4. When an exclusive branch is followed by parallel work, model `Exclusive split -> alternative paths -> Exclusive merge -> Parallel split -> parallel tasks -> Parallel join`.
5. In schema v1.0, one gateway has one control-flow responsibility. Do not use one gateway as both join and split.
6. Outgoing flows from a Parallel Gateway must not have `condition` or `default`.
7. A converging Exclusive Gateway used only as a merge normally has multiple incoming flows and one outgoing flow.
8. For an Exclusive Gateway used as a split, give every outgoing route a concise `name` for human-readable diagrams. A default route may omit `condition` but should still keep an explicit label when the branch meaning is known.
9. In a BPR To-Be model, when a Parallel Split / Join directly controls at least one `service` / `script` or other system-executed branch, place the Parallel Gateway itself in a `type: system` participant lane. Purely human parallel work is not automatically system-owned.

## Progressive modeling

The first model should be produced as soon as the main control flow is sufficiently defined: start/end, participants, major tasks, branching conditions, returns/exceptions, and parallelism. Optional analysis fields such as owner, duration, frequency, issues, SLA, and automation candidates must not block first output. Ask before first output only when an unresolved point changes the process topology, branch semantics, or responsible actor materially. After first output, the agent may propose a small number of high-value enrichment questions relevant to analysis or improvement.

## General modeling rules

1. BPMN, PlantUML, and HTML are generated from the same YAML definition and should not diverge semantically.
2. IDs must be stable across conversational revisions when the same business element remains.
3. Preserve information already confirmed by the user unless the user changes it.
4. Important unresolved items belong in `metadata.open_questions`.
5. Important non-obvious inferred assumptions may be recorded in `metadata.inferences`.
6. Every normal execution node should be reachable from a `start` node and have at least one path to an `end` node.
7. Use explicit gateways for decisions and parallel splits/joins instead of encoding branching only in task text.
8. Keep display names concise. Put details in `description` and analysis fields.
9. Gateway nodes are control-flow elements, but assign `participant` when the surrounding flow makes the lane clear. Decision splits normally use the lane of the person/system making the decision. A merge/join normally uses the lane that best represents the next control point or immediately following work. Start/End events likewise use the initiating/final actor when clear. Do not leave these nodes unassigned merely because they are not Tasks.


## BPR Final To-Be semantic guardrails

When `metadata.bpr` is present, the model is a BPR To-Be and additional finalization rules apply:

1. Do not finalize while an unresolved business rule prevents one unambiguous product-neutral Control Flow from being modeled. Numeric/timing parameters and implementation details may remain open when the abstract flow is still unambiguous.
2. If a task outputs an approval/decision result, downstream control flow must consume that result with an explicit condition or exclusive split before unconditional downstream work.
3. Natural-language guard clauses such as "only if both succeed" must be represented in control flow, not only in task descriptions.
4. Every relevant analysis/As-Is unknown must be tracked in `metadata.bpr.open_question_disposition`; `carried_forward` entries must exactly match top-level `metadata.open_questions`, and blocking questions cannot be carried forward in Final To-Be.
5. Schema v1.0 and the documented BPR extension are strict: unknown keys or accidental nesting are Errors even when YAML parsing succeeds.
6. Automated tasks with an `exception_owner` may keep implementation-level retry/SLA detail unresolved when the product-neutral exception route itself is already clear.


## BPR To-Be open-question origin

- Analysis/As-Is由来の質問は元のsourceを維持する。
- To-Be設計によって新しく生じた具体パラメータの未確認事項は `metadata.bpr.open_question_disposition[].source: design` として追跡できる。
- 元質問をdesign質問へ置換して消してはならない。元質問は `resolved / not_applicable` 等でDispositionを確定し、残る具体事項を別questionとして追加する。

## Automated branch exception semantics

`service / script` Taskが `automation.exception_owner` を持つ場合、正常系と例外系を同じParallel Joinへ無条件に流さない。Task直後のExclusive Gateway等で成功と失敗/期限超過を分離し、成功だけをJoinへ送る。例外branchは `exception_owner` の人Taskへ接続し、解消後に当該自動Taskを再実行する。
