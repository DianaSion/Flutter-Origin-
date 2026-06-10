#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class RepoRecord:
    raw: str
    slug: str
    clone_url: str
    accessible: bool = False
    viewer_permission: str = ""
    private: Optional[bool] = None
    default_branch: str = ""
    updated_at: str = ""
    mirror_status: str = ""
    error: str = ""


def run(cmd: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def normalize_repo(raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None, None, None

    line = line.rstrip("/")

    m = re.match(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", line)
    if m:
        slug = f"{m.group(1)}/{m.group(2)}"
        return slug, f"https://github.com/{slug}.git", None

    m = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", line)
    if m:
        slug = f"{m.group(1)}/{m.group(2)}"
        return slug, f"https://github.com/{slug}.git", None

    m = re.match(r"^([^/\s]+)/([^/\s]+)$", line)
    if m:
        slug = f"{m.group(1)}/{m.group(2)}"
        return slug, f"https://github.com/{slug}.git", None

    return None, None, f"Could not parse repository: {raw.strip()}"


def ensure_tools() -> None:
    for tool in ["gh", "git"]:
        code, _, _ = run(["bash", "-lc", f"command -v {tool}"])
        if code != 0:
            print(f"Missing required tool: {tool}", file=sys.stderr)
            sys.exit(2)


def gh_repo_view(slug: str) -> Tuple[bool, dict, str]:
    cmd = [
        "gh",
        "repo",
        "view",
        slug,
        "--json",
        "nameWithOwner,isPrivate,defaultBranchRef,viewerPermission,updatedAt,url",
    ]
    code, out, err = run(cmd)
    if code != 0:
        return False, {}, err or out or "Unknown gh error"
    try:
        return True, json.loads(out), ""
    except json.JSONDecodeError:
        return False, {}, "Failed to parse GitHub API output"


def mirror_repo(record: RepoRecord, mirror_root: Path, dry_run: bool) -> str:
    mirror_name = record.slug.replace("/", "__") + ".git"
    mirror_path = mirror_root / mirror_name

    if dry_run:
        if mirror_path.exists():
            return "dry-run: would update mirror"
        return "dry-run: would clone mirror"

    if mirror_path.exists():
        code, _, err = run(["git", "-C", str(mirror_path), "remote", "update", "--prune"])
        if code == 0:
            return "updated"
        return f"update failed: {err}"

    code, _, err = run(["git", "clone", "--mirror", record.clone_url, str(mirror_path)])
    if code == 0:
        return "cloned"
    return f"clone failed: {err}"


def write_report(records: List[RepoRecord], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    ok_path = out_dir / "accessible.txt"
    fail_path = out_dir / "inaccessible.txt"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in records], f, indent=2)

    with ok_path.open("w", encoding="utf-8") as f:
        for r in records:
            if r.accessible:
                f.write(f"{r.slug}\n")

    with fail_path.open("w", encoding="utf-8") as f:
        for r in records:
            if not r.accessible:
                f.write(f"{r.raw} | {r.error}\n")

    lines = [
        "# Repository Recovery Report",
        "",
        "| Repo | Access | Permission | Private | Default Branch | Mirror | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        access = "yes" if r.accessible else "no"
        private = "yes" if r.private else ("no" if r.private is not None else "?")
        notes = r.error.replace("|", "/")[:120]
        lines.append(
            f"| {r.slug or r.raw} | {access} | {r.viewer_permission or '-'} | {private} | "
            f"{r.default_branch or '-'} | {r.mirror_status or '-'} | {notes or '-'} |"
        )

    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory and mirror GitHub repositories you can access.")
    parser.add_argument("--input", required=True, help="Path to text file with one repo per line (owner/repo or URL)")
    parser.add_argument("--output", default="tools/repo_recovery/output", help="Output folder for reports and mirrors")
    parser.add_argument("--mirror", action="store_true", help="Create/update local --mirror clones")
    parser.add_argument("--dry-run", action="store_true", help="Do not clone/update, just report")
    args = parser.parse_args()

    ensure_tools()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.output)
    mirror_root = out_dir / "mirrors"
    if args.mirror:
        mirror_root.mkdir(parents=True, exist_ok=True)

    records: List[RepoRecord] = []

    for raw in input_path.read_text(encoding="utf-8").splitlines():
        slug, clone_url, parse_error = normalize_repo(raw)
        if raw.strip().startswith("#") or not raw.strip():
            continue

        if parse_error:
            records.append(
                RepoRecord(
                    raw=raw,
                    slug="",
                    clone_url="",
                    accessible=False,
                    error=parse_error,
                )
            )
            continue

        record = RepoRecord(raw=raw, slug=slug or "", clone_url=clone_url or "")

        ok, payload, err = gh_repo_view(record.slug)
        if not ok:
            record.accessible = False
            record.error = err
            records.append(record)
            continue

        record.accessible = True
        record.viewer_permission = payload.get("viewerPermission", "")
        record.private = payload.get("isPrivate", None)
        default_branch = payload.get("defaultBranchRef") or {}
        record.default_branch = default_branch.get("name", "")
        record.updated_at = payload.get("updatedAt", "")

        if args.mirror:
            record.mirror_status = mirror_repo(record, mirror_root, args.dry_run)

        records.append(record)

    write_report(records, out_dir)

    total = len(records)
    accessible = len([r for r in records if r.accessible])
    inaccessible = total - accessible
    print(f"Processed {total} repos: {accessible} accessible, {inaccessible} inaccessible")
    print(f"Report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
