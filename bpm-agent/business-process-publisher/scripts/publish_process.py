#!/usr/bin/env python3
import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

for prefix, uri in [("bpmn", BPMN), ("bpmndi", BPMNDI), ("dc", DC), ("di", DI), ("xsi", XSI)]:
    ET.register_namespace(prefix, uri)

TASK_TAGS = {
    "generic": "task",
    "user": "userTask",
    "manual": "manualTask",
    "service": "serviceTask",
    "business_rule": "businessRuleTask",
    "send": "sendTask",
    "receive": "receiveTask",
    "script": "scriptTask",
}

# Readable-view layout constants. The HTML intentionally favors legibility over fitting the entire process on one screen.
EVENT_SIZE = 52
GATEWAY_SIZE = 72
TASK_W = 230
TASK_H = 92
X_START = 220
X_STEP = 310
LANE_MIN_H = 190
GROUP_GAP = 28

# HTML jump-connector geometry. These values are intentionally larger than ordinary
# edge labels because jump IDs must remain legible after fit-to-width scaling.
JUMP_BADGE_W = 72.0
JUMP_BADGE_H = 38.0
JUMP_BADGE_RX = 19.0
JUMP_BADGE_FONT = 16
JUMP_NODE_CLEARANCE = 28.0
JUMP_ARROW_CLEARANCE = 24.0

# Layout-only classification. These words identify exception/return branches so the
# renderer can keep the normal flow on the visual main row. They never change the
# business semantics or generated BPMN conditions.
_EXCEPTION_EDGE_RE = re.compile(r"不備|失敗|例外|エラー|期限|タイムアウト|重複|非承認|却下|差し戻し|継続しない|戻")

def _edge_is_exception(edge: dict[str, Any]) -> bool:
    text = f"{edge.get('name') or ''} {edge.get('condition') or ''}"
    return bool(_EXCEPTION_EDGE_RE.search(text))

def _flow_aware_lane_order(
    lane_ids: list[str],
    nodes: list[dict[str, Any]],
    lane_by_node: dict[str, str],
    depth: dict[str, int],
) -> list[str]:
    """Order swimlanes by where they first participate in the forward process.

    Source YAML participant order remains semantic metadata; this ordering is only for
    the derived diagram. It prevents late system lanes from forcing normal-flow edges
    to traverse the full height of the canvas. Ties preserve the source order.
    """
    original = {lane: i for i, lane in enumerate(lane_ids)}
    first_depth: dict[str, int] = {lane: 10**9 for lane in lane_ids}
    median_depth: dict[str, float] = {lane: 10**9 for lane in lane_ids}
    by_lane: dict[str, list[int]] = defaultdict(list)
    for n in nodes:
        nid = str(n.get('id') or '')
        lane = lane_by_node.get(nid)
        if lane in first_depth:
            d = int(depth.get(nid, 10**8))
            by_lane[lane].append(d)
            first_depth[lane] = min(first_depth[lane], d)
    for lane, vals in by_lane.items():
        vals = sorted(vals)
        m = len(vals)//2
        median_depth[lane] = float(vals[m] if len(vals)%2 else (vals[m-1]+vals[m])/2)
    return sorted(lane_ids, key=lambda lane: (first_depth[lane], median_depth[lane], original[lane]))


def safe_id(value: Any, prefix: str = "id") -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    if not text or not re.match(r"[A-Za-z_]", text):
        text = f"{prefix}_{text}"
    return text


