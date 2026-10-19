"""Behavior tests for Git candidate identity and evidence validity."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_harness_state import HarnessProject, digest


def run_git(project: HarnessProject, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project.linked), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class HarnessEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_project(self, *, candidate_required: bool = False) -> HarnessProject:
        return HarnessProject(self.base, candidate_required=candidate_required)

    def capture(self, project: HarnessProject, scope: str) -> dict:
        state = json.loads(project.run("state", "--json").stdout)
        if state["legacy_read_only"]:
            project.migrate()
        result = project.run(
            "capture-baseline", "--scope", scope,
            "--expected-sha", digest(project.record),
        )
        if result.returncode:
            raise AssertionError(result.stderr or result.stdout)
        return json.loads(result.stdout)

    def diff(self, project: HarnessProject) -> dict:
        result = project.run("diff", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_diff_reports_committed_staged_unstaged_and_untracked_changes_without_contents(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        committed = project.linked / "src" / "committed.txt"
        committed.parent.mkdir()
        committed.write_text("committed payload\n", encoding="utf-8")
        run_git(project, "add", "src/committed.txt")
        run_git(project, "commit", "-qm", "committed slice")
        self.capture(project, "slice")

        (project.linked / "src/staged.txt").write_text("staged payload\n", encoding="utf-8")
        run_git(project, "add", "src/staged.txt")
        (project.linked / "src/unstaged.txt").write_text("unstaged payload\n", encoding="utf-8")
        (project.linked / "src/untracked.txt").write_text("untracked payload\n", encoding="utf-8")
        (project.linked / ".env").write_text("TOKEN=diff-secret-canary\n", encoding="utf-8")

        report = self.diff(project)
        self.assertEqual(report["candidate"]["repository"], "example.test/acme/sample")
        self.assertEqual(len(report["candidate"]["candidate_fingerprint"]), 64)
        self.assertEqual(report["counts"]["cumulative"], 5)
        self.assertEqual(report["counts"]["slice"], 4)
        self.assertEqual(len(report["candidate"]["head_sha"]), 40)
        self.assertNotIn("diff-secret-canary", json.dumps(report))
        paths = {item["path"] for item in report["files"]}
        self.assertIn("src/committed.txt", paths)
        self.assertIn("src/staged.txt", paths)
        self.assertIn("src/unstaged.txt", paths)
        self.assertIn("src/untracked.txt", paths)
        self.assertIn("[敏感路径已隐藏]", paths)
        self.assertFalse(report["completeness"]["complete"])
        self.assertEqual(report["completeness"]["sensitive_paths_withheld"], 1)

    def test_task_baseline_refuses_dirty_worktree_and_sensitive_content_is_never_read(self) -> None:
        project = self.make_project()
        project.migrate()
        (project.linked / "src/dirty.txt").parent.mkdir()
        (project.linked / "src/dirty.txt").write_text("dirty", encoding="utf-8")
        result = project.run(
            "capture-baseline", "--scope", "task",
            "--expected-sha", digest(project.record),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("工作树", result.stderr)
        state = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(state["revision"], 0)
        self.assertIn("cumulative_baseline_missing", state["diff_completeness"]["stale_reasons"])

    def test_candidate_evidence_is_bound_to_exact_candidate_and_becomes_stale_after_change(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        self.capture(project, "slice")
        report = self.diff(project)
        evidence = {
            "type": "candidate-approval",
            "verification": "attested",
            "verified_by": "user",
            "source": "chat confirmation 2026-10-19T13:00:00+08:00",
            "repository": "example.test/acme/sample",
            "subject": report["candidate"]["candidate_fingerprint"],
            "collected_at": "2026-10-19T13:00:00+08:00",
            "coverage": ["final candidate"],
            "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
            "report_sha256": report["report_sha256"],
        }
        unverified_approval = dict(evidence, verification="unverified")
        refused = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(unverified_approval),
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("attested", refused.stderr)
        recorded = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(evidence),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        current = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(current["evidence_summary"][0]["validity"], "current_candidate_attested")
        self.assertEqual(current["scope_authorization"], "local implementation only")

        input_evidence = dict(evidence)
        input_evidence.update({
            "type": "validation-report",
            "subject": "reports/tests/synthetic.json",
            "input_identity": "caseset-sha256:1234",
        })
        recorded_input = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(input_evidence),
        )
        self.assertEqual(recorded_input.returncode, 0, recorded_input.stderr)
        with_input = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(with_input["evidence_summary"][1]["validity"], "input_identity_needs_recheck")

        changed = project.linked / "src/change.py"
        changed.parent.mkdir()
        changed.write_text("changed after approval\n", encoding="utf-8")
        after_change = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(after_change["evidence_summary"][0]["validity"], "stale_candidate")

    def test_candidate_required_transition_rejects_old_fingerprint_without_writing(self) -> None:
        project = self.make_project(candidate_required=True)
        self.capture(project, "task")
        self.capture(project, "slice")
        report = self.diff(project)
        evidence = {
            "type": "candidate",
            "verification": "attested",
            "verified_by": "agent",
            "source": "current diff report",
            "repository": "example.test/acme/sample",
            "subject": report["candidate"]["candidate_fingerprint"],
            "collected_at": "2026-10-19T13:00:00+08:00",
            "coverage": ["current candidate"],
            "candidate_fingerprint": "0" * 64,
            "report_sha256": report["report_sha256"],
        }
        before = project.record.read_bytes()
        result = project.run(
            "transition", "--to", "验证 / Review", "--next", "review candidate",
            "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps([evidence]),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(project.record.read_bytes(), before)

        evidence["candidate_fingerprint"] = report["candidate"]["candidate_fingerprint"]
        accepted = project.run(
            "transition", "--to", "验证 / Review", "--next", "review candidate",
            "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps([evidence]),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(project.run("state", "--json").stdout)["stage"], "验证 / Review")

    def test_base_branch_movement_changes_candidate_and_lists_upstream_delta(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        self.capture(project, "slice")
        original = self.diff(project)
        evidence = {
            "type": "candidate-approval",
            "verification": "attested",
            "verified_by": "user",
            "source": "chat confirmation",
            "repository": "example.test/acme/sample",
            "subject": original["candidate"]["candidate_fingerprint"],
            "collected_at": "2026-10-19T13:00:00+08:00",
            "coverage": ["current candidate and base"],
            "candidate_fingerprint": original["candidate"]["candidate_fingerprint"],
            "report_sha256": original["report_sha256"],
        }
        recorded = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(evidence),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        base_file = project.repo / "upstream-change.md"
        base_file.write_text("new base state\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project.repo), "add", "upstream-change.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project.repo), "commit", "-qm", "advance base"],
            check=True, capture_output=True,
        )
        moved = self.diff(project)
        self.assertNotEqual(
            original["candidate"]["candidate_fingerprint"],
            moved["candidate"]["candidate_fingerprint"],
        )
        self.assertEqual(moved["counts"]["base_movement"], 1)
        self.assertIn("upstream-change.md", {item["path"] for item in moved["files"]})
        self.assertIn("slice_base_sha_changed", moved["completeness"]["stale_reasons"])
        state = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(state["evidence_summary"][0]["validity"], "stale_candidate")

    @unittest.skipIf(os.name == "nt", "Git executable-bit behavior is platform-specific")
    def test_executable_bit_change_is_part_of_candidate_and_slice_diff(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        script = project.linked / "src/mode.sh"
        script.parent.mkdir()
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)
        run_git(project, "add", "src/mode.sh")
        run_git(project, "commit", "-qm", "add executable script")
        self.capture(project, "slice")
        before = self.diff(project)
        script.chmod(0o644)
        after = self.diff(project)
        self.assertNotEqual(
            before["candidate"]["candidate_fingerprint"],
            after["candidate"]["candidate_fingerprint"],
        )
        self.assertEqual(after["counts"]["slice"], 1)
        self.assertEqual(after["files"][0]["path"], "src/mode.sh")

    def test_classifier_change_invalidates_captured_baselines(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        self.capture(project, "slice")
        before = self.diff(project)
        adapter_path = project.linked / ".harness/project.json"
        adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
        adapter["sensitive_paths"] = ["src/*.py"]
        adapter_path.write_text(json.dumps(adapter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        after = self.diff(project)
        self.assertNotEqual(
            before["candidate"]["candidate_fingerprint"],
            after["candidate"]["candidate_fingerprint"],
        )
        self.assertFalse(after["completeness"]["complete"])
        self.assertIn("cumulative_baseline_identity_mismatch", after["completeness"]["stale_reasons"])
        self.assertIn("slice_baseline_identity_mismatch", after["completeness"]["stale_reasons"])

    def test_remote_git_snapshot_must_match_a_clean_local_candidate(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        self.capture(project, "slice")
        report = self.diff(project)
        candidate = report["candidate"]
        evidence = {
            "type": "remote-check-snapshot",
            "verification": "attested",
            "verified_by": "user",
            "source": "synthetic GitHub check snapshot",
            "repository": candidate["repository"],
            "subject": candidate["head_sha"],
            "collected_at": "2026-10-19T13:00:00+08:00",
            "coverage": ["repository", "head", "base", "check result"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "report_sha256": report["report_sha256"],
            "git_snapshot": {
                "repository": candidate["repository"],
                "head_sha": candidate["head_sha"],
                "base_ref": candidate["base_ref"],
                "base_sha": candidate["base_sha"],
                "captured_at": "2026-10-19T13:00:00+08:00",
            },
        }
        mismatch = json.loads(json.dumps(evidence))
        mismatch["git_snapshot"]["base_sha"] = "0" * 40
        before = project.record.read_bytes()
        rejected = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(mismatch),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("不相容", rejected.stderr)
        self.assertEqual(project.record.read_bytes(), before)

        accepted = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(evidence),
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        current = json.loads(project.run("state", "--json").stdout)
        self.assertEqual(current["evidence_summary"][0]["validity"], "input_identity_needs_recheck")

        dirty = project.linked / "src/dirty-after-snapshot.py"
        dirty.parent.mkdir()
        dirty.write_text("value = True\n", encoding="utf-8")
        new_report = self.diff(project)
        stale_local = json.loads(json.dumps(evidence))
        stale_local["candidate_fingerprint"] = new_report["candidate"]["candidate_fingerprint"]
        stale_local["report_sha256"] = new_report["report_sha256"]
        refused = project.run(
            "attest-evidence", "--expected-sha", digest(project.record),
            "--evidence-json", json.dumps(stale_local),
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("工作树、index", refused.stderr)

    def test_path_risk_labels_dependencies_and_unknown_semantics(self) -> None:
        project = self.make_project()
        self.capture(project, "task")
        self.capture(project, "slice")
        (project.linked / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        code = project.linked / "src/unclassified.py"
        code.parent.mkdir()
        code.write_text("value = 1\n", encoding="utf-8")
        report = self.diff(project)
        risks = {item["path"]: item["risk"] for item in report["files"]}
        self.assertIn("dependency", risks["pyproject.toml"])
        self.assertIn("requires_semantic_review", risks["src/unclassified.py"])


if __name__ == "__main__":
    unittest.main()
