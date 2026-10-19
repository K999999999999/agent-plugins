"""Behavior tests for the Harness state command."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
PLUGIN_TOOLS = PLUGIN / "plugins/engineering-workflow/tools"
sys.path.insert(0, str(PLUGIN_TOOLS))
from harness_lib.state import HarnessError, transition_stage


CLI = PLUGIN_TOOLS / "harness.py"
ITEM = "sample-work"


class HarnessProject:
    def __init__(self, base: Path, *, stage: str = "实施中", candidate_required: bool = False) -> None:
        self.repo = base / "repo"
        self.repo.mkdir()
        self.adapter_path = self.repo / ".harness" / "project.json"
        self.adapter_path.parent.mkdir()
        adapter = {
            "schema_version": 1,
            "repository": "example.test/acme/sample",
            "work_item_record_directory": "harness/work-items",
            "workflow": {
                "stages": ["需求澄清", "实施中", "验证 / Review"],
                "transitions": [
                    {
                        "from": "实施中",
                        "to": "验证 / Review",
                        "required_evidence": ["candidate"],
                        "candidate_required": candidate_required,
                    }
                ],
            },
        }
        self.adapter_path.write_text(
            json.dumps(adapter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self._git("init", "-q", "-b", "master")
        self._git("config", "user.name", "Harness Test")
        self._git("config", "user.email", "harness-test@example.invalid")
        self._git("add", ".harness/project.json")
        self._git("commit", "-qm", "test adapter")
        self.record = self.common_dir() / "harness/work-items" / ITEM / "status.md"
        self.record.parent.mkdir(parents=True)
        self.record.write_text(
            "# Work item\n"
            f"ID: {ITEM}\n"
            "Status: in-progress\n"
            f"Stage: {stage}\n"
            "Last updated: 2026-10-19T13:00:00+08:00\n"
            "Implementation authorization: local implementation only\n"
            "Publication authorization: None\n"
            "Owner: test\n"
            "Next: exercise the Harness CLI\n",
            encoding="utf-8",
        )
        self.linked = base / "linked"
        self._git("worktree", "add", "-q", "-b", "linked-test", str(self.linked))

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def common_dir(self) -> Path:
        value = self._git("rev-parse", "--path-format=absolute", "--git-common-dir")
        return Path(value).resolve()

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--project-root",
                str(self.linked),
                *args,
                "--work-item",
                ITEM,
            ],
            capture_output=True,
            text=True,
        )

    def migrate(self) -> None:
        result = self.run("migrate", "--expected-sha", digest(self.record))
        if result.returncode:
            raise AssertionError(result.stderr or result.stdout)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_candidate_evidence() -> str:
    return json.dumps(
        [
            {
                "type": "candidate",
                "verification": "attested",
                "verified_by": "current-agent",
                "source": "local candidate review",
                "repository": "example.test/acme/sample",
                "subject": "abc123",
                "collected_at": "2026-10-19T13:00:00+08:00",
                "coverage": ["worktree", "staged", "commit"],
            }
        ]
    )


class HarnessStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = HarnessProject(self.base)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_status_reads_legacy_without_mutating_it_and_supports_linked_worktree(self) -> None:
        original = self.project.record.read_bytes()
        result = self.project.run("state", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stage"], "实施中")
        self.assertTrue(payload["legacy_read_only"])
        self.assertEqual(payload["git_common_dir"], str(self.project.common_dir()))
        self.assertEqual(self.project.record.read_bytes(), original)

    def test_missing_adapter_is_reported_without_falling_back_to_success(self) -> None:
        plain = self.base / "plain"
        plain.mkdir()
        (plain / ".env").write_text("SECRET=canary-value\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(CLI), "--project-root", str(plain), "state", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["connected"])
        self.assertNotIn("canary-value", result.stdout + result.stderr)

    def test_explicit_migration_preserves_original_and_legal_transition_is_readable(self) -> None:
        original = self.project.record.read_bytes()
        self.project.migrate()
        backup = self.project.record.with_name(
            f"status.md.pre-harness-{hashlib.sha256(original).hexdigest()}.bak"
        )
        self.assertEqual(backup.read_bytes(), original)
        migrated = self.project.run("state", "--json")
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertFalse(json.loads(migrated.stdout)["legacy_read_only"])

        expected = digest(self.project.record)
        moved = self.project.run(
            "transition",
            "--to",
            "验证 / Review",
            "--next",
            "复核当前候选与验证范围",
            "--expected-sha",
            expected,
            "--evidence-json",
            valid_candidate_evidence(),
        )
        self.assertEqual(moved.returncode, 0, moved.stderr or moved.stdout)
        state = json.loads(self.project.run("state", "--json").stdout)
        self.assertEqual(state["stage"], "验证 / Review")
        self.assertEqual(state["next"], "复核当前候选与验证范围")
        self.assertEqual(state["revision"], 1)
        self.assertEqual(len(state["transition_history"]), 1)

    def test_rejected_transition_stale_digest_and_existing_lock_leave_original_unchanged(self) -> None:
        self.project.migrate()
        original = self.project.record.read_bytes()
        claimed_machine = valid_candidate_evidence().replace('"attested"', '"machine-verified"')
        forged_evidence = self.project.run(
            "transition",
            "--to",
            "验证 / Review",
            "--next",
            "继续复核",
            "--expected-sha",
            digest(self.project.record),
            "--evidence-json",
            claimed_machine,
        )
        self.assertNotEqual(forged_evidence.returncode, 0)
        self.assertIn("不能伪装机器核实", forged_evidence.stderr)
        self.assertEqual(self.project.record.read_bytes(), original)

        unverified = valid_candidate_evidence().replace('"attested"', '"unverified"')
        unsupported_evidence = self.project.run(
            "transition",
            "--to",
            "验证 / Review",
            "--next",
            "继续复核",
            "--expected-sha",
            digest(self.project.record),
            "--evidence-json",
            unverified,
        )
        self.assertNotEqual(unsupported_evidence.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), original)

        invalid = self.project.run(
            "transition",
            "--to",
            "完成",
            "--next",
            "继续复核",
            "--expected-sha",
            digest(self.project.record),
            "--evidence-json",
            valid_candidate_evidence(),
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), original)

        stale = self.project.run(
            "transition",
            "--to",
            "验证 / Review",
            "--next",
            "继续复核",
            "--expected-sha",
            "0" * 64,
            "--evidence-json",
            valid_candidate_evidence(),
        )
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), original)

        lock = self.project.record.with_name(self.project.record.name + ".lock")
        lock.write_text("owner=unverified\n", encoding="utf-8")
        locked = self.project.run(
            "transition",
            "--to",
            "验证 / Review",
            "--next",
            "继续复核",
            "--expected-sha",
            digest(self.project.record),
            "--evidence-json",
            valid_candidate_evidence(),
        )
        self.assertNotEqual(locked.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), original)
        self.assertTrue(lock.exists())

    def test_failed_atomic_replace_keeps_original_and_cleans_only_its_temporary_files(self) -> None:
        self.project.migrate()
        original = self.project.record.read_bytes()
        with patch("harness_lib.state.os.replace", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                transition_stage(
                    self.project.linked,
                    None,
                    ITEM,
                    "验证 / Review",
                    digest(self.project.record),
                    valid_candidate_evidence(),
                    "复核候选",
                )
        self.assertEqual(self.project.record.read_bytes(), original)
        self.assertFalse(self.project.record.with_name("status.md.lock").exists())
        self.assertEqual(list(self.project.record.parent.glob(".status.md.*.tmp")), [])

    def test_simultaneous_writer_cannot_enter_while_another_writer_holds_lock(self) -> None:
        self.project.migrate()
        expected = digest(self.project.record)
        entered_replace = threading.Event()
        finish_replace = threading.Event()
        real_replace = os.replace

        def pause_before_replace(source, target):
            entered_replace.set()
            if not finish_replace.wait(timeout=3):
                raise TimeoutError("test did not release the first writer")
            real_replace(source, target)

        with ThreadPoolExecutor(max_workers=1) as pool:
            with patch("harness_lib.state.os.replace", side_effect=pause_before_replace):
                first = pool.submit(
                    transition_stage,
                    self.project.linked,
                    None,
                    ITEM,
                    "验证 / Review",
                    expected,
                    valid_candidate_evidence(),
                    next_step="复核候选",
                )
                self.assertTrue(entered_replace.wait(timeout=2))
                with self.assertRaisesRegex(HarnessError, "写锁已存在"):
                    transition_stage(
                        self.project.linked,
                        None,
                        ITEM,
                        "验证 / Review",
                        expected,
                        valid_candidate_evidence(),
                        next_step="复核候选",
                    )
                finish_replace.set()
                first.result(timeout=3)

    def test_runtime_status_is_separate_from_stage(self) -> None:
        self.project.migrate()
        state = json.loads(self.project.run("state", "--json").stdout)
        changed = self.project.run(
            "set-runtime",
            "--status",
            "waiting-user",
            "--reason",
            "需要用户确认影响范围",
            "--expected-sha",
            state["record_sha256"],
        )
        self.assertEqual(changed.returncode, 0, changed.stderr)
        after = json.loads(self.project.run("state", "--json").stdout)
        self.assertEqual(after["stage"], "实施中")
        self.assertEqual(after["runtime_status"], "waiting-user")
        self.assertEqual(after["runtime_reason"], "需要用户确认影响范围")

    def test_duplicate_current_field_is_rejected_without_mutation(self) -> None:
        with self.project.record.open("a", encoding="utf-8") as stream:
            stream.write("Stage: 验证 / Review\n")
        before = self.project.record.read_bytes()
        result = self.project.run("state", "--json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), before)

    def test_historical_body_fields_do_not_override_current_header(self) -> None:
        with self.project.record.open("a", encoding="utf-8") as stream:
            stream.write("\n## History\nStage: 历史阶段\n")
        result = self.project.run("state", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stage"], "实施中")

    def test_unknown_stage_and_unknown_extension_are_rejected_without_write(self) -> None:
        self.project.record.write_text(
            self.project.record.read_text(encoding="utf-8").replace(
                "Stage: 实施中", "Stage: 不存在的阶段"
            ),
            encoding="utf-8",
        )
        before = self.project.record.read_bytes()
        unknown_stage = self.project.run("state", "--json")
        self.assertNotEqual(unknown_stage.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), before)

        self.project.record.write_text(
            "# Work item\n"
            f"ID: {ITEM}\nStatus: in-progress\nStage: 实施中\n"
            "<!-- harness-state-extension:v9 -->\n{}\n"
            "<!-- /harness-state-extension -->\n",
            encoding="utf-8",
        )
        before = self.project.record.read_bytes()
        unknown_format = self.project.run("state", "--json")
        self.assertNotEqual(unknown_format.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), before)

        self.project.record.write_text(
            "# Work item\n"
            f"ID: {ITEM}\nStatus: in-progress\nStage: 实施中\n"
            "<!-- harness-state-extension:vx -->\n{}\n"
            "<!-- /harness-state-extension -->\n",
            encoding="utf-8",
        )
        before = self.project.record.read_bytes()
        malformed_format = self.project.run("state", "--json")
        self.assertNotEqual(malformed_format.returncode, 0)
        self.assertEqual(self.project.record.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
