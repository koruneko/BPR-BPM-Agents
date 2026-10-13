#!/usr/bin/env python3
"""Package tracked Skill source folders as Agent Builder-ready ZIPs.

Designed for public source checkouts. It does not include sample-outputs,
user input files, generated reports, hidden files, or unrelated repository files.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "bpm": ("bpm-agent", (
        "business-process-modeler",
        "business-process-reviewer",
        "business-process-publisher",
    )),
    "bpr": ("bpr-agent", (
        "business-process-improvement-analyst",
        "business-process-improvement-report-publisher",
        "business-process-tobe-modeler",
        "business-process-reviewer",
        "business-process-publisher",
    )),
    "gap": ("to-be-gap-analyst-agent", (
        "bpr-gap-analysis",
        "gap-planning",
        "gap-business-calendar",
        "gap-delivery",
        "gap-report-format",
    )),
}
SUPPORT_FOLDERS = {"scripts", "resources", "references"}
SUPPORT_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".csv", ".xml", ".html", ".puml", ".svg"}
MAX_PACKAGE_SIZE = 50 * 1024 * 1024


def package(source: Path, destination: Path) -> tuple[int, int]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"Missing or invalid Skill folder: {source}")
    main = source / "SKILL.md"
    if not main.is_file() or main.is_symlink():
        raise ValueError(f"Missing regular SKILL.md: {source}")
    files = [main]
    for dirname in sorted(SUPPORT_FOLDERS):
        directory = source / dirname
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Invalid support folder: {directory}")
        for item in sorted(directory.rglob("*")):
            parts = item.relative_to(source).parts
            if item.is_symlink():
                raise ValueError(f"Symlink not allowed in a Skill ZIP: {item}")
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            if item.is_file():
                if item.suffix.lower() not in SUPPORT_EXTENSIONS:
                    raise ValueError(f"Unexpected file extension in Skill sources: {item}")
                files.append(item)
    total = sum(p.stat().st_size for p in files)
    if total > MAX_PACKAGE_SIZE:
        raise ValueError(f"Skill package exceeds 50 MB: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            path = item.relative_to(source).as_posix()
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, item.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        if not names or names[0] != "SKILL.md" or len(names) != len(set(names)):
            destination.unlink(missing_ok=True)
            raise ValueError(f"Invalid Skill ZIP structure: {destination}")
    return len(files), total


def main() -> int:
    parser = argparse.ArgumentParser(description="Create independent SKILL.md-root ZIP packages for Agent Builder")
    parser.add_argument("--agent", choices=[*SKILLS, "all"], required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "skills")
    args = parser.parse_args()
    agents = SKILLS if args.agent == "all" else {args.agent: SKILLS[args.agent]}
    for _key, (agent_dir, skills) in agents.items():
        for name in skills:
            source = ROOT / agent_dir / name
            destination = args.output_dir / agent_dir / f"{name}.zip"
            count, byte_count = package(source, destination)
            print(f"{destination.relative_to(ROOT) if destination.is_relative_to(ROOT) else destination} ({count} files, {byte_count} bytes)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"Skill package creation failed: {exc}", file=sys.stderr)
        sys.exit(1)
