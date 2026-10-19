"""Dynamic-document, completion, recovery, and maintenance closeout tests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_harness_state import HarnessProject, digest


def git(project: HarnessProject, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project.linked), *args], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


class HarnessCloseoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = HarnessProject(self.base)
        self.project.migrate()
        self.manifest_path = self.project.linked / ".harness/dynamic-files.json"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.docs = self.project.linked / "docs"
        self.docs.mkdir()
        (self.project.linked / ".scratch/demo/issues").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def configure_project(self, *, delivery_required: bool = True, ticket_status: str = "done",
                          child_status: str = "done") -> None:
        adapter_path = self.project.linked / ".harness/project.json"
        adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
        adapter["dynamic_file_manifest"] = ".harness/dynamic-files.json"
        adapter_path.write_text(json.dumps(adapter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "delivery_required": delivery_required,
            "files": [
                {"id": "agents", "path": "AGENTS.md", "owner": "engineering",
                 "authority": "AGENTS.md", "triggers": ["workflow rules change"],
                 "history_path": ".scratch/demo/history.md"},
                {"id": "runbook", "path": "docs/runbook.md", "owner": "engineering",
                 "authority": "Runbook", "triggers": ["command or recovery changes"],
                 "history_path": ".scratch/demo/history.md"},
            ],
            "tickets": [{"id": "01", "path": ".scratch/demo/issues/01-work.md"}],
            "child_work_items": ["child-work"],
        }
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.project.linked / "AGENTS.md").write_text("# Agent instructions\n\nStable rules.\n", encoding="utf-8")
        (self.docs / "runbook.md").write_text("# Runbook\n\nCurrent commands.\n", encoding="utf-8")
        (self.project.linked / ".scratch/demo/history.md").parent.mkdir(parents=True, exist_ok=True)
        (self.project.linked / ".scratch/demo/history.md").write_text("# History\n\nPrior decisions.\n", encoding="utf-8")
        (self.project.linked / ".scratch/demo/issues/01-work.md").write_text(
            "# Ticket\nStatus: " + ticket_status + "\nTicket Readiness: READY\n\n"
            "Result: " + ("Validated locally." if ticket_status == "done" else "") + "\n",
            encoding="utf-8",
        )
        child = self.project.common_dir() / "harness/work-items/child-work/status.md"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(
            "# Child work\nID: child-work\nStatus: " + child_status + "\nStage: 实施中\n"
            "Last updated: 2026-10-19T13:00:00+08:00\nOwner: test\nNext: verify child\n",
            encoding="utf-8",
        )
        git(self.project, "add", ".harness", "AGENTS.md", "docs", ".scratch/demo")
        git(self.project, "commit", "-qm", "configure closeout fixture")
        self.capture("task")
        (self.project.linked / "AGENTS.md").write_text(
            "# Agent instructions\n\nStable rules.\n\nCloseout rule added by this task.\n", encoding="utf-8"
        )
        git(self.project, "add", "AGENTS.md")
        git(self.project, "commit", "-qm", "update dynamic file")
        self.capture("slice")

    def capture(self, scope: str) -> None:
        result = self.project.run(
            "capture-baseline", "--scope", scope, "--expected-sha", digest(self.project.record)
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def record_file(self, file_id: str, disposition: str, reason: str) -> None:
        result = self.project.run(
            "closeout", "record-file", "--file-id", file_id, "--disposition", disposition,
            "--reason", reason, "--reviewer", "reviewer", "--review-summary", "Checked authority and applicability.",
            "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def add_evidence(self, evidence_type: str) -> str:
        report_result = self.project.run("diff", "--json")
        self.assertEqual(report_result.returncode, 0, report_result.stderr)
        report = json.loads(report_result.stdout)
        item = {
            "type": evidence_type, "verification": "attested", "verified_by": "agent",
            "source": "local synthetic fixture", "repository": "example.test/acme/sample",
            "subject": f"reports/{evidence_type}.json", "collected_at": "2026-10-19T13:00:00+08:00",
            "coverage": ["current candidate"],
            "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
            "report_sha256": report["report_sha256"],
        }
        result = self.project.run(
            "attest-evidence", "--expected-sha", digest(self.project.record),
            "--evidence-json", json.dumps(item),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(self.project.run("state", "--json").stdout)
        return next(e["evidence_id"] for e in state["evidence_summary"] if e["type"] == evidence_type)

    def prepare_local_closeout(self, *, delivery_required: bool = True) -> None:
        self.configure_project(delivery_required=delivery_required)
        self.record_file("agents", "updated", "Updated the workflow guidance.")
        self.record_file("runbook", "reviewed-no-change", "No command or recovery behavior changed.")
        self.add_evidence("validation-report")
        self.add_evidence("code-review")

    def test_local_scope_can_complete_while_overall_waits_for_delivery(self) -> None:
        self.prepare_local_closeout(delivery_required=True)
        current = self.project.record.read_text(encoding="utf-8")
        current = current.replace(
            "Publication authorization: None\n",
            "Publication authorization: test-scope authorization\nPRs: PR #1 OPEN\n",
            1,
        )
        self.project.record.write_text(current, encoding="utf-8")
        result = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(result.returncode, 0, result.stderr)
        check = json.loads(result.stdout)
        self.assertTrue(check["local_ready"])
        self.assertEqual(check["delivery_status"], "pending_remote_evidence")
        self.assertEqual(set(check["missing_remote_evidence"]), {
            "review-confirmation", "merge-confirmation", "cleanup-confirmation",
        })
        self.assertFalse(check["overall_ready"])
        local = self.project.run(
            "closeout", "finalize", "--scope", "local", "--recorded-by", "agent",
            "--reason", "Local candidate and records are complete.", "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(local.returncode, 0, local.stderr)
        before = self.project.record.read_bytes()
        overall = self.project.run(
            "closeout", "finalize", "--scope", "overall", "--recorded-by", "agent",
            "--reason", "Attempted overall completion.", "--expected-sha", digest(self.project.record),
        )
        self.assertNotEqual(overall.returncode, 0)
        self.assertIn("pending_remote_evidence", overall.stderr)
        self.assertEqual(self.project.record.read_bytes(), before)

    def test_local_only_scope_can_finalize_overall_and_state_reads_valid_completion(self) -> None:
        self.prepare_local_closeout(delivery_required=False)
        finalized = self.project.run(
            "closeout", "finalize", "--scope", "overall", "--recorded-by", "agent",
            "--reason", "This adapter declares local-only delivery.",
            "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        state_result = self.project.run("state", "--json")
        self.assertEqual(state_result.returncode, 0, state_result.stderr)
        state = json.loads(state_result.stdout)
        self.assertEqual(state["lifecycle_status"], "done")
        self.assertTrue(state["closeout"]["lifecycle_claim_valid"])
        self.assertTrue(state["closeout"]["overall_completion_valid"])

    def test_external_child_record_change_invalidates_completion_without_git_diff(self) -> None:
        self.prepare_local_closeout(delivery_required=False)
        finalized = self.project.run(
            "closeout", "finalize", "--scope", "overall", "--recorded-by", "agent",
            "--reason", "Local-only candidate is complete.", "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        child = self.project.common_dir() / "harness/work-items/child-work/status.md"
        changed = child.read_text(encoding="utf-8").replace("Status: done", "Status: in-progress", 1)
        child.write_text(changed, encoding="utf-8")
        state_result = self.project.run("state", "--json")
        self.assertEqual(state_result.returncode, 0, state_result.stderr)
        state = json.loads(state_result.stdout)
        self.assertEqual(state["lifecycle_status"], "done")
        self.assertFalse(state["closeout"]["overall_completion_valid"])
        self.assertFalse(state["closeout"]["lifecycle_claim_valid"])

    def test_missing_manifest_unfinished_ticket_or_child_blocks_completion(self) -> None:
        self.configure_project(ticket_status="open", child_status="in-progress")
        result = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(result.returncode, 0, result.stderr)
        check = json.loads(result.stdout)
        self.assertFalse(check["local_ready"])
        self.assertIn("unfinished_or_missing_ticket", check["local_reasons"])
        self.assertIn("unfinished_or_missing_child_work_item", check["local_reasons"])

    def test_missing_manifest_is_explicitly_unconfigured_and_not_complete(self) -> None:
        result = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(result.returncode, 0, result.stderr)
        check = json.loads(result.stdout)
        self.assertFalse(check["manifest"]["configured"])
        self.assertFalse(check["local_ready"])
        self.assertIn("dynamic_file_manifest_not_configured", check["local_reasons"])

    def test_candidate_or_manifest_change_stales_dynamic_file_assessment(self) -> None:
        self.configure_project(delivery_required=False)
        self.record_file("agents", "updated", "Updated the workflow guidance.")
        self.record_file("runbook", "not-applicable", "No runtime or recovery behavior changed.")
        (self.docs / "runbook.md").write_text("# Runbook\n\nChanged after the closeout assessment.\n", encoding="utf-8")
        result = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(result.returncode, 0, result.stderr)
        check = json.loads(result.stdout)
        self.assertFalse(check["local_ready"])
        runbook = next(item for item in check["dynamic_files"] if item["id"] == "runbook")
        self.assertIn("candidate_changed", runbook["reasons"])
        self.assertIn("file_changed", runbook["reasons"])

    def test_manifest_change_requires_separate_semantic_review_evidence(self) -> None:
        self.configure_project(delivery_required=False)
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["triggers"].append("closeout requirement changed")
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git(self.project, "add", ".harness/dynamic-files.json")
        git(self.project, "commit", "-qm", "change dynamic inventory")
        self.capture("slice")
        self.record_file("agents", "updated", "Updated the workflow guidance.")
        self.record_file("runbook", "reviewed-no-change", "Runtime instructions still apply.")
        self.add_evidence("validation-report")
        self.add_evidence("code-review")
        check_result = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(check_result.returncode, 0, check_result.stderr)
        check = json.loads(check_result.stdout)
        self.assertTrue(check["manifest_changed_in_candidate"])
        self.assertFalse(check["manifest_review_evidence_current"])
        self.assertIn("changed_manifest_needs_semantic_review", check["local_reasons"])
        self.add_evidence("manifest-review")
        current = self.project.run("closeout", "check", "--work-item", "sample-work")
        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertTrue(json.loads(current.stdout)["local_ready"])

    def test_recovery_view_preserves_damaged_record_and_reports_candidate(self) -> None:
        self.configure_project()
        original = self.project.record.read_bytes()
        user_change = self.project.linked / "src/user-change.py"
        user_change.parent.mkdir()
        user_change.write_text("value = 'keep'\n", encoding="utf-8")
        self.project.record.write_bytes(b"corrupted status record\n")
        damaged = self.project.record.read_bytes()
        result = self.project.run("closeout", "recover")
        self.assertEqual(result.returncode, 0, result.stderr)
        recovery = json.loads(result.stdout)
        self.assertEqual(recovery["status_record"], "damaged-or-unsupported")
        self.assertFalse(recovery["writes_performed"])
        self.assertTrue(recovery["candidate_fingerprint"])
        self.assertEqual(recovery["primary_record_status"], "damaged-or-unsupported")
        self.assertIn("src/user-change.py", {item["path"] for item in recovery["current_tree_changes"]})
        self.assertEqual(self.project.record.read_bytes(), damaged)
        self.assertNotEqual(damaged, original)

    def test_maintenance_followup_requires_effect_evidence_and_rechecks_staleness(self) -> None:
        self.configure_project(delivery_required=False)
        opened = self.project.run(
            "maintenance", "open", "--item-id", "review-gap", "--category", "rule-not-followed",
            "--problem", "A closeout review was skipped.", "--owner", "engineering",
            "--scope", "Plugin workflow", "--authorization", "Within current task scope",
            "--acceptance", "A synthetic closeout run rejects an unreviewed file.",
            "--action", "Add deterministic closeout check and rerun the fixture.",
            "--replacement-coverage", "Keep the existing review skill and add a structural check.",
            "--history-location", ".scratch/demo/history.md",
            "--recheck-trigger", "After the next closeout implementation.",
            "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)
        deferred = self.project.run(
            "maintenance", "defer", "--item-id", "review-gap", "--reason", "Wait for the synthetic gate fix.",
            "--recheck-trigger", "When the gate check is updated.", "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(deferred.returncode, 0, deferred.stderr)
        before = self.project.record.read_bytes()
        no_effect = self.project.run(
            "maintenance", "close", "--item-id", "review-gap", "--effect-evidence-id", "evidence-sha256:" + "0" * 64,
            "--effect-summary", "Attempt to close without evidence.", "--expected-sha", digest(self.project.record),
        )
        self.assertNotEqual(no_effect.returncode, 0)
        self.assertIn("maintenance-effect", no_effect.stderr)
        self.assertEqual(self.project.record.read_bytes(), before)
        effect_id = self.add_evidence("maintenance-effect")
        closed = self.project.run(
            "maintenance", "close", "--item-id", "review-gap", "--effect-evidence-id", effect_id,
            "--effect-summary", "A fresh synthetic run rejected the missing review and passed when recorded.",
            "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(closed.returncode, 0, closed.stderr)
        listed = self.project.run("maintenance", "list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertTrue(json.loads(listed.stdout)[0]["effect_current"])
        (self.project.linked / "src/change.py").parent.mkdir()
        (self.project.linked / "src/change.py").write_text("value = 1\n", encoding="utf-8")
        after = self.project.run("maintenance", "list")
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertFalse(json.loads(after.stdout)[0]["effect_current"])


if __name__ == "__main__":
    unittest.main()
