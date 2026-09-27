#!/usr/bin/env python3
"""Structured YAML validator + canonical renderer for Material Business Rule Gate.

v1.1 moves recommendation state into one explicit recommendation mapping and
validates source-question lineage against improvement-analysis.yaml. The YAML is
the machine contract; rendered Markdown is a canonical reference, not a rule
that the conversational model must reproduce verbatim.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

QUESTION_RE = re.compile(r"(?ms)^###\s+(\d+)\.\s+.*?(?=^###\s+\d+\.\s+|\Z)")
RECOMMENDED_HEADING_RE = re.compile(r"(?m)^####\s+【推奨】([A-Z]):\s+(.+)$")
OPTION_HEADING_RE = re.compile(r"(?m)^####\s+(?:【推奨】)?([A-Z]):\s+(.+)$")
NO_REC_RE = re.compile(r"(?m)^\*\*推奨なし\*\*\s*$")
REASON_RE = re.compile(r"(?m)^推奨理由:\s*\S.+$")
NO_REC_REASON_RE = re.compile(r"(?m)^理由:\s*\S.+$")

TOP_KEYS = {"gate_version", "analysis_id", "intro", "questions", "footer_note"}
QUESTION_KEYS = {"id", "source_refs", "question", "recommendation", "options"}
SOURCE_REF_KEYS = {"source", "question"}
RECOMMENDATION_KEYS = {"status", "option_id", "rationale", "basis", "confidence", "provisional"}
OPTION_KEYS = {"id", "label", "explanation"}
RECOMMENDATION_STATUS = {"recommended", "none"}
RECOMMENDATION_BASIS = {"source_evidence", "design_consistency", "minimal_change", "control_safety", "other"}
CONFIDENCE = {"low", "medium", "high"}


def _result(ok: bool, errors: list[str], **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"ok": ok, "errors": errors}
    data.update(extra)
    return data


def _unknown_keys(obj: dict[str, Any], allowed: set[str], prefix: str) -> list[str]:
    return [f"{prefix}: unknown_key_{key}" for key in obj if key not in allowed]


def _nonblank_after(lines: list[str], idx: int) -> str | None:
    for j in range(idx + 1, len(lines)):
        if lines[j].strip():
            return lines[j].strip()
    return None


def _load_yaml(path: str) -> Any:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _analysis_question_map(analysis: Any) -> tuple[str, dict[str, set[str]]]:
    if not isinstance(analysis, dict):
        return "", {}
    analysis_id = str(analysis.get("analysis_id", "")).strip()
    mapping: dict[str, set[str]] = {}
    for imp in analysis.get("improvements") or []:
        if not isinstance(imp, dict):
            continue
        iid = str(imp.get("id", "")).strip()
        if not iid:
            continue
        mapping[iid] = {str(q).strip() for q in (imp.get("unresolved_questions") or []) if str(q).strip()}
    mapping["analysis"] = {str(q).strip() for q in (analysis.get("analysis_open_questions") or []) if str(q).strip()}
    return analysis_id, mapping


def validate_markdown(text: str) -> dict[str, Any]:
    """Validate the canonical renderer output only.

    This is intentionally not a conversational-response validator. The Agent may
    phrase the user-facing response naturally, provided the recommendation
    semantics remain consistent with the validated YAML contract.
    """
    errors: list[str] = []
    matches = list(QUESTION_RE.finditer(text))
    if not matches:
        return _result(False, ["no_material_gate_questions_found"], question_count=0)

    recommended_count = 0
    no_recommendation_count = 0

    for match in matches:
        qid = match.group(1)
        q = match.group(0)
        recommended = RECOMMENDED_HEADING_RE.findall(q)
        option_ids = OPTION_HEADING_RE.findall(q)
        option_letters = [x[0] for x in option_ids]
        no_rec = bool(NO_REC_RE.search(q))
        reasons = REASON_RE.findall(q)
        no_rec_reasons = NO_REC_REASON_RE.findall(q)

        if len(option_letters) < 2:
            errors.append(f"question_{qid}: at_least_two_options_required")
        if len(set(option_letters)) != len(option_letters):
            errors.append(f"question_{qid}: duplicate_option_ids")

        if no_rec:
            no_recommendation_count += 1
            if recommended:
                errors.append(f"question_{qid}: no_recommendation_but_recommended_heading_present")
            if reasons:
                errors.append(f"question_{qid}: no_recommendation_but_recommendation_reason_present")
            if len(no_rec_reasons) != 1:
                errors.append(f"question_{qid}: no_recommendation_requires_exactly_one_reason; found={len(no_rec_reasons)}")
        else:
            if len(recommended) != 1:
                errors.append(f"question_{qid}: exactly_one_recommended_heading_required; found={len(recommended)}")
            else:
                recommended_count += 1
            if len(reasons) != 1:
                errors.append(f"question_{qid}: recommendation_requires_exactly_one_reason; found={len(reasons)}")
            if no_rec_reasons:
                errors.append(f"question_{qid}: recommendation_question_must_not_use_plain_reason_label")

        lines = q.splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^####\s+【推奨】[A-Z]:\s+.+$", line):
                nxt = _nonblank_after(lines, i)
                if not nxt or not nxt.startswith("推奨理由:"):
                    errors.append(f"question_{qid}: recommendation_reason_must_immediately_follow_recommended_heading")
            if line.strip() == "**推奨なし**":
                nxt = _nonblank_after(lines, i)
                if not nxt or not nxt.startswith("理由:"):
                    errors.append(f"question_{qid}: no_recommendation_reason_must_immediately_follow_marker")

    return _result(
        not errors,
        errors,
        question_count=len(matches),
        recommended_question_count=recommended_count,
        no_recommendation_question_count=no_recommendation_count,
    )


def validate_input(data: Any, analysis: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    summary: dict[str, Any] = {
        "question_count": 0,
        "recommended_question_count": 0,
        "no_recommendation_question_count": 0,
        "source_ref_count": 0,
        "recommendations": {},
    }
    if not isinstance(data, dict):
        return ["root_must_be_mapping"], summary
    errors.extend(_unknown_keys(data, TOP_KEYS, "root"))
    if str(data.get("gate_version", "")) != "1.1":
        errors.append("gate_version_must_be_1.1")

    analysis_id, source_map = _analysis_question_map(analysis)
    supplied_analysis_id = str(data.get("analysis_id", "")).strip()
    if not supplied_analysis_id:
        errors.append("analysis_id_required")
    if not analysis_id:
        errors.append("analysis_yaml_missing_analysis_id")
    elif supplied_analysis_id and supplied_analysis_id != analysis_id:
        errors.append("analysis_id_mismatch")

    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("questions_must_be_nonempty_list")
        return errors, summary

    summary["question_count"] = len(questions)
    seen_qids: set[str] = set()
    seen_source_refs: set[tuple[str, str]] = set()

    for idx, q in enumerate(questions, 1):
        prefix = f"question_{idx}"
        if not isinstance(q, dict):
            errors.append(f"{prefix}: must_be_mapping")
            continue
        errors.extend(_unknown_keys(q, QUESTION_KEYS, prefix))

        qid = str(q.get("id", "")).strip()
        if not re.fullmatch(r"\d+", qid):
            errors.append(f"{prefix}: id_must_be_numeric_string")
        elif qid in seen_qids:
            errors.append(f"{prefix}: duplicate_question_id_{qid}")
        else:
            seen_qids.add(qid)
        if not str(q.get("question", "")).strip():
            errors.append(f"{prefix}: question_required")

        source_refs = q.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            errors.append(f"{prefix}: source_refs_must_be_nonempty_list")
        else:
            for sidx, ref in enumerate(source_refs, 1):
                sp = f"{prefix}_source_ref_{sidx}"
                if not isinstance(ref, dict):
                    errors.append(f"{sp}: must_be_mapping")
                    continue
                errors.extend(_unknown_keys(ref, SOURCE_REF_KEYS, sp))
                source = str(ref.get("source", "")).strip()
                source_question = str(ref.get("question", "")).strip()
                if not source:
                    errors.append(f"{sp}: source_required")
                elif source != "design" and source != "analysis" and not re.fullmatch(r"IMP-\d{3}", source):
                    errors.append(f"{sp}: source_must_be_improvement_id_analysis_or_design")
                if not source_question:
                    errors.append(f"{sp}: question_required")
                pair = (source, source_question)
                if source and source_question:
                    if pair in seen_source_refs:
                        errors.append(f"{sp}: duplicate_source_question_reference")
                    seen_source_refs.add(pair)
                    summary["source_ref_count"] += 1
                if source == "design":
                    continue
                if source and source not in source_map:
                    errors.append(f"{sp}: source_not_found_in_analysis")
                elif source_question and source_question not in source_map.get(source, set()):
                    errors.append(f"{sp}: source_question_must_exactly_match_analysis_unresolved_question")

        options = q.get("options")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"{prefix}: at_least_two_options_required")
            option_ids: list[str] = []
        else:
            option_ids = []
            for j, opt in enumerate(options, 1):
                op = f"{prefix}_option_{j}"
                if not isinstance(opt, dict):
                    errors.append(f"{op}: must_be_mapping")
                    continue
                errors.extend(_unknown_keys(opt, OPTION_KEYS, op))
                oid = str(opt.get("id", "")).strip()
                if not re.fullmatch(r"[A-Z]", oid):
                    errors.append(f"{op}: id_must_be_single_uppercase_letter")
                elif oid in option_ids:
                    errors.append(f"{op}: duplicate_option_id_{oid}")
                option_ids.append(oid)
                if not str(opt.get("label", "")).strip():
                    errors.append(f"{op}: label_required")

        recommendation = q.get("recommendation")
        if not isinstance(recommendation, dict):
            errors.append(f"{prefix}: recommendation_must_be_mapping")
            continue
        errors.extend(_unknown_keys(recommendation, RECOMMENDATION_KEYS, f"{prefix}_recommendation"))
        status = str(recommendation.get("status", "")).strip()
        rationale = str(recommendation.get("rationale", "")).strip()
        option_id = str(recommendation.get("option_id", "")).strip()
        basis = str(recommendation.get("basis", "")).strip()
        confidence = str(recommendation.get("confidence", "")).strip()
        provisional = recommendation.get("provisional")

        if status not in RECOMMENDATION_STATUS:
            errors.append(f"{prefix}: recommendation_status_must_be_recommended_or_none")
        if not rationale:
            errors.append(f"{prefix}: recommendation_rationale_required")
        if basis and basis not in RECOMMENDATION_BASIS:
            errors.append(f"{prefix}: recommendation_basis_invalid")
        if confidence and confidence not in CONFIDENCE:
            errors.append(f"{prefix}: recommendation_confidence_invalid")
        if provisional is not None and not isinstance(provisional, bool):
            errors.append(f"{prefix}: recommendation_provisional_must_be_boolean")

        if status == "recommended":
            summary["recommended_question_count"] += 1
            if option_id not in option_ids:
                errors.append(f"{prefix}: recommendation_option_id_must_match_an_option")
            summary["recommendations"][qid or str(idx)] = {
                "status": "recommended",
                "option_id": option_id or None,
                "rationale": rationale,
                "basis": basis or None,
                "confidence": confidence or None,
                "provisional": provisional if isinstance(provisional, bool) else None,
            }
        elif status == "none":
            summary["no_recommendation_question_count"] += 1
            if option_id:
                errors.append(f"{prefix}: no_recommendation_must_not_have_option_id")
            summary["recommendations"][qid or str(idx)] = {
                "status": "none",
                "option_id": None,
                "rationale": rationale,
                "basis": basis or None,
                "confidence": confidence or None,
                "provisional": provisional if isinstance(provisional, bool) else None,
            }

    return errors, summary


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = ["## Material Business Rule Gate", "", f"分析ID: `{str(data['analysis_id']).strip()}`", ""]
    intro = str(data.get("intro", "")).strip()
    if intro:
        lines.extend([intro, ""])

    questions = data["questions"]
    for q in questions:
        qid = str(q["id"]).strip()
        lines.extend([f"### {qid}. {str(q['question']).strip()}", ""])
        recommendation = q["recommendation"]
        status = str(recommendation["status"]).strip()
        recommended_id = str(recommendation.get("option_id", "")).strip() if status == "recommended" else None
        if status == "none":
            lines.extend(["**推奨なし**", f"理由: {str(recommendation['rationale']).strip()}", ""])

        for opt in q["options"]:
            oid = str(opt["id"]).strip()
            label = str(opt["label"]).strip()
            if recommended_id == oid:
                lines.append(f"#### 【推奨】{oid}: {label}")
                lines.append(f"推奨理由: {str(recommendation['rationale']).strip()}")
            else:
                lines.append(f"#### {oid}: {label}")
            explanation = str(opt.get("explanation", "")).strip()
            if explanation:
                lines.append(explanation)
            lines.append("")

    ids = [str(q["id"]).strip() for q in questions]
    example_parts = [f"{q['id']}:{q['options'][0]['id']}" for q in questions[:2]]
    if len(ids) > 1:
        lines.append(f"回答は `{', '.join(example_parts)}` のようにまとめても、`{ids[0]}:{questions[0]['options'][0]['id']}` のように一部だけ回答しても構いません。")
    else:
        lines.append(f"回答は `{ids[0]}:{questions[0]['options'][0]['id']}` のように指定できます。独自案は文章で指定しても構いません。")
    extra = str(data.get("footer_note", "")).strip()
    if extra:
        lines.extend(["", extra])
    return "\n".join(lines).rstrip() + "\n"


def write_result(path: str | None, result: dict[str, Any]) -> None:
    if path:
        Path(path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_for_validation(args: argparse.Namespace) -> tuple[Any, Any, dict[str, Any] | None]:
    try:
        data = _load_yaml(args.input)
    except Exception as exc:
        return None, None, _result(False, [f"input_parse_error: {exc}"])
    try:
        analysis = _load_yaml(args.analysis)
    except Exception as exc:
        return data, None, _result(False, [f"analysis_parse_error: {exc}"])
    return data, analysis, None


def cmd_validate_input(args: argparse.Namespace) -> int:
    data, analysis, failure = _load_for_validation(args)
    if failure:
        failure["stage"] = "input_validation"
        write_result(args.result, failure)
        print(json.dumps(failure, ensure_ascii=False))
        return 1
    errors, summary = validate_input(data, analysis)
    result = _result(not errors, errors, stage="input_validation", **summary)
    write_result(args.result, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def cmd_render(args: argparse.Namespace) -> int:
    data, analysis, failure = _load_for_validation(args)
    if failure:
        failure["stage"] = "input_validation"
        write_result(args.result, failure)
        print(json.dumps(failure, ensure_ascii=False))
        return 1

    errors, summary = validate_input(data, analysis)
    if errors:
        result = _result(False, errors, stage="input_validation", **summary)
        write_result(args.result, result)
        print(json.dumps(result, ensure_ascii=False))
        return 1

    markdown = render_markdown(data)
    validation = validate_markdown(markdown)
    result = dict(validation)
    result.update(summary)
    result["stage"] = "render_and_validate"
    result["output"] = args.output
    result["machine_contract"] = args.input
    write_result(args.result, result)
    if result["ok"]:
        Path(args.output).write_text(markdown, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def cmd_validate_markdown(args: argparse.Namespace) -> int:
    text = Path(args.input).read_text(encoding="utf-8")
    result = validate_markdown(text)
    result["stage"] = "canonical_markdown_validation"
    write_result(args.result, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate_input = sub.add_parser("validate-input", help="Validate Material Gate structured YAML and source-question lineage")
    p_validate_input.add_argument("--input", required=True)
    p_validate_input.add_argument("--analysis", required=True)
    p_validate_input.add_argument("--result")
    p_validate_input.set_defaults(func=cmd_validate_input)

    p_render = sub.add_parser("render", help="Render canonical Material Gate Markdown from validated structured YAML")
    p_render.add_argument("--input", required=True)
    p_render.add_argument("--analysis", required=True)
    p_render.add_argument("--output", required=True)
    p_render.add_argument("--result")
    p_render.set_defaults(func=cmd_render)

    p_validate_md = sub.add_parser("validate-markdown", help="Validate canonical renderer Markdown (not arbitrary conversational prose)")
    p_validate_md.add_argument("--input", required=True)
    p_validate_md.add_argument("--result")
    p_validate_md.set_defaults(func=cmd_validate_markdown)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
