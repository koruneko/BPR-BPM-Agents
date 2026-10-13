"""Generate and verify the complete Gap Analysis delivery package from one analysis JSON.

This is the registered derivative generator used by gap_workflow.py.
Formal delivery must enter through gap_workflow.py final. This module keeps all
derived artifacts synchronized with one canonical analysis JSON.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

from inspect_sources import inspect, pack_files, validate as validate_sources
from planning_report import dependency_relations, validate_dependencies
from render_report import GENERATOR_ID, render, validate_next_actions

SCRIPT_NAMES = [
    "gap_workflow.py",
    "generate_delivery.py",
    "render_report.py",
    "report_format.py",
    "planning_report.py",
    "business_calendar.py",
    "inspect_sources.py",
]
DIMENSIONS = ("process", "technology", "data", "people", "organization", "rules", "control", "measurement")
DECISION_CONTEXT_FIELDS = (
    "impact",
    "root_cause",
    "preserve",
    "target_outcome",
    "response_strategy",
    "scope",
    "success_measure",
    "priority_assessment",
    "tradeoff",
    "source_refs",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _excel_safe(value: Any) -> str:
    text = _as_text(value)
    if re.match(r"^[\s]*[=+\-@]", text):
        return "'" + text
    return text


def _join(values: Iterable[Any] | None) -> str:
    if not values:
        return ""
    return ";".join(_as_text(v) for v in values)


def _ids(rows: list[dict[str, Any]], label: str) -> set[str]:
    found = [r.get("id") for r in rows]
    if any(not x for x in found):
        raise ValueError(f"{label} contains an empty ID")
    if len(found) != len(set(found)):
        raise ValueError(f"Duplicate {label} ID")
    return set(found)


def _is_placeholder(value: Any) -> bool:
    text = _as_text(value).strip()
    return text in {"", "未整理", "未確認", "関連Gapと質問を参照。", "関連するGapと質問を参照。", "TBD", "TODO"}


def _valid_source_refs(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for row in value:
        if not isinstance(row, dict):
            return False
        if not row.get("file") or not row.get("field") or not row.get("evidence_kind"):
            return False
    return True


def _validate_quality(data: dict[str, Any], mode: str = "draft") -> dict[str, Any]:
    """Validate the information model before any derivative is generated.

    `final` is deliberately strict: it rejects an ad-hoc or thin analysis even
    if the renderer could technically produce HTML from it. No fixed number of
    GAP/ACT/Q items is required.
    """
    issues: list[str] = []
    warnings: list[str] = []
    final = mode == "final"

    for key in ("analysis_id", "analysis_version", "gaps", "actions", "questions", "source_manifest", "mappings", "roadmap", "verification"):
        if key not in data:
            issues.append(f"Missing top-level field: {key}")

    workflow = data.get("workflow")
    if final:
        if not isinstance(workflow, dict) or workflow.get("prepared_by") != "gap-delivery/scripts/gap_workflow.py@3":
            issues.append("final analysis must originate from gap_workflow.py@3 prepare")
        elif not workflow.get("source_pack_sha256") or not workflow.get("source_index_sha256"):
            issues.append("workflow preparation hashes are missing")

    gaps = data.get("gaps") or []
    actions = data.get("actions") or []
    questions = data.get("questions") or []
    next_actions = data.get("next_actions") or []
    gap_ids = _ids(gaps, "GAP")
    action_ids = _ids(actions, "ACT")
    question_ids = _ids(questions, "Q")
    next_ids = _ids(next_actions, "NA") if next_actions else set()

    # Questions may legitimately be absent when the original materials contain
    # no open questions and the analysis does not discover any new ones.
    if final and (not gaps or not actions or not next_actions):
        issues.append("final analysis requires non-empty GAP, ACT and Next Action sets")
    if final and not data.get("roadmap"):
        issues.append("final analysis requires roadmap")
    if final and (data.get("input_validation") or {}).get("status") != "pass":
        issues.append("final analysis requires input_validation.status=pass")
    if final and (data.get("input_validation") or {}).get("issues"):
        issues.append("final analysis input_validation.issues must be empty")

    allowed_priority = {"critical", "high", "medium", "low"}
    allowed_mapping_changes = {"maintained", "added", "changed", "removed", "merged", "split"}

    scope_summary = data.get("scope_summary")
    if not isinstance(scope_summary, dict):
        issues.append("scope_summary must be an object")
    else:
        for key in ("included", "excluded", "later", "external", "temporary"):
            if key not in scope_summary:
                issues.append(f"scope_summary missing: {key}")
            elif final and _is_placeholder(scope_summary.get(key)):
                issues.append(f"scope_summary.{key} is not substantively completed")

    dimensions = data.get("analysis_dimensions")
    dimension_summaries: list[str] = []
    if not isinstance(dimensions, dict):
        issues.append("analysis_dimensions must be an object")
    else:
        for key in DIMENSIONS:
            row = dimensions.get(key)
            if not isinstance(row, dict):
                issues.append(f"analysis_dimensions missing: {key}")
                continue
            for field in ("status", "summary", "gap_ids", "question_ids", "source_refs"):
                if field not in row:
                    issues.append(f"analysis_dimensions.{key} missing: {field}")
            unknown_gap = set(row.get("gap_ids") or []) - gap_ids
            unknown_q = set(row.get("question_ids") or []) - question_ids
            if unknown_gap:
                issues.append(f"analysis_dimensions.{key} unknown GAP IDs: {sorted(unknown_gap)}")
            if unknown_q:
                issues.append(f"analysis_dimensions.{key} unknown Q IDs: {sorted(unknown_q)}")
            summary = _as_text(row.get("summary")).strip()
            if final:
                if _is_placeholder(summary) or len(summary) < 16:
                    issues.append(f"analysis_dimensions.{key}.summary is too thin or placeholder")
                if not _valid_source_refs(row.get("source_refs")):
                    issues.append(f"analysis_dimensions.{key}.source_refs must contain structured evidence")
            if summary:
                dimension_summaries.append(summary)
        if final and len(dimension_summaries) == len(DIMENSIONS) and len(set(dimension_summaries)) <= 2:
            issues.append("analysis_dimensions summaries are overly repetitive; record dimension-specific findings")

    context_values: dict[str, list[str]] = {k: [] for k in ("impact", "root_cause", "preserve", "success_measure", "tradeoff")}
    for gap in gaps:
        gid = gap.get("id", "<unknown>")
        if final and gap.get("priority") not in allowed_priority:
            issues.append(f"{gid}.priority must use internal enum {sorted(allowed_priority)}")
        dc = gap.get("decision_context")
        if not isinstance(dc, dict):
            issues.append(f"{gid} missing decision_context")
        else:
            for field in DECISION_CONTEXT_FIELDS:
                if field not in dc:
                    issues.append(f"{gid}.decision_context missing: {field}")
            if final:
                for field in DECISION_CONTEXT_FIELDS[:-1]:
                    if _is_placeholder(dc.get(field)) or len(_as_text(dc.get(field)).strip()) < 8:
                        issues.append(f"{gid}.decision_context.{field} is too thin or placeholder")
                if not _valid_source_refs(dc.get("source_refs")):
                    issues.append(f"{gid}.decision_context.source_refs must contain structured evidence")
                if not _valid_source_refs(gap.get("source_refs")):
                    issues.append(f"{gid}.source_refs must contain structured evidence")
            for field in context_values:
                value = _as_text(dc.get(field)).strip() if isinstance(dc, dict) else ""
                if value:
                    context_values[field].append(value)
        if set(gap.get("action_ids") or []) - action_ids:
            issues.append(f"{gid} contains unknown action_ids")
        if set(gap.get("question_ids") or []) - question_ids:
            issues.append(f"{gid} contains unknown question_ids")
    if final and len(gaps) >= 4:
        repeated_fields = [field for field, values in context_values.items() if len(values) == len(gaps) and len(set(values)) == 1]
        if len(repeated_fields) >= 3:
            issues.append("Gap decision_context is overly templated across items: " + ", ".join(repeated_fields))

    validate_dependencies(actions)
    validate_next_actions(data)

    for action in actions:
        aid = action.get("id", "<unknown>")
        if final and action.get("priority") not in allowed_priority:
            issues.append(f"{aid}.priority must use internal enum {sorted(allowed_priority)}")
        if final and not isinstance(action.get("owner_candidate"), str):
            issues.append(f"{aid}.owner_candidate must be a human-readable string")
        if final and not _valid_source_refs(action.get("source_refs")):
            issues.append(f"{aid}.source_refs must contain structured evidence")
        if set(action.get("gap_ids") or []) - gap_ids:
            issues.append(f"{aid} contains unknown gap_ids")
        for rel in dependency_relations(action):
            if rel["predecessor_id"] not in action_ids:
                issues.append(f"{aid} dependency has unknown ACT: {rel['predecessor_id']}")
            if rel["type"] == "required" and not rel.get("condition"):
                issues.append(f"{aid} required dependency lacks condition")
            if rel["type"] == "optional" and (not rel.get("can_proceed") or not rel.get("if_deferred")):
                issues.append(f"{aid} optional dependency lacks can_proceed/if_deferred")

    for na in next_actions:
        nid = na.get("id", "<unknown>")
        if final and na.get("priority") not in allowed_priority:
            issues.append(f"{nid}.priority must use internal enum {sorted(allowed_priority)}")
        if final and not isinstance(na.get("consult_with"), str):
            issues.append(f"{nid}.consult_with must be a human-readable string")
        if set(na.get("related_action_ids") or []) - action_ids:
            issues.append(f"{nid} contains unknown related_action_ids")
        if set(na.get("question_ids") or []) - question_ids:
            issues.append(f"{nid} contains unknown question_ids")
        for rel in dependency_relations(na):
            if rel["predecessor_id"] not in next_ids:
                issues.append(f"{nid} dependency has unknown NA: {rel['predecessor_id']}")

    for q in questions:
        qid = q.get("id", "<unknown>")
        if final and not _valid_source_refs(q.get("source_refs")):
            issues.append(f"{qid}.source_refs must contain structured evidence")
        if set(q.get("gap_ids") or []) - gap_ids:
            issues.append(f"{qid} contains unknown gap_ids")
        if q.get("status") == "resolved" and (not q.get("resolution") or not q.get("resolution_source")):
            issues.append(f"{qid} is resolved without resolution and source")
        if final and _is_placeholder(q.get("impact")):
            issues.append(f"{qid}.impact is not completed")

    mappings = data.get("mappings") or []
    if final and not mappings:
        issues.append("final analysis requires semantic mappings")
    for m in mappings:
        mid = m.get("id", "<mapping>")
        if final:
            if m.get("change_type") not in allowed_mapping_changes:
                issues.append(f"{mid}.change_type is not semantically classified")
            if _is_placeholder(m.get("semantic_delta")):
                issues.append(f"{mid}.semantic_delta is missing")
            if not _valid_source_refs(m.get("source_refs")):
                issues.append(f"{mid}.source_refs must contain structured evidence")
            as_ids = m.get("as_is_ids") or []
            to_ids = m.get("to_be_ids") or []
            ct = m.get("change_type")
            if ct == "added" and (as_ids or not to_ids):
                issues.append(f"{mid} added mapping must have only To-Be IDs")
            if ct == "removed" and (not as_ids or to_ids):
                issues.append(f"{mid} removed mapping must have only As-Is IDs")
            if ct in {"maintained", "changed"} and (not as_ids or not to_ids):
                issues.append(f"{mid} {ct} mapping requires both As-Is and To-Be IDs")
            if ct == "merged" and (len(as_ids) < 2 or not to_ids):
                issues.append(f"{mid} merged mapping requires multiple As-Is IDs and To-Be ID(s)")
            if ct == "split" and (not as_ids or len(to_ids) < 2):
                issues.append(f"{mid} split mapping requires As-Is ID(s) and multiple To-Be IDs")

    seq = data.get("execution_sequence")
    if seq:
        seq_ids = [aid for group in seq for aid in (group.get("action_ids") or [])]
        if set(seq_ids) != action_ids or len(seq_ids) != len(action_ids):
            issues.append("execution_sequence must contain every ACT exactly once")
    elif final:
        issues.append("final analysis requires execution_sequence")
    else:
        warnings.append("execution_sequence is not present")

    dialogue = data.get("dialogue") or {}
    if dialogue.get("status") == "completed" and not next_actions:
        issues.append("completed dialogue requires next_actions")
    if final:
        if dialogue.get("status") != "completed":
            issues.append("final mode requires dialogue.status=completed")
        if not dialogue.get("agreed_scope") or not dialogue.get("confirmation_source"):
            issues.append("final mode requires agreed_scope and confirmation_source")
        if data.get("status") != "analysis_complete":
            issues.append("final mode requires status=analysis_complete")

    return {
        "status": "pass" if not issues else "fail",
        "mode": mode,
        "issues": issues,
        "warnings": warnings,
        "counts": {
            "gaps": len(gaps),
            "actions": len(actions),
            "questions": len(questions),
            "next_actions": len(next_actions),
        },
    }

def _write_csv(data: dict[str, Any], path: Path) -> None:
    gaps_by_id = {g["id"]: g for g in data.get("gaps", [])}
    headers = [
        "action_id", "gap_ids", "title", "category", "as_is", "to_be", "delta",
        "improvement_ids", "owner_candidate", "owner_status", "priority", "priority_reason",
        "start_status", "depends_on", "entry_conditions", "acceptance_criteria", "question_ids", "source_refs",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for action in data.get("actions", []):
            gids = action.get("gap_ids") or []
            linked = [gaps_by_id[g] for g in gids if g in gaps_by_id]
            categories = sorted({str(g.get("category", "")) for g in linked if g.get("category")})
            as_is = " / ".join(str(g.get("as_is", "")) for g in linked if g.get("as_is"))
            to_be = " / ".join(str(g.get("to_be", "")) for g in linked if g.get("to_be"))
            delta = " / ".join(str(g.get("delta", "")) for g in linked if g.get("delta"))
            improvement_ids = sorted({i for g in linked for i in (g.get("improvement_ids") or [])})
            question_ids = sorted({q for g in linked for q in (g.get("question_ids") or [])})
            source_refs = action.get("source_refs") or [r for g in linked for r in (g.get("source_refs") or [])]
            row = {
                "action_id": action.get("id"),
                "gap_ids": _join(gids),
                "title": action.get("title"),
                "category": _join(categories),
                "as_is": as_is,
                "to_be": to_be,
                "delta": delta,
                "improvement_ids": _join(improvement_ids),
                "owner_candidate": action.get("owner_candidate"),
                "owner_status": action.get("owner_status"),
                "priority": action.get("priority"),
                "priority_reason": action.get("priority_reason"),
                "start_status": action.get("start_status"),
                "depends_on": _join(action.get("depends_on") or []),
                "entry_conditions": _join(action.get("entry_conditions") or []),
                "acceptance_criteria": _join(action.get("acceptance_criteria") or []),
                "question_ids": _join(question_ids),
                "source_refs": _as_text(source_refs),
            }
            w.writerow({k: _excel_safe(v) for k, v in row.items()})


def _md_list(values: Iterable[Any] | None) -> str:
    values = list(values or [])
    return "\n".join(f"- {_as_text(v)}" for v in values) if values else "- 未確認"


def _write_markdown_report(data: dict[str, Any], path: Path) -> None:
    gaps = data.get("gaps", [])
    actions = data.get("actions", [])
    questions = data.get("questions", [])
    pending = [q for q in questions if q.get("status") != "resolved"]
    lines = [
        f"# {data.get('title') or data.get('process_name') or 'Gap分析・実行計画レポート'}",
        "",
        f"- 分析ID: {data.get('analysis_id', '')}",
        f"- 版: {data.get('analysis_version', '')}",
        f"- Gap: {len(gaps)} / ACT: {len(actions)} / 未確認Q: {len(pending)}",
        "",
        "## 今回の範囲",
        _as_text(data.get("scope_summary") or {}),
        "",
        "## 次に行うこと",
    ]
    for na in data.get("next_actions", []):
        lines += [
            f"### {na.get('id')} {na.get('title')}",
            f"- 優先度: {na.get('priority', 'unknown')}",
            f"- 最初の一歩: {na.get('first_step', '')}",
            f"- 相談する役割: {na.get('consult_with', '')}",
            f"- 得たい結果: {na.get('expected_result', '')}",
            f"- 関連ACT: {_join(na.get('related_action_ids') or [])}",
            f"- 関連Q: {_join(na.get('question_ids') or [])}",
            "",
        ]
    lines += ["## Gap一覧", ""]
    for g in gaps:
        lines += [
            f"### {g.get('id')} {g.get('title')}",
            f"- 現在: {g.get('as_is', '')}",
            f"- 変更後: {g.get('to_be', '')}",
            f"- 必要な対応: {g.get('delta', '')}",
            f"- 優先度: {g.get('priority', 'unknown')} — {g.get('priority_reason', '')}",
            "- 完了を確認する条件:",
            _md_list(g.get("acceptance_criteria")),
            f"- 関連ACT: {_join(g.get('action_ids') or [])}",
            f"- 関連Q: {_join(g.get('question_ids') or [])}",
            "",
        ]
    lines += ["## 実施すること", ""]
    for a in actions:
        lines += [
            f"### {a.get('id')} {a.get('title')}",
            f"- 担当候補: {a.get('owner_candidate', '')} ({a.get('owner_status', 'unknown')})",
            f"- 成果物: {a.get('deliverable', '')}",
            "- 着手条件:", _md_list(a.get("entry_conditions")),
            "- 完了条件:", _md_list(a.get("acceptance_criteria")),
            "",
        ]
    lines += ["## 確認したいこと", ""]
    for q in questions:
        lines += [
            f"- **{q.get('id')}** [{q.get('status', 'open')}] {q.get('question', '')} — {q.get('respondent_candidate', '')}",
        ]
    lines += ["", "## 検証と限界", "### 実施", _md_list((data.get("verification") or {}).get("performed")), "", "### 未実施", _md_list((data.get("verification") or {}).get("not_performed")), "", "### 限界", _md_list((data.get("verification") or {}).get("limitations")), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_roadmap(data: dict[str, Any], path: Path) -> None:
    lines = ["# 実施ロードマップ", ""]
    if data.get("execution_sequence"):
        lines += ["## 対話で整理した実行順", ""]
        for row in data["execution_sequence"]:
            lines += [
                f"### {row.get('order')}. {row.get('name', '')}",
                f"- 対応: {_join(row.get('action_ids') or [])}",
                f"- 状態: {row.get('status', 'proposed')}",
                f"- 理由・着手条件: {row.get('reason', '')}",
                "",
            ]
    lines += ["## 段階ごとの条件", ""]
    for i, p in enumerate(data.get("roadmap", []), 1):
        lines += [
            f"### 段階 {i}: {p.get('phase') or p.get('title') or ''}",
            f"- 対応: {_join(p.get('action_ids') or [])}",
            "- 始める条件:", _md_list(p.get("entry_conditions")),
            "- 次へ進む条件:", _md_list(p.get("exit_conditions")),
            "",
        ]
    schedule = data.get("schedule") or {}
    lines += ["## 日程", ""]
    if schedule.get("tasks"):
        lines += [f"- 前提: {_as_text(schedule.get('basis'))}", ""]
        for row in schedule["tasks"]:
            lines.append(f"- {row.get('action_id')}: {row.get('start')} → {row.get('end')} ({row.get('status', 'proposed')})")
    else:
        lines.append("- 日程は未確定です。見積・開始日・担当稼働等を確認してから設定します。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _verify_outputs(data: dict[str, Any], paths: dict[str, Path], html_text: str) -> dict[str, Any]:
    issues: list[str] = []
    gap_ids = {g["id"] for g in data.get("gaps", [])}
    act_ids = {a["id"] for a in data.get("actions", [])}
    q_ids = {q["id"] for q in data.get("questions", [])}
    na_ids = {a["id"] for a in data.get("next_actions", [])}

    # Official renderer fingerprint and required report sections.
    if f'<meta name="generator" content="{GENERATOR_ID}">' not in html_text:
        issues.append("HTML generator marker is missing")
    for section_id in ("overview", "identifier-guide", "analysis-context", "next-actions", "gaps", "actions", "questions", "roadmap", "evidence"):
        if f'id="{section_id}"' not in html_text:
            issues.append(f"HTML missing section: {section_id}")
    for identifier in sorted(gap_ids | act_ids | q_ids | na_ids):
        if identifier not in html_text:
            issues.append(f"HTML missing ID: {identifier}")
    critical_count = sum(1 for g in data.get("gaps", []) if g.get("priority") == "critical")
    rendered_critical = html_text.count('class="card critical"')
    if rendered_critical != critical_count:
        issues.append(f"Critical Gap card count mismatch analysis={critical_count} html={rendered_critical}")

    # CSV must contain every ACT exactly once.
    with paths["csv"].open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    csv_ids = [r.get("action_id") for r in rows]
    if set(csv_ids) != act_ids or len(csv_ids) != len(act_ids):
        issues.append("CSV ACT IDs/count do not match analysis")

    # Human-readable derivatives retain every primary ID.
    md = paths["markdown"].read_text(encoding="utf-8")
    roadmap = paths["roadmap"].read_text(encoding="utf-8")
    for identifier in sorted(gap_ids | act_ids | q_ids | na_ids):
        if identifier not in md and (identifier not in roadmap or identifier not in act_ids):
            issues.append(f"Markdown derivatives missing ID: {identifier}")

    return {"status": "pass" if not issues else "fail", "issues": issues}


def cli_main() -> int:
    p = argparse.ArgumentParser(description="Internal derivative generator; use gap_workflow.py for formal delivery")
    p.add_argument("--mode", choices=("draft", "final"), default="final")
    p.add_argument("--analysis", required=True, help="Path to canonical gap-analysis.json")
    p.add_argument("--output-dir", required=True, help="Directory for generated artifacts")
    p.add_argument("--pack", help="Optional source pack with ## FILE / BEGIN FILE / END FILE markers")
    p.add_argument("--title", help="Optional report title override")
    p.add_argument("--report-view", choices=("preserve", "full"), default="preserve")
    p.add_argument("--zip", dest="zip_path", help="Output ZIP path; defaults inside output-dir")
    args = p.parse_args()
    if args.mode == "final":
        raise ValueError("Direct final generation is unsupported; use gap_workflow.py final with a prepare manifest")
    return generate(args)


def generate(args: argparse.Namespace) -> int:
    analysis_path = Path(args.analysis).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(__file__).resolve().parent

    # Remove stale generated artifacts first so a failed final run cannot leave
    # an older report or ZIP that looks current. Diagnostics may be recreated.
    for name in ("gap-analysis.json", "gap-register.csv", "gap-report.md", "gap-report.html",
                 "implementation-roadmap.md", "source-index.json", "source-verification.json",
                 "verification-manifest.json", "gap-analysis-delivery.zip", "gap-analysis-DRAFT.zip"):
        target = out_dir / name
        if target.exists():
            target.unlink()
    shutil.rmtree(out_dir / "scripts", ignore_errors=True)
    # A custom ZIP may be outside output-dir and survive an earlier failed run.
    zip_path = Path(args.zip_path).resolve() if args.zip_path else out_dir / ("gap-analysis-delivery.zip" if args.mode == "final" else "gap-analysis-DRAFT.zip")
    if zip_path.exists():
        zip_path.unlink()

    if args.mode == "final" and not args.pack:
        manifest = {"overall_status": "fail", "formal_verified": False, "mode": "final",
                    "error": "final mode requires --pack; source verification cannot be skipped"}
        (out_dir / "verification-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ValueError("final mode requires --pack")

    data = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
    if args.title:
        data["title"] = args.title
    if args.report_view == "full":
        data["report_view"] = "full"

    quality = _validate_quality(data, args.mode)
    if quality["status"] != "pass":
        diagnostic = out_dir / "verification-manifest.json"
        diagnostic.write_text(json.dumps({"overall_status": "fail", "formal_verified": False, "mode": args.mode, "quality": quality}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ValueError("Analysis quality validation failed: " + "; ".join(quality["issues"]))

    if args.mode == "final":
        pack_path_for_hash = Path(args.pack).resolve()
        expected_hash = (data.get("workflow") or {}).get("source_pack_sha256")
        actual_hash = _sha256(pack_path_for_hash)
        if expected_hash != actual_hash:
            manifest = {"overall_status": "fail", "formal_verified": False, "mode": "final",
                        "error": "source pack hash does not match prepared analysis",
                        "expected_source_pack_sha256": expected_hash, "actual_source_pack_sha256": actual_hash}
            (out_dir / "verification-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            raise ValueError("Source pack does not match the pack used by gap_workflow.py prepare")

    # The canonical analysis included in the package is exactly the data used for all derivatives.
    canonical = out_dir / "gap-analysis.json"
    canonical.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    source_index_result: dict[str, Any] | None = None
    source_validation_result: dict[str, Any] | None = None
    if args.pack:
        pack_path = Path(args.pack).resolve()
        source_index_result = inspect(pack_files(pack_path.read_text(encoding="utf-8-sig")))
        source_index_path = out_dir / "source-index.json"
        source_index_path.write_text(json.dumps(source_index_result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.mode == "final":
            expected_index_hash = (data.get("workflow") or {}).get("source_index_sha256")
            actual_index_hash = _sha256(source_index_path)
            if expected_index_hash != actual_index_hash:
                manifest = {"overall_status": "fail", "formal_verified": False, "mode": "final",
                            "error": "source index differs from prepare step",
                            "expected_source_index_sha256": expected_index_hash, "actual_source_index_sha256": actual_index_hash}
                (out_dir / "verification-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                raise ValueError("Source index does not match gap_workflow.py prepare")
        source_validation_result = validate_sources(source_index_result, data)
        source_verification = dict(source_index_result)
        source_verification["validation"] = source_validation_result
        (out_dir / "source-verification.json").write_text(json.dumps(source_verification, ensure_ascii=False, indent=2), encoding="utf-8")
        if source_index_result.get("unsupported") or source_validation_result.get("status") != "pass":
            manifest = {
                "overall_status": "fail",
                "quality": quality,
                "source_validation": source_validation_result,
                "unsupported": source_index_result.get("unsupported", []),
            }
            (out_dir / "verification-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            raise ValueError("Source verification failed; formal package was not created")

    csv_path = out_dir / "gap-register.csv"
    md_path = out_dir / "gap-report.md"
    roadmap_path = out_dir / "implementation-roadmap.md"
    html_path = out_dir / "gap-report.html"
    _write_csv(data, csv_path)
    _write_markdown_report(data, md_path)
    _write_roadmap(data, roadmap_path)

    html_text = render(data)
    html_path.write_text(html_text, encoding="utf-8")
    rerendered = render(json.loads(canonical.read_text(encoding="utf-8-sig")))
    rerender_match = html_text == rerendered
    if not rerender_match:
        raise ValueError("Registered renderer reproducibility check failed")

    paths = {"csv": csv_path, "markdown": md_path, "roadmap": roadmap_path, "html": html_path}
    derivative_validation = _verify_outputs(data, paths, html_text)
    if derivative_validation["status"] != "pass":
        raise ValueError("Derived artifact validation failed: " + "; ".join(derivative_validation["issues"]))

    runtime_dir = out_dir / "scripts"
    runtime_dir.mkdir(exist_ok=True)
    for name in SCRIPT_NAMES:
        shutil.copy2(scripts_dir / name, runtime_dir / name)

    files_for_hash = [canonical, csv_path, md_path, roadmap_path, html_path] + [runtime_dir / n for n in SCRIPT_NAMES]
    if args.pack:
        files_for_hash += [out_dir / "source-index.json", out_dir / "source-verification.json"]
    manifest = {
        "schema_version": "1.0",
        "overall_status": "pass" if args.mode == "final" else "draft",
        "formal_verified": args.mode == "final",
        "mode": args.mode,
        "workflow": "gap-delivery/scripts/gap_workflow.py@3",
        "generator": "gap-delivery/scripts/generate_delivery.py",
        "html_renderer": GENERATOR_ID,
        "analysis_id": data.get("analysis_id"),
        "analysis_version": data.get("analysis_version"),
        "analysis_sha256": _sha256(canonical),
        "quality": quality,
        "source_validation": source_validation_result if args.pack else {"status": "not_performed", "reason": "draft mode source pack was not supplied"},
        "checks": {
            "single_canonical_analysis_used": True,
            "csv_regenerated_from_final_analysis": True,
            "markdown_regenerated_from_final_analysis": True,
            "roadmap_regenerated_from_final_analysis": True,
            "html_generated_by_registered_renderer": True,
            "html_rerender_exact_match": rerender_match,
            "id_and_count_consistency": True,
            "runtime_scripts_packaged": True,
        },
        "artifacts": {p.relative_to(out_dir).as_posix(): {"sha256": _sha256(p), "bytes": p.stat().st_size} for p in files_for_hash},
        "limits": [] if args.mode == "final" else ["draft mode。正式成果物ではない。final gateを通過するまで正式版・検証済みと表現しない。"],
    }
    manifest_path = out_dir / "verification-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Explicit, verified artifact allowlist: never archive arbitrary contents of
    # a reused output directory (such as input YAML, secrets, or stale reports).
    payloads = [*files_for_hash, manifest_path]
    if len({p.resolve() for p in payloads}) != len(payloads):
        raise ValueError("Output archive payload has duplicate file destinations")
    if zip_path.resolve() in {p.resolve() for p in payloads}:
        raise ValueError("Output ZIP must not replace a generated artifact")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for pth in sorted(payloads, key=lambda p: p.relative_to(out_dir).as_posix()):
            if not pth.is_file() or not pth.resolve().is_relative_to(out_dir.resolve()):
                raise ValueError(f"Expected generated artifact missing/outside output directory: {pth}")
            z.write(pth, pth.relative_to(out_dir).as_posix())

    print(json.dumps({
        "status": manifest["overall_status"],
        "formal_verified": manifest["formal_verified"],
        "analysis_id": manifest["analysis_id"],
        "analysis_version": manifest["analysis_version"],
        "output_dir": str(out_dir),
        "zip": str(zip_path),
        "html": str(html_path),
        "manifest": str(manifest_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(cli_main())
    except Exception as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
