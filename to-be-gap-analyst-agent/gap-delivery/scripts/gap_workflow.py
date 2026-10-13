"""Formal Gap Analysis workflow entry point.

The model should call this script instead of inventing orchestration code.

Commands:
  prepare  Build a deterministic source pack, source index and analysis template.
  calendar Calculate a verified Japanese-business-day span for dialogue planning.
  draft    Generate a clearly non-formal package for an in-progress analysis.
  final    Run the formal source-verified delivery gate and create the final package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from business_calendar import SOURCE, VERIFIED_ON, HOLIDAYS, business_span
from inspect_sources import inspect, pack_files

WORKFLOW_ID = "gap-delivery/scripts/gap_workflow.py@3"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def infer_role(name: str) -> str:
    base = Path(name).name.lower()
    if base == "process.yaml" or base == "process.yml":
        return "as_is_process"
    if base in {"to-be-process.yaml", "to-be-process.yml"}:
        return "to_be_process"
    if base in {"improvement-analysis.yaml", "improvement-analysis.yml"}:
        return "improvement_analysis"
    if base in {"improvement-decisions.yaml", "improvement-decisions.yml"}:
        return "improvement_decisions"
    return "supporting"


def yaml_metadata(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        obj = yaml.safe_load(text)
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, Any] = {}
    for container in (obj, obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("id", "process_id", "analysis_id", "version", "analysis_version"):
            if key in container and key not in out:
                out[key] = container[key]
    process = obj.get("process")
    if isinstance(process, dict):
        for key in ("id", "version", "scope"):
            if key in process and key not in out:
                out[key] = process[key]
    return out


def build_pack(source_paths: list[Path]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for path in source_paths:
        if not path.is_file():
            raise ValueError(f"Source file not found: {path}")
        name = path.name
        if name in seen:
            raise ValueError(f"Duplicate source basename is ambiguous: {name}")
        seen.add(name)
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        parts += [
            f"## FILE: {name}",
            f"SHA256: {sha256_bytes(raw)}",
            "BEGIN FILE",
            text.rstrip("\r\n"),
            "END FILE",
            "",
        ]
    return "\n".join(parts)


def ref(file: str, field: str, note: str, evidence_kind: str = "documented") -> dict[str, Any]:
    return {"file": file, "entity_id": None, "field": field, "note": note, "evidence_kind": evidence_kind}


def make_source_manifest(files: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for name, text in files.items():
        meta = yaml_metadata(text)
        row: dict[str, Any] = {
            "file": name,
            "artifact_role": infer_role(name),
            "read_status": "read_full",
            "read_range": "full",
            "sha256": sha256_bytes(text.encode("utf-8")),
        }
        row.update({k: v for k, v in meta.items() if v is not None})
        rows.append(row)
    return rows


def make_questions(index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    questions: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []
    for n, row in enumerate(index.get("source_question_lineage", []), 1):
        qid = f"Q-{n:03d}"
        sref = ref(row["file"], row["field_path"], "原文の未確認事項")
        questions.append({
            "id": qid,
            "question": row["original_text"],
            "gap_ids": [],
            "source_refs": [sref],
            "respondent_candidate": "未確認",
            "impact": "未整理",
            "status": "open",
            "resolution": None,
            "resolution_source": None,
        })
        lineage.append({**row, "question_id": qid, "status": "open", "resolution_source": None})
    return questions, lineage


def make_mappings(index: dict[str, Any], manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_by_file = {x["file"]: x["artifact_role"] for x in manifest}
    rows: list[dict[str, Any]] = []
    counter = 1
    for file, entity_sets in index.get("entity_sets", {}).items():
        role = role_by_file.get(file)
        if role not in {"as_is_process", "to_be_process"}:
            continue
        side = "as_is_ids" if role == "as_is_process" else "to_be_ids"
        for section, mtype in (("participants", "participant"), ("nodes", "node"), ("edges", "edge")):
            for entity_id in entity_sets.get(section, []):
                row = {
                    "id": f"MAP-{counter:04d}",
                    "type": mtype,
                    "as_is_ids": [],
                    "to_be_ids": [],
                    "change_type": "unmapped",
                    "semantic_delta": "",
                    "improvement_ids": [],
                    "source_refs": [ref(file, f"{section}[id={entity_id}]", "prepareで検出した原本ID")],
                }
                row[side] = [entity_id]
                rows.append(row)
                counter += 1
    return rows


def make_template(pack_path: Path, index_path: Path, files: dict[str, str], index: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    manifest = make_source_manifest(files)
    questions, lineage = make_questions(index)
    mappings = make_mappings(index, manifest)
    dims = {
        key: {"status": "未整理", "summary": "", "gap_ids": [], "question_ids": [], "source_refs": []}
        for key in ("process", "technology", "data", "people", "organization", "rules", "control", "measurement")
    }
    return {
        "schema_version": "1.0",
        "analysis_id": args.analysis_id or "SET-ANALYSIS-ID",
        "analysis_version": args.analysis_version,
        "process_name": args.process_name or "対象業務",
        "status": "provisional",
        "readiness": {"status": "unknown", "reason": "prepare完了。Gap分析と対話は未完了。"},
        "workflow": {
            "prepared_by": WORKFLOW_ID,
            "source_pack_sha256": sha256_path(pack_path),
            "source_index_sha256": sha256_path(index_path),
            "prepared_from_files": [x["file"] for x in manifest],
        },
        "source_manifest": manifest,
        "input_validation": {"status": "pending_semantic_review", "issues": []},
        "mappings": mappings,
        "gaps": [],
        "actions": [],
        "questions": questions,
        "coverage": {
            "source_question_lineage": lineage,
            "improvement_lineage": [
                {"improvement_id": imp, "status": "unmapped", "gap_ids": [], "action_ids": [], "no_gap_reason": None}
                for file, ids in index.get("improvement_sets", {}).items()
                if next((m.get("artifact_role") for m in manifest if m.get("file") == file), None) == "improvement_analysis"
                for imp in ids
            ],
            "mapping_status": "prepare_only_semantic_mapping_required",
        },
        "scope_summary": {"included": "", "excluded": "", "later": "", "external": "", "temporary": ""},
        "analysis_dimensions": dims,
        "next_actions": [],
        "planning_decisions": [],
        "execution_sequence": [],
        "roadmap": [],
        "dialogue": {
            "status": "in_progress",
            "agreed_scope": "",
            "summary": "",
            "deferred_topics": [],
            "confirmation_source": "",
        },
        "change_log": [],
        "verification": {
            "performed": ["source pack generated", "source index generated"],
            "not_performed": ["semantic As-Is/To-Be mapping", "Gap/ACT analysis", "dialogue completion", "formal final verification"],
            "limitations": ["prepareで作成したtemplateは正式成果物ではない"],
        },
    }


def cmd_prepare(args: argparse.Namespace) -> int:
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.pack:
        pack_path = Path(args.pack).resolve()
        if not pack_path.is_file():
            raise ValueError(f"Pack not found: {pack_path}")
        pack_text = read_text(pack_path)
        files = pack_files(pack_text)
        canonical_pack = out / "source-pack.txt"
        canonical_pack.write_text(pack_text, encoding="utf-8")
    else:
        if not args.source:
            raise ValueError("prepare requires --source files or --pack")
        sources = [Path(x).resolve() for x in args.source]
        pack_text = build_pack(sources)
        canonical_pack = out / "source-pack.txt"
        canonical_pack.write_text(pack_text, encoding="utf-8")
        files = pack_files(pack_text)

    index = inspect(files)
    index_path = out / "source-index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    if index.get("unsupported"):
        raise ValueError("Source index contains unsupported content: " + json.dumps(index["unsupported"], ensure_ascii=False))

    roles = {infer_role(name) for name in files}
    required = {"as_is_process", "to_be_process", "improvement_analysis", "improvement_decisions"}
    missing = sorted(required - roles)
    if missing and not args.allow_missing_core:
        raise ValueError("Missing core source roles: " + ", ".join(missing))

    template = make_template(canonical_pack, index_path, files, index, args)
    template_path = out / "gap-analysis.template.json"
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "template_sha256": sha256_path(template_path),
        "workflow": WORKFLOW_ID,
        "status": "prepared",
        "source_pack": str(canonical_pack),
        "source_pack_sha256": sha256_path(canonical_pack),
        "source_index": str(index_path),
        "source_index_sha256": sha256_path(index_path),
        "analysis_template": str(template_path),
        "question_occurrences": len(index.get("source_question_lineage", [])),
        "process_entity_files": sorted(index.get("entity_sets", {}).keys()),
        "missing_core_roles": missing,
    }
    manifest_path = out / "workflow-preparation.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


def verify_preparation(args: argparse.Namespace) -> None:
    """Bind final delivery to a prepare-generated manifest, index and template.

    Hashes document consistency, not cryptographic attestation against a
    malicious local writer. The authoritative source is rechecked in delivery.
    """
    if not args.pack or not args.preparation:
        raise ValueError("final requires --pack and --preparation from gap_workflow.py prepare")
    prep_path=Path(args.preparation).resolve()
    prep=json.loads(prep_path.read_text(encoding="utf-8-sig"))
    if prep.get("workflow")!=WORKFLOW_ID or prep.get("status")!="prepared":
        raise ValueError("Invalid workflow preparation manifest")
    pack_path=Path(args.pack).resolve()
    if Path(prep.get("source_pack", "")).resolve()!=pack_path:
        raise ValueError("The pack is not the prepared source pack")
    if sha256_path(pack_path)!=prep.get("source_pack_sha256"):
        raise ValueError("Prepared source pack hash mismatch")
    index_path=Path(prep.get("source_index", "")).resolve()
    template_path=Path(prep.get("analysis_template", "")).resolve()
    if not index_path.is_file() or sha256_path(index_path)!=prep.get("source_index_sha256"):
        raise ValueError("Prepared source index missing or modified")
    if not template_path.is_file() or sha256_path(template_path)!=prep.get("template_sha256"):
        raise ValueError("Prepared analysis template missing or modified")
    template=json.loads(template_path.read_text(encoding="utf-8-sig"))
    data=json.loads(Path(args.analysis).read_text(encoding="utf-8-sig"))
    required_workflow={
        "prepared_by":WORKFLOW_ID,
        "source_pack_sha256":prep["source_pack_sha256"],
        "source_index_sha256":prep["source_index_sha256"],
        "prepared_from_files":template["workflow"]["prepared_from_files"],
    }
    if template.get("workflow")!=required_workflow or data.get("workflow")!=required_workflow:
        raise ValueError("Final analysis workflow provenance differs from prepared template")
    if data.get("source_manifest")!=template.get("source_manifest"):
        raise ValueError("Final source_manifest differs from prepared original sources")
    if set(x.get("improvement_id") for x in data.get("coverage",{}).get("improvement_lineage",[])) != \
       set(x.get("improvement_id") for x in template.get("coverage",{}).get("improvement_lineage",[])):
        raise ValueError("Improvement lineage differs from prepared original sources")
    # Verify the original pack really yields the same index (no stale/forged index).
    regenerated=inspect(pack_files(read_text(pack_path)))
    indexed=json.loads(index_path.read_text(encoding="utf-8-sig"))
    if regenerated!=indexed:
        raise ValueError("Source index does not match original prepared pack")
    if make_source_manifest(pack_files(read_text(pack_path))) != template.get("source_manifest"):
        raise ValueError("Prepared manifest disagrees with original pack")


def run_delivery(args: argparse.Namespace, mode: str) -> int:
    import generate_delivery
    # Check all cleanup paths, including custom ZIP and inputs, before unlinking
    # anything. The generator repeats this guard for direct draft callers.
    options=argparse.Namespace(
        mode=mode, analysis=args.analysis, output_dir=args.output_dir,
        pack=args.pack, preparation=getattr(args, "preparation", None),
        title=args.title, report_view=args.report_view, zip_path=args.zip_path,
    )
    out, zip_path = generate_delivery.validate_delivery_paths(options)
    if mode=="final":
        out.mkdir(parents=True, exist_ok=True)
        # Invalidating previous "pass" diagnostics is essential even if the
        # prepare-manifest preflight fails before the generator is called.
        for artifact in generate_delivery.generated_artifacts(out):
            if artifact.is_file():
                artifact.unlink()
        shutil.rmtree(out / "scripts", ignore_errors=True)
        if zip_path.is_file():
            zip_path.unlink()
        try:
            verify_preparation(args)
        except Exception as exc:
            (out / "verification-manifest.json").write_text(
                json.dumps({"overall_status": "fail", "formal_verified": False,
                            "mode": "final", "error": str(exc)}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            raise
    return generate_delivery.generate(options)


def cmd_calendar(args: argparse.Namespace) -> int:
    span = business_span(args.start, args.duration, args.extra_holiday or [])
    out = {
        **span,
        "calendar": {
            "mode": "japan_business_days",
            "source": SOURCE,
            "verified_on": VERIFIED_ON,
            "verified_years": sorted(HOLIDAYS),
            "extra_holidays": args.extra_holiday or [],
        },
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prepare, validate and generate a Gap Analysis package through one registered workflow")
    sp = p.add_subparsers(dest="command", required=True)

    prep = sp.add_parser("prepare", help="Create source-pack, source-index and canonical analysis template")
    prep.add_argument("--source", action="append", help="Original UTF-8 source file; repeat for each file")
    prep.add_argument("--pack", help="Existing supported source pack instead of --source")
    prep.add_argument("--output-dir", required=True)
    prep.add_argument("--analysis-id")
    prep.add_argument("--analysis-version", default="1.0")
    prep.add_argument("--process-name")
    prep.add_argument("--allow-missing-core", action="store_true", help="Allow a provisional template when a core source is unavailable")
    prep.set_defaults(func=cmd_prepare)

    cal = sp.add_parser("calendar", help="Calculate one verified business-day span")
    cal.add_argument("--start", required=True)
    cal.add_argument("--duration", required=True, type=int)
    cal.add_argument("--extra-holiday", action="append")
    cal.set_defaults(func=cmd_calendar)

    for name, mode in (("draft", "draft"), ("final", "final")):
        g = sp.add_parser(name, help=("Generate a non-formal in-progress package" if mode == "draft" else "Run the formal final gate and package"))
        g.add_argument("--analysis", required=True)
        g.add_argument("--output-dir", required=True)
        g.add_argument("--pack", required=(mode == "final"))
        g.add_argument("--preparation", required=(mode == "final"), help="workflow-preparation.json produced by prepare")
        g.add_argument("--title")
        g.add_argument("--report-view", choices=("preserve", "full"), default="full")
        g.add_argument("--zip", dest="zip_path")
        g.set_defaults(func=lambda a, m=mode: run_delivery(a, m))
    return p


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "fail", "workflow": WORKFLOW_ID, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
