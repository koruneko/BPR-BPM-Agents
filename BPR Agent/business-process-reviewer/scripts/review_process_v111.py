#!/usr/bin/env python3
import argparse
import json
import re
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




def _unknown_keys(obj: Any, allowed: set[str], path: str, errors: list[dict[str,str]]) -> None:
    if not isinstance(obj, dict):
        return
    for key in sorted(set(obj) - allowed):
        errors.append({"code":"unknown_schema_key","message":f"定義外のキーがあります: {path}.{key}"})

def strict_schema_findings(data: dict[str, Any]) -> list[dict[str,str]]:
    errors: list[dict[str,str]]=[]
    _unknown_keys(data, {'schema_version','process','participants','nodes','edges','metadata'}, '$', errors)
    proc=data.get('process')
    if isinstance(proc,dict):
        _unknown_keys(proc, {'id','name','description','owner','version','scope'}, '$.process', errors)
        if isinstance(proc.get('scope'),dict): _unknown_keys(proc['scope'], {'start','end'}, '$.process.scope', errors)
    for i,x in enumerate(data.get('participants') or []):
        if isinstance(x,dict): _unknown_keys(x, {'id','name','type'}, f'$.participants[{i}]', errors)
    node_allowed={'id','type','name','participant','task_type','description','system','inputs','outputs','duration','frequency','issues','automation'}
    for i,x in enumerate(data.get('nodes') or []):
        if not isinstance(x,dict): continue
        _unknown_keys(x,node_allowed,f'$.nodes[{i}]',errors)
        if isinstance(x.get('automation'),dict): _unknown_keys(x['automation'], {'candidate','level','notes','exception_owner'}, f'$.nodes[{i}].automation', errors)
    for i,x in enumerate(data.get('edges') or []):
        if isinstance(x,dict): _unknown_keys(x, {'id','from','to','name','condition','default'}, f'$.edges[{i}]', errors)
    meta=data.get('metadata')
    if isinstance(meta,dict):
        _unknown_keys(meta, {'assumptions','open_questions','inferences','bpr'}, '$.metadata', errors)
        bpr=meta.get('bpr')
        if isinstance(bpr,dict):
            _unknown_keys(bpr, {'source_process','source_analysis_version','source_analysis_id','applied_improvements','conditional_improvements','change_log','source_node_context','performance_targets','issue_disposition','open_question_disposition'}, '$.metadata.bpr', errors)
            if isinstance(bpr.get('source_process'),dict): _unknown_keys(bpr['source_process'], {'id','name','version'}, '$.metadata.bpr.source_process', errors)
            for i,x in enumerate(bpr.get('conditional_improvements') or []):
                if isinstance(x,dict): _unknown_keys(x, {'improvement_id','condition'}, f'$.metadata.bpr.conditional_improvements[{i}]', errors)
            for i,x in enumerate(bpr.get('change_log') or []):
                if not isinstance(x,dict): continue
                _unknown_keys(x, {'improvement_id','title','action','summary','expected_effect','confidence','condition','source_node_ids','target_node_ids','source_edge_ids','target_edge_ids'}, f'$.metadata.bpr.change_log[{i}]', errors)
                if isinstance(x.get('expected_effect'),dict): _unknown_keys(x['expected_effect'], {'impact','notes'}, f'$.metadata.bpr.change_log[{i}].expected_effect', errors)
            for i,x in enumerate(bpr.get('performance_targets') or []):
                if isinstance(x,dict): _unknown_keys(x, {'metric','baseline','target','direction','note','related_improvements','source_node_ids','target_node_ids'}, f'$.metadata.bpr.performance_targets[{i}]', errors)
            for i,x in enumerate(bpr.get('open_question_disposition') or []):
                if isinstance(x,dict): _unknown_keys(x, {'source','question','status','materiality','resolution','note'}, f'$.metadata.bpr.open_question_disposition[{i}]', errors)
            idisp=bpr.get('issue_disposition')
            if isinstance(idisp,dict):
                for nid,entries in idisp.items():
                    for i,x in enumerate(entries or []):
                        if isinstance(x,dict): _unknown_keys(x, {'source_issue','status','to_be_issue','performance_target_metric','note'}, f'$.metadata.bpr.issue_disposition.{nid}[{i}]', errors)
            sctx=bpr.get('source_node_context')
            if isinstance(sctx,dict):
                for nid,x in sctx.items():
                    if isinstance(x,dict): _unknown_keys(x, {'name','participant','system','duration','frequency','issues'}, f'$.metadata.bpr.source_node_context.{nid}', errors)
    return errors

