import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.publish_archive import publish_archive


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_archive.py"


class PublishArchiveTest(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-C", str(root), *args],
            check=True, text=True, capture_output=True,
        ).stdout.strip()

    def write(self, root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, root, message):
        self.git(root, "add", "-A")
        self.git(root, "commit", "-m", message)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.remote.mkdir()
        self.git(self.remote, "init", "--bare", "--initial-branch=main")
        self.seed = self.root / "seed"
        self.seed.mkdir()
        self.git(self.seed, "init", "--initial-branch=main")
        self.git(self.seed, "config", "user.name", "Test")
        self.git(self.seed, "config", "user.email", "test@example.com")
        self.git(self.seed, "remote", "add", "origin", self.remote.as_uri())
        self.write(self.seed, "README.md", "main code")
        self.commit(self.seed, "main")
        self.git(self.seed, "push", "origin", "main")
        self.git(self.seed, "switch", "--orphan", "archive")
        self.files = {
            "catalog.json": "old catalog",
            "source_state.json": "fetch status",
            "rss/example.xml": "RSS content",
            "ai/custom.xml": "AI content",
            "rendered.json": "rendered index",
            "categories/example/1.json": "category page",
            "articles/old.json": "old article",
        }
        for name, content in self.files.items():
            self.write(self.seed, name, content)
        self.commit(self.seed, "initial archive")
        self.write(self.seed, "catalog.json", "current catalog")
        self.commit(self.seed, "second archive version")
        self.git(self.seed, "push", "origin", "archive")
        self.clone_number = 0

    def checkout(self, branch="archive"):
        path = self.root / f"checkout-{self.clone_number}"
        self.clone_number += 1
        self.git(
            self.root, "clone", "--depth=1", "--single-branch", "--no-tags",
            "--branch", branch, self.remote.as_uri(), str(path),
        )
        return path

    def assert_snapshot(self):
        self.assertEqual("1", self.git(self.remote, "rev-list", "--count", "archive"))
        headers = self.git(self.remote, "cat-file", "-p", "archive").split("\n\n", 1)[0]
        self.assertFalse(any(line.startswith("parent ") for line in headers.splitlines()))

    def test_shallow_legacy_history_is_cut_even_without_file_changes(self):
        checkout = self.checkout()
        self.assertEqual("true", self.git(checkout, "rev-parse", "--is-shallow-repository"))
        previous_tree = self.git(self.remote, "rev-parse", "archive^{tree}")
        main = self.git(self.remote, "rev-parse", "main")
        self.assertTrue(publish_archive(checkout, "migrate"))
        self.assert_snapshot()
        self.assertEqual(previous_tree, self.git(self.remote, "rev-parse", "archive^{tree}"))
        self.assertEqual(main, self.git(self.remote, "rev-parse", "main"))

    def test_successive_updates_preserve_other_data_and_staged_deletions(self):
        for name, content in (
            ("catalog.json", "new catalog"),
            ("rss/example.xml", "updated RSS"),
            ("rendered.json", "new rendering"),
        ):
            checkout = self.checkout()
            self.write(checkout, name, content)
            self.git(checkout, "add", name)
            if name == "rendered.json":
                self.git(checkout, "rm", "articles/old.json")
                self.write(checkout, "articles/new.json", "new article")
                self.git(checkout, "add", "articles/new.json")
            self.assertTrue(publish_archive(checkout, f"update {name}"))
            self.assert_snapshot()
            self.assertEqual(content, self.git(self.remote, "show", f"archive:{name}"))
            self.assertEqual("AI content", self.git(self.remote, "show", "archive:ai/custom.xml"))
        paths = self.git(self.remote, "ls-tree", "-r", "--name-only", "archive").splitlines()
        self.assertNotIn("articles/old.json", paths)
        self.assertIn("articles/new.json", paths)
        self.assertEqual("updated RSS", self.git(self.remote, "show", "archive:rss/example.xml"))
        self.assertEqual("new catalog", self.git(self.remote, "show", "archive:catalog.json"))

    def test_unchanged_root_snapshot_skips_push(self):
        publish_archive(self.checkout(), "migrate")
        previous = self.git(self.remote, "rev-parse", "archive")
        self.assertFalse(publish_archive(self.checkout(), "no changes"))
        self.assertEqual(previous, self.git(self.remote, "rev-parse", "archive"))

    def test_initial_archive_from_shallow_main_worktree(self):
        self.git(self.remote, "update-ref", "-d", "refs/heads/archive")
        main = self.checkout("main")
        archive = self.root / "archive-worktree"
        self.git(main, "worktree", "add", "--detach", str(archive))
        self.git(archive, "switch", "--orphan", "archive")
        self.write(archive, "catalog.json", "first catalog")
        self.git(archive, "add", "catalog.json")
        self.assertTrue(publish_archive(archive, "initial snapshot"))
        self.assert_snapshot()
        self.assertEqual("catalog.json", self.git(self.remote, "ls-tree", "--name-only", "archive"))
        self.assertEqual("main code", self.git(main, "show", "HEAD:README.md"))

    def test_shallow_archive_worktree_can_fetch_and_replace_unrelated_snapshots(self):
        main = self.checkout("main")
        archive = self.root / "archive-worktree"
        for number in range(2):
            self.git(
                main, "fetch", "--depth=1", "--no-tags", "origin",
                "+refs/heads/archive:refs/remotes/origin/archive",
            )
            self.git(main, "worktree", "add", "--detach", str(archive), "origin/archive")
            self.write(archive, "catalog.json", f"catalog {number}")
            self.git(archive, "add", "catalog.json")
            self.assertTrue(publish_archive(archive, f"snapshot {number}"))
            self.assert_snapshot()
            self.assertEqual("RSS content", self.git(self.remote, "show", "archive:rss/example.xml"))
            self.git(main, "worktree", "remove", "--force", str(archive))
        self.assertEqual("main code", self.git(main, "show", "HEAD:README.md"))

    def test_remote_update_is_not_overwritten_even_after_background_fetch(self):
        checkout = self.checkout()
        self.write(checkout, "catalog.json", "stale writer")
        self.git(checkout, "add", "catalog.json")
        self.write(self.seed, "catalog.json", "other writer")
        self.commit(self.seed, "concurrent change")
        self.git(self.seed, "push", "origin", "archive")
        expected = self.git(self.remote, "rev-parse", "archive")
        self.git(checkout, "fetch", "--depth=1", "origin", "archive")
        with self.assertRaises(subprocess.CalledProcessError):
            publish_archive(checkout, "must reject stale snapshot")
        self.assertEqual(expected, self.git(self.remote, "rev-parse", "archive"))

    def test_initial_creation_lease_rejects_existing_branch(self):
        main = self.checkout("main")
        self.git(main, "switch", "--orphan", "archive")
        self.write(main, "catalog.json", "first catalog")
        self.git(main, "add", "catalog.json")
        expected = self.git(self.remote, "rev-parse", "archive")
        with self.assertRaises(subprocess.CalledProcessError):
            publish_archive(main, "must not overwrite existing branch")
        self.assertEqual(expected, self.git(self.remote, "rev-parse", "archive"))

    def run_cli(self, checkout):
        output = self.root / "github-output"
        output.write_text("", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--archive-root", str(checkout), "--message", "snapshot"],
            env={**os.environ, "GITHUB_OUTPUT": str(output)},
            text=True, capture_output=True,
        )
        return result, output.read_text(encoding="utf-8")

    def test_cli_reports_changes_only_after_successful_push(self):
        result, output = self.run_cli(self.checkout())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("changed=true\n", output)
        result, output = self.run_cli(self.checkout())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("changed=false\n", output)
        stale = self.checkout()
        newer = self.checkout()
        self.write(newer, "catalog.json", "newer writer")
        self.git(newer, "add", "catalog.json")
        publish_archive(newer, "concurrent snapshot")
        self.write(stale, "catalog.json", "stale writer")
        self.git(stale, "add", "catalog.json")
        result, output = self.run_cli(stale)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", output)


if __name__ == "__main__":
    unittest.main()
