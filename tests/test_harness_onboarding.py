"""Safe discovery, onboarding plans, and remote configuration snapshot tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_harness_state import HarnessProject


PLUGIN = Path(__file__).resolve().parents[1]
PLUGIN_TOOLS = PLUGIN / "plugins/engineering-workflow/tools"
CLI = PLUGIN_TOOLS / "harness.py"
sys.path.insert(0, str(PLUGIN_TOOLS))
from harness_lib.onboarding import (  # noqa: E402
    apply_local_file,
    check_github_snapshot,
    discover_project,
    plan_local_file,
    validate_github_snapshot,
)
from harness_lib.state import HarnessError  # noqa: E402


def git(project: HarnessProject, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project.linked), *args], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def cli(root: Path, *args: str, input_json: dict | None = None) -> subprocess.CompletedProcess[str]:
    raw = None if input_json is None else json.dumps(input_json, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(CLI), "--project-root", str(root), *args],
        input=raw, capture_output=True, text=True,
    )


class HarnessOnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = HarnessProject(self.base)
        git(self.project, "remote", "add", "origin", "https://user:canary-token@github.com/acme/sample.git")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def commit(self, *paths: str) -> None:
        git(self.project, "add", *paths)
        git(self.project, "commit", "-qm", "onboarding fixture")

    def test_discovery_is_read_only_and_unknown_stack_does_not_invent_checks(self) -> None:
        before_head = git(self.project, "rev-parse", "HEAD")
        before_status = git(self.project, "status", "--porcelain")
        (self.project.linked / ".env.local").write_text("API_KEY=canary-secret-value\n", encoding="utf-8")
        before_status = git(self.project, "status", "--porcelain")
        result = discover_project(self.project.linked)
        after_status = git(self.project, "status", "--porcelain")
        self.assertEqual(result["head_sha"], before_head)
        self.assertEqual(before_status, after_status)
        self.assertEqual(result["stack_markers"], [])
        self.assertEqual(result["test_entries"], [])
        self.assertEqual(result["ci_files"], [])
        self.assertFalse(result["complete"])
        encoded = json.dumps(result)
        self.assertNotIn("canary-token", encoded)
        self.assertNotIn("canary-secret-value", encoded)
        self.assertIn("<sensitive-path>", encoded)

    def test_discovery_reports_declared_tests_and_ci_markers_without_claiming_remote_success(self) -> None:
        (self.project.linked / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8"
        )
        workflow = self.project.linked / ".github/workflows/ci.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            "name: pytest documentation build\njobs:\n  test:\n    steps:\n"
            "      - name: mention pytest without running tests\n"
            "      - run: uv run --with pytest python -m pytest -q\n",
            encoding="utf-8",
        )
        docs_workflow = self.project.linked / ".github/workflows/docs.yml"
        docs_workflow.write_text(
            "name: pytest docs\njobs:\n  docs:\n    steps:\n      - name: pytest docs only\n",
            encoding="utf-8",
        )
        result = discover_project(self.project.linked)
        self.assertEqual(result["repository"]["repository"], "github.com/acme/sample")
        self.assertEqual(result["test_entries"][0]["source"], "pyproject.toml [tool.pytest.ini_options]")
        self.assertEqual(result["ci_files"][0]["test_command_markers"], ["pytest"])
        self.assertEqual(result["ci_files"][1]["test_command_markers"], [])
        self.assertEqual(result["ci_files"][0]["status"], "observed-not-remotely-verified")
        self.assertFalse(result["complete"])

    def test_plan_and_confirmed_apply_are_atomic_idempotent_and_read_back(self) -> None:
        content = "# Workflow rules\n\nUse the repository's verified test entry.\n"
        request = {"schema_version": 1, "path": ".harness/workflow.md", "content": content,
                   "expected_sha256": None}
        plan = plan_local_file(self.project.linked, request)
        self.assertTrue(plan["applicable"])
        self.assertEqual(plan["action"], "create")
        self.assertIn("+Use the repository's verified test entry.", "".join(plan["diff"]))
        target = self.project.linked / request["path"]
        self.assertFalse(target.exists())
        missing_confirmation = cli(
            self.project.linked, "onboard", "apply", "--request-stdin", "--plan-fingerprint",
            plan["plan_fingerprint"], "--confirm-path", "AGENTS.md", input_json=request,
        )
        self.assertNotEqual(missing_confirmation.returncode, 0)
        self.assertFalse(target.exists())
        applied = cli(
            self.project.linked, "onboard", "apply", "--request-stdin", "--plan-fingerprint",
            plan["plan_fingerprint"], "--confirm-path", request["path"], input_json=request,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        result = json.loads(applied.stdout)
        self.assertEqual(result["status"], "applied-and-read-back")
        self.assertEqual(target.read_text(encoding="utf-8"), content)
        repeated = apply_local_file(self.project.linked, request, plan["plan_fingerprint"], request["path"])
        self.assertEqual(repeated["status"], "already-present")
        self.assertFalse(repeated["writes_performed"])

    def test_existing_file_diff_and_plan_require_matching_clean_file_identity(self) -> None:
        target = self.project.linked / ".harness/workflow.md"
        target.write_text("# Existing rules\n", encoding="utf-8")
        self.commit(".harness/workflow.md")
        old_sha = digest_bytes(target.read_bytes())
        request = {"schema_version": 1, "path": ".harness/workflow.md",
                   "content": "# Existing rules\n\nNew confirmed rule.\n", "expected_sha256": old_sha}
        plan = plan_local_file(self.project.linked, request)
        self.assertTrue(plan["applicable"])
        self.assertEqual(plan["action"], "update")
        changed = "# Existing rules\n\nUser edit.\n"
        target.write_text(changed, encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), changed)
        plan_after_user_edit = plan_local_file(
            self.project.linked,
            {**request, "expected_sha256": digest_bytes(target.read_bytes())},
        )
        self.assertFalse(plan_after_user_edit["applicable"])
        self.assertIn("target_has_user_or_uncommitted_changes", plan_after_user_edit["conflicts"])

    def test_replacing_file_after_plan_changes_identity_even_when_bytes_match(self) -> None:
        target = self.project.linked / ".harness/workflow.md"
        target.write_text("# Existing rules\n", encoding="utf-8")
        self.commit(".harness/workflow.md")
        request = {"schema_version": 1, "path": ".harness/workflow.md",
                   "content": "# New rules\n", "expected_sha256": digest_bytes(target.read_bytes())}
        before = plan_local_file(self.project.linked, request)
        replacement = target.with_name("workflow.tmp")
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
        after = plan_local_file(self.project.linked, request)
        self.assertEqual(before["current_sha256"], after["current_sha256"])
        self.assertNotEqual(before["target_identity"], after["target_identity"])
        self.assertNotEqual(before["plan_fingerprint"], after["plan_fingerprint"])
        with self.assertRaises(HarnessError):
            apply_local_file(self.project.linked, request, before["plan_fingerprint"], request["path"])

    def test_application_rejects_stale_fingerprint_without_overwriting_user_change(self) -> None:
        target = self.project.linked / ".harness/workflow.md"
        target.write_text("# Existing rules\n", encoding="utf-8")
        self.commit(".harness/workflow.md")
        original = target.read_bytes()
        request = {"schema_version": 1, "path": ".harness/workflow.md",
                   "content": "# Desired rules\n", "expected_sha256": digest_bytes(original)}
        plan = plan_local_file(self.project.linked, request)
        target.write_text("# User changed this after planning\n", encoding="utf-8")
        changed = target.read_bytes()
        with self.assertRaises(HarnessError):
            apply_local_file(self.project.linked, request, plan["plan_fingerprint"], request["path"])
        self.assertEqual(target.read_bytes(), changed)

    def test_existing_untracked_and_gitignored_targets_are_not_applied(self) -> None:
        target = self.project.linked / ".harness/local.md"
        target.write_text("User-owned local file.\n", encoding="utf-8")
        request = {"schema_version": 1, "path": ".harness/local.md", "content": "New content.\n",
                   "expected_sha256": digest_bytes(target.read_bytes())}
        plan = plan_local_file(self.project.linked, request)
        self.assertFalse(plan["applicable"])
        self.assertIn("existing_target_is_not_tracked_and_cannot_be_restored_from_git", plan["conflicts"])
        before = target.read_bytes()
        with self.assertRaises(HarnessError):
            apply_local_file(self.project.linked, request, plan["plan_fingerprint"], request["path"])
        self.assertEqual(target.read_bytes(), before)

        ignore = self.project.linked / ".gitignore"
        ignore.write_text(".harness/ignored.md\n", encoding="utf-8")
        self.commit(".gitignore")
        ignored_request = {"schema_version": 1, "path": ".harness/ignored.md", "content": "rules\n",
                           "expected_sha256": None}
        ignored_plan = plan_local_file(self.project.linked, ignored_request)
        self.assertFalse(ignored_plan["applicable"])
        self.assertIn("new_target_would_be_hidden_by_git_ignore", ignored_plan["conflicts"])

    def test_path_traversal_symlinks_sensitive_paths_and_secret_content_are_rejected(self) -> None:
        for path in ("../outside.md", ".git/config", ".env.local"):
            with self.subTest(path=path), self.assertRaises(HarnessError):
                plan_local_file(self.project.linked, {
                    "schema_version": 1, "path": path, "content": "safe\n", "expected_sha256": None,
                })
        outside = self.base / "outside.md"
        outside.write_text("keep\n", encoding="utf-8")
        (self.project.linked / "escape.md").symlink_to(outside)
        with self.assertRaises(HarnessError):
            plan_local_file(self.project.linked, {
                "schema_version": 1, "path": "escape.md", "content": "overwrite\n", "expected_sha256": None,
            })
        nested = self.project.linked / "nested"
        nested.mkdir()
        (nested / ".git").mkdir()
        with self.assertRaises(HarnessError):
            plan_local_file(self.project.linked, {
                "schema_version": 1, "path": "nested/rules.md", "content": "rules\n", "expected_sha256": None,
            })
        with self.assertRaises(HarnessError):
            plan_local_file(self.project.linked, {
                "schema_version": 1, "path": ".harness/rules.md",
                "content": "api_key=canary-secret-value\n", "expected_sha256": None,
            })
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")

    def test_remote_plan_requires_real_nonempty_checks_and_specific_target(self) -> None:
        base = {"provider": "github", "target": "acme/sample", "base_ref": "master",
                "required_checks": ["CI / pytest"], "checks_source": "read-only GitHub Ruleset query",
                "source_verification": "attested", "strict_required": True,
                "rollback": "Restore the saved Ruleset snapshot after authorization."}
        good = plan_local_file(self.project.linked, {
            "schema_version": 1, "path": ".harness/workflow.md", "content": "rules\n",
            "expected_sha256": None, "remote_plan": base,
        })
        self.assertEqual(good["remote_plan"]["status"], "proposed-not-applied")
        self.assertFalse(good["remote_plan"]["remote_apply_supported"])
        for invalid in (
            {**base, "required_checks": []},
            {**base, "target": "https://user:secret@github.com/acme/sample"},
            {**base, "provider": "gitlab"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(HarnessError):
                plan_local_file(self.project.linked, {
                    "schema_version": 1, "path": ".harness/workflow.md", "content": "rules\n",
                    "expected_sha256": None, "remote_plan": invalid,
                })

    def _snapshot(self, **changes: object) -> dict:
        head = git(self.project, "rev-parse", "HEAD")
        base = git(self.project, "rev-parse", "master")
        snapshot = {
            "schema_version": 1, "provider": "github", "repository": "acme/sample",
            "head_sha": head, "base_ref": "master", "base_sha": base,
            "captured_at": "2026-10-19T13:00:00+08:00",
            "source": {"kind": "branch-protection", "identity": "refs/heads/master"},
            "rules_status": "available", "strict_required": True,
            "required_checks": [{"context": "CI / pytest", "app_id": 123}],
            "observed_jobs": [
                {"name": "CI / pytest", "conclusion": "success", "source": "github-actions", "app_id": 123, "head_sha": head},
                {"name": "docs-preview", "conclusion": "success", "source": "other-app", "app_id": 321, "head_sha": head},
            ],
            "verification": "attested", "unverified_reasons": [],
        }
        snapshot.update(changes)
        return snapshot

    def test_remote_snapshot_separates_required_checks_from_other_jobs_and_never_claims_live_verification(self) -> None:
        snapshot = self._snapshot()
        result = check_github_snapshot(
            self.project.linked, snapshot, expected_repository="github.com/acme/sample",
            expected_base_ref="master", expected_base_sha=snapshot["base_sha"],
        )
        self.assertTrue(result["repository_matches"])
        self.assertTrue(result["base_ref_matches"])
        self.assertTrue(result["base_sha_matches"])
        self.assertEqual(result["successful_jobs_not_required"][0]["name"], "docs-preview")
        self.assertEqual(result["required_check_observations"][0]["context"], "CI / pytest")
        self.assertTrue(result["snapshot_claim_consistent"])
        self.assertFalse(result["complete"])
        self.assertFalse(result["live_remote_read_performed"])
        cli_result = cli(
            self.project.linked, "onboard", "remote-check", "--snapshot-stdin",
            "--repository", "acme/sample", "--base-ref", "master", "--base-sha", snapshot["base_sha"],
            input_json=snapshot,
        )
        self.assertEqual(cli_result.returncode, 0, cli_result.stderr)
        self.assertFalse(json.loads(cli_result.stdout)["complete"])

    def test_success_from_wrong_app_does_not_satisfy_required_check(self) -> None:
        snapshot = self._snapshot(observed_jobs=[
            {"name": "CI / pytest", "conclusion": "success", "source": "other-app", "app_id": 321,
             "head_sha": git(self.project, "rev-parse", "HEAD")},
        ])
        result = check_github_snapshot(self.project.linked, snapshot, expected_base_ref="master")
        self.assertFalse(result["required_check_observations"][0]["observed_success_on_snapshot_head"])
        self.assertEqual(result["successful_jobs_not_required"][0]["source"], "other-app")

    def test_remote_snapshot_detects_wrong_repository_stale_base_permissions_and_unknown_platform(self) -> None:
        snapshot = self._snapshot()
        wrong_repo = check_github_snapshot(
            self.project.linked, snapshot, expected_repository="other/repo", expected_base_ref="master",
            expected_base_sha=snapshot["base_sha"],
        )
        self.assertFalse(wrong_repo["repository_matches"])
        stale_base = check_github_snapshot(
            self.project.linked, snapshot, expected_repository="acme/sample", expected_base_ref="master",
            expected_base_sha="f" * 40,
        )
        self.assertFalse(stale_base["base_sha_matches"])
        denied = check_github_snapshot(
            self.project.linked, self._snapshot(rules_status="permission-denied", required_checks=[]),
            expected_repository="acme/sample", expected_base_ref="master",
        )
        self.assertFalse(denied["complete"])
        unsupported = validate_github_snapshot({**snapshot, "provider": "gitlab"})
        self.assertFalse(unsupported["supported"])

    def test_remote_snapshot_rejects_malformed_unhashable_values_and_forged_machine_claim(self) -> None:
        snapshot = self._snapshot()
        for changes in (
            {"rules_status": []}, {"verification": []},
            {"source": {"kind": [], "identity": "ruleset-1"}},
            {"verification": "machine-verified"},
        ):
            with self.subTest(changes=changes), self.assertRaises(HarnessError):
                validate_github_snapshot({**snapshot, **changes})


if __name__ == "__main__":
    unittest.main()