def _active_improvement_ids(decisions: dict[str,Any] | None) -> list[str]:
    if not isinstance(decisions,dict): return []
    return [str(x.get('improvement_id')) for x in decisions.get('decisions') or [] if isinstance(x,dict) and x.get('decision') in {'approved','conditional_approved'} and x.get('improvement_id')]

def _expected_open_questions(source: dict[str,Any], analysis: dict[str,Any], active_ids: list[str]) -> list[tuple[str,str]]:
    out=[]; seen=set(); active=set(active_ids)
    def add(q, src):
        q=str(q or '').strip()
        if q and q not in seen: seen.add(q); out.append((q,src))
    impmap={str(x.get('id')):x for x in analysis.get('improvements') or [] if isinstance(x,dict) and x.get('id')}
    covered=set()
    for cov in analysis.get('as_is_open_question_coverage') or []:
        if isinstance(cov,dict) and active.intersection(set(cov.get('improvement_ids') or [])):
            q=str(cov.get('question') or '').strip()
            if q: covered.add(q)
    for iid in active_ids:
        for q in (impmap.get(iid) or {}).get('unresolved_questions') or []: add(q,iid)
    for q in ((source.get('metadata') or {}).get('open_questions') or []):
        if str(q or '').strip() not in covered: add(q,'as_is')
    for q in analysis.get('analysis_open_questions') or []: add(q,'analysis')
    return out

def traceability_findings(data: dict[str,Any], source: dict[str,Any] | None, analysis: dict[str,Any] | None, decisions: dict[str,Any] | None) -> list[dict[str,str]]:
    metadata=data.get('metadata') if isinstance(data.get('metadata'),dict) else {}
    bpr=metadata.get('bpr') if isinstance(metadata.get('bpr'),dict) else None
    if not bpr: return []
    if not (isinstance(source,dict) and isinstance(analysis,dict) and isinstance(decisions,dict)):
        return [{"code":"bpr_traceability_context_missing","message":"BPR To-Beの最終レビューには --source-process / --analysis / --decisions を渡してください。open questionの全件追跡を検証できません。"}]
    errors=[]
    active=_active_improvement_ids(decisions)
    expected=_expected_open_questions(source,analysis,active)
    expected_map={q:src for q,src in expected}
    oqd=bpr.get('open_question_disposition')
    entries=oqd if isinstance(oqd,list) else []
    actual={}
    for e in entries:
        if not isinstance(e,dict): continue
        q=str(e.get('question') or '').strip()
        if q: actual[q]=e
    missing=[q for q in expected_map if q not in actual]
    if missing:
        errors.append({"code":"open_question_disposition_incomplete","message":"分析/As-Isの未確認事項がopen_question_dispositionから欠落しています: " + " / ".join(missing)})
    extra=[q for q,e in actual.items() if q not in expected_map and str(e.get('source') or '')!='design']
    if extra:
        errors.append({"code":"open_question_disposition_unknown","message":"分析/As-Isに存在しない未確認事項をopen_question_dispositionが参照しています。To-Beで新しく生じた未確認事項はsource=designにしてください: " + " / ".join(extra)})
    for q,src in expected_map.items():
        e=actual.get(q)
        if not e: continue
        if str(e.get('source') or '') != src:
            errors.append({"code":"open_question_source_mismatch","message":f"open_question_disposition.sourceが不一致です: {q} expected={src} actual={e.get('source')}"})
        if e.get('status') not in {'resolved','carried_forward','not_applicable'}:
            errors.append({"code":"open_question_status_invalid","message":f"statusはresolved/carried_forward/not_applicableのいずれかです: {q}"})
    carried={q for q,e in actual.items() if e.get('status')=='carried_forward'}
    top={str(q).strip() for q in metadata.get('open_questions') or [] if str(q).strip()}
    if carried != top:
        errors.append({"code":"open_questions_not_synchronized","message":f"metadata.open_questionsはcarried_forwardと完全一致させてください。missing={sorted(carried-top)}, extra={sorted(top-carried)}"})
    return errors

