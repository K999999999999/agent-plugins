#!/usr/bin/env python3
"""Engineering workflow Harness command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness_lib.state import (
    HarnessError,
    attest_evidence,
    capture_baseline_record,
    get_diff,
    get_state,
    migrate_record,
    set_runtime_status,
    transition_stage,
)
from harness_lib.budget import (
    add_alias,
    diagnostic_report,
    record_attempt,
    record_decision,
    resume_wait,
    start_problem,
    start_wait,
)
from harness_lib.closeout import check_closeout, finalize_closeout, record_dynamic_file, recover_view
from harness_lib.maintenance import close_followup, defer_followup, open_followup
from harness_lib.onboarding import apply_local_file, check_github_snapshot, discover_project, plan_local_file


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Inspect and update project Harness state")
    result.add_argument("--project-root", type=Path, default=Path.cwd())
    result.add_argument("--adapter", type=Path, help="project JSON adapter path")
    commands = result.add_subparsers(dest="command", required=True)

    state = commands.add_parser("state", help="show the current work item state")
    state.add_argument("--work-item")
    state.add_argument("--json", action="store_true", dest="as_json")

    diff = commands.add_parser("diff", help="show slice and cumulative Git changes")
    diff.add_argument("--work-item", required=True)
    diff.add_argument("--json", action="store_true", dest="as_json")

    baseline = commands.add_parser("capture-baseline", help="record a task or slice baseline")
    baseline.add_argument("--work-item", required=True)
    baseline.add_argument("--scope", required=True, choices=("task", "slice"))
    baseline.add_argument("--expected-sha", required=True)

    attest = commands.add_parser("attest-evidence", help="bind one evidence item to the current candidate")
    attest.add_argument("--work-item", required=True)
    attest.add_argument("--expected-sha", required=True)
    attest.add_argument("--evidence-json", required=True)

    migrate = commands.add_parser("migrate", help="explicitly enable the v1 state extension")
    migrate.add_argument("--work-item", required=True)
    migrate.add_argument("--expected-sha", required=True)

    transition = commands.add_parser("transition", help="move to an allowed workflow stage")
    transition.add_argument("--work-item", required=True)
    transition.add_argument("--to", required=True)
    transition.add_argument("--next", required=True, help="the next executable step")
    transition.add_argument("--expected-sha", required=True)
    transition.add_argument("--evidence-json", required=True)

    runtime = commands.add_parser("set-runtime", help="record the current execution condition")
    runtime.add_argument("--work-item", required=True)
    runtime.add_argument("--status", required=True)
    runtime.add_argument("--reason", required=True)
    runtime.add_argument("--expected-sha", required=True)

    diagnostic = commands.add_parser("diagnostic", help="track bounded diagnostic work")
    diagnostic_commands = diagnostic.add_subparsers(dest="diagnostic_command", required=True)
    start = diagnostic_commands.add_parser("start", help="start a persistent problem budget")
    start.add_argument("--work-item", required=True)
    start.add_argument("--problem-id", required=True)
    start.add_argument("--title", required=True)
    start.add_argument("--expected-sha", required=True)
    record = diagnostic_commands.add_parser("record", help="record one diagnostic round")
    record.add_argument("--work-item", required=True)
    record.add_argument("--problem-id", required=True)
    record.add_argument("--hypothesis", required=True)
    record.add_argument("--action", required=True)
    record.add_argument("--result", required=True)
    record.add_argument("--progress-evidence-id")
    record.add_argument("--expected-sha", required=True)
    wait = diagnostic_commands.add_parser("wait", help="record a bounded wait or pause")
    wait.add_argument("--work-item", required=True)
    wait.add_argument("--problem-id", required=True)
    wait.add_argument("--reason", required=True)
    wait.add_argument("--seconds", required=True, type=int)
    wait.add_argument("--expected-sha", required=True)
    resume = diagnostic_commands.add_parser("resume", help="close a bounded wait")
    resume.add_argument("--work-item", required=True)
    resume.add_argument("--problem-id", required=True)
    resume.add_argument("--expected-sha", required=True)
    alias = diagnostic_commands.add_parser("alias", help="link a renamed problem to its existing budget")
    alias.add_argument("--work-item", required=True)
    alias.add_argument("--problem-id", required=True)
    alias.add_argument("--alias", required=True)
    alias.add_argument("--expected-sha", required=True)
    decision = diagnostic_commands.add_parser("decision", help="record a user decision after escalation")
    decision.add_argument("--work-item", required=True)
    decision.add_argument("--problem-id", required=True)
    decision.add_argument("--decision", required=True, choices=("continue", "stop"))
    decision.add_argument("--reason", required=True)
    decision.add_argument("--verified-by", required=True)
    decision.add_argument("--source", required=True)
    decision.add_argument("--expected-sha", required=True)
    report = diagnostic_commands.add_parser("report", help="show attempts, budget, candidate and unknowns")
    report.add_argument("--work-item", required=True)
    report.add_argument("--problem-id")

    closeout = commands.add_parser("closeout", help="check dynamic records and complete only a verified scope")
    closeout_commands = closeout.add_subparsers(dest="closeout_command", required=True)
    closeout_check = closeout_commands.add_parser("check", help="read current local and overall completion evidence")
    closeout_check.add_argument("--work-item", required=True)
    file_record = closeout_commands.add_parser("record-file", help="record applicability, update and semantic review")
    file_record.add_argument("--work-item", required=True)
    file_record.add_argument("--file-id", required=True)
    file_record.add_argument("--disposition", required=True,
                             choices=("updated", "reviewed-no-change", "not-applicable"))
    file_record.add_argument("--reason", required=True)
    file_record.add_argument("--reviewer", required=True)
    file_record.add_argument("--review-summary", required=True)
    file_record.add_argument("--expected-sha", required=True)
    finalize = closeout_commands.add_parser("finalize", help="record local completion or guarded overall completion")
    finalize.add_argument("--work-item", required=True)
    finalize.add_argument("--scope", required=True, choices=("local", "overall"))
    finalize.add_argument("--recorded-by", required=True)
    finalize.add_argument("--reason", required=True)
    finalize.add_argument("--expected-sha", required=True)
    recover = closeout_commands.add_parser("recover", help="inspect state and Git identity without repairing anything")
    recover.add_argument("--work-item", required=True)

    maintenance = commands.add_parser("maintenance", help="track justified Harness follow-ups and their effects")
    maintenance_commands = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_open = maintenance_commands.add_parser("open", help="register a concrete, authorized follow-up")
    maintenance_open.add_argument("--work-item", required=True)
    maintenance_open.add_argument("--item-id", required=True)
    maintenance_open.add_argument("--category", required=True,
                                  choices=("rule-missing", "rule-not-followed", "tool-defect",
                                           "insufficient-evidence", "product-issue"))
    for name in ("problem", "owner", "scope", "authorization", "acceptance", "action",
                 "replacement-coverage", "history-location", "recheck-trigger"):
        maintenance_open.add_argument(f"--{name}", required=True)
    maintenance_open.add_argument("--expected-sha", required=True)
    maintenance_defer = maintenance_commands.add_parser("defer", help="preserve a follow-up with a review trigger")
    maintenance_defer.add_argument("--work-item", required=True)
    maintenance_defer.add_argument("--item-id", required=True)
    maintenance_defer.add_argument("--reason", required=True)
    maintenance_defer.add_argument("--recheck-trigger", required=True)
    maintenance_defer.add_argument("--expected-sha", required=True)
    maintenance_close = maintenance_commands.add_parser("close", help="close only after effect evidence exists")
    maintenance_close.add_argument("--work-item", required=True)
    maintenance_close.add_argument("--item-id", required=True)
    maintenance_close.add_argument("--effect-evidence-id", required=True)
    maintenance_close.add_argument("--effect-summary", required=True)
    maintenance_close.add_argument("--expected-sha", required=True)
    maintenance_list = maintenance_commands.add_parser("list", help="show open and closed follow-ups")
    maintenance_list.add_argument("--work-item", required=True)

    onboarding = commands.add_parser("onboard", help="discover a project and prepare explicit local or remote plans")
    onboarding_commands = onboarding.add_subparsers(dest="onboard_command", required=True)
    onboarding_commands.add_parser("discover", help="read repository rules, test markers and CI files")
    onboarding_plan = onboarding_commands.add_parser("plan", help="show a safe diff for one proposed local file")
    onboarding_plan.add_argument("--request-stdin", action="store_true", required=True,
                                 help="read a JSON plan from stdin; no file is written")
    onboarding_apply = onboarding_commands.add_parser("apply", help="apply one explicitly confirmed local file plan")
    onboarding_apply.add_argument("--request-stdin", action="store_true", required=True)
    onboarding_apply.add_argument("--plan-fingerprint", required=True)
    onboarding_apply.add_argument("--confirm-path", required=True)
    remote_check = onboarding_commands.add_parser("remote-check", help="validate a supplied GitHub snapshot without network access")
    remote_check.add_argument("--snapshot-stdin", action="store_true", required=True)
    remote_check.add_argument("--repository")
    remote_check.add_argument("--base-ref")
    remote_check.add_argument("--base-sha")
    return result


def _json_stdin() -> object:
    raw = sys.stdin.buffer.read(4_000_001)
    if len(raw) > 4_000_000:
        raise HarnessError("stdin JSON 超过4MB安全上限")
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "state":
            state = get_state(args.project_root, args.adapter, args.work_item)
            if args.as_json:
                print(json.dumps(state, ensure_ascii=False, indent=2))
            elif not state["connected"]:
                print("Harness: 未接入项目适配；未检查或修改项目状态。")
            else:
                print(f"工作项: {state['work_item_id']} @ {state['repository']}")
                print(f"生命周期: {state['lifecycle_status']}；阶段: {state['stage']}")
                print(f"运行状态: {state['runtime_status']}；Owner: {state['owner'] or '未记录'}")
                print(f"本机记录: sha256:{state['record_sha256']}；修订: {state['revision']}")
                print(f"最后更新: {state['last_updated'] or '未记录'}")
                print(f"已确认范围: {state['confirmed_decisions'] or '未记录'}")
                print(f"实施授权: {state['scope_authorization'] or '未记录'}")
                print(f"发布授权: {state['publication_authorization'] or '未记录'}")
                print(f"上次停点: {state['last_stop'] or '未记录'}")
                print(f"下一步: {state['next'] or '未记录'}")
                print(f"当前候选: {state['candidate']['candidate_fingerprint']}")
                print(f"Diff完整: {'是' if state['diff_completeness']['complete'] else '否'}")
                print(
                    f"本地收尾: {'可完成' if state['closeout'].get('local_ready') else '未完成'}；"
                    f"总体收尾: {'可完成' if state['closeout'].get('overall_ready') else '未完成'}"
                )
                if not state["closeout"].get("lifecycle_claim_valid", True):
                    print("错误: 当前 Status: done 缺少与当前候选相容的总体收尾证据。")
                if state["evidence_summary"]:
                    evidence_types = ", ".join(
                        f"{item['type']} ({item['verification_claim']}；来源尚未重核)"
                        for item in state["evidence_summary"]
                    )
                    print(f"已记录依据声明: {evidence_types}")
                for budget in state["diagnostic_budgets"]:
                    print(
                        f"诊断预算: {budget['problem_id']} / {budget['status']}；"
                        f"无进展 {budget['no_progress_rounds']} 轮；"
                        f"连续诊断 {budget['seconds_since_progress']} 秒"
                    )
                if state["legacy_read_only"]:
                    print("提示: 这是旧格式只读状态；需要显式 migrate 才能写入扩展。")
            return 0

        if args.command == "diff":
            report = get_diff(args.project_root, args.adapter, args.work_item)
            if args.as_json:
                print(json.dumps(report, ensure_ascii=True, indent=2))
            else:
                candidate = report["candidate"]
                print(f"候选: {report['repository']} / {report['work_item_id']} / {candidate['branch']}")
                print(f"HEAD: {candidate['head_sha']}；base {candidate['base_ref']}: {candidate['base_sha']}")
                print(f"候选指纹: {candidate['candidate_fingerprint']}")
                print(f"累计变更: {report['counts']['cumulative']} 个文件；本轮变更: {report['counts']['slice']} 个文件")
                for item in report["files"]:
                    print(f"{item['change']} {item['path']} [{', '.join(item['scopes'])}; {', '.join(item['risk'])}]")
                if not report["completeness"]["complete"]:
                    print("候选不完整：敏感 / 不可读内容未纳入；不能据此声称完整验证。")
                if report["completeness"]["stale_reasons"]:
                    print(f"待核实: {', '.join(report['completeness']['stale_reasons'])}")
            return 0

        if args.command == "capture-baseline":
            result = capture_baseline_record(
                args.project_root, args.adapter, args.work_item, args.scope, args.expected_sha
            )
        elif args.command == "attest-evidence":
            result = attest_evidence(
                args.project_root, args.adapter, args.work_item,
                args.expected_sha, args.evidence_json,
            )
        elif args.command == "migrate":
            result = migrate_record(
                args.project_root, args.adapter, args.work_item, args.expected_sha
            )
        elif args.command == "transition":
            result = transition_stage(
                args.project_root,
                args.adapter,
                args.work_item,
                args.to,
                args.expected_sha,
                args.evidence_json,
                args.next,
            )
        elif args.command == "diagnostic":
            if args.diagnostic_command == "start":
                result = start_problem(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.title, args.expected_sha,
                )
            elif args.diagnostic_command == "record":
                result = record_attempt(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.hypothesis, args.action, args.result, args.expected_sha,
                    args.progress_evidence_id,
                )
            elif args.diagnostic_command == "wait":
                result = start_wait(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.reason, args.seconds, args.expected_sha,
                )
            elif args.diagnostic_command == "resume":
                result = resume_wait(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.expected_sha,
                )
            elif args.diagnostic_command == "alias":
                result = add_alias(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.alias, args.expected_sha,
                )
            elif args.diagnostic_command == "decision":
                result = record_decision(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                    args.decision, args.reason, args.verified_by, args.source,
                    args.expected_sha,
                )
            else:
                result = diagnostic_report(
                    args.project_root, args.adapter, args.work_item, args.problem_id,
                )
        elif args.command == "closeout":
            if args.closeout_command == "check":
                result = check_closeout(args.project_root, args.adapter, args.work_item)
            elif args.closeout_command == "record-file":
                result = record_dynamic_file(
                    args.project_root, args.adapter, args.work_item, args.file_id,
                    args.disposition, args.reason, args.reviewer, args.review_summary,
                    args.expected_sha,
                )
            elif args.closeout_command == "finalize":
                result = finalize_closeout(
                    args.project_root, args.adapter, args.work_item, args.scope,
                    args.recorded_by, args.reason, args.expected_sha,
                )
            else:
                result = recover_view(args.project_root, args.adapter, args.work_item)
        elif args.command == "maintenance":
            if args.maintenance_command == "open":
                result = open_followup(
                    args.project_root, args.adapter, args.work_item, args.item_id, args.category,
                    args.problem, args.owner, args.scope, args.authorization, args.acceptance,
                    args.action, args.replacement_coverage, args.history_location,
                    args.recheck_trigger, args.expected_sha,
                )
            elif args.maintenance_command == "defer":
                result = defer_followup(
                    args.project_root, args.adapter, args.work_item, args.item_id,
                    args.reason, args.recheck_trigger, args.expected_sha,
                )
            elif args.maintenance_command == "close":
                result = close_followup(
                    args.project_root, args.adapter, args.work_item, args.item_id,
                    args.effect_evidence_id, args.effect_summary, args.expected_sha,
                )
            else:
                result = get_state(args.project_root, args.adapter, args.work_item)["maintenance_followups"]
        elif args.command == "onboard":
            if args.onboard_command == "discover":
                result = discover_project(args.project_root)
            elif args.onboard_command == "plan":
                result = plan_local_file(args.project_root, _json_stdin())
            elif args.onboard_command == "apply":
                result = apply_local_file(
                    args.project_root, _json_stdin(), args.plan_fingerprint, args.confirm_path,
                )
            else:
                result = check_github_snapshot(
                    args.project_root, _json_stdin(), expected_repository=args.repository,
                    expected_base_ref=args.base_ref, expected_base_sha=args.base_sha,
                )
        else:
            result = set_runtime_status(
                args.project_root,
                args.adapter,
                args.work_item,
                args.status,
                args.reason,
                args.expected_sha,
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (HarnessError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"harness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
