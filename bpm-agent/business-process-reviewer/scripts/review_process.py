#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml


def load_model(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def xor_branch_reaches_parallel_join(
    xor_id: str,
    target_parallel_id: str,
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
    node_map: dict[str, dict[str, Any]],
) -> int:
    count = 0
    for branch in outgoing[xor_id]:
        start = str(branch.get("to", ""))
        q = deque([start])
        seen: set[str] = set()
        reached = False
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            if cur == target_parallel_id:
                reached = True
                break
            # A loop may return to the same XOR split. Do not treat that cycle as a second independent alternative reaching the target.
            if cur == xor_id:
                continue
            node = node_map.get(cur, {})
            ntype = node.get("type")
            if ntype == "gateway_exclusive" and cur != xor_id and len(incoming[cur]) > 1:
                continue
            if ntype == "gateway_parallel" and len(outgoing[cur]) > 1:
                continue
            for e in outgoing[cur]:
                nxt = str(e.get("to", ""))
                if nxt not in seen:
                    q.append(nxt)
        if reached:
            count += 1
    return count



def normal_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def input_has_provenance(
    node_id: str,
    object_name: str,
    node_map: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
) -> bool:
    """Check whether an input is available from upstream or is plausibly an entry input."""
    q = deque([(node_id, False)])
    seen: set[tuple[str, bool]] = set()
    while q:
        cur, passed_task = q.popleft()
        state = (cur, passed_task)
        if state in seen:
            continue
        seen.add(state)
        for edge in incoming.get(cur, []):
            prev = str(edge.get("from", ""))
            node = node_map.get(prev, {})
            ntype = str(node.get("type", ""))
            if ntype == "task":
                if object_name in normal_list(node.get("outputs")):
                    return True
                q.append((prev, True))
            elif ntype == "start":
                if not passed_task:
                    return True
            else:
                q.append((prev, passed_task))
    return False


def quality_warnings(
    node_map: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []

    missing_task_participant = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and not n.get("participant")
    ]
    if missing_task_participant:
        warnings.append({
            "code": "missing_task_participant",
            "message": "担当者が未設定のTaskがあります。文脈から明確ならparticipantを補完してください: " + ", ".join(missing_task_participant),
        })

    missing_control_participant = [
        nid for nid, n in node_map.items()
        if n.get("type") in {"start", "end", "gateway_exclusive", "gateway_parallel"} and not n.get("participant")
    ]
    if missing_control_participant:
        warnings.append({
            "code": "missing_control_participant",
            "message": "Start / End / Gatewayのparticipantが未設定です。担当レーンが文脈から明確なら補完してください: " + ", ".join(missing_control_participant),
        })

    missing_descriptions = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and not str(n.get("description") or "").strip()
    ]
    if missing_descriptions:
        warnings.append({
            "code": "missing_task_description",
            "message": "descriptionが未設定のTaskがあります。内容を文脈から説明できる場合は簡潔に補完してください: " + ", ".join(missing_descriptions),
        })

    user_without_system = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and n.get("task_type") == "user" and not str(n.get("system") or "").strip()
    ]
    if user_without_system:
        warnings.append({
            "code": "user_task_without_system",
            "message": "user Taskなのに利用システムが未設定です。ソフトウェア支援が確認できなければgenericを検討してください: " + ", ".join(user_without_system),
        })

    missing_labels: list[str] = []
    for nid, node in node_map.items():
        if node.get("type") != "gateway_exclusive" or len(outgoing.get(nid, [])) <= 1:
            continue
        for e in outgoing[nid]:
            if not str(e.get("name") or "").strip():
                missing_labels.append(str(e.get("id") or f"{nid}->{e.get('to')}"))
    if missing_labels:
        warnings.append({
            "code": "missing_branch_label",
            "message": "Exclusive Gatewayの分岐Edgeに人向けnameがない経路があります。default経路にも意味が分かるラベルを保持してください: " + ", ".join(missing_labels),
        })

    # If a task is named as though approval is already complete, but the next
    # exclusive gateway still decides approval vs rejection, the task name is
    # semantically premature. Keep this heuristic narrow to avoid flagging
    # approval requests or unrelated approval-related tasks.
    approval_outcome_conflicts: list[str] = []
    negative_terms = ("却下", "否認", "不承認", "非承認", "承認しない")
    positive_terms = ("承認", "可決", "許可")
    for nid, node in node_map.items():
        if node.get("type") != "task":
            continue
        task_name = str(node.get("name") or "").strip()
        # Examples intentionally covered: 「経費申請を承認」「承認」.
        # Examples intentionally excluded: 「承認依頼」「承認結果を通知」.
        looks_final_approval = task_name == "承認" or task_name.endswith("を承認") or task_name.endswith("の承認")
        if not looks_final_approval:
            continue
        outs = outgoing.get(nid, [])
        if len(outs) != 1:
            continue
        gateway_id = str(outs[0].get("to", ""))
        gateway = node_map.get(gateway_id, {})
        if gateway.get("type") != "gateway_exclusive" or len(outgoing.get(gateway_id, [])) < 2:
            continue
        branch_texts = [
            " ".join(str(e.get(k) or "") for k in ("name", "condition"))
            for e in outgoing[gateway_id]
        ]
        combined = " ".join(branch_texts)
        has_negative = any(term in combined for term in negative_terms)
        has_positive = any(term in combined for term in positive_terms)
        gateway_name = str(gateway.get("name") or "")
        if has_negative and (has_positive or "承認" in gateway_name):
            approval_outcome_conflicts.append(f"{nid}->{gateway_id}")
    if approval_outcome_conflicts:
        warnings.append({
            "code": "approval_task_before_outcome_decision",
            "message": "承認済みを示すTask名の直後で承認/却下を判定しています。判断前のTaskは『審査』『確認』などにし、承認/却下はGatewayの結果として表現してください: " + ", ".join(approval_outcome_conflicts),
        })

    # A task description can explicitly state that the task *consumes*
    # operational feedback/error detail as the basis for correction or retry.
    # Only consumer phrasing is flagged; a return task that merely *produces*
    # a rejection reason (e.g. 「却下理由を示して差し戻す」) must not be treated
    # as though that reason were its own input.
    referenced_info_missing: list[str] = []
    for nid, node in node_map.items():
        if node.get("type") != "task":
            continue
        desc = str(node.get("description") or "")
        inputs = normal_list(node.get("inputs"))

        feedback_concepts = ("指摘内容", "差し戻し理由", "却下理由", "修正指示", "指摘された内容")
        consumer_terms = ("基づ", "確認", "参照", "踏まえ", "受けて")
        consumes_feedback = (
            any(concept in desc for concept in feedback_concepts)
            and any(term in desc for term in consumer_terms)
        )
        if consumes_feedback and not any(
            any(term in obj for term in ("指摘", "理由", "修正指示", "フィードバック", "コメント"))
            for obj in inputs
        ):
            referenced_info_missing.append(f"{nid}:差し戻し・修正の根拠情報")
            continue

        consumes_error_detail = (
            "エラー" in desc
            and any(term in desc for term in ("内容を確認", "詳細を確認", "情報を確認", "内容に基づ", "情報に基づ"))
        )
        if consumes_error_detail and not any("エラー" in obj for obj in inputs):
            referenced_info_missing.append(f"{nid}:エラー修正の根拠情報")

    if referenced_info_missing:
        warnings.append({
            "code": "referenced_operational_info_missing",
            "message": "Taskのdescriptionで修正・再処理の根拠情報を参照していますが、対応するinputがありません。差し戻し指摘や入力エラー情報など、実際に参照する情報をI/Oへ保持し、上流outputsまで追跡できるようにしてください: " + ", ".join(referenced_info_missing),
        })

    missing_provenance: list[str] = []
    for nid, node in node_map.items():
        if node.get("type") != "task":
            continue
        for obj in normal_list(node.get("inputs")):
            if not input_has_provenance(nid, obj, node_map, incoming):
                missing_provenance.append(f"{nid}:{obj}")
    if missing_provenance:
        warnings.append({
            "code": "input_provenance_missing",
            "message": "下流Taskのinputに、上流での生成・添付元を確認できないオブジェクトがあります。外部入力ならその前提を確認してください: " + ", ".join(missing_provenance),
        })

    return warnings


