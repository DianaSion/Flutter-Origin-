#!/usr/bin/env python3
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANNEL_PATH = "tools/branch_hub/BRANCH_BROADCAST.md"
UNIFIED_PATH = REPO_ROOT / "tools/branch_hub/UNIFIED_STREAM.md"


def run(cmd):
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def current_branch():
    code, out, err = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        raise RuntimeError(err or "Unable to get current branch")
    return out


def append_broadcast(author, message):
    path = REPO_ROOT / CHANNEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    branch = current_branch()

    if not path.exists():
        path.write_text(
            "# Branch Broadcast\n\n"
            "Messages written on a branch are visible from any other branch via branch_hub aggregate.\n\n",
            encoding="utf-8",
        )

    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {ts} | branch={branch} | author={author} | {message}\n")

    print(f"Broadcast appended to {CHANNEL_PATH}")


def list_refs(include_remote):
    refs = ["refs/heads"]
    if include_remote:
        refs.append("refs/remotes/origin")
    code, out, err = run(["git", "for-each-ref", "--format=%(refname:short)", *refs])
    if code != 0:
        raise RuntimeError(err or "Unable to list branches")

    branch_refs = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.endswith("/HEAD"):
            continue
        branch_refs.append(line)
    return sorted(set(branch_refs))


def safe_show(ref, path):
    code, out, _ = run(["git", "show", f"{ref}:{path}"])
    if code != 0:
        return None
    return out


def latest_commits(ref, limit):
    code, out, _ = run(["git", "log", "--oneline", f"-n{limit}", ref])
    if code != 0:
        return []
    return out.splitlines()


def aggregate(include_remote, commit_limit, output_path):
    refs = list_refs(include_remote)
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = [
        "# Unified Branch Stream",
        "",
        "This file is generated. It lets one branch hear all branches.",
        f"Generated at: {now}",
        "",
    ]

    for ref in refs:
        lines.append(f"## {ref}")
        lines.append("")

        broadcast = safe_show(ref, CHANNEL_PATH)
        if broadcast:
            lines.append("### Broadcast")
            lines.append("")
            lines.extend(broadcast.splitlines())
            lines.append("")

        lines.append("### Recent Commits")
        lines.append("")
        commits = latest_commits(ref, commit_limit)
        if not commits:
            lines.append("- (no commits visible)")
        else:
            for c in commits:
                lines.append(f"- {c}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Unified stream written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Cross-branch broadcast and aggregation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("broadcast", help="Write a message on current branch")
    b.add_argument("--author", required=True)
    b.add_argument("--message", required=True)

    a = sub.add_parser("aggregate", help="Collect messages and commits from all branches")
    a.add_argument("--include-remote", action="store_true", help="Include origin/* refs")
    a.add_argument("--commit-limit", type=int, default=5)
    a.add_argument("--output", default=str(UNIFIED_PATH))

    h = sub.add_parser("hear", help="Alias for aggregate (one branch hears all)")
    h.add_argument("--include-remote", action="store_true", help="Include origin/* refs")
    h.add_argument("--commit-limit", type=int, default=5)
    h.add_argument("--output", default=str(UNIFIED_PATH))

    args = parser.parse_args()
    try:
        if args.cmd == "broadcast":
            append_broadcast(args.author, args.message)
        elif args.cmd in {"aggregate", "hear"}:
            aggregate(args.include_remote, args.commit_limit, Path(args.output))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
