#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run(cmd: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def ensure_bundle(bundle_path: Path) -> None:
    if not bundle_path.exists():
        print(f"Bundle not found: {bundle_path}", file=sys.stderr)
        sys.exit(2)

    code, out, err = run(["git", "bundle", "verify", str(bundle_path)])
    if code != 0:
        print("Bundle verification failed", file=sys.stderr)
        print(err or out, file=sys.stderr)
        sys.exit(2)


def import_bundle(bundle_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_name = bundle_path.stem.replace(".bundle", "")
    target = out_dir / f"{repo_name}-recovered"

    if target.exists():
        code, _, err = run(["git", "-C", str(target), "fetch", str(bundle_path), "refs/*:refs/*"])
        if code != 0:
            print(f"Failed to refresh existing recovered repo: {err}", file=sys.stderr)
            sys.exit(1)
        return target

    code, _, err = run(["git", "clone", str(bundle_path), str(target)])
    if code != 0:
        print(f"Failed to clone from bundle: {err}", file=sys.stderr)
        sys.exit(1)
    return target


def write_branch_report(repo_path: Path, output_path: Path) -> None:
    code, out, err = run(["git", "-C", str(repo_path), "for-each-ref", "--format=%(refname:short)|%(objectname:short)|%(subject)", "refs/heads", "refs/remotes"])
    if code != 0:
        print(f"Failed to list refs: {err}", file=sys.stderr)
        sys.exit(1)

    lines = [
        "# Bundle Import Report",
        "",
        f"Recovered Repository: {repo_path}",
        "",
        "| Ref | Commit | Subject |",
        "|---|---|---|",
    ]
    for row in out.splitlines():
        parts = row.split("|", 2)
        if len(parts) < 3:
            continue
        ref, commit, subject = parts
        lines.append(f"| {ref} | {commit} | {subject.replace('|', '/')} |")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and inspect a git bundle for recovery.")
    parser.add_argument("--bundle", required=True, help="Path to .bundle file")
    parser.add_argument("--out", default="tools/repo_recovery/recovered", help="Directory for recovered repository")
    parser.add_argument("--report", default="tools/repo_recovery/output/bundle_import_report.md", help="Path for branch/ref report")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    out_dir = Path(args.out)
    report_path = Path(args.report)

    ensure_bundle(bundle_path)
    recovered_repo = import_bundle(bundle_path, out_dir)
    write_branch_report(recovered_repo, report_path)

    print(f"Bundle imported to: {recovered_repo}")
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    main()