def is_material_business_rule_question(question: str) -> bool:
    q = str(question or "")
    patterns = [
        r"上限到達.*?(?:経路|どの|どこ|却下|相談|確認|進め)",
        r"(?:非承認|承認しない).*?(?:却下|差し戻し|経路|終了|振込対象)",
        r"差し戻し先.*?(?:社員|上長|経理|どこ)",
        r"非承認申請.*?(?:振込対象|終了|状態)",
        r"(?:外貨|税抜|税込|支払金額|どの金額).*?(?:閾値|判定)",
        r"(?:閾値|判定).*?(?:外貨|税抜|税込|支払金額|どの金額)",
        r"職務分離", r"二重承認",
    ]
    return any(re.search(p, q, re.I) for p in patterns)

def bpr_semantic_findings(
    data: dict[str, Any],
    node_map: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Semantic guardrails applied only to BPR To-Be models (metadata.bpr present)."""
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    bpr = metadata.get("bpr") if isinstance(metadata.get("bpr"), dict) else None
    if not bpr:
        return errors, warnings

    # Final To-Be must not silently carry unresolved rules that can change topology,
    # branch semantics, exception routing, or responsible actor.
    for q in metadata.get("open_questions") or []:
        if is_material_business_rule_question(str(q)):
            errors.append({
                "code": "material_open_question_unresolved",
                "message": f"Final To-BeのControl Flow/担当に影響し得る未確認事項が残っています。Human Gateで確定してから再生成してください: {q}",
            })

    oqd = bpr.get("open_question_disposition")
    if oqd is None:
        errors.append({
            "code": "open_question_disposition_missing",
            "message": "BPR To-Beではmetadata.bpr.open_question_dispositionが必要です。分析時の未確認事項をresolved/carried_forward/not_applicableで追跡してください。",
        })
    elif isinstance(oqd, list):
        for e in oqd:
            if not isinstance(e, dict):
                continue
            if e.get("materiality") == "blocking" and e.get("status") == "carried_forward":
                errors.append({
                    "code": "blocking_open_question_carried_forward",
                    "message": f"Blockingな未確認事項をFinal To-Beへ持ち越せません: {e.get('question')}",
                })

    for nid, node in node_map.items():
        if node.get("type") != "task":
            continue
        outs = outgoing.get(nid, [])
        desc = str(node.get("description") or "")
        outputs = normal_list(node.get("outputs"))

        # A task that produces an approval/decision result must have that outcome
        # consumed by a real split/condition before unconditional downstream work.
        decision_result = any(re.search(r"(?:承認|判定|審査).*結果|結果.*(?:承認|判定|審査)", x) for x in outputs)
        if decision_result and len(outs) == 1:
            target = node_map.get(str(outs[0].get("to")), {})
            target_outs = outgoing.get(str(outs[0].get("to")), [])
            is_real_split = target.get("type") == "gateway_exclusive" and len(target_outs) > 1
            edge_is_conditional = bool(str(outs[0].get("condition") or "").strip())
            if not is_real_split and not edge_is_conditional:
                errors.append({
                    "code": "decision_outcome_not_consumed",
                    "message": f"{nid} は判断結果を出力しますが、その結果を条件分岐で消費せず無条件に後続へ進みます。承認/非承認等の結果をControl Flowへ反映してください。",
                })

        # Natural-language guard clauses such as "only if both succeed" must be
        # represented by an edge condition or an explicit exclusive split.
        guarded = bool(re.search(r"(?:場合|とき).*?のみ.*?(?:進|実行|可能|開始)|両方.*?成功.*?のみ|成功.*?場合のみ", desc))
        if guarded and len(outs) == 1:
            edge = outs[0]
            target = node_map.get(str(edge.get("to")), {})
            target_outs = outgoing.get(str(edge.get("to")), [])
            has_condition = bool(str(edge.get("condition") or "").strip())
            is_real_split = target.get("type") == "gateway_exclusive" and len(target_outs) > 1
            if not has_condition and not is_real_split:
                errors.append({
                    "code": "conditional_progression_unmodeled",
                    "message": f"{nid} のdescriptionには後続へ進む条件がありますが、Control Flowに条件分岐がありません。文章だけでなくEdge/Gatewayへモデル化してください。",
                })

        auto = node.get("automation") if isinstance(node.get("automation"), dict) else {}
        exception_owner = str(auto.get("exception_owner") or "")
        if exception_owner:
            if len(outs) != 1:
                errors.append({
                    "code": "exception_result_gateway_required",
                    "message": f"{nid} はexception_ownerを持つ自動Taskです。正常/例外を分岐する1つの結果Gatewayへ接続してください。",
                })
            else:
                gate_id = str(outs[0].get("to") or "")
                gate = node_map.get(gate_id, {})
                gate_outs = outgoing.get(gate_id, [])
                if gate.get("type") != "gateway_exclusive" or len(gate_outs) < 2:
                    errors.append({
                        "code": "exception_path_unmodeled",
                        "message": f"{nid} はexception_ownerを持ちますが、Task直後に成功/失敗を分けるExclusive Gatewayがありません。Parallel Joinへ直接接続せず、各branch内で例外を処理してください。",
                    })
                else:
                    success = [e for e in gate_outs if re.search(r"成功|正常", str(e.get("name") or "") + " " + str(e.get("condition") or ""))]
                    failure = [e for e in gate_outs if re.search(r"失敗|例外|エラー|滞留|期限|タイムアウト", str(e.get("name") or "") + " " + str(e.get("condition") or "")) or e.get("default") is True]
                    if not success or not failure:
                        errors.append({
                            "code": "exception_outcome_coverage_incomplete",
                            "message": f"{nid} の結果Gateway {gate_id} は成功と失敗/例外の両方を明示してください。",
                        })
                    elif not any(str(node_map.get(str(e.get("to") or ""),{}).get("participant") or "") == exception_owner for e in failure):
                        errors.append({
                            "code": "exception_owner_path_mismatch",
                            "message": f"{nid} の失敗/例外経路がautomation.exception_owner={exception_owner} のTaskへ接続されていません。",
                        })

    return errors, warnings

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

def review(data: dict[str, Any], source: dict[str,Any] | None = None, analysis: dict[str,Any] | None = None, decisions: dict[str,Any] | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []

    errors.extend(strict_schema_findings(data))
    errors.extend(traceability_findings(data, source, analysis, decisions))

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

    # Parallel gateways that directly coordinate at least one system-executed branch
    # should themselves be placed in a system lane. Purely human parallel work is not
    # forced into a system lane.
    participant_types = {str(p.get("id")): str(p.get("type") or "") for p in participants if isinstance(p, dict) and p.get("id")}
    for nid,node in node_map.items():
        if node.get("type") != "gateway_parallel":
            continue
        adjacent=[]
        for e in outgoing.get(nid, []):
            adjacent.append(node_map.get(str(e.get("to") or ""), {}))
        for e in incoming.get(nid, []):
            adjacent.append(node_map.get(str(e.get("from") or ""), {}))
        has_system_branch=any(
            isinstance(x,dict) and participant_types.get(str(x.get("participant") or "")) == "system"
            for x in adjacent
        )
        if has_system_branch and participant_types.get(str(node.get("participant") or "")) != "system":
            errors.append({
                "code": "parallel_gateway_human_lane_for_system_branch",
                "message": f"並行ゲートウェイ {nid} はsystem実行branchを制御しています。Split/Join自体もtype=systemのparticipantへ配置してください。",
            })

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

    semantic_errors, semantic_warnings = bpr_semantic_findings(data, node_map, outgoing)
    errors.extend(semantic_errors)
    warnings.extend(semantic_warnings)
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
    parser.add_argument("--source-process")
    parser.add_argument("--analysis")
    parser.add_argument("--decisions")
    parser.add_argument("--json-output", default="/mnt/data/process-review.json")
    parser.add_argument("--md-output", default="/mnt/data/process-review.md")
    args = parser.parse_args()

    try:
        data = load_model(Path(args.input))
        source = load_model(Path(args.source_process)) if args.source_process else None
        analysis = load_model(Path(args.analysis)) if args.analysis else None
        decisions = load_model(Path(args.decisions)) if args.decisions else None
        result = review(data, source=source, analysis=analysis, decisions=decisions)
        Path(args.json_output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(args.md_output).write_text(markdown_report(result), encoding="utf-8")
        print(json.dumps({"ok": result["ok"], "json_output": args.json_output, "md_output": args.md_output, "summary": result["summary"]}, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