def _unknown_schema_keys(obj: Any, allowed: set[str], path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(obj, dict):
        return
    for key in sorted(set(obj) - allowed):
        errors.append({"code": "unknown_schema_key", "message": f"定義外のキーがあります: {path}.{key}"})


def strict_schema_findings(data: dict[str, Any]) -> list[dict[str, str]]:
    """Reject keys that are not defined by the BPM process schema v1.0."""
    errors: list[dict[str, str]] = []
    _unknown_schema_keys(data, {"schema_version", "process", "participants", "nodes", "edges", "metadata"}, "$", errors)

    process = data.get("process")
    if isinstance(process, dict):
        _unknown_schema_keys(process, {"id", "name", "description", "owner", "version", "scope"}, "$.process", errors)
        scope = process.get("scope")
        if isinstance(scope, dict):
            _unknown_schema_keys(scope, {"start", "end"}, "$.process.scope", errors)

    for idx, participant in enumerate(data.get("participants") or []):
        if isinstance(participant, dict):
            _unknown_schema_keys(participant, {"id", "name", "type"}, f"$.participants[{idx}]", errors)

    node_allowed = {
        "id", "type", "name", "participant", "task_type", "description", "system",
        "inputs", "outputs", "duration", "frequency", "issues", "automation",
    }
    for idx, node in enumerate(data.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        _unknown_schema_keys(node, node_allowed, f"$.nodes[{idx}]", errors)
        automation = node.get("automation")
        if isinstance(automation, dict):
            _unknown_schema_keys(automation, {"candidate", "notes"}, f"$.nodes[{idx}].automation", errors)

    for idx, edge in enumerate(data.get("edges") or []):
        if isinstance(edge, dict):
            _unknown_schema_keys(edge, {"id", "from", "to", "name", "condition", "default"}, f"$.edges[{idx}]", errors)

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        _unknown_schema_keys(metadata, {"assumptions", "open_questions", "inferences"}, "$.metadata", errors)

    return errors

def review(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []

    errors.extend(strict_schema_findings(data))

    participants = data.get("participants") if isinstance(data.get("participants"), list) else []
    nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    edges = data.get("edges") if isinstance(data.get("edges"), list) else []

    participant_ids = {str(p.get("id")) for p in participants if isinstance(p, dict) and p.get("id")}
    node_map: dict[str, dict[str, Any]] = {}
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        nid = str(n["id"])
        if nid in node_map:
            errors.append({"code": "duplicate_node", "message": f"ノードIDが重複しています: {nid}"})
        node_map[nid] = n

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edge_ids: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id", ""))
        if eid:
            if eid in edge_ids:
                errors.append({"code": "duplicate_edge", "message": f"エッジIDが重複しています: {eid}"})
            edge_ids.add(eid)
        src, dst = e.get("from"), e.get("to")
        if src not in node_map:
            errors.append({"code": "missing_source", "message": f"存在しない遷移元です: {src}"})
        if dst not in node_map:
            errors.append({"code": "missing_target", "message": f"存在しない遷移先です: {dst}"})
        if src in node_map and dst in node_map:
            outgoing[str(src)].append(e)
            incoming[str(dst)].append(e)
        if e.get("default") is True and e.get("condition") not in (None, ""):
            errors.append({"code": "default_has_condition", "message": f"default経路 {eid or '(IDなし)'} に condition を設定しないでください。"})

    starts = [nid for nid, n in node_map.items() if n.get("type") == "start"]
    ends = [nid for nid, n in node_map.items() if n.get("type") == "end"]
    if not starts:
        errors.append({"code": "no_start", "message": "start ノードがありません。"})
    if not ends:
        errors.append({"code": "no_end", "message": "end ノードがありません。"})

    for nid, node in node_map.items():
        p = node.get("participant")
        if p and p not in participant_ids:
            errors.append({"code": "unknown_participant", "message": f"{nid} が存在しない participant を参照しています: {p}"})
        ntype = node.get("type")
        ins, outs = incoming[nid], outgoing[nid]
        if ntype == "start" and ins:
            warnings.append({"code": "start_has_incoming", "message": f"start ノード {nid} に流入があります。"})
        if ntype == "end" and outs:
            warnings.append({"code": "end_has_outgoing", "message": f"end ノード {nid} に流出があります。"})
        if ntype == "gateway_exclusive":
            if len(outs) > 1:
                defaults = [e for e in outs if e.get("default") is True]
                if len(defaults) > 1:
                    errors.append({"code": "multiple_default", "message": f"排他ゲートウェイ {nid} に default 経路が複数あります。"})
                # User-facing branch labels are checked in quality_warnings, including default routes.
            elif len(outs) < 1:
                warnings.append({"code": "exclusive_no_outgoing", "message": f"排他ゲートウェイ {nid} に流出がありません。"})
            if len(ins) > 1 and len(outs) > 1:
                errors.append({"code": "exclusive_mixed_join_split", "message": f"排他ゲートウェイ {nid} が結合と分岐を兼務しています。v1.0では別々のゲートウェイに分けてください。"})
        if ntype == "gateway_parallel":
            if any(e.get("condition") not in (None, "") or e.get("default") is True for e in outs):
                errors.append({"code": "parallel_conditional_flow", "message": f"並行ゲートウェイ {nid} の流出に condition/default は設定できません。"})
            if len(ins) == 1 and len(outs) == 1:
                warnings.append({"code": "parallel_no_effect", "message": f"並行ゲートウェイ {nid} は流入・流出とも1本で、分岐/結合として機能していません。"})
            if len(ins) > 1 and len(outs) > 1:
                errors.append({"code": "parallel_mixed_join_split", "message": f"並行ゲートウェイ {nid} が結合と分岐を兼務しています。v1.0ではJoinとSplitを分けてください。"})

    # A default edge is only meaningful from an exclusive gateway.
    for nid, outs in outgoing.items():
        if any(e.get("default") is True for e in outs) and node_map.get(nid, {}).get("type") != "gateway_exclusive":
            errors.append({"code": "default_from_non_exclusive", "message": f"{nid} からのdefault経路は排他ゲートウェイ以外では使用できません。"})

    # Detect mutually-exclusive branches that would deadlock at a parallel join.
    parallel_joins = [nid for nid, n in node_map.items() if n.get("type") == "gateway_parallel" and len(incoming[nid]) > 1]
    xor_splits = [nid for nid, n in node_map.items() if n.get("type") == "gateway_exclusive" and len(outgoing[nid]) > 1]
    for pg in parallel_joins:
        for xor in xor_splits:
            if xor_branch_reaches_parallel_join(xor, pg, outgoing, incoming, node_map) >= 2:
                errors.append({
                    "code": "exclusive_branches_to_parallel_join",
                    "message": f"排他ゲートウェイ {xor} の相互排他的な複数経路が並行ゲートウェイ {pg} に合流します。排他結合ゲートウェイを先に挿入してください。",
                })
                break

    # Reachability from any start.
    reachable: set[str] = set(starts)
    q = deque(starts)
    while q:
        cur = q.popleft()
        for e in outgoing[cur]:
            nxt = str(e["to"])
            if nxt not in reachable:
                reachable.add(nxt)
                q.append(nxt)
    unreachable = [nid for nid in node_map if starts and nid not in reachable]
    for nid in unreachable:
        warnings.append({"code": "unreachable", "message": f"開始点から到達できないノードがあります: {nid}"})

    # Can reach an end (existence of at least one path; this does not prove termination of every execution path).
    can_reach_end: set[str] = set(ends)
    q = deque(ends)
    while q:
        cur = q.popleft()
        for e in incoming[cur]:
            prev = str(e["from"])
            if prev not in can_reach_end:
                can_reach_end.add(prev)
                q.append(prev)
    no_path_to_end = [nid for nid in node_map if ends and nid not in can_reach_end]
    for nid in no_path_to_end:
        warnings.append({"code": "no_path_to_end", "message": f"終了点へ到達する経路が存在しないノードがあります: {nid}"})

    warnings.extend(quality_warnings(node_map, outgoing, incoming))

    task_count = sum(1 for n in node_map.values() if n.get("type") == "task")
    issue_count = sum(len(n.get("issues") or []) for n in node_map.values() if isinstance(n.get("issues"), list))
    automation_count = sum(1 for n in node_map.values() if isinstance(n.get("automation"), dict) and n["automation"].get("candidate") is True)
    observations.extend([
        {"code": "node_count", "message": f"ノード数: {len(node_map)}"},
        {"code": "task_count", "message": f"タスク数: {task_count}"},
        {"code": "participant_count", "message": f"参加者/レーン数: {len(participants)}"},
        {"code": "issue_count", "message": f"記録済み課題数: {issue_count}"},
        {"code": "automation_count", "message": f"自動化候補として明示されたタスク数: {automation_count}"},
    ])
    if starts and not unreachable:
        observations.append({"code": "all_nodes_reachable", "message": "すべてのノードが少なくとも1つの開始点から到達可能です。"})
    if ends and not no_path_to_end:
        observations.append({"code": "all_nodes_have_path_to_end", "message": "すべてのノードから少なくとも1つの終了点へ到達する経路が存在します。"})

    return {
        "ok": not errors,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "nodes": len(node_map),
            "edges": len(edges),
        },
        "errors": errors,
        "warnings": warnings,
        "observations": observations,
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = ["# Business Process Review", ""]
    s = result["summary"]
    lines += [f"- 結果: {'OK' if result['ok'] else 'ERROR'}", f"- Errors: {s['errors']}", f"- Warnings: {s['warnings']}", f"- Nodes: {s['nodes']}", f"- Edges: {s['edges']}", ""]
    if result["errors"]:
        lines += ["## Errors", ""] + [f"- `{x['code']}`: {x['message']}" for x in result["errors"]] + [""]
    if result["warnings"]:
        lines += ["## Warnings", ""] + [f"- `{x['code']}`: {x['message']}" for x in result["warnings"]] + [""]
    lines += ["## Observations", ""] + [f"- {x['message']}" for x in result["observations"]] + [""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review canonical business process YAML.")
    parser.add_argument("--input", default="/mnt/data/process.yaml")
    parser.add_argument("--json-output", default="/mnt/data/process-review.json")
    parser.add_argument("--md-output", default="/mnt/data/process-review.md")
    args = parser.parse_args()

    try:
        data = load_model(Path(args.input))
        result = review(data)
        Path(args.json_output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(args.md_output).write_text(markdown_report(result), encoding="utf-8")
        print(json.dumps({"ok": result["ok"], "json_output": args.json_output, "md_output": args.md_output, "summary": result["summary"]}, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