def esc_puml(text: Any) -> str:
    return str(text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def load_model(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    for key in ("process", "participants", "nodes", "edges"):
        if key not in data:
            raise ValueError(f"required root field missing: {key}")
    return data


def graph_data(data: dict[str, Any]):
    nodes = [n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in data.get("edges", []) if isinstance(e, dict) and e.get("from") and e.get("to")]
    node_map = {str(n["id"]): n for n in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        if str(e["from"]) in node_map and str(e["to"]) in node_map:
            outgoing[str(e["from"])].append(e)
            incoming[str(e["to"])].append(e)
    return nodes, edges, node_map, outgoing, incoming


def xor_branch_reaches_parallel_join(
    xor_id: str,
    target_parallel_id: str,
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
    node_map: dict[str, dict[str, Any]],
) -> int:
    count = 0
    for branch in outgoing[xor_id]:
        q = deque([str(branch.get("to", ""))])
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


def preflight(data: dict[str, Any]) -> list[str]:
    """Defensive checks in case Publisher is invoked without Reviewer."""
    nodes, edges, node_map, outgoing, incoming = graph_data(data)
    errors: list[str] = []
    for e in edges:
        eid = str(e.get("id") or "(IDなし)")
        if e.get("default") is True and e.get("condition") not in (None, ""):
            errors.append(f"{eid}: default route must not also define condition")
    for nid, node in node_map.items():
        ins, outs = incoming[nid], outgoing[nid]
        ntype = node.get("type")
        if any(e.get("default") is True for e in outs) and ntype != "gateway_exclusive":
            errors.append(f"{nid}: default route is only supported from gateway_exclusive")
        if ntype == "gateway_exclusive" and len(ins) > 1 and len(outs) > 1:
            errors.append(f"{nid}: mixed exclusive join+split is not supported; use separate merge and split gateways")
        if ntype == "gateway_parallel":
            if any(e.get("condition") not in (None, "") or e.get("default") is True for e in outs):
                errors.append(f"{nid}: parallel gateway outgoing routes must not use condition/default")
            if len(ins) > 1 and len(outs) > 1:
                errors.append(f"{nid}: mixed parallel join+split is not supported; use separate join and split gateways")
    parallel_joins = [nid for nid, n in node_map.items() if n.get("type") == "gateway_parallel" and len(incoming[nid]) > 1]
    xor_splits = [nid for nid, n in node_map.items() if n.get("type") == "gateway_exclusive" and len(outgoing[nid]) > 1]
    for pg in parallel_joins:
        for xor in xor_splits:
            if xor_branch_reaches_parallel_join(xor, pg, outgoing, incoming, node_map) >= 2:
                errors.append(f"{pg}: mutually exclusive branches from {xor} converge at a parallel gateway; insert an exclusive merge first")
                break
    return errors


def node_size(node: dict[str, Any]) -> tuple[int, int]:
    ntype = str(node.get("type", ""))
    if ntype in ("start", "end"):
        return EVENT_SIZE, EVENT_SIZE
    if ntype.startswith("gateway_"):
        return GATEWAY_SIZE, GATEWAY_SIZE
    return TASK_W, TASK_H


def visual_height(node: dict[str, Any]) -> int:
    _, h = node_size(node)
    ntype=str(node.get("type", ""))
    if ntype.startswith("gateway_"):
        return h + 62
    if ntype in {"start","end"}:
        return h + 34  # event name is rendered outside the circle
    return h




def _resolved_neighbor_lanes(
    edge_list: list[dict[str, Any]],
    endpoint_key: str,
    resolved: dict[str, str | None],
) -> list[str]:
    values: list[str] = []
    for edge in edge_list:
        nid = str(edge.get(endpoint_key, ""))
        lane = resolved.get(nid)
        if lane and lane not in values:
            values.append(lane)
    return values


def _first_reachable_lane(
    start_id: str,
    direction: str,
    resolved: dict[str, str | None],
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> str | None:
    """Find the nearest already-resolved lane in a deterministic graph walk."""
    q = deque([start_id])
    seen: set[str] = {start_id}
    while q:
        cur = q.popleft()
        edges = outgoing.get(cur, []) if direction == "downstream" else incoming.get(cur, [])
        key = "to" if direction == "downstream" else "from"
        next_ids = [str(e.get(key, "")) for e in edges]
        for nxt in next_ids:
            if nxt in seen:
                continue
            lane = resolved.get(nxt)
            if lane:
                return lane
        for nxt in next_ids:
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return None


def resolve_display_lanes(
    nodes: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
    lane_names: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Resolve a display lane without changing the YAML model.

    Explicit participants always win. Missing participants are inferred only for control-flow nodes
    (start/end/gateways). Tasks remain unassigned when their actor is unknown.
    """
    control_types = {"start", "end", "gateway_exclusive", "gateway_parallel"}
    resolved: dict[str, str | None] = {}
    for node in nodes:
        nid = str(node["id"])
        participant = str(node.get("participant") or "")
        resolved[nid] = participant if participant in lane_names else None

    # First pass: only unique adjacent-lane evidence.
    for _ in range(max(2, len(nodes))):
        changed = False
        for node in nodes:
            nid = str(node["id"])
            if resolved.get(nid) or node.get("type") not in control_types:
                continue
            ins = incoming.get(nid, [])
            outs = outgoing.get(nid, [])
            pred_lanes = _resolved_neighbor_lanes(ins, "from", resolved)
            succ_lanes = _resolved_neighbor_lanes(outs, "to", resolved)
            ntype = str(node.get("type"))
            chosen: str | None = None
            if ntype == "start" and len(succ_lanes) == 1:
                chosen = succ_lanes[0]
            elif ntype == "end" and len(pred_lanes) == 1:
                chosen = pred_lanes[0]
            elif ntype.startswith("gateway_"):
                if len(outs) > 1 and len(ins) <= 1 and len(pred_lanes) == 1:
                    # A split belongs with the activity/actor making the decision.
                    chosen = pred_lanes[0]
                elif len(ins) > 1 and len(outs) <= 1 and len(succ_lanes) == 1:
                    # A join belongs with the next stable control point when that is clear.
                    chosen = succ_lanes[0]
                elif len(pred_lanes) == 1:
                    chosen = pred_lanes[0]
                elif len(succ_lanes) == 1:
                    chosen = succ_lanes[0]
            if chosen:
                resolved[nid] = chosen
                changed = True
        if not changed:
            break

    # Defensive fallback for still-unresolved control nodes. Prefer downstream for joins/start,
    # upstream for splits/end. This is display-only and keeps diagrams readable.
    for node in nodes:
        nid = str(node["id"])
        if resolved.get(nid) or node.get("type") not in control_types:
            continue
        ins = incoming.get(nid, [])
        outs = outgoing.get(nid, [])
        ntype = str(node.get("type"))
        if ntype == "start":
            chosen = _first_reachable_lane(nid, "downstream", resolved, outgoing, incoming)
        elif ntype == "end":
            chosen = _first_reachable_lane(nid, "upstream", resolved, outgoing, incoming)
        elif len(outs) > 1 and len(ins) <= 1:
            chosen = _first_reachable_lane(nid, "upstream", resolved, outgoing, incoming)
            if not chosen:
                chosen = _first_reachable_lane(nid, "downstream", resolved, outgoing, incoming)
        else:
            chosen = _first_reachable_lane(nid, "downstream", resolved, outgoing, incoming)
            if not chosen:
                chosen = _first_reachable_lane(nid, "upstream", resolved, outgoing, incoming)
        if chosen:
            resolved[nid] = chosen

    lane_by_node: dict[str, str] = {}
    inferences: list[dict[str, str]] = []
    for node in nodes:
        nid = str(node["id"])
        explicit = str(node.get("participant") or "")
        lane = resolved.get(nid) or "__unassigned__"
        lane_by_node[nid] = lane
        if explicit not in lane_names and lane != "__unassigned__":
            inferences.append({"node": nid, "lane": lane, "reason": "publication-time lane inference from adjacent process flow"})
    return lane_by_node, inferences

def compute_layout(data: dict[str, Any]) -> dict[str, Any]:
    participants = [p for p in data.get("participants", []) if isinstance(p, dict) and p.get("id")]
    nodes, _, node_map, outgoing, incoming = graph_data(data)

    lane_ids = [str(p["id"]) for p in participants]
    lane_names = {str(p["id"]): str(p.get("name", p["id"])) for p in participants}
    lane_by_node, lane_inferences = resolve_display_lanes(nodes, node_map, outgoing, incoming, lane_names)
    if any(lane == "__unassigned__" for lane in lane_by_node.values()):
        lane_ids.append("__unassigned__")
        lane_names["__unassigned__"] = "未割当"

    # Start with shortest-path depths. They identify obvious backward loop edges.
    starts = [str(n["id"]) for n in nodes if n.get("type") == "start"]
    shortest: dict[str, int] = {}
    q = deque()
    for s in starts:
        shortest[s] = 0
        q.append(s)
    while q:
        cur = q.popleft()
        for e in outgoing[cur]:
            nxt = str(e["to"])
            if nxt not in shortest:
                shortest[nxt] = shortest[cur] + 1
                q.append(nxt)
    max_known = max(shortest.values(), default=0)
    for nid in node_map:
        if nid not in shortest:
            max_known += 1
            shortest[nid] = max_known

    # Recompute display depth as a longest-path rank after removing obvious backward loop edges.
    # This keeps loop returns routed backward while ensuring converging gateways sit to the right
    # of every forward incoming predecessor (e.g. approval task -> exclusive merge).
    indegree: dict[str, int] = {nid: 0 for nid in node_map}
    forward_out: dict[str, list[str]] = defaultdict(list)
    for e in data.get("edges", []):
        if not isinstance(e, dict):
            continue
        src, dst = str(e.get("from", "")), str(e.get("to", ""))
        if src not in node_map or dst not in node_map:
            continue
        # Strictly lower shortest depth is a loop/back edge. Equal-depth edges remain forward;
        # this is important for joins reached through branches of different lengths.
        if shortest.get(dst, 0) < shortest.get(src, 0):
            continue
        forward_out[src].append(dst)
        indegree[dst] += 1

    topo = deque(sorted([nid for nid, deg in indegree.items() if deg == 0], key=lambda n: shortest.get(n, 0)))
    order: list[str] = []
    while topo:
        cur = topo.popleft()
        order.append(cur)
        for nxt in forward_out[cur]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                topo.append(nxt)

    if len(order) == len(node_map):
        depth = {nid: 0 for nid in node_map}
        for nid in order:
            depth[nid] = max(depth[nid], shortest.get(nid, 0))
            for nxt in forward_out[nid]:
                depth[nxt] = max(depth[nxt], depth[nid] + 1)
    else:
        # Defensive fallback for unusual equal-rank cycles.
        depth = dict(shortest)

    # Reorder only the derived swimlane display. The YAML participant list remains intact.
    # A system/control lane that appears early in the normal flow should not be left at the
    # bottom merely because it was declared last in the source file.
    lane_ids = _flow_aware_lane_order(lane_ids, nodes, lane_by_node, depth)

    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    for n in nodes:
        nid = str(n["id"])
        lane = lane_by_node.get(nid, "__unassigned__")
        groups[(lane, depth[nid])].append(nid)

    lane_heights: dict[str, int] = {}
    for lane in lane_ids:
        max_block = 0
        for (group_lane, _), ids in groups.items():
            if group_lane != lane:
                continue
            heights = [visual_height(node_map[nid]) for nid in ids]
            block = sum(heights) + GROUP_GAP * max(0, len(heights) - 1)
            max_block = max(max_block, block)
        lane_heights[lane] = max(LANE_MIN_H, max_block + 80)

    lane_tops: dict[str, int] = {}
    y_cursor = 60
    for lane in lane_ids:
        lane_tops[lane] = y_cursor
        y_cursor += lane_heights[lane]

    positions: dict[str, dict[str, float]] = {}
    for (lane, d), ids in groups.items():
        lane_top = lane_tops[lane]
        lane_h = lane_heights[lane]
        if len(ids) == 1:
            nid = ids[0]
            node = node_map[nid]
            w, h = node_size(node)
            # Shape centers are aligned to the lane center. This makes same-lane edges horizontal even when node heights differ.
            y = lane_top + (lane_h - h) / 2
            positions[nid] = {"x": X_START + d * X_STEP, "y": y, "w": w, "h": h, "lane": lane, "depth": d}
            continue

        # When a normal-flow node and an exception-handler node share the same
        # lane/depth, keep the normal-flow node on the lane centerline and move the
        # exception node to a secondary sub-row. This is common around result gateways
        # where success continues to a Join while failure goes to a repair task.
        def is_exception_node(nid: str) -> bool:
            ins = incoming.get(nid, [])
            return bool(ins) and all(_edge_is_exception(e) for e in ins)

        main_ids = [nid for nid in ids if not is_exception_node(nid)]
        exception_ids = [nid for nid in ids if is_exception_node(nid)]
        if len(main_ids) == 1 and exception_ids:
            main_id = main_ids[0]
            mw, mh = node_size(node_map[main_id])
            main_y = lane_top + (lane_h - mh) / 2
            positions[main_id] = {"x": X_START + d * X_STEP, "y": main_y, "w": mw, "h": mh, "lane": lane, "depth": d}
            # Prefer the upper sub-row for exception handlers; alternate below if needed.
            upper_cursor = main_y - GROUP_GAP
            lower_cursor = main_y + mh + GROUP_GAP
            for i, nid in enumerate(exception_ids):
                w, h = node_size(node_map[nid])
                vh = visual_height(node_map[nid])
                if i % 2 == 0:
                    y = max(lane_top + 18, upper_cursor - h)
                    upper_cursor = y - GROUP_GAP
                else:
                    y = min(lane_top + lane_h - h - 18, lower_cursor)
                    lower_cursor = y + vh + GROUP_GAP
                positions[nid] = {"x": X_START + d * X_STEP, "y": y, "w": w, "h": h, "lane": lane, "depth": d}
        else:
            heights = [visual_height(node_map[nid]) for nid in ids]
            block_h = sum(heights) + GROUP_GAP * (len(ids) - 1)
            cursor = lane_top + (lane_h - block_h) / 2
            for nid, vh in zip(ids, heights):
                node = node_map[nid]
                w, h = node_size(node)
                positions[nid] = {"x": X_START + d * X_STEP, "y": cursor, "w": w, "h": h, "lane": lane, "depth": d}
                cursor += vh + GROUP_GAP

    # Prefer straight horizontal flow for simple same-lane linear chains.
    # If a target has exactly one incoming edge, its source has exactly one outgoing edge,
    # both nodes are in the same lane, and the target is the only node in its lane/depth group,
    # align the target center Y to the source center Y. This keeps obvious Task -> Gateway
    # or Task -> Task continuations visually straight without disturbing branch stacks.
    group_sizes = {key: len(ids) for key, ids in groups.items()}
    for dst_id in sorted(node_map, key=lambda nid: depth.get(nid, 0)):
        ins = incoming.get(dst_id, [])
        if len(ins) != 1:
            continue
        src_id = str(ins[0].get("from", ""))
        if src_id not in positions or dst_id not in positions:
            continue
        if len(outgoing.get(src_id, [])) != 1:
            continue
        src = positions[src_id]
        dst = positions[dst_id]
        if src.get("lane") != dst.get("lane"):
            continue
        if dst.get("depth", 0) <= src.get("depth", 0):
            continue
        lane = str(dst.get("lane"))
        if group_sizes.get((lane, int(dst.get("depth", 0))), 0) != 1:
            continue
        desired_y = src["y"] + src["h"] / 2 - dst["h"] / 2
        lane_top = lane_tops[lane]
        lane_bottom = lane_top + lane_heights[lane]
        extra_bottom = 30 if str(node_map[dst_id].get("type", "")).startswith("gateway_") else 0
        if desired_y < lane_top + 20 or desired_y + dst["h"] + extra_bottom > lane_bottom - 14:
            continue
        dst["y"] = desired_y

    # Second pass: align readable same-lane chains on one horizontal sub-row.
    # Unlike the initial grouping pass this may align nodes from stacked depth groups, but only
    # when the move does not overlap another node. This keeps exception chains such as
    # Task -> Gateway -> End visually straight while preserving a separate normal-flow row.
    def _would_overlap(nid: str, new_y: float) -> bool:
        p0=positions[nid]
        ax1,ax2=p0['x'],p0['x']+p0['w']; ay1,ay2=new_y,new_y+p0['h']
        for oid,o in positions.items():
            if oid==nid or o.get('lane')!=p0.get('lane'):
                continue
            bx1,bx2=o['x'],o['x']+o['w']; by1,by2=o['y'],o['y']+o['h']
            if max(ax1,bx1) < min(ax2,bx2) and max(ay1,by1) < min(ay2,by2):
                return True
        return False

    # Propagate center alignment across unambiguous same-lane one-to-one edges.
    for _ in range(3):
        changed=False
        for e in data.get('edges',[]):
            if not isinstance(e,dict):
                continue
            src_id,dst_id=str(e.get('from') or ''),str(e.get('to') or '')
            if src_id not in positions or dst_id not in positions:
                continue
            src,dst=positions[src_id],positions[dst_id]
            if src.get('lane')!=dst.get('lane') or dst.get('depth',0)<=src.get('depth',0):
                continue
            if len(outgoing.get(src_id,[]))!=1 or len(incoming.get(dst_id,[]))!=1:
                continue
            desired=src['y']+src['h']/2-dst['h']/2
            if not _would_overlap(dst_id,desired) and abs(dst['y']-desired)>0.5:
                dst['y']=desired; changed=True
        if not changed:
            break

    # End events may converge from multiple branches. Prefer a same-lane predecessor's row
    # when this is collision-free, rather than dropping the event onto another visual row.
    for nid,node in node_map.items():
        if str(node.get('type'))!='end' or nid not in positions:
            continue
        dst=positions[nid]
        candidates=[]
        for e in incoming.get(nid,[]):
            sid=str(e.get('from') or '')
            if sid in positions and positions[sid].get('lane')==dst.get('lane'):
                candidates.append(positions[sid])
        for src in candidates:
            desired=src['y']+src['h']/2-dst['h']/2
            if not _would_overlap(nid,desired):
                dst['y']=desired
                break

    max_depth = max(depth.values(), default=0)
    canvas_width = max(1200, 610 + max_depth * X_STEP)
    canvas_height = max(500, y_cursor + 40)
    lanes = [{"id": lane, "name": lane_names[lane], "y": lane_tops[lane], "h": lane_heights[lane]} for lane in lane_ids]
    return {
        "positions": positions,
        "lanes": lanes,
        "width": canvas_width,
        "height": canvas_height,
        "depth": depth,
        "lane_by_node": lane_by_node,
        "layout_lane_inferences": lane_inferences,
    }


def edge_points(src: dict[str, float], dst: dict[str, float], trunk_x: float | None = None) -> list[tuple[float, float]]:
    """Create a simple orthogonal seed route.

    Final routes are selected by ``build_edge_routes`` from several candidates.  This
    function intentionally stays small and deterministic so it can also be used as the
    least-complex fallback.
    """
    sx = src["x"] + src["w"]
    sy = src["y"] + src["h"] / 2
    tx = dst["x"]
    ty = dst["y"] + dst["h"] / 2

    if tx >= sx + 24:
        if trunk_x is not None:
            bx = max(sx + 24, min(tx - 24, trunk_x))
            if abs(sy - ty) < 0.5:
                return [(sx, sy), (bx, sy), (tx, ty)]
            return [(sx, sy), (bx, sy), (bx, ty), (tx, ty)]
        if abs(sy - ty) < 0.5:
            return [(sx, sy), (tx, ty)]
        mx = (sx + tx) / 2
        return [(sx, sy), (mx, sy), (mx, ty), (tx, ty)]

    # Backward seed route enters from the target's LEFT side, not through its center.
    # Entering a target from below at its center can cut through another node stacked
    # directly above the target (the regression that occurred around the rejected end).
    route_y = max(src["y"] + src["h"], dst["y"] + dst["h"]) + 42
    approach_x = max(30, dst["x"] - 42)
    return [
        (sx, sy),
        (sx + 42, sy),
        (sx + 42, route_y),
        (approach_x, route_y),
        (approach_x, ty),
        (tx, ty),
    ]


def edge_route_key(edge: dict[str, Any], index: int) -> str:
    return str(edge.get("id") or f"flow_{index}")


def _polyline_length(points: list[tuple[float, float]]) -> float:
    return sum(abs(a[0]-b[0]) + abs(a[1]-b[1]) for a,b in zip(points, points[1:]))


def _point_eq(a: tuple[float,float], b: tuple[float,float], eps: float=0.5) -> bool:
    return abs(a[0]-b[0]) <= eps and abs(a[1]-b[1]) <= eps


def _segments_cross(a1: tuple[float,float], a2: tuple[float,float], b1: tuple[float,float], b2: tuple[float,float]) -> bool:
    """Return True for an interior orthogonal crossing (not a shared endpoint)."""
    a_h = abs(a1[1]-a2[1]) < 0.5
    b_h = abs(b1[1]-b2[1]) < 0.5
    if a_h == b_h:
        return False
    if a_h:
        h1,h2,v1,v2=a1,a2,b1,b2
    else:
        h1,h2,v1,v2=b1,b2,a1,a2
    hx1,hx2=sorted((h1[0],h2[0])); vy1,vy2=sorted((v1[1],v2[1]))
    x=v1[0]; y=h1[1]
    if not (hx1+0.5 < x < hx2-0.5 and vy1+0.5 < y < vy2-0.5):
        return False
    p=(x,y)
    endpoints=(a1,a2,b1,b2)
    return not any(_point_eq(p,e) for e in endpoints)


def _route_node_hits(points: list[tuple[float,float]], positions: dict[str,dict[str,float]], src_id: str, dst_id: str) -> int:
    hits=0
    for nid,rect in positions.items():
        if nid in (src_id,dst_id):
            continue
        if any(_segment_hits_rect(a,b,rect) for a,b in zip(points,points[1:])):
            hits += 1
    return hits


def _candidate_routes(
    src: dict[str,float],
    dst: dict[str,float],
    trunk_x: float | None,
    canvas_height: float,
    slot: int,
) -> list[list[tuple[float,float]]]:
    """Generate orthogonal candidates, including dedicated return corridors.

    The important invariant is that a backward route must be able to approach the
    target from the LEFT without traversing the target's x-column.  Multiple return
    corridors are generated so unrelated loops do not all occupy one horizontal line.
    """
    sx,sy=src['x']+src['w'],src['y']+src['h']/2
    tx,ty=dst['x'],dst['y']+dst['h']/2
    out=[edge_points(src,dst,trunk_x)]

    if tx >= sx + 24:
        # Ordinary forward bends. Include candidates that deliberately abandon a
        # shared gateway trunk when that trunk would intersect a third-party node.
        for bx in (sx+36, tx-36, (sx+tx)/2, sx+64, tx-64):
            if sx+20 < bx < tx-20:
                out.append([(sx,sy),(bx,sy),(bx,ty),(tx,ty)])
        # An upper/lower bypass can route around a dense column of nodes.
        gap=42 + slot*24
        upper=max(20.0,min(src['y'],dst['y'])-gap)
        lower=min(canvas_height-20.0,max(src['y']+src['h'],dst['y']+dst['h'])+gap)
        for cy in (upper,lower):
            left=sx+32; right=tx-32
            if left < right:
                out.append([(sx,sy),(left,sy),(left,cy),(right,cy),(right,ty),(tx,ty)])
    else:
        # Backward / loop routes: use several dedicated corridors and approach the
        # target from its left edge. This prevents arrows crossing nodes stacked in
        # the target column (e.g. rejected_end below accounting_exception_review).
        base_gap=42 + slot*28
        upper=max(20.0,min(src['y'],dst['y'])-base_gap)
        lower=min(canvas_height-20.0,max(src['y']+src['h'],dst['y']+dst['h'])+base_gap)
        for i,cy in enumerate((upper,lower,
                               max(20.0,upper-34),
                               min(canvas_height-20.0,lower+34))):
            source_x=sx+42+i*10
            approach_x=max(30.0,tx-42-i*12)
            out.append([(sx,sy),(source_x,sy),(source_x,cy),(approach_x,cy),(approach_x,ty),(tx,ty)])
    # Preserve order but remove duplicates.
    dedup=[]; seen=set()
    for pts in out:
        key=tuple((round(x,2),round(y,2)) for x,y in pts)
        if key not in seen:
            seen.add(key); dedup.append(pts)
    return dedup


def build_edge_routes(data: dict[str, Any], layout: dict[str, Any]) -> dict[str, list[tuple[float, float]]]:
    """Choose collision-aware routes used by BPMN DI and HTML SVG.

    v1.18 keeps the collision-aware router from "seed route + occasional bend fix" to a small
    deterministic cost search.  A route that intersects a third-party node is always
    heavily penalized; crossings with unrelated already-routed edges, bend count and
    total length are secondary costs.  This means a diagram can no longer report a
    known Edge×Node collision while still emitting that same route when a clear
    orthogonal alternative exists.
    """
    _, edges, node_map, outgoing, _ = graph_data(data)
    positions = layout["positions"]
    trunk_by_source: dict[str, float] = {}

    for src_id, outs in outgoing.items():
        node = node_map.get(src_id, {})
        if not str(node.get("type", "")).startswith("gateway_") or len(outs) < 2:
            continue
        src = positions.get(src_id)
        if not src:
            continue
        sx = src["x"] + src["w"]
        forward_targets = []
        for e in outs:
            dst = positions.get(str(e.get("to", "")))
            if dst and dst["x"] >= sx + 24:
                forward_targets.append(dst)
        if len(forward_targets) < 2:
            continue
        nearest_tx = min(dst["x"] for dst in forward_targets)
        if nearest_tx > sx + 48:
            trunk_by_source[src_id] = (sx + nearest_tx) / 2

    # Normal forward edges first; return/exception edges then select among dedicated
    # corridors while seeing the already-established main spine.
    indexed=list(enumerate(edges,1))
    def _priority(item):
        idx,e=item; src=positions[str(e['from'])]; dst=positions[str(e['to'])]
        backward = dst['x'] < src['x'] + src['w'] + 24
        return (1 if backward or _edge_is_exception(e) else 0, idx)
    ordered=sorted(indexed,key=_priority)

    routes: dict[str, list[tuple[float, float]]] = {}
    chosen_meta: list[tuple[dict[str,Any],list[tuple[float,float]]]]=[]
    return_slot=0
    for idx,e in ordered:
        src_id,dst_id=str(e['from']),str(e['to'])
        src,dst=positions[src_id],positions[dst_id]
        backward=dst['x'] < src['x']+src['w']+24
        slot=return_slot if backward or _edge_is_exception(e) else 0
        if backward or _edge_is_exception(e):
            return_slot += 1
        candidates=_candidate_routes(src,dst,trunk_by_source.get(src_id),float(layout.get('height') or 2000),slot)

        def score(pts):
            node_hits=_route_node_hits(pts,positions,src_id,dst_id)
            crossings=0
            for prev_e,prev_pts in chosen_meta:
                shared={src_id,dst_id} & {str(prev_e.get('from')),str(prev_e.get('to'))}
                if shared:
                    continue
                for a,b in zip(pts,pts[1:]):
                    for c,d in zip(prev_pts,prev_pts[1:]):
                        if _segments_cross(a,b,c,d):
                            crossings += 1
            bends=max(0,len(pts)-2)
            return node_hits*100000 + crossings*450 + bends*9 + _polyline_length(pts)/100.0

        best=min(candidates,key=score)
        key=edge_route_key(e,idx)
        routes[key]=best
        chosen_meta.append((e,best))

    # Return mapping in source edge order for deterministic downstream consumers.
    return {edge_route_key(e,idx):routes[edge_route_key(e,idx)] for idx,e in indexed}


def build_html_jump_edges(data: dict[str, Any], layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Select very long backward edges for compact HTML jump connectors.

    YAML/BPMN semantics keep the full Sequence Flow. HTML may replace only visually
    expensive returns with paired Rn connectors; short/local loops remain explicit.
    """
    _, edges, node_map, _, _ = graph_data(data)
    positions = layout["positions"]
    routes = layout.get("edge_routes") or {}
    selected: dict[str, dict[str, Any]] = {}
    jump_no = 1
    for idx, edge in enumerate(edges, 1):
        key = edge_route_key(edge, idx)
        src_id, dst_id = str(edge.get("from") or ""), str(edge.get("to") or "")
        src, dst = positions.get(src_id), positions.get(dst_id)
        pts = routes.get(key) or []
        if not src or not dst or len(pts) < 2:
            continue
        src_right = src["x"] + src["w"]
        backtrack = src_right - dst["x"]
        if backtrack <= 24:
            continue
        route_length = _polyline_length(pts)
        if not (backtrack >= X_STEP * 2 or (backtrack >= X_STEP and route_length >= 1500)):
            continue
        selected[key] = {
            "id": f"R{jump_no}",
            "source_node": src_id,
            "target_node": dst_id,
            "source_name": str(node_map.get(src_id, {}).get("name") or src_id),
            "target_name": str(node_map.get(dst_id, {}).get("name") or dst_id),
            "edge_label": str(edge.get("name") or ""),
            "route_length": round(route_length, 1),
            "backtrack": round(backtrack, 1),
        }
        jump_no += 1
    return selected



def _jump_box(cx: float, cy: float) -> dict[str, float]:
    return {"x": cx - JUMP_BADGE_W / 2, "y": cy - JUMP_BADGE_H / 2, "w": JUMP_BADGE_W, "h": JUMP_BADGE_H}


def _segment_intersects_box(a: tuple[float, float], b: tuple[float, float], box: dict[str, float]) -> bool:
    """Return True when an orthogonal connector segment crosses a rectangle interior."""
    return _segment_hits_rect(a, b, box)


def build_html_jump_geometry(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Place large paired jump badges and collision-aware target arrows.

    The source badge marks where the long return leaves the local flow. The target
    badge sits near the destination, but the actual arrow terminates on the target
    node boundary with enough clearance that the marker cannot cover the Rn badge.
    """
    jumps = layout.get("html_jump_edges") or {}
    positions = layout.get("positions") or {}
    label_boxes = [x.get("box") for x in (layout.get("edge_labels") or {}).values() if x.get("box")]
    canvas_w = float(layout.get("width") or 4000)
    canvas_h = float(layout.get("height") or 2000)
    placed_badges: list[dict[str, float]] = []
    geometry: dict[str, dict[str, Any]] = {}

    def score_candidate(box, stub_a, stub_b, source_id, target_id):
        score = 0
        for nid, rect in positions.items():
            if nid in (source_id, target_id):
                continue
            if _rect_overlap(box, rect, 4):
                score += 100000
            if _segment_intersects_box(stub_a, stub_b, rect):
                score += 100000
        for other in placed_badges:
            if _rect_overlap(box, other, 6):
                score += 80000
            if _segment_intersects_box(stub_a, stub_b, other):
                score += 60000
        for lb in label_boxes:
            if _rect_overlap(box, lb, 4):
                score += 6000
            if _segment_intersects_box(stub_a, stub_b, lb):
                score += 3500
        return score

    for key, jump in jumps.items():
        src_id = str(jump["source_node"])
        dst_id = str(jump["target_node"])
        src = positions.get(src_id)
        dst = positions.get(dst_id)
        if not src or not dst:
            continue

        # Source badge candidates: prefer the right side, then above/below the source.
        scx = src["x"] + src["w"] / 2
        scy = src["y"] + src["h"] / 2
        source_candidates = []
        cx = min(canvas_w - JUMP_BADGE_W / 2 - 8, src["x"] + src["w"] + 34 + JUMP_BADGE_W / 2)
        source_candidates.append((cx, scy, (src["x"] + src["w"], scy), (cx - JUMP_BADGE_W / 2, scy)))
        cy = max(JUMP_BADGE_H / 2 + 8, src["y"] - JUMP_NODE_CLEARANCE - JUMP_BADGE_H / 2)
        source_candidates.append((scx, cy, (scx, src["y"]), (scx, cy + JUMP_BADGE_H / 2)))
        cy2 = min(canvas_h - JUMP_BADGE_H / 2 - 8, src["y"] + src["h"] + JUMP_NODE_CLEARANCE + JUMP_BADGE_H / 2)
        source_candidates.append((scx, cy2, (scx, src["y"] + src["h"]), (scx, cy2 - JUMP_BADGE_H / 2)))
        scored = []
        for cx0, cy0, a, b in source_candidates:
            box = _jump_box(cx0, cy0)
            scored.append((score_candidate(box, a, b, src_id, dst_id), cx0, cy0, a, b, box))
        _, source_cx, source_cy, source_a, source_b, source_box = min(scored, key=lambda x: x[0])
        placed_badges.append(source_box)

        # Target badge candidates: place above/below target corners.  The gap between
        # badge and target edge is deliberately larger than the jump arrowhead.
        x_offsets = (dst["x"] + dst["w"] - JUMP_BADGE_W / 2, dst["x"] + JUMP_BADGE_W / 2)
        target_candidates = []
        above_y = max(JUMP_BADGE_H / 2 + 8, dst["y"] - JUMP_NODE_CLEARANCE - JUMP_BADGE_H / 2)
        below_y = min(canvas_h - JUMP_BADGE_H / 2 - 8, dst["y"] + dst["h"] + JUMP_NODE_CLEARANCE + JUMP_BADGE_H / 2)
        for tx0 in x_offsets:
            tx0 = max(JUMP_BADGE_W / 2 + 8, min(canvas_w - JUMP_BADGE_W / 2 - 8, tx0))
            a = (tx0, above_y + JUMP_BADGE_H / 2)
            b = (tx0, dst["y"])
            box = _jump_box(tx0, above_y)
            target_candidates.append((score_candidate(box, a, b, src_id, dst_id), tx0, above_y, a, b, box, "above"))
            a2 = (tx0, below_y - JUMP_BADGE_H / 2)
            b2 = (tx0, dst["y"] + dst["h"])
            box2 = _jump_box(tx0, below_y)
            target_candidates.append((score_candidate(box2, a2, b2, src_id, dst_id), tx0, below_y, a2, b2, box2, "below"))
        _, target_cx, target_cy, target_a, target_b, target_box, target_side = min(target_candidates, key=lambda x: x[0])
        placed_badges.append(target_box)

        clearance = abs(target_b[1] - target_a[1]) if abs(target_a[0] - target_b[0]) < 0.5 else abs(target_b[0] - target_a[0])
        geometry[key] = {
            "source_center": (source_cx, source_cy),
            "source_box": source_box,
            "source_stub": (source_a, source_b),
            "target_center": (target_cx, target_cy),
            "target_box": target_box,
            "target_stub": (target_a, target_b),
            "target_side": target_side,
            "target_clearance": clearance,
        }
    return geometry



def label_point(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Place a label on a branch-specific segment, preferring the last horizontal leg.

    With shared gateway trunks this intentionally selects the horizontal segment after the trunk,
    so sibling labels never sit on the common split point.
    """
    if len(points) < 2:
        return points[0] if points else (0, 0)
    segments = list(zip(points, points[1:]))
    for a, b in reversed(segments):
        if abs(a[1] - b[1]) < 0.5 and abs(a[0] - b[0]) >= 30:
            return ((a[0] + b[0]) / 2, a[1])
    a, b = segments[-1]
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)



def _label_box(x: float, y: float, text: str) -> dict[str,float]:
    # Japanese glyphs are close to font-size width; use a conservative estimate.
    width=max(44.0, min(360.0, len(str(text))*16.0 + 16.0))
    return {'x':x-width/2,'y':y-20.0,'w':width,'h':26.0}


def _rect_overlap(a: dict[str,float], b: dict[str,float], margin: float=4.0) -> bool:
    return not (a['x']+a['w']+margin <= b['x'] or b['x']+b['w']+margin <= a['x'] or a['y']+a['h']+margin <= b['y'] or b['y']+b['h']+margin <= a['y'])


def build_edge_label_positions(data: dict[str,Any], layout: dict[str,Any], routes: dict[str,list[tuple[float,float]]]) -> dict[str,dict[str,Any]]:
    """Place edge labels on clear route segments and avoid node/label collisions."""
    _,edges,_,_,_=graph_data(data)
    positions=layout['positions']
    occupied=[]
    result={}
    for idx,e in enumerate(edges,1):
        label=e.get('name') or (None if e.get('default') is True else e.get('condition'))
        if not label:
            continue
        key=edge_route_key(e,idx); pts=routes.get(key,[])
        segments=list(zip(pts,pts[1:]))
        candidates=[]
        # Prefer long horizontal segments, especially those close to the destination.
        for a,b in reversed(segments):
            if abs(a[1]-b[1])<0.5 and abs(a[0]-b[0])>=42:
                mid=((a[0]+b[0])/2,a[1])
                candidates.extend([(mid[0],mid[1]-10),(mid[0],mid[1]+28)])
        if not candidates:
            x,y=label_point(pts); candidates=[(x,y-10),(x,y+28)]
        # Additional deterministic offsets avoid two labels sharing the same final leg.
        x0,y0=candidates[0]
        for step in (42,-42,84,-84):
            candidates.append((x0+step,y0))
        chosen=candidates[0]; box=_label_box(chosen[0],chosen[1],str(label))
        for cand in candidates:
            cb=_label_box(cand[0],cand[1],str(label))
            node_hit=any(_rect_overlap(cb,r,2) for r in positions.values())
            label_hit=any(_rect_overlap(cb,r,3) for r in occupied)
            if not node_hit and not label_hit:
                chosen,box=cand,cb; break
        occupied.append(box)
        result[key]={'x':chosen[0],'y':chosen[1],'text':str(label),'box':box}
    return result


def _segment_hits_rect(a: tuple[float, float], b: tuple[float, float], rect: dict[str, float], margin: float = 8) -> bool:
    rx1 = rect["x"] - margin
    ry1 = rect["y"] - margin
    rx2 = rect["x"] + rect["w"] + margin
    ry2 = rect["y"] + rect["h"] + margin
    x1, y1 = a
    x2, y2 = b
    if abs(y1 - y2) < 0.5:  # horizontal
        lo, hi = sorted((x1, x2))
        return ry1 < y1 < ry2 and max(lo, rx1) < min(hi, rx2)
    if abs(x1 - x2) < 0.5:  # vertical
        lo, hi = sorted((y1, y2))
        return rx1 < x1 < rx2 and max(lo, ry1) < min(hi, ry2)
    return False


def layout_warnings(data: dict[str, Any], layout: dict[str, Any], routes: dict[str, list[tuple[float, float]]]) -> list[str]:
    """Detect residual route and label collisions after automatic placement."""
    _, edges, _, _, _ = graph_data(data)
    positions = layout["positions"]
    warnings: list[str] = []
    for idx, e in enumerate(edges, 1):
        key = edge_route_key(e, idx)
        pts = routes.get(key, [])
        src_id, dst_id = str(e["from"]), str(e["to"])
        for nid, rect in positions.items():
            if nid in (src_id, dst_id):
                continue
            if any(_segment_hits_rect(a, b, rect) for a, b in zip(pts, pts[1:])):
                warnings.append(f"{key}: route intersects node {nid}")
                break
    # Readability diagnostics: collision-free diagrams can still be difficult to scan.
    # Flag only unusually complex routes so normal cross-lane edges do not create noise.
    lane_index={str(x.get('id')):i for i,x in enumerate(layout.get('lanes') or [])}
    for idx,e in enumerate(edges,1):
        key=edge_route_key(e,idx); pts=routes.get(key,[])
        bends=max(0,len(pts)-2)
        src=positions.get(str(e.get('from') or '')); dst=positions.get(str(e.get('to') or ''))
        if bends >= 5:
            warnings.append(f"{key}: route has {bends} bends; readability may be reduced")
        if src and dst and not _edge_is_exception(e):
            a=lane_index.get(str(src.get('lane'))); b=lane_index.get(str(dst.get('lane')))
            if a is not None and b is not None and abs(a-b) >= 4:
                warnings.append(f"{key}: normal-flow route crosses {abs(a-b)} swimlane gaps")

    labels=list((layout.get("edge_labels") or {}).items())
    for i,(k,a) in enumerate(labels):
        ab=a.get("box") or {}
        for nid,rect in positions.items():
            if ab and _rect_overlap(ab,rect,1):
                warnings.append(f"{k}: edge label intersects node {nid}")
                break
        for k2,b in labels[i+1:]:
            bb=b.get("box") or {}
            if ab and bb and _rect_overlap(ab,bb,1):
                warnings.append(f"{k}/{k2}: edge labels overlap")

    # Jump-connector diagnostics.  Compact Rn badges are part of the published UI, so
    # validate their geometry independently from the hidden full Sequence Flow.
    jump_geometry = layout.get("html_jump_geometry") or {}
    jump_items = list(jump_geometry.items())
    edge_label_boxes = [x.get("box") for x in (layout.get("edge_labels") or {}).values() if x.get("box")]
    jump_defs = layout.get("html_jump_edges") or {}
    for key, geo in jump_items:
        jump = jump_defs.get(key) or {}
        src_id = str(jump.get("source_node") or "")
        dst_id = str(jump.get("target_node") or "")
        for kind in ("source_box", "target_box"):
            box = geo.get(kind) or {}
            for nid, rect in positions.items():
                if nid in (src_id, dst_id):
                    continue
                if box and _rect_overlap(box, rect, 2):
                    warnings.append(f"{key}: jump badge intersects node {nid}")
                    break
            for lb in edge_label_boxes:
                if box and _rect_overlap(box, lb, 2):
                    warnings.append(f"{key}: jump badge intersects edge label")
                    break
        for stub_name in ("source_stub", "target_stub"):
            stub = geo.get(stub_name)
            if not stub:
                continue
            a, b = stub
            for nid, rect in positions.items():
                if nid in (src_id, dst_id):
                    continue
                if _segment_intersects_box(a, b, rect):
                    warnings.append(f"{key}: jump connector intersects node {nid}")
                    break
        if float(geo.get("target_clearance") or 0) < JUMP_ARROW_CLEARANCE:
            warnings.append(f"{key}: jump target badge is too close to arrowhead")

    for i, (k1, g1) in enumerate(jump_items):
        boxes1 = [g1.get("source_box") or {}, g1.get("target_box") or {}]
        for k2, g2 in jump_items[i+1:]:
            boxes2 = [g2.get("source_box") or {}, g2.get("target_box") or {}]
            if any(a and b and _rect_overlap(a, b, 4) for a in boxes1 for b in boxes2):
                warnings.append(f"{k1}/{k2}: jump badges overlap")
    return warnings


def generate_plantuml(data: dict[str, Any], layout: dict[str, Any]) -> str:
    process = data.get("process", {})
    participants = [p for p in data.get("participants", []) if isinstance(p, dict) and p.get("id")]
    nodes, edges, _, _, _ = graph_data(data)
    by_lane = defaultdict(list)
    participant_names = {str(p["id"]): str(p.get("name", p["id"])) for p in participants}
    lane_by_node = layout.get("lane_by_node", {})
    for n in nodes:
        by_lane[str(lane_by_node.get(str(n["id"]), n.get("participant") or "__unassigned__"))].append(n)
    if "__unassigned__" in by_lane:
        participant_names["__unassigned__"] = "未割当"

    lines = [
        "@startuml",
        f'title {esc_puml(process.get("name", "Business Process"))}',
        "left to right direction",
        "skinparam shadowing false",
        "skinparam RoundCorner 8",
        "skinparam defaultTextAlignment center",
        "skinparam ArrowThickness 1",
        "",
    ]
    lane_order = [str(p["id"]) for p in participants]
    if "__unassigned__" in by_lane:
        lane_order.append("__unassigned__")
    for lane in lane_order:
        lines.append(f'rectangle "{esc_puml(participant_names[lane])}" as lane_{safe_id(lane)} {{')
        for n in by_lane.get(lane, []):
            nid = f'n_{safe_id(n["id"])}'
            label = esc_puml(n.get("name", n["id"]))
            ntype = n.get("type")
            if ntype in ("start", "end"):
                lines.append(f'  circle "{label}" as {nid}')
            elif ntype == "gateway_exclusive":
                lines.append(f'  diamond "{label}" as {nid}')
            elif ntype == "gateway_parallel":
                lines.append(f'  diamond "AND\\n{label}" as {nid}')
            else:
                lines.append(f'  rectangle "{label}" as {nid}')
        lines.append("}")
        lines.append("")
    for e in edges:
        src = f'n_{safe_id(e["from"])}'
        dst = f'n_{safe_id(e["to"])}'
        name = e.get("name")
        condition = None if e.get("default") is True else e.get("condition")
        if name and condition:
            label = f"{name} [{condition}]"
        else:
            label = name or condition
        suffix = f' : {esc_puml(label)}' if label else ""
        lines.append(f"{src} --> {dst}{suffix}")
    lines += ["", "@enduml", ""]
    return "\n".join(lines)


def generate_bpmn(data: dict[str, Any], layout: dict[str, Any]) -> str:
    process_meta = data.get("process", {})
    nodes, edges, _, outgoing, incoming = graph_data(data)
    participants = [p for p in data.get("participants", []) if isinstance(p, dict) and p.get("id")]

    definitions = ET.Element(f"{{{BPMN}}}definitions", {
        "id": f"Definitions_{safe_id(process_meta.get('id', 'process'))}",
        "targetNamespace": "https://example.local/business-process",
        "exporter": "Business Process Publisher Skill",
        "exporterVersion": "1.16.0",
    })
    process_id = f"Process_{safe_id(process_meta.get('id', 'process'))}"
    process = ET.SubElement(definitions, f"{{{BPMN}}}process", {
        "id": process_id,
        "name": str(process_meta.get("name", "Business Process")),
        "isExecutable": "false",
    })

    lane_xml_ids: dict[str, str] = {}
    if participants:
        lane_set = ET.SubElement(process, f"{{{BPMN}}}laneSet", {"id": f"LaneSet_{safe_id(process_meta.get('id', 'process'))}"})
        for p in participants:
            pid = str(p["id"])
            lid = f"Lane_{safe_id(pid)}"
            lane_xml_ids[pid] = lid
            lane = ET.SubElement(lane_set, f"{{{BPMN}}}lane", {"id": lid, "name": str(p.get("name", pid))})
            lane_by_node = layout.get("lane_by_node", {})
            for n in nodes:
                node_lane = str(lane_by_node.get(str(n["id"]), n.get("participant") or ""))
                if node_lane == pid:
                    ref = ET.SubElement(lane, f"{{{BPMN}}}flowNodeRef")
                    ref.text = f"Node_{safe_id(n['id'])}"

    xml_node_ids: dict[str, str] = {}
    xml_elements: dict[str, ET.Element] = {}
    for n in nodes:
        nid = str(n["id"])
        xid = f"Node_{safe_id(nid)}"
        xml_node_ids[nid] = xid
        attrs = {"id": xid, "name": str(n.get("name", nid))}
        ntype = n.get("type")
        if ntype == "start":
            el = ET.SubElement(process, f"{{{BPMN}}}startEvent", attrs)
        elif ntype == "end":
            el = ET.SubElement(process, f"{{{BPMN}}}endEvent", attrs)
        elif ntype == "gateway_exclusive":
            if len(outgoing[nid]) > 1:
                attrs["gatewayDirection"] = "Diverging"
            elif len(incoming[nid]) > 1:
                attrs["gatewayDirection"] = "Converging"
            el = ET.SubElement(process, f"{{{BPMN}}}exclusiveGateway", attrs)
        elif ntype == "gateway_parallel":
            if len(outgoing[nid]) > 1:
                attrs["gatewayDirection"] = "Diverging"
            elif len(incoming[nid]) > 1:
                attrs["gatewayDirection"] = "Converging"
            el = ET.SubElement(process, f"{{{BPMN}}}parallelGateway", attrs)
        else:
            tag = TASK_TAGS.get(str(n.get("task_type", "generic")), "task")
            el = ET.SubElement(process, f"{{{BPMN}}}{tag}", attrs)
            if n.get("description"):
                doc = ET.SubElement(el, f"{{{BPMN}}}documentation")
                doc.text = str(n["description"])
        xml_elements[nid] = el

    flow_ids: dict[str, str] = {}
    for idx, e in enumerate(edges, 1):
        eid = str(e.get("id") or f"flow_{idx}")
        fid = f"Flow_{safe_id(eid)}"
        flow_ids[eid] = fid
        attrs = {"id": fid, "sourceRef": xml_node_ids[str(e["from"])], "targetRef": xml_node_ids[str(e["to"])]}
        if e.get("name"):
            attrs["name"] = str(e["name"])
        flow = ET.SubElement(process, f"{{{BPMN}}}sequenceFlow", attrs)
        # BPMN default Sequence Flow does not carry a conditionExpression.
        if e.get("condition") and e.get("default") is not True:
            cond = ET.SubElement(flow, f"{{{BPMN}}}conditionExpression", {f"{{{XSI}}}type": "bpmn:tFormalExpression"})
            cond.text = str(e["condition"])
        if e.get("default") is True and str(e["from"]) in xml_elements:
            xml_elements[str(e["from"])].set("default", fid)

    diagram = ET.SubElement(definitions, f"{{{BPMNDI}}}BPMNDiagram", {"id": f"BPMNDiagram_{safe_id(process_meta.get('id', 'process'))}"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI}}}BPMNPlane", {"id": f"BPMNPlane_{safe_id(process_meta.get('id', 'process'))}", "bpmnElement": process_id})

    for lane in layout["lanes"]:
        if lane["id"] not in lane_xml_ids:
            continue
        shape = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNShape", {"id": f"Shape_{lane_xml_ids[lane['id']]}", "bpmnElement": lane_xml_ids[lane["id"]], "isHorizontal": "true"})
        ET.SubElement(shape, f"{{{DC}}}Bounds", {"x": "40", "y": str(round(lane["y"], 1)), "width": str(layout["width"] - 80), "height": str(round(lane["h"], 1))})

    for nid, pos in layout["positions"].items():
        shape = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNShape", {"id": f"Shape_{xml_node_ids[nid]}", "bpmnElement": xml_node_ids[nid]})
        ET.SubElement(shape, f"{{{DC}}}Bounds", {"x": str(round(pos["x"], 1)), "y": str(round(pos["y"], 1)), "width": str(pos["w"]), "height": str(pos["h"])})

    for idx, e in enumerate(edges, 1):
        eid = str(e.get("id") or f"flow_{idx}")
        edge_el = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNEdge", {"id": f"Edge_{flow_ids[eid]}", "bpmnElement": flow_ids[eid]})
        pts = layout["edge_routes"][edge_route_key(e, idx)]
        for x, y in pts:
            ET.SubElement(edge_el, f"{{{DI}}}waypoint", {"x": str(round(x, 1)), "y": str(round(y, 1))})

    ET.indent(definitions, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(definitions, encoding="unicode") + "\n"


def split_svg_text(value: Any, max_chars: int = 13) -> list[str]:
    text = str(value or "")
    if len(text) <= max_chars:
        return [text]
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)][:3]


def svg_text(x: float, y: float, label: str, css_class: str = "node-label", max_chars: int = 13) -> str:
    lines = split_svg_text(label, max_chars=max_chars)
    line_height = 22
    start_y = y - (len(lines) - 1) * (line_height / 2)
    tspans = []
    for i, line in enumerate(lines):
        dy = "0" if i == 0 else str(line_height)
        tspans.append(f'<tspan x="{x:.1f}" dy="{dy}">{html.escape(line)}</tspan>')
    return f'<text class="{css_class}" x="{x:.1f}" y="{start_y:.1f}" text-anchor="middle">{"".join(tspans)}</text>'


def generate_svg(data: dict[str, Any], layout: dict[str, Any]) -> str:
    nodes, edges, _, _, _ = graph_data(data)
    w, h = layout["width"], layout["height"]
    parts = [
        f'<svg id="process-svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="業務プロセス図">',
        '<defs><marker id="arrow" markerWidth="11" markerHeight="11" refX="10" refY="3.5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,7 L10,3.5 z" class="arrow-head"/></marker><marker id="jump-arrow" markerWidth="12" markerHeight="12" refX="11" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L0,8 L11,4 z" class="arrow-head"/></marker></defs>',
    ]
    for i, lane in enumerate(layout["lanes"]):
        parts.append(f'<rect class="lane-bg lane-{i % 2}" x="40" y="{lane["y"]}" width="{w - 80}" height="{lane["h"]}" rx="5"/>')
        parts.append(f'<text class="lane-label" x="62" y="{lane["y"] + 34}">{html.escape(lane["name"])}</text>')

    jump_edges = layout.get("html_jump_edges") or {}
    for idx, e in enumerate(edges, 1):
        key = edge_route_key(e, idx)
        pts = layout["edge_routes"][key]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        jump = jump_edges.get(key)
        edge_class = "flow-edge jump-full-route" if jump else "flow-edge"
        parts.append(f'<path class="{edge_class}" d="{d}" marker-end="url(#arrow)"/>')
        label = e.get("name") or (None if e.get("default") is True else e.get("condition"))
        if label:
            lp=(layout.get('edge_labels') or {}).get(key)
            if lp:
                lx,ly=float(lp['x']),float(lp['y'])
            else:
                lx,ly=label_point(pts); ly-=10
            label_class = "edge-label jump-full-route" if jump else "edge-label"
            parts.append(f'<text class="{label_class}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{html.escape(str(label))}</text>')

    for n in nodes:
        nid = str(n["id"])
        p = layout["positions"][nid]
        x, y, nw, nh = p["x"], p["y"], p["w"], p["h"]
        label = str(n.get("name", nid))
        ntype = str(n.get("type"))
        parts.append(f'<g class="process-node" data-node-id="{html.escape(nid)}" tabindex="0" role="button">')
        if ntype == "start":
            cx, cy, r = x + nw / 2, y + nh / 2, nw / 2 - 3
            parts.append(f'<circle class="event-start" cx="{cx}" cy="{cy}" r="{r}"/>')
            parts.append(svg_text(cx, cy + 5, label, "event-label"))
        elif ntype == "end":
            cx, cy, r = x + nw / 2, y + nh / 2, nw / 2 - 3
            parts.append(f'<circle class="event-end" cx="{cx}" cy="{cy}" r="{r}"/>')
            parts.append(f'<circle class="event-end-inner" cx="{cx}" cy="{cy}" r="{r - 6}"/>')
            parts.append(svg_text(cx, y + nh + 22, label, "event-label"))
        elif ntype.startswith("gateway_"):
            cx, cy = x + nw / 2, y + nh / 2
            points = f"{cx},{y} {x + nw},{cy} {cx},{y + nh} {x},{cy}"
            parts.append(f'<polygon class="gateway" points="{points}"/>')
            symbol = "+" if ntype == "gateway_parallel" else "×"
            parts.append(f'<text class="gateway-symbol" x="{cx}" y="{cy + 8}" text-anchor="middle">{symbol}</text>')
            parts.append(svg_text(cx, y + nh + 26, label, "gateway-caption", max_chars=11))
        else:
            parts.append(f'<rect class="task" x="{x}" y="{y}" width="{nw}" height="{nh}" rx="12"/>')
            parts.append(svg_text(x + nw / 2, y + nh / 2 + 6, label))
        parts.append('</g>')

    # HTML-only paired jump connectors for very long returns. Full paths remain in the
    # SVG and can be toggled on; BPMN DI always uses the complete Sequence Flow.
    jump_geometry = layout.get("html_jump_geometry") or {}
    for key, jump in jump_edges.items():
        geo = jump_geometry.get(key)
        if not geo:
            continue
        jid = html.escape(str(jump["id"]))
        source_name = html.escape(str(jump.get("source_name") or ""))
        target_name = html.escape(str(jump.get("target_name") or ""))
        source_box = geo["source_box"]
        source_cx, source_cy = geo["source_center"]
        (sa_x, sa_y), (sb_x, sb_y) = geo["source_stub"]
        target_box = geo["target_box"]
        target_cx, target_cy = geo["target_center"]
        (ta_x, ta_y), (tb_x, tb_y) = geo["target_stub"]

        parts.append(f'<g class="jump-compact jump-source-connector"><title>{jid}: {source_name} → {target_name}</title>')
        parts.append(f'<path class="jump-stub" d="M {sa_x:.1f} {sa_y:.1f} L {sb_x:.1f} {sb_y:.1f}"/>')
        parts.append(f'<rect class="jump-badge jump-source" x="{source_box["x"]:.1f}" y="{source_box["y"]:.1f}" width="{source_box["w"]:.1f}" height="{source_box["h"]:.1f}" rx="{JUMP_BADGE_RX:.1f}"/>')
        parts.append(f'<text class="jump-badge-text" x="{source_cx:.1f}" y="{source_cy + 5:.1f}" text-anchor="middle">{jid}</text></g>')

        parts.append(f'<g class="jump-compact jump-target-connector"><title>{jid}: {source_name} から戻る</title>')
        parts.append(f'<rect class="jump-badge jump-target" x="{target_box["x"]:.1f}" y="{target_box["y"]:.1f}" width="{target_box["w"]:.1f}" height="{target_box["h"]:.1f}" rx="{JUMP_BADGE_RX:.1f}"/>')
        parts.append(f'<text class="jump-badge-text" x="{target_cx:.1f}" y="{target_cy + 5:.1f}" text-anchor="middle">{jid}</text>')
        parts.append(f'<path class="jump-target-stub" d="M {ta_x:.1f} {ta_y:.1f} L {tb_x:.1f} {tb_y:.1f}" marker-end="url(#jump-arrow)"/></g>')

    parts.append('</svg>')
    return "\n".join(parts)


def generate_html(data: dict[str, Any], layout: dict[str, Any]) -> str:
    process = data.get("process", {})
    svg = generate_svg(data, layout)
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    layout_meta = {
        "lane_by_node": layout.get("lane_by_node", {}),
        "lane_inferences": layout.get("layout_lane_inferences", []),
        "jump_edges": layout.get("html_jump_edges", {}),
    }
    layout_json = json.dumps(layout_meta, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(str(process.get("name", "Business Process")))
    description = html.escape(str(process.get("description") or ""))
    w, h = layout["width"], layout["height"]
    jumps = layout.get("html_jump_edges") or {}
    jump_button = '<span class="toolbar-separator" aria-hidden="true"></span><button class="toolbar-button" id="toggle-return-routes" type="button" aria-pressed="false">戻り線を表示</button>' if jumps else ''
    jump_rows = ''.join(
        f'<div><b>{html.escape(str(j["id"]))}</b>: {html.escape(str(j.get("source_name") or ""))} → {html.escape(str(j.get("target_name") or ""))}</div>'
        for j in jumps.values()
    )
    jump_legend = (
        f'<details class="jump-legend"><summary>↩ 長距離の戻り線 {len(jumps)}件をジャンプ表示</summary>'
        f'<p>図の混雑を避けるため、長い戻り線だけ Rn の対応記号で省略しています。YAML/BPMN上の接続は変更していません。「戻り線を表示」で完全な線へ切り替えられます。</p>{jump_rows}</details>'
        if jumps else ''
    )
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light dark; font-family: "Segoe UI", "Yu Gothic UI", sans-serif; font-size: 16px; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: Canvas; color: CanvasText; font-size: 16px; }}
button, input {{ font: inherit; }}
header {{ padding: 22px 28px 16px; border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent); }}
h1 {{ margin: 0 0 8px; font-size: 28px; line-height: 1.25; }}
header p {{ margin: 0; opacity: .78; font-size: 17px; line-height: 1.55; }}
main {{ display: grid; grid-template-columns: minmax(0, 1fr) 420px; height: calc(100vh - 106px); min-height: 680px; }}
main.details-hidden {{ grid-template-columns: minmax(0, 1fr); }}
main.details-hidden aside {{ display: none; }}
.viewer {{ overflow: auto; padding: 0 22px 22px; background: color-mix(in srgb, Canvas 94%, CanvasText 6%); }}
.viewer-toolbar {{ position: sticky; top: 0; left: 0; z-index: 20; display: flex; align-items: center; gap: 8px; width: max-content; min-height: 58px; padding: 10px 12px; margin: 0 0 12px; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-top: 0; border-radius: 0 0 10px 10px; background: color-mix(in srgb, Canvas 94%, transparent); backdrop-filter: blur(8px); box-shadow: 0 2px 8px color-mix(in srgb, CanvasText 10%, transparent); }}
.toolbar-button {{ min-width: 42px; min-height: 38px; padding: 6px 11px; border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); border-radius: 8px; background: color-mix(in srgb, Canvas 92%, CanvasText 8%); color: CanvasText; cursor: pointer; }}
.toolbar-button:hover, .toolbar-button:focus-visible {{ border-color: color-mix(in srgb, CanvasText 48%, transparent); outline: none; }}
.zoom-range {{ width: 190px; min-width: 120px; }}
.zoom-value {{ min-width: 56px; text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; }}
.toolbar-separator {{ width: 1px; height: 30px; background: color-mix(in srgb, CanvasText 18%, transparent); margin: 0 2px; }}
.canvas {{ width: max-content; min-width: 100%; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 12px; overflow: visible; background: Canvas; }}
#process-svg {{ display: block; width: {w}px; height: {h}px; max-width: none; transform-origin: top left; }}
aside {{ border-left: 1px solid color-mix(in srgb, CanvasText 16%, transparent); padding: 24px; overflow: auto; font-size: 16px; line-height: 1.55; }}
aside h2 {{ margin-top: 0; font-size: 22px; line-height: 1.35; }}
.detail-row {{ margin: 0 0 18px; }}
.detail-row dt {{ font-weight: 700; font-size: 14px; opacity: .72; margin-bottom: 5px; }}
.detail-row dd {{ margin: 0; white-space: pre-wrap; font-size: 17px; }}
.lane-bg {{ stroke: color-mix(in srgb, CanvasText 18%, transparent); stroke-width: 1.3; }}
.lane-0 {{ fill: color-mix(in srgb, Canvas 97%, CanvasText 3%); }}
.lane-1 {{ fill: color-mix(in srgb, Canvas 93%, CanvasText 7%); }}
.lane-label {{ font-size: 18px; font-weight: 700; fill: CanvasText; }}
.flow-edge {{ fill: none; stroke: color-mix(in srgb, CanvasText 68%, transparent); stroke-width: 2.1; }}
.arrow-head {{ fill: color-mix(in srgb, CanvasText 68%, transparent); }}
.edge-label {{ font-size: 15px; font-weight: 650; fill: CanvasText; paint-order: stroke; stroke: Canvas; stroke-width: 5px; stroke-linejoin: round; }}
.jump-full-route {{ display: none; }}
#process-svg.show-full-returns .jump-full-route {{ display: block; }}
#process-svg.show-full-returns .jump-compact {{ display: none; }}
 .jump-stub, .jump-target-stub {{ fill: none; stroke: color-mix(in srgb, CanvasText 72%, transparent); stroke-width: 2.4; stroke-dasharray: 7 5; }}
