"""Cross-session diagnostic budget tests with controllable timestamps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

from test_harness_state import HarnessProject, digest

from harness_lib.budget import (
    add_alias,
    diagnostic_report,
    record_attempt,
    record_decision,
    resume_wait,
    start_problem,
    start_wait,
    summaries,
)
from harness_lib.state import EXTENSION_PATTERN, HarnessError


class HarnessBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = HarnessProject(self.base)
        self.project.migrate()
        self.t0 = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def start(self, problem_id: str = "database-timeout", title: str = "Database timeout") -> dict:
        return start_problem(
            self.project.linked, None, "sample-work", problem_id, title,
            digest(self.project.record), now=self.t0,
        )

    def record(self, at: datetime, *, problem_id: str = "database-timeout",
               evidence_id: str | None = None, action: str = "run bounded query") -> dict:
        return record_attempt(
            self.project.linked, None, "sample-work", problem_id,
            "query plan may be missing an index", action, "query still exceeds the deadline",
            digest(self.project.record), evidence_id, now=at,
        )

    def extension(self) -> dict:
        text = self.project.record.read_text(encoding="utf-8")
        matches = list(EXTENSION_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)
        return json.loads(matches[0].group(2))

    def problem(self, problem_id: str = "database-timeout") -> dict:
        return self.extension()["diagnostics"]["problems"][problem_id]

    def test_third_no_progress_round_escalates_and_blocks_more_diagnosis(self) -> None:
        self.start()
        for index in range(1, 4):
            result = self.record(self.t0 + timedelta(seconds=index * 10))
            if index < 3:
                self.assertTrue(result["diagnostic_continued"])
        self.assertEqual(result["budget"]["status"], "escalated")
        self.assertFalse(result["diagnostic_continued"])
        before = self.project.record.read_bytes()
        with self.assertRaisesRegex(HarnessError, "预算已触发"):
            self.record(self.t0 + timedelta(seconds=31))
        self.assertEqual(self.project.record.read_bytes(), before)
        report = diagnostic_report(
            self.project.linked, None, "sample-work", "database-timeout", now=self.t0 + timedelta(seconds=30)
        )
        self.assertEqual(report["problems"][0]["status"], "escalated")
        self.assertEqual(len(report["problems"][0]["attempts"]), 3)
        self.assertTrue(report["problems"][0]["next_step_cost"]["requires_user_decision"])
        stopped = record_decision(
            self.project.linked, None, "sample-work", "database-timeout", "stop",
            "用户决定停止本轮诊断", "user", "chat confirmation", digest(self.project.record),
            now=self.t0 + timedelta(seconds=40),
        )
        self.assertEqual(stopped["status"], "stopped")
        with self.assertRaisesRegex(HarnessError, "已停止"):
            self.record(self.t0 + timedelta(seconds=41))

    def test_1800_second_boundary_escalates_and_user_continuation_keeps_history(self) -> None:
        self.start()
        self.record(self.t0 + timedelta(seconds=1799))
        summary = summaries(self.extension(), now=self.t0 + timedelta(seconds=1800))[0]
        self.assertEqual(summary["status"], "escalated")
        triggered = self.record(self.t0 + timedelta(seconds=1800))
        self.assertEqual(triggered["status"], "escalated")
        self.assertEqual(len(self.problem()["attempts"]), 1)
        decision = record_decision(
            self.project.linked, None, "sample-work", "database-timeout", "continue",
            "用户决定再进行一个有界诊断窗口", "user", "chat confirmation", digest(self.project.record),
            now=self.t0 + timedelta(seconds=1810),
        )
        self.assertEqual(decision["status"], "active")
        continued = self.record(self.t0 + timedelta(seconds=1811))
        self.assertTrue(continued["diagnostic_continued"])
        current = self.problem()
        self.assertEqual(len(current["attempts"]), 2)
        self.assertEqual(current["total_seconds"], 1801)
        self.assertEqual(len(current["decisions"]), 1)

    def test_unique_current_attested_evidence_resets_rounds_but_reuse_does_not(self) -> None:
        for scope in ("task", "slice"):
            result = self.project.run("capture-baseline", "--scope", scope, "--expected-sha", digest(self.project.record))
            self.assertEqual(result.returncode, 0, result.stderr)
        report_result = self.project.run("diff", "--json")
        report = json.loads(report_result.stdout)
        item = {
            "type": "diagnostic-progress", "verification": "attested", "verified_by": "user",
            "source": "local reproducible query plan report", "repository": "example.test/acme/sample",
            "subject": "reports/query-plan.txt", "collected_at": "2026-10-19T00:00:00+00:00",
            "coverage": ["index hypothesis narrowed"],
            "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
            "report_sha256": report["report_sha256"],
        }
        recorded = self.project.run(
            "attest-evidence", "--expected-sha", digest(self.project.record),
            "--evidence-json", json.dumps(item),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        duplicate = dict(item)
        duplicate["source"] = "same report reread in another session"
        duplicate["collected_at"] = "2026-10-19T00:00:01+00:00"
        duplicate_result = self.project.run(
            "attest-evidence", "--expected-sha", digest(self.project.record),
            "--evidence-json", json.dumps(duplicate),
        )
        self.assertEqual(duplicate_result.returncode, 0, duplicate_result.stderr)
        state = json.loads(self.project.run("state", "--json").stdout)
        evidence_key = state["evidence_summary"][0]["evidence_id"]
        self.assertEqual(state["evidence_summary"][1]["evidence_id"], evidence_key)
        self.start()
        first = self.record(self.t0 + timedelta(seconds=5), evidence_id=evidence_key)
        self.assertTrue(first["attempt"]["progress"])
        repeated = self.record(self.t0 + timedelta(seconds=10), evidence_id=evidence_key)
        self.assertFalse(repeated["attempt"]["progress"])
        self.assertIn("重复证据", repeated["attempt"]["progress_reason"])
        self.assertEqual(repeated["budget"]["no_progress_rounds"], 1)

    def test_wait_is_bounded_and_excluded_from_budget_at_deadline(self) -> None:
        self.start()
        self.record(self.t0 + timedelta(seconds=60))
        waiting = start_wait(
            self.project.linked, None, "sample-work", "database-timeout", "CI query is running", 300,
            digest(self.project.record), now=self.t0 + timedelta(seconds=60),
        )
        self.assertEqual(waiting["status"], "waiting")
        at_deadline = summaries(self.extension(), now=self.t0 + timedelta(seconds=360))[0]
        self.assertEqual(at_deadline["status"], "waiting")
        resumed = resume_wait(
            self.project.linked, None, "sample-work", "database-timeout", digest(self.project.record),
            now=self.t0 + timedelta(seconds=360),
        )
        self.assertEqual(resumed["status"], "active")
        final = self.record(self.t0 + timedelta(seconds=420))
        self.assertEqual(final["budget"]["cumulative_diagnostic_seconds"], 120)
        self.assertEqual(self.problem()["waits"][0]["ended_at"], "2026-10-19T00:06:00+00:00")

    def test_wait_limit_and_secret_like_attempt_text_are_rejected(self) -> None:
        self.start()
        before = self.project.record.read_bytes()
        with self.assertRaisesRegex(HarnessError, "1到3600秒"):
            start_wait(
                self.project.linked, None, "sample-work", "database-timeout", "unbounded CI", 3601,
                digest(self.project.record), now=self.t0,
            )
        with self.assertRaisesRegex(HarnessError, "Secret"):
            record_attempt(
                self.project.linked, None, "sample-work", "database-timeout", "token is bad",
                "inspect", "TOKEN=synthetic-canary", digest(self.project.record),
                now=self.t0 + timedelta(seconds=1),
            )
        self.assertEqual(self.project.record.read_bytes(), before)

    def test_expired_wait_and_clock_regression_require_review(self) -> None:
        self.start()
        start_wait(
            self.project.linked, None, "sample-work", "database-timeout", "test process", 10,
            digest(self.project.record), now=self.t0,
        )
        expired = resume_wait(
            self.project.linked, None, "sample-work", "database-timeout", digest(self.project.record),
            now=self.t0 + timedelta(seconds=11),
        )
        self.assertEqual(expired["status"], "needs_review")
        self.assertTrue(self.problem()["time_uncertain"])
        continued = record_decision(
            self.project.linked, None, "sample-work", "database-timeout", "continue",
            "用户复核时间缺口后授权新预算窗口", "user", "chat confirmation", digest(self.project.record),
            now=self.t0 + timedelta(seconds=12),
        )
        self.assertEqual(continued["status"], "active")
        self.record(self.t0 + timedelta(seconds=13))
        summary = summaries(self.extension(), now=self.t0 + timedelta(seconds=13))[0]
        self.assertEqual(summary["status"], "active")
        self.assertTrue(summary["time_uncertain"])

        other = start_problem(
            self.project.linked, None, "sample-work", "clock-test", "Clock test",
            digest(self.project.record), now=self.t0,
        )
        with self.assertRaisesRegex(HarnessError, "时钟倒退"):
            record_attempt(
                self.project.linked, None, "sample-work", "clock-test", "hypothesis", "action", "result",
                digest(self.project.record), now=self.t0 - timedelta(seconds=1),
            )
        current = summaries(self.extension(), now=self.t0 - timedelta(seconds=1))
        self.assertEqual(next(item for item in current if item["problem_id"] == "clock-test")["status"], "needs_review")

    def test_alias_and_duplicate_title_cannot_create_a_fresh_budget(self) -> None:
        self.start()
        first = self.record(self.t0 + timedelta(seconds=5))
        self.assertEqual(first["budget"]["no_progress_rounds"], 1)
        with self.assertRaisesRegex(HarnessError, "已存在"):
            self.start()
        with self.assertRaisesRegex(HarnessError, "相同问题标题"):
            self.start("new-id", "Database timeout")
        alias = add_alias(
            self.project.linked, None, "sample-work", "database-timeout", "renamed-timeout",
            digest(self.project.record),
        )
        self.assertEqual(alias["problem_id"], "database-timeout")
        recorded = self.record(self.t0 + timedelta(seconds=10), problem_id="renamed-timeout")
        self.assertEqual(recorded["problem_id"], "database-timeout")
        self.assertEqual(recorded["budget"]["no_progress_rounds"], 2)
        with self.assertRaisesRegex(HarnessError, "已存在"):
            start_problem(
                self.project.linked, None, "sample-work", "renamed-timeout", "Another wording",
                digest(self.project.record), now=self.t0 + timedelta(seconds=2),
            )

    def test_cli_reloads_diagnostic_budget_across_processes_and_reports_diff(self) -> None:
        started = self.project.run(
            "diagnostic", "start", "--problem-id", "process-timeout", "--title", "Process timeout",
            "--expected-sha", digest(self.project.record),
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        for index in range(3):
            attempt = self.project.run(
                "diagnostic", "record", "--problem-id", "process-timeout",
                "--hypothesis", "lock contention", "--action", "inspect lock owner",
                "--result", "lock is stale but owner unknown", "--expected-sha", digest(self.project.record),
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)
        state_result = self.project.run("state", "--json")
        self.assertEqual(state_result.returncode, 0, state_result.stderr)
        state = json.loads(state_result.stdout)
        self.assertEqual(state["diagnostic_budgets"][0]["problem_id"], "process-timeout")
        self.assertEqual(state["diagnostic_budgets"][0]["status"], "escalated")
        report = self.project.run("diagnostic", "report", "--problem-id", "process-timeout")
        self.assertEqual(report.returncode, 0, report.stderr)
        output = json.loads(report.stdout)
        self.assertEqual(len(output["problems"][0]["attempts"]), 3)
        self.assertIn("candidate", output["problems"][0])


if __name__ == "__main__":
    unittest.main()
