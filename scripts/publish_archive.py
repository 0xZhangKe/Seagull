#!/usr/bin/env python3
"""Publish a disposable archive checkout's staged files as one root commit."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, text=True, stdout=subprocess.PIPE,
    ).stdout.strip()


def publish_archive(root: Path, message: str) -> bool:
    """Push the full index; keep HEAD unchanged in this disposable checkout.

    HEAD is the archive revision checked out before modifying files. Its exact
    SHA is the push lease, so an intervening remote update cannot be overwritten.
    An unborn HEAD requires the remote archive branch to still be absent.
    """
    head_result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if head_result.returncode not in (0, 128):
        head_result.check_returncode()
    previous = head_result.stdout.strip() if head_result.returncode == 0 else ""
    tree = git(root, "write-tree")
    if previous:
        # rev-list hides parents beyond a shallow boundary; inspect raw headers.
        headers = git(root, "cat-file", "-p", previous).split("\n\n", 1)[0]
        has_parent = any(line.startswith("parent ") for line in headers.splitlines())
        if not has_parent and tree == git(root, "rev-parse", f"{previous}^{{tree}}"):
            print("Archive snapshot is already up to date.")
            return False

    snapshot = git(
        root,
        "-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit-tree", tree, "-m", message,
    )
    # Omitting -p creates a root commit. Preserve all indexed files, including
    # unchanged data written by other workflows, without retaining old commits.
    git(
        root, "push", f"--force-with-lease=refs/heads/archive:{previous}",
        "origin", f"{snapshot}:refs/heads/archive",
    )
    print(f"Published archive snapshot {snapshot}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    try:
        changed = publish_archive(args.archive_root, args.message)
    except subprocess.CalledProcessError as error:
        print(f"Archive publication failed: {error}", file=sys.stderr)
        return 1
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"changed={str(changed).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