.jump-target-stub {{ stroke-dasharray: none; }}
 .jump-badge {{ fill: Canvas; stroke: color-mix(in srgb, CanvasText 78%, transparent); stroke-width: 2.2; }}
 .jump-target {{ stroke-width: 3; }}
 .jump-badge-text {{ fill: CanvasText; font-size: 16px; font-weight: 800; pointer-events: none; }}
.jump-legend {{ width: min(760px, calc(100vw - 90px)); margin: 0 0 12px; padding: 9px 12px; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 9px; background: color-mix(in srgb, Canvas 96%, CanvasText 4%); font-size: 14px; line-height: 1.5; }}
.jump-legend summary {{ cursor: pointer; font-weight: 700; }}
.jump-legend p {{ margin: 7px 0; opacity: .78; }}
.task {{ fill: color-mix(in srgb, Canvas 86%, #4f7cff 14%); stroke: color-mix(in srgb, CanvasText 56%, transparent); stroke-width: 1.8; }}
.gateway {{ fill: color-mix(in srgb, Canvas 86%, #f5a623 14%); stroke: color-mix(in srgb, CanvasText 62%, transparent); stroke-width: 1.8; }}
.gateway-symbol {{ fill: CanvasText; font-size: 34px; font-weight: 500; }}
.gateway-caption {{ fill: CanvasText; font-size: 14px; font-weight: 650; }}
.event-start, .event-end, .event-end-inner {{ fill: Canvas; stroke: CanvasText; }}
.event-start {{ stroke-width: 2; }}
.event-end {{ stroke-width: 1.8; }}
.event-end-inner {{ fill: none; stroke-width: 1.8; }}
.node-label {{ fill: CanvasText; font-size: 18px; font-weight: 650; pointer-events: none; }}
.event-label {{ fill: CanvasText; font-size: 12px; font-weight: 650; pointer-events: none; }}
.process-node {{ cursor: pointer; outline: none; }}
.process-node:hover .task, .process-node:focus .task {{ stroke-width: 3.5; }}
.process-node:hover .gateway, .process-node:focus .gateway {{ stroke-width: 3.5; }}
.process-node.selected .task, .process-node.selected .gateway {{ stroke: #4f7cff; stroke-width: 3.5; }}
.badge {{ display:inline-block; padding:3px 9px; border-radius:999px; background:color-mix(in srgb, CanvasText 10%, transparent); margin:0 5px 5px 0; font-size:14px; }}
.issue-list {{ margin: 0; padding-left: 1.35em; }}
.issue-list li {{ margin: 0 0 7px; line-height: 1.55; }}
.issue-list li:last-child {{ margin-bottom: 0; }}
.empty {{ opacity:.64; }}
.muted {{ opacity:.7; }}
@media (max-width: 1100px) {{
  main {{ grid-template-columns: 1fr; height:auto; }}
  main:not(.details-hidden) aside {{ border-left:0; border-top:1px solid color-mix(in srgb, CanvasText 16%, transparent); min-height:320px; }}
  .zoom-range {{ width: 130px; }}
}}
</style>
</head>
<body>
<header><h1>{title}</h1><p>{description}</p></header>
<main id="main-layout">
<section class="viewer" id="viewer">
  <div class="viewer-toolbar" id="viewer-toolbar" role="toolbar" aria-label="業務フロー表示設定">
    <button class="toolbar-button" id="zoom-out" type="button" title="10%縮小" aria-label="10%縮小">−</button>
    <input class="zoom-range" id="zoom-range" type="range" min="5" max="200" step="5" value="100" aria-label="表示倍率">
    <button class="toolbar-button" id="zoom-in" type="button" title="10%拡大" aria-label="10%拡大">＋</button>
    <span class="zoom-value" id="zoom-value" aria-live="polite">100%</span>
    <button class="toolbar-button" id="zoom-reset" type="button">100%</button>
    <button class="toolbar-button" id="zoom-fit-width" type="button">幅に合わせる</button>
    <button class="toolbar-button" id="zoom-fit" type="button">全体表示</button>
    <span class="toolbar-separator" aria-hidden="true"></span>
    <button class="toolbar-button" id="toggle-details" type="button" aria-pressed="false">詳細を隠す</button>
    {jump_button}
  </div>
  {jump_legend}
  <div class="canvas">{svg}</div>
</section>
<aside id="details">
<h2>プロセス概要</h2>
<dl>
<div class="detail-row"><dt>プロセスID</dt><dd>{html.escape(str(process.get('id', '')))}</dd></div>
<div class="detail-row"><dt>オーナー</dt><dd>{html.escape(str(process.get('owner') or '未設定'))}</dd></div>
</dl>
<p class="empty">図の処理・判断を選択すると詳細を表示します。</p>
<noscript><p>JavaScriptが無効でも業務フロー図は表示できます。表示倍率、詳細パネル切り替え、詳細表示のみ利用できません。</p></noscript>
</aside>
</main>
<script type="application/json" id="process-data">{data_json}</script>
<script type="application/json" id="layout-data">{layout_json}</script>
<script>
(() => {{
  const data = JSON.parse(document.getElementById('process-data').textContent);
  const layoutData = JSON.parse(document.getElementById('layout-data').textContent);
  const nodes = Object.fromEntries((data.nodes || []).map(n => [String(n.id), n]));
  const participants = Object.fromEntries((data.participants || []).map(p => [String(p.id), p]));
  const inferredNodeIds = new Set((layoutData.lane_inferences || []).map(x => String(x.node)));
  const details = document.getElementById('details');
  const main = document.getElementById('main-layout');
  const viewer = document.getElementById('viewer');
  const toolbar = document.getElementById('viewer-toolbar');
  const svg = document.getElementById('process-svg');
  const toggleReturnRoutes = document.getElementById('toggle-return-routes');
  const zoomRange = document.getElementById('zoom-range');
  const zoomValue = document.getElementById('zoom-value');
  const toggleDetails = document.getElementById('toggle-details');
  const baseWidth = Number(svg.getAttribute('width')) || {w};
  const baseHeight = Number(svg.getAttribute('height')) || {h};
  const MIN_ZOOM = 0.05;
  const MAX_ZOOM = 2.0;
  let zoom = 1;
  let fitMode = 'none';

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
  const list = v => Array.isArray(v) && v.length ? v.map(x => `<span class="badge">${{esc(x)}}</span>`).join('') : '<span class="empty">未設定</span>';
  const issueList = v => Array.isArray(v) && v.length ? `<ul class="issue-list">${{v.map(x => `<li>${{esc(x)}}</li>`).join('')}}</ul>` : '<span class="empty">未設定</span>';
  const row = (k, v) => `<div class="detail-row"><dt>${{esc(k)}}</dt><dd>${{v}}</dd></div>`;
  function clampZoom(value) {{ return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value)); }}
  function applyZoom(value, preserveCenter = true) {{
    const next = clampZoom(value);
    const old = zoom;
    const centerX = viewer.scrollLeft + viewer.clientWidth / 2;
    const centerY = viewer.scrollTop + viewer.clientHeight / 2;
    zoom = next;
    svg.style.width = `${{baseWidth * zoom}}px`;
    svg.style.height = `${{baseHeight * zoom}}px`;
    const percent = Math.round(zoom * 100);
    zoomRange.value = String(Math.max(5, Math.min(200, Math.round(percent / 5) * 5)));
    zoomValue.textContent = `${{percent}}%`;
    if (preserveCenter && old > 0) {{
      const ratio = zoom / old;
      requestAnimationFrame(() => {{
        viewer.scrollLeft = Math.max(0, centerX * ratio - viewer.clientWidth / 2);
        viewer.scrollTop = Math.max(0, centerY * ratio - viewer.clientHeight / 2);
      }});
    }}
  }}
  function fitToView() {{
    const availableWidth = Math.max(120, viewer.clientWidth - 46);
    const availableHeight = Math.max(120, viewer.clientHeight - toolbar.offsetHeight - 46);
    const fit = Math.min(1, availableWidth / baseWidth, availableHeight / baseHeight);
    fitMode = 'all';
    applyZoom(fit, false);
    requestAnimationFrame(() => {{ viewer.scrollLeft = 0; viewer.scrollTop = 0; }});
  }}
  function fitToWidth() {{
    const availableWidth = Math.max(120, viewer.clientWidth - 46);
    const fit = Math.min(1, availableWidth / baseWidth);
    fitMode = 'width';
    applyZoom(fit, false);
    requestAnimationFrame(() => {{ viewer.scrollLeft = 0; }});
  }}
  function manualZoom(value) {{ fitMode = 'none'; applyZoom(value); }}

  document.getElementById('zoom-out').addEventListener('click', () => manualZoom(zoom - 0.10));
  document.getElementById('zoom-in').addEventListener('click', () => manualZoom(zoom + 0.10));
  document.getElementById('zoom-reset').addEventListener('click', () => manualZoom(1));
  document.getElementById('zoom-fit-width').addEventListener('click', fitToWidth);
  document.getElementById('zoom-fit').addEventListener('click', fitToView);
  zoomRange.addEventListener('input', () => manualZoom(Number(zoomRange.value) / 100));

  if (toggleReturnRoutes) {{
    toggleReturnRoutes.addEventListener('click', () => {{
      const showing = svg.classList.toggle('show-full-returns');
      toggleReturnRoutes.textContent = showing ? '戻り線を省略' : '戻り線を表示';
      toggleReturnRoutes.setAttribute('aria-pressed', String(showing));
    }});
  }}

  toggleDetails.addEventListener('click', () => {{
    const hidden = main.classList.toggle('details-hidden');
    toggleDetails.textContent = hidden ? '詳細を表示' : '詳細を隠す';
    toggleDetails.setAttribute('aria-pressed', String(hidden));
    if (fitMode === 'all') requestAnimationFrame(fitToView);
    if (fitMode === 'width') requestAnimationFrame(fitToWidth);
  }});
  window.addEventListener('resize', () => {{ if (fitMode === 'all') requestAnimationFrame(fitToView); if (fitMode === 'width') requestAnimationFrame(fitToWidth); }});

  function show(id) {{
    const n = nodes[id]; if (!n) return;
    document.querySelectorAll('.process-node').forEach(x => x.classList.toggle('selected', x.dataset.nodeId === id));
    const explicitP = participants[String(n.participant)]?.name || n.participant || '';
    const layoutLane = layoutData.lane_by_node?.[id];
    const inferredP = layoutLane && participants[String(layoutLane)]?.name;
    const p = explicitP || (inferredP ? `${{inferredP}}${{inferredNodeIds.has(String(id)) ? '（表示上推定）' : ''}}` : '未割当');
    const auto = n.automation || {{}};
    details.innerHTML = `<h2>${{esc(n.name || id)}}</h2><dl>` +
      row('種類', esc(n.type || '')) + row('担当', esc(p)) +
      row('説明', esc(n.description || '未設定')) + row('利用システム', esc(n.system || '未設定')) +
      row('入力', list(n.inputs)) + row('出力', list(n.outputs)) +
      row('所要時間', esc(n.duration || '未設定')) + row('頻度', esc(n.frequency || '未設定')) + row('課題', issueList(n.issues)) +
      row('自動化候補', auto.candidate === true ? 'あり' : auto.candidate === false ? 'なし' : '未評価') +
      row('自動化メモ', esc(auto.notes || '未設定')) + '</dl>';
  }}
  document.querySelectorAll('.process-node').forEach(el => {{
    el.addEventListener('click', () => show(el.dataset.nodeId));
    el.addEventListener('keydown', e => {{ if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); show(el.dataset.nodeId); }} }});
  }});
}})();
</script>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish business process YAML to BPMN, PlantUML, and self-contained HTML.")
    parser.add_argument("--input", default="/mnt/data/process.yaml")
    parser.add_argument("--output-dir", default="/mnt/data")
    parser.add_argument("--basename", default="process")
    args = parser.parse_args()

    try:
        data = load_model(Path(args.input))
        errors = preflight(data)
        if errors:
            print(json.dumps({"ok": False, "errors": errors, "message": "Publisher preflight failed. Run Modeler/Reviewer and fix the YAML before publishing."}, ensure_ascii=False, indent=2))
            return 1
        layout = compute_layout(data)
        layout["edge_routes"] = build_edge_routes(data, layout)
        layout["edge_labels"] = build_edge_label_positions(data, layout, layout["edge_routes"])
        layout["html_jump_edges"] = build_html_jump_edges(data, layout)
        layout["html_jump_geometry"] = build_html_jump_geometry(layout)
        layout["layout_warnings"] = layout_warnings(data, layout, layout["edge_routes"])
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        bpmn_path = out / f"{args.basename}.bpmn"
        puml_path = out / f"{args.basename}.puml"
        html_path = out / f"{args.basename}.html"
        bpmn_path.write_text(generate_bpmn(data, layout), encoding="utf-8")
        puml_path.write_text(generate_plantuml(data, layout), encoding="utf-8")
        html_path.write_text(generate_html(data, layout), encoding="utf-8")
        ET.fromstring(bpmn_path.read_text(encoding="utf-8"))
        result = {
            "ok": True,
            "outputs": {"bpmn": str(bpmn_path), "plantuml": str(puml_path), "html": str(html_path)},
            "layout": {"width": layout["width"], "height": layout["height"], "mode": "readable-interactive"},
            "layout_warnings": layout.get("layout_warnings", []),
            "layout_lane_inferences": layout.get("layout_lane_inferences", []),
            "html_jump_connectors": len(layout.get("html_jump_edges") or {}),
            "notes": [
                "HTML is self-contained and contains a pre-rendered SVG; JavaScript adds zoom, fit-to-width, fit-to-view, detail-panel toggle, and node details.",
                "HTML defaults to a readable non-shrinking SVG canvas; users can zoom out or use fit-to-view when an overview is needed.",
                "Swimlanes are ordered for the derived view by first forward-flow participation; the source YAML participant order is not modified.",
                "Gateway alternatives may share a source-side routing trunk; local return loops use collision-aware dedicated corridors, while exceptionally long backward routes use paired Rn jump connectors in HTML by default and keep the full route available via a toolbar toggle.",
                "Normal-flow nodes keep the lane main row when exception handlers compete at the same depth; simple same-lane chains and End events are centered when safe.",
                "Edge labels use collision-aware placement; End event names are rendered outside the event circle.",
                "Missing participants on control-flow nodes are resolved to publication-time lanes from adjacent flow when possible; unknown task actors remain unassigned.",
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
