#!/usr/bin/env python3
import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"PyYAML import failed: {exc}"}, ensure_ascii=False))
    raise SystemExit(2)

ALLOWED_NODE_TYPES = {"start", "end", "task", "gateway_exclusive", "gateway_parallel"}
ALLOWED_TASK_TYPES = {"generic", "user", "manual", "service", "business_rule", "send", "receive", "script"}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]):
    node_map = {str(n["id"]): n for n in nodes if isinstance(n, dict) and n.get("id")}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        if not isinstance(e, dict):
            continue
        src, dst = str(e.get("from", "")), str(e.get("to", ""))
        if src in node_map and dst in node_map:
            outgoing[src].append(e)
            incoming[dst].append(e)
    return node_map, outgoing, incoming


def _xor_branch_reaches_parallel_join(
    xor_id: str,
    target_parallel_id: str,
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
    node_map: dict[str, dict[str, Any]],
) -> int:
    """Count XOR outgoing branches that can reach target parallel gateway before a proper merge/split boundary."""
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
            # A converging XOR is the explicit merge boundary we require before later parallelization.
            if ntype == "gateway_exclusive" and cur != xor_id and len(incoming[cur]) > 1:
                continue
            # A parallel split legitimately creates multiple tokens; do not trace through it for this check.
            if ntype == "gateway_parallel" and len(outgoing[cur]) > 1:
                continue
            for e in outgoing[cur]:
                nxt = str(e.get("to", ""))
                if nxt not in seen:
                    q.append(nxt)
        if reached:
            count += 1
    return count



def _normal_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _input_has_provenance(
    node_id: str,
    object_name: str,
    node_map: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
) -> bool:
    """Return True when an input is produced upstream or is a plausible process-entry input.

    This deliberately treats inputs to the first business activity (possibly through control nodes)
    as external inputs. It does not require unrelated intermediate tasks to repeat pass-through I/O.
    """
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
                if object_name in _normal_list(node.get("outputs")):
                    return True
                q.append((prev, True))
            elif ntype == "start":
                # No upstream business activity: treat as a process-entry/external input.
                if not passed_task:
                    return True
            else:
                q.append((prev, passed_task))
    return False


def _quality_warnings(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> list[str]:
    warnings: list[str] = []

    missing_task_participant = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and not n.get("participant")
    ]
    if missing_task_participant:
        warnings.append(
            "missing_task_participant: participant is missing on task nodes: " + ", ".join(missing_task_participant)
        )

    missing_control_participant = [
        nid for nid, n in node_map.items()
        if n.get("type") in {"start", "end", "gateway_exclusive", "gateway_parallel"} and not n.get("participant")
    ]
    if missing_control_participant:
        warnings.append(
            "missing_control_participant: assign participant when the responsible lane is clear: "
            + ", ".join(missing_control_participant)
        )

    missing_descriptions = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and not str(n.get("description") or "").strip()
    ]
    if missing_descriptions:
        warnings.append(
            "missing_task_description: add concise descriptions when the activity is understandable from context: "
            + ", ".join(missing_descriptions)
        )

    user_without_system = [
        nid for nid, n in node_map.items()
        if n.get("type") == "task" and n.get("task_type") == "user" and not str(n.get("system") or "").strip()
    ]
    if user_without_system:
        warnings.append(
            "user_task_without_system: confirm software assistance/system or use generic task_type: "
            + ", ".join(user_without_system)
        )

    missing_branch_labels: list[str] = []
    for nid, node in node_map.items():
        if node.get("type") != "gateway_exclusive" or len(outgoing.get(nid, [])) <= 1:
            continue
        for e in outgoing[nid]:
            if not str(e.get("name") or "").strip():
                missing_branch_labels.append(str(e.get("id") or f"{nid}->{e.get('to')}"))
    if missing_branch_labels:
        warnings.append(
            "missing_branch_label: every exclusive split route, including default, should have a user-facing name: "
            + ", ".join(missing_branch_labels)
        )

    provenance_missing: list[str] = []
    for nid, node in node_map.items():
        if node.get("type") != "task":
            continue
        for obj in _normal_list(node.get("inputs")):
            if not _input_has_provenance(nid, obj, node_map, incoming):
                provenance_missing.append(f"{nid}:{obj}")
    if provenance_missing:
        warnings.append(
            "input_provenance_missing: downstream inputs should be produced/attached upstream or be explicit external inputs: "
            + ", ".join(provenance_missing)
        )

    return warnings


def _unknown_schema_keys(obj: Any, allowed: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        return
    for key in sorted(set(obj) - allowed):
        errors.append(f"unknown_schema_key at {path}: {key}")


def _strict_schema_errors(data: dict[str, Any]) -> list[str]:
    """Reject keys that are not defined by the BPM process schema v1.0."""
    errors: list[str] = []
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

def validate_model(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_strict_schema_errors(data))

    if str(data.get("schema_version", "")) != "1.0":
        errors.append("schema_version must be '1.0'")

    process = data.get("process")
    if not isinstance(process, dict):
        errors.append("process must be a mapping")
        process = {}
    for field in ("id", "name"):
        if not process.get(field):
            errors.append(f"process.{field} is required")

    participants = data.get("participants")
    if not isinstance(participants, list):
        errors.append("participants must be a list")
        participants = []
    participant_ids: set[str] = set()
    normalized_participants: list[dict[str, Any]] = []
    for idx, participant in enumerate(participants):
        if not isinstance(participant, dict):
            errors.append(f"participants[{idx}] must be a mapping")
            continue
        normalized_participants.append(participant)
        pid = str(participant.get("id", "")).strip()
        if not pid:
            errors.append(f"participants[{idx}].id is required")
        elif pid in participant_ids:
            errors.append(f"duplicate participant id: {pid}")
        participant_ids.add(pid)
        if not participant.get("name"):
            errors.append(f"participants[{idx}].name is required")

    nodes_raw = data.get("nodes")
    if not isinstance(nodes_raw, list):
        errors.append("nodes must be a list")
        nodes_raw = []
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    start_count = 0
    end_count = 0
    for idx, node in enumerate(nodes_raw):
        if not isinstance(node, dict):
            errors.append(f"nodes[{idx}] must be a mapping")
            continue
        nodes.append(node)
        nid = str(node.get("id", "")).strip()
        ntype = str(node.get("type", "")).strip()
        if not nid:
            errors.append(f"nodes[{idx}].id is required")
        elif nid in node_ids:
            errors.append(f"duplicate node id: {nid}")
        node_ids.add(nid)
        if not node.get("name"):
            errors.append(f"nodes[{idx}].name is required")
        if ntype not in ALLOWED_NODE_TYPES:
            errors.append(f"node {nid or idx}: unsupported type '{ntype}'")
        if ntype == "start":
            start_count += 1
        elif ntype == "end":
            end_count += 1
        elif ntype == "task":
            task_type = node.get("task_type", "generic")
            if task_type not in ALLOWED_TASK_TYPES:
                errors.append(f"node {nid}: unsupported task_type '{task_type}'")
        participant = node.get("participant")
        if participant and participant not in participant_ids:
            errors.append(f"node {nid}: unknown participant '{participant}'")

    if start_count == 0:
        errors.append("at least one start node is required")
    if end_count == 0:
        errors.append("at least one end node is required")
    if start_count > 1:
        warnings.append("multiple start nodes are present; supported but verify intended semantics")
    if end_count > 1:
        warnings.append("multiple end nodes are present; supported but verify intended semantics")

    edges_raw = data.get("edges")
    if not isinstance(edges_raw, list):
        errors.append("edges must be a list")
        edges_raw = []
    edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()
    for idx, edge in enumerate(edges_raw):
        if not isinstance(edge, dict):
            errors.append(f"edges[{idx}] must be a mapping")
            continue
        edges.append(edge)
        eid = str(edge.get("id", "")).strip()
        if not eid:
            errors.append(f"edges[{idx}].id is required")
        elif eid in edge_ids:
            errors.append(f"duplicate edge id: {eid}")
        edge_ids.add(eid)
        source = edge.get("from")
        target = edge.get("to")
        if not source or source not in node_ids:
            errors.append(f"edge {eid or idx}: unknown from node '{source}'")
        if not target or target not in node_ids:
            errors.append(f"edge {eid or idx}: unknown to node '{target}'")
        if edge.get("default") is True and edge.get("condition") not in (None, ""):
            errors.append(f"edge {eid or idx}: default route must not also define condition")

    node_map, outgoing, incoming = _graph(nodes, edges)

    for nid, node in node_map.items():
        ntype = node.get("type")
        outs, ins = outgoing[nid], incoming[nid]
        defaults = [e for e in outs if e.get("default") is True]
        if defaults and ntype != "gateway_exclusive":
            errors.append(f"node {nid}: default route is only supported from gateway_exclusive")
        if ntype == "gateway_exclusive":
            if len(outs) > 1 and len(defaults) > 1:
                errors.append(f"node {nid}: multiple default routes are not allowed")
            if len(ins) > 1 and len(outs) > 1:
                errors.append(f"node {nid}: mixed exclusive join+split is not supported in schema v1.0; use separate merge and split gateways")
        if ntype == "gateway_parallel":
            if any(e.get("condition") not in (None, "") or e.get("default") is True for e in outs):
                errors.append(f"node {nid}: parallel gateway outgoing routes must not use condition/default")
            if len(ins) > 1 and len(outs) > 1:
                errors.append(f"node {nid}: mixed parallel join+split is not supported in schema v1.0; use separate join and split gateways")

    # Prevent mutually-exclusive alternatives from joining directly at a Parallel Gateway.
    parallel_joins = [nid for nid, n in node_map.items() if n.get("type") == "gateway_parallel" and len(incoming[nid]) > 1]
    xor_splits = [nid for nid, n in node_map.items() if n.get("type") == "gateway_exclusive" and len(outgoing[nid]) > 1]
    for pg in parallel_joins:
        for xor in xor_splits:
            if _xor_branch_reaches_parallel_join(xor, pg, outgoing, incoming, node_map) >= 2:
                errors.append(
                    f"node {pg}: mutually exclusive branches from {xor} converge at a parallel gateway; insert an exclusive merge before the parallel gateway"
                )
                break

    warnings.extend(_quality_warnings(nodes, edges, node_map, outgoing, incoming))

    metadata = data.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("metadata must be a mapping when provided")
    elif isinstance(metadata, dict):
        for field in ("assumptions", "open_questions", "inferences"):
            if field in metadata and not isinstance(metadata.get(field), list):
                errors.append(f"metadata.{field} must be a list when provided")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def canonicalize(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("schema_version", "1.0")
    data.setdefault("participants", [])
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    data.setdefault("metadata", {})
    if isinstance(data["metadata"], dict):
        data["metadata"].setdefault("assumptions", [])
        data["metadata"].setdefault("open_questions", [])
        data["metadata"].setdefault("inferences", [])
    for node in data.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "task":
            node.setdefault("task_type", "generic")
    return data


def parse_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.json:
        value = json.loads(args.json)
    elif args.json_file:
        value = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    elif args.stdin_format:
        raw = sys.stdin.read()
        value = json.loads(raw) if args.stdin_format == "json" else yaml.safe_load(raw)
    else:
        raise ValueError("one of --json, --json-file, or --stdin-format is required")
    if not isinstance(value, dict):
        raise ValueError("input root must be an object/mapping")
    return value


def cmd_write(args: argparse.Namespace) -> int:
    try:
        data = canonicalize(parse_input(args))
        report = validate_model(data)
        if not report["ok"]:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        report["output"] = str(output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        data = _load_yaml(Path(args.input))
        report = validate_model(data)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate canonical business process YAML.")
    sub = parser.add_subparsers(dest="command", required=True)

    write = sub.add_parser("write")
    write.add_argument("--json")
    write.add_argument("--json-file")
    write.add_argument("--stdin-format", choices=["json", "yaml"])
    write.add_argument("--output", default="/mnt/data/process.yaml")
    write.set_defaults(func=cmd_write)

    validate = sub.add_parser("validate")
    validate.add_argument("--input", default="/mnt/data/process.yaml")
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
