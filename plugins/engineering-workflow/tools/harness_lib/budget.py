"""Persistent, bounded diagnostic budgets for the Harness CLI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from .state import (
    HarnessError,
    _check_expected,
    _load_target,
    _render,
    _replace_under_lock,
    _timestamp,
    _validate_timestamp,
)


PROBLEM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DIAGNOSTIC_LIMIT_SECONDS = 1800
NO_PROGRESS_LIMIT = 3
MAX_WAIT_SECONDS = 3600
EVIDENCE_PREFIX = "evidence-sha256:"
SUSPECT_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|token|password|secret|authorization|credential)\s*[:=]\s*(?:\"[^\"]+\"|'[^']+'|\S+)"
    r"|\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"
)
DIAGNOSTIC_KEYS = {"schema_version", "problems", "aliases"}
PROBLEM_KEYS = {
    "id", "title", "status", "created_at", "last_accounted_at", "total_seconds",
    "segment_seconds", "no_progress_rounds", "segment_started_at", "used_evidence_ids",
    "attempts", "waits", "pending_wait", "decisions", "time_uncertain",
}
ATTEMPT_KEYS = {
    "at", "hypothesis", "action", "result", "evidence_id", "progress", "progress_reason",
    "elapsed_seconds",
}
WAIT_KEYS = {"reason", "started_at", "deadline", "ended_at", "expired"}
PENDING_WAIT_KEYS = {"reason", "started_at", "deadline"}
DECISION_KEYS = {"at", "decision", "reason", "verified_by", "source"}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def evidence_id(item: dict) -> str:
    identity = {
        key: item.get(key)
        for key in (
            "type", "verification", "repository", "subject", "candidate_fingerprint",
            "report_sha256", "input_identity",
        )
    }
    return EVIDENCE_PREFIX + hashlib.sha256(_canonical(identity)).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HarnessError("诊断预算时间格式无效；需人工核实") from exc
    if parsed.tzinfo is None:
        raise HarnessError("诊断预算时间缺少时区；需人工核实")
    return parsed.astimezone(timezone.utc)


def _now(value: datetime | None = None) -> datetime:
    current = value if value is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise HarnessError("当前时间无时区；诊断预算需人工核实")
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _safe_summary(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise HarnessError(f"{label} 必须是非空安全摘要且不超过4000字符")
    if SUSPECT_SECRET.search(value):
        raise HarnessError(f"{label} 疑似包含凭据；请先改为不含Secret的摘要")
    return value.strip()


def _elapsed(now: datetime, since: str) -> int:
    seconds = int((now - _parse_time(since)).total_seconds())
    if seconds < 0:
        raise HarnessError("检测到时钟倒退；诊断预算需人工核实")
    return seconds


def _empty_diagnostics() -> dict:
    return {"schema_version": 1, "problems": {}, "aliases": {}}


def _diagnostics(extension: dict) -> dict:
    current = extension.get("diagnostics", _empty_diagnostics())
    if not isinstance(current, dict):
        raise HarnessError("诊断预算记录格式无效")
    return json.loads(json.dumps(current, ensure_ascii=True))


def _resolve(diagnostics: dict, problem_id: str) -> tuple[str, dict]:
    if not PROBLEM_ID.fullmatch(problem_id):
        raise HarnessError("problem-id 格式无效")
    canonical_id = diagnostics["aliases"].get(problem_id, problem_id)
    problem = diagnostics["problems"].get(canonical_id)
    if problem is None:
        raise HarnessError(f"找不到诊断问题：{problem_id}")
    return canonical_id, problem


def _view(problem: dict, now: datetime) -> dict:
    status = problem["status"]
    segment_seconds = problem["segment_seconds"]
    total_seconds = problem["total_seconds"]
    trigger_reasons = []
    try:
        if status == "active":
            elapsed = _elapsed(now, problem["last_accounted_at"])
            segment_seconds += elapsed
            total_seconds += elapsed
            if segment_seconds >= DIAGNOSTIC_LIMIT_SECONDS:
                status = "escalated"
                trigger_reasons.append("连续诊断达到1800秒")
            if problem["no_progress_rounds"] >= NO_PROGRESS_LIMIT:
                status = "escalated"
                trigger_reasons.append("连续3轮无实质进展")
        elif status == "waiting":
            pending = problem.get("pending_wait")
            if pending is None:
                status = "needs_review"
                trigger_reasons.append("等待状态缺少计时依据")
            elif now > _parse_time(pending["deadline"]):
                status = "needs_review"
                trigger_reasons.append("等待已超时，实际耗时需人工核实")
        if problem["time_uncertain"]:
            continued = bool(problem["decisions"] and problem["decisions"][-1]["decision"] == "continue")
            if status not in {"stopped", "escalated"} and not continued:
                status = "needs_review"
            trigger_reasons.append("历史诊断时间含未核实区间")
        if problem["status"] == "escalated":
            if problem["no_progress_rounds"] >= NO_PROGRESS_LIMIT:
                trigger_reasons.append("连续3轮无实质进展")
            if problem["segment_seconds"] >= DIAGNOSTIC_LIMIT_SECONDS:
                trigger_reasons.append("连续诊断达到1800秒")
    except HarnessError as exc:
        status = "needs_review"
        trigger_reasons.append(str(exc))
    return {
        "problem_id": problem["id"],
        "title": problem["title"],
        "status": status,
        "persisted_status": problem["status"],
        "no_progress_rounds": problem["no_progress_rounds"],
        "seconds_since_progress": segment_seconds,
        "cumulative_diagnostic_seconds": total_seconds,
        "limits": {"no_progress_rounds": NO_PROGRESS_LIMIT, "seconds_without_progress": DIAGNOSTIC_LIMIT_SECONDS},
        "time_uncertain": problem["time_uncertain"],
        "trigger_reasons": trigger_reasons,
        "wait_deadline": problem["pending_wait"]["deadline"] if problem.get("pending_wait") else None,
    }


def validate_diagnostics(value: object) -> None:
    if (not isinstance(value, dict) or set(value) != DIAGNOSTIC_KEYS
            or value.get("schema_version") != 1 or isinstance(value.get("schema_version"), bool)):
        raise HarnessError("状态扩展 diagnostics 格式无效")
    problems, aliases = value.get("problems"), value.get("aliases")
    if not isinstance(problems, dict) or not isinstance(aliases, dict):
        raise HarnessError("状态扩展 diagnostics 索引无效")
    for problem_id, problem in problems.items():
        if not isinstance(problem_id, str) or not PROBLEM_ID.fullmatch(problem_id):
            raise HarnessError("状态扩展 problem-id 无效")
        if not isinstance(problem, dict) or set(problem) != PROBLEM_KEYS or problem.get("id") != problem_id:
            raise HarnessError("状态扩展诊断问题字段无效")
        if (
            not isinstance(problem.get("title"), str) or not problem["title"].strip()
            or not isinstance(problem.get("status"), str)
            or problem.get("status") not in {"active", "waiting", "escalated", "needs_review", "stopped"}
            or any(not isinstance(problem.get(field), int) or isinstance(problem.get(field), bool) or problem[field] < 0
                   for field in ("total_seconds", "segment_seconds", "no_progress_rounds"))
            or not isinstance(problem.get("time_uncertain"), bool)
            or not isinstance(problem.get("used_evidence_ids"), list)
            or any(not isinstance(item, str) or not re.fullmatch(r"evidence-sha256:[0-9a-f]{64}", item)
                   for item in problem["used_evidence_ids"])
            or len(set(problem["used_evidence_ids"])) != len(problem["used_evidence_ids"])
            or not isinstance(problem.get("attempts"), list)
            or not isinstance(problem.get("waits"), list)
            or not isinstance(problem.get("decisions"), list)
        ):
            raise HarnessError("状态扩展诊断问题值无效")
        for field in ("created_at", "last_accounted_at", "segment_started_at"):
            _validate_timestamp(problem.get(field), f"diagnostics {field}")
        pending = problem.get("pending_wait")
        if pending is not None:
            if not isinstance(pending, dict) or set(pending) != PENDING_WAIT_KEYS or not isinstance(pending.get("reason"), str) or not pending["reason"].strip():
                raise HarnessError("状态扩展诊断等待字段无效")
            _validate_timestamp(pending.get("started_at"), "diagnostics wait start")
            _validate_timestamp(pending.get("deadline"), "diagnostics wait deadline")
            wait_limit = _elapsed(_parse_time(pending["deadline"]), pending["started_at"])
            if not 1 <= wait_limit <= MAX_WAIT_SECONDS:
                raise HarnessError("状态扩展诊断等待超过允许上限")
        if (problem["status"] == "waiting") != (pending is not None):
            raise HarnessError("状态扩展诊断等待状态不一致")
        for attempt in problem["attempts"]:
            if (
                not isinstance(attempt, dict) or set(attempt) != ATTEMPT_KEYS
                or any(not isinstance(attempt.get(field), str) or not attempt[field].strip()
                       for field in ("hypothesis", "action", "result", "progress_reason"))
                or attempt.get("evidence_id") is not None and (
                    not isinstance(attempt.get("evidence_id"), str)
                    or not re.fullmatch(r"evidence-sha256:[0-9a-f]{64}", attempt["evidence_id"])
                )
                or not isinstance(attempt.get("progress"), bool)
                or not isinstance(attempt.get("elapsed_seconds"), int)
                or isinstance(attempt.get("elapsed_seconds"), bool)
                or attempt["elapsed_seconds"] < 0
            ):
                raise HarnessError("状态扩展诊断轮次无效")
            _validate_timestamp(attempt.get("at"), "diagnostics attempt")
        for wait in problem["waits"]:
            if (
                not isinstance(wait, dict) or set(wait) != WAIT_KEYS
                or not isinstance(wait.get("reason"), str) or not wait["reason"].strip()
                or not isinstance(wait.get("expired"), bool)
                or wait.get("ended_at") is not None and not isinstance(wait["ended_at"], str)
            ):
                raise HarnessError("状态扩展诊断等待历史无效")
            _validate_timestamp(wait.get("started_at"), "diagnostics wait start")
            _validate_timestamp(wait.get("deadline"), "diagnostics wait deadline")
            wait_limit = _elapsed(_parse_time(wait["deadline"]), wait["started_at"])
            if not 1 <= wait_limit <= MAX_WAIT_SECONDS:
                raise HarnessError("状态扩展诊断等待历史超过允许上限")
            if wait["ended_at"] is not None:
                _validate_timestamp(wait["ended_at"], "diagnostics wait end")
        for decision in problem["decisions"]:
            if (
                not isinstance(decision, dict) or set(decision) != DECISION_KEYS
                or not isinstance(decision.get("decision"), str)
                or decision.get("decision") not in {"continue", "stop"}
                or any(not isinstance(decision.get(field), str) or not decision[field].strip()
                       for field in ("reason", "verified_by", "source"))
            ):
                raise HarnessError("状态扩展诊断决定无效")
            _validate_timestamp(decision.get("at"), "diagnostics decision")
    for alias, canonical_id in aliases.items():
        if (
            not isinstance(alias, str) or not PROBLEM_ID.fullmatch(alias)
            or alias in problems or not isinstance(canonical_id, str)
            or canonical_id not in problems or canonical_id == alias
        ):
            raise HarnessError("状态扩展诊断别名无效")


def summaries(extension: dict | None, now: datetime | None = None) -> list[dict]:
    diagnostics = extension.get("diagnostics", _empty_diagnostics()) if extension else _empty_diagnostics()
    current = _now(now)
    return [_view(problem, current) for problem in diagnostics["problems"].values()]


def _write(path, raw: bytes, parsed: dict, extension: dict, expected_sha: str, result: dict) -> dict:
    extension["revision"] += 1
    extension["diagnostics"] = result.pop("diagnostics")
    content = _render(parsed["text"], parsed, extension, updates={"Last updated": _timestamp()})
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return result | {"record_sha256": new_hash}


def _prepare(root, adapter_arg, work_item, expected_sha):
    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    diagnostics = _diagnostics(extension)
    validate_diagnostics(diagnostics)
    extension = dict(extension)
    return git_root, adapter, path, raw, parsed, extension, diagnostics


def start_problem(root, adapter_arg, work_item: str, problem_id: str, title: str,
                  expected_sha: str, *, now: datetime | None = None) -> dict:
    if not isinstance(problem_id, str) or not PROBLEM_ID.fullmatch(problem_id):
        raise HarnessError("problem-id 或标题无效")
    safe_title = _safe_summary(title, "问题标题")
    _, _, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    if problem_id in diagnostics["problems"] or problem_id in diagnostics["aliases"]:
        raise HarnessError("问题 ID 已存在；别名必须明确指向既有问题，不能重置预算")
    normalized_title = " ".join(safe_title.casefold().split())
    if any(" ".join(problem["title"].casefold().split()) == normalized_title
           for problem in diagnostics["problems"].values()):
        raise HarnessError("相同问题标题已存在；使用原问题 ID 或登记别名，不能重置预算")
    current = _now(now)
    stamp = _iso(current)
    problem = {
        "id": problem_id, "title": safe_title, "status": "active",
        "created_at": stamp, "last_accounted_at": stamp, "total_seconds": 0,
        "segment_seconds": 0, "no_progress_rounds": 0, "segment_started_at": stamp,
        "used_evidence_ids": [], "attempts": [], "waits": [], "pending_wait": None,
        "decisions": [], "time_uncertain": False,
    }
    diagnostics["problems"][problem_id] = problem
    extension["diagnostics"] = diagnostics
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": problem_id, "status": "active", "diagnostics": diagnostics,
    })


def record_attempt(root, adapter_arg, work_item: str, problem_id: str, hypothesis: str,
                   action: str, result: str, expected_sha: str,
                   progress_evidence: str | None = None, *, now: datetime | None = None) -> dict:
    hypothesis = _safe_summary(hypothesis, "原因假设")
    action = _safe_summary(action, "验证动作")
    result = _safe_summary(result, "观察结果")
    git_root, adapter, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    canonical_id, problem = _resolve(diagnostics, problem_id)
    current = _now(now)
    view = _view(problem, current)
    if view["status"] == "escalated":
        if problem["status"] == "active":
            problem["status"] = "escalated"
            problem["total_seconds"] = view["cumulative_diagnostic_seconds"]
            problem["segment_seconds"] = view["seconds_since_progress"]
            problem["last_accounted_at"] = _iso(current)
            extension["diagnostics"] = diagnostics
            saved = _write(path, raw, parsed, extension, expected_sha, {
                "problem_id": canonical_id, "status": "escalated", "trigger_reasons": view["trigger_reasons"],
                "diagnostics": diagnostics,
            })
            return saved | {"diagnostic_continued": False}
        raise HarnessError("诊断预算已触发；保存证据并生成报告，等待用户决定")
    if view["status"] == "stopped":
        raise HarnessError("诊断问题已停止；不会自动创建新预算")
    if view["status"] != "active":
        detail = "；".join(view["trigger_reasons"])
        raise HarnessError(f"当前诊断状态为 {view['status']}；必须先处理等待或人工核实。{detail}")
    elapsed = _elapsed(current, problem["last_accounted_at"])
    from .diff import build_diff_report

    report = build_diff_report(git_root, adapter, work_item, extension)
    progress = False
    progress_reason = "未提供新的有效证据"
    evidence_key = progress_evidence
    if progress_evidence:
        item = next((e for e in extension.get("evidence", []) if evidence_id(e) == progress_evidence), None)
        if item is None:
            raise HarnessError("progress-evidence-id 未引用状态记录中已存在的依据")
        if progress_evidence in problem["used_evidence_ids"]:
            progress_reason = "重复证据，不重置预算"
        elif item.get("verification") != "attested" or item.get("input_identity"):
            progress_reason = "依据未验证或外部输入需复核，不重置预算"
        elif item.get("candidate_fingerprint") != report["candidate"]["candidate_fingerprint"]:
            progress_reason = "依据绑定了旧候选，不重置预算"
        elif item.get("report_sha256") and item["report_sha256"] != report["report_sha256"]:
            progress_reason = "依据绑定了旧报告，不重置预算"
        elif not report["completeness"]["complete"]:
            progress_reason = "当前候选不完整，不重置预算"
        else:
            progress = True
            progress_reason = "引用了新的当前候选依据"
    problem["total_seconds"] += elapsed
    problem["last_accounted_at"] = _iso(current)
    if progress:
        problem["used_evidence_ids"].append(progress_evidence)
        problem["segment_seconds"] = 0
        problem["no_progress_rounds"] = 0
        problem["segment_started_at"] = _iso(current)
        problem["status"] = "active"
    else:
        problem["segment_seconds"] += elapsed
        problem["no_progress_rounds"] += 1
    attempt = {
        "at": _iso(current), "hypothesis": hypothesis, "action": action,
        "result": result, "evidence_id": evidence_key, "progress": progress,
        "progress_reason": progress_reason, "elapsed_seconds": elapsed,
    }
    problem["attempts"].append(attempt)
    if not progress and (problem["no_progress_rounds"] >= NO_PROGRESS_LIMIT
                         or problem["segment_seconds"] >= DIAGNOSTIC_LIMIT_SECONDS):
        problem["status"] = "escalated"
    diagnostics["problems"][canonical_id] = problem
    extension["diagnostics"] = diagnostics
    report_view = _view(problem, current)
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": canonical_id, "attempt": attempt, "budget": report_view,
        "diagnostic_continued": problem["status"] == "active", "diagnostics": diagnostics,
    })


def start_wait(root, adapter_arg, work_item: str, problem_id: str, reason: str,
               seconds: int, expected_sha: str, *, now: datetime | None = None) -> dict:
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 1 <= seconds <= MAX_WAIT_SECONDS:
        raise HarnessError(f"等待必须有理由且为1到{MAX_WAIT_SECONDS}秒")
    reason = _safe_summary(reason, "等待理由")
    _, _, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    canonical_id, problem = _resolve(diagnostics, problem_id)
    current = _now(now)
    view = _view(problem, current)
    if view["status"] == "escalated":
        raise HarnessError("诊断预算已触发；不能用等待延长预算")
    if view["status"] != "active":
        raise HarnessError(f"当前诊断状态为 {view['status']}；不能开始新等待")
    elapsed = _elapsed(current, problem["last_accounted_at"])
    projected = problem["segment_seconds"] + elapsed
    problem["total_seconds"] += elapsed
    problem["segment_seconds"] = projected
    problem["last_accounted_at"] = _iso(current)
    if projected >= DIAGNOSTIC_LIMIT_SECONDS:
        problem["status"] = "escalated"
        diagnostics["problems"][canonical_id] = problem
        extension["diagnostics"] = diagnostics
        return _write(path, raw, parsed, extension, expected_sha, {
            "problem_id": canonical_id, "status": "escalated", "diagnostic_continued": False,
            "trigger_reasons": ["连续诊断达到1800秒"], "diagnostics": diagnostics,
        })
    problem["pending_wait"] = {
        "reason": reason.strip(), "started_at": _iso(current),
        "deadline": _iso(current + timedelta(seconds=seconds)),
    }
    problem["status"] = "waiting"
    diagnostics["problems"][canonical_id] = problem
    extension["diagnostics"] = diagnostics
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": canonical_id, "status": "waiting", "deadline": problem["pending_wait"]["deadline"],
        "diagnostics": diagnostics,
    })


def resume_wait(root, adapter_arg, work_item: str, problem_id: str,
                expected_sha: str, *, now: datetime | None = None) -> dict:
    _, _, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    canonical_id, problem = _resolve(diagnostics, problem_id)
    if problem["status"] != "waiting" or not problem.get("pending_wait"):
        raise HarnessError("当前问题没有待恢复的有界等待")
    current = _now(now)
    pending = problem["pending_wait"]
    started = _parse_time(pending["started_at"])
    deadline = _parse_time(pending["deadline"])
    if current < started or current > deadline:
        problem["status"] = "needs_review"
        problem["time_uncertain"] = True
        problem["waits"].append({
            "reason": pending["reason"], "started_at": pending["started_at"],
            "deadline": pending["deadline"], "ended_at": None, "expired": current > deadline,
        })
        problem["pending_wait"] = None
        diagnostics["problems"][canonical_id] = problem
        extension["diagnostics"] = diagnostics
        return _write(path, raw, parsed, extension, expected_sha, {
            "problem_id": canonical_id, "status": "needs_review", "diagnostic_continued": False,
            "reason": "等待超时或时钟倒退；预算区间需人工核实", "diagnostics": diagnostics,
        })
    problem["waits"].append({
        "reason": pending["reason"], "started_at": pending["started_at"],
        "deadline": pending["deadline"], "ended_at": _iso(current), "expired": False,
    })
    problem["pending_wait"] = None
    problem["last_accounted_at"] = _iso(current)
    problem["status"] = "active"
    diagnostics["problems"][canonical_id] = problem
    extension["diagnostics"] = diagnostics
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": canonical_id, "status": "active", "resumed_at": _iso(current),
        "diagnostics": diagnostics,
    })


def add_alias(root, adapter_arg, work_item: str, problem_id: str, alias: str,
              expected_sha: str) -> dict:
    if not PROBLEM_ID.fullmatch(alias) or alias == problem_id:
        raise HarnessError("诊断别名格式无效")
    _, _, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    canonical_id, _ = _resolve(diagnostics, problem_id)
    if alias in diagnostics["problems"] or alias in diagnostics["aliases"]:
        raise HarnessError("诊断别名已占用；不会创建新预算")
    diagnostics["aliases"][alias] = canonical_id
    extension["diagnostics"] = diagnostics
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": canonical_id, "alias": alias, "diagnostics": diagnostics,
    })


def record_decision(root, adapter_arg, work_item: str, problem_id: str, decision: str,
                    reason: str, verified_by: str, source: str, expected_sha: str,
                    *, now: datetime | None = None) -> dict:
    if not isinstance(decision, str) or decision not in {"continue", "stop"}:
        raise HarnessError("用户决定必须记录 continue / stop、理由、核实人和来源")
    reason = _safe_summary(reason, "用户决定理由")
    verified_by = _safe_summary(verified_by, "决定核实人")
    source = _safe_summary(source, "决定来源")
    _, _, path, raw, parsed, extension, diagnostics = _prepare(root, adapter_arg, work_item, expected_sha)
    canonical_id, problem = _resolve(diagnostics, problem_id)
    current = _now(now)
    view = _view(problem, current)
    if problem["status"] == "stopped":
        raise HarnessError("诊断问题已停止；不会自动创建新预算")
    if problem["status"] == "active":
        try:
            elapsed = _elapsed(current, problem["last_accounted_at"])
            problem["total_seconds"] += elapsed
            problem["segment_seconds"] += elapsed
            problem["last_accounted_at"] = _iso(current)
        except HarnessError:
            problem["time_uncertain"] = True
    if decision == "continue":
        if view["status"] not in {"escalated", "needs_review"}:
            raise HarnessError("只有预算触发或待人工核实时，才能登记继续决定")
        if view["status"] == "needs_review":
            problem["time_uncertain"] = True
    if problem.get("pending_wait"):
        pending = problem["pending_wait"]
        expired = current > _parse_time(pending["deadline"]) or current < _parse_time(pending["started_at"])
        problem["waits"].append({
            "reason": pending["reason"], "started_at": pending["started_at"],
            "deadline": pending["deadline"], "ended_at": None if expired else _iso(current),
            "expired": expired,
        })
        problem["pending_wait"] = None
        if expired:
            problem["time_uncertain"] = True
    problem["decisions"].append({
        "at": _iso(current), "decision": decision, "reason": reason.strip(),
        "verified_by": verified_by.strip(), "source": source.strip(),
    })
    if decision == "continue":
        problem["status"] = "active"
        problem["segment_started_at"] = _iso(current)
        problem["last_accounted_at"] = _iso(current)
        problem["segment_seconds"] = 0
        problem["no_progress_rounds"] = 0
    else:
        problem["status"] = "stopped"
    diagnostics["problems"][canonical_id] = problem
    extension["diagnostics"] = diagnostics
    return _write(path, raw, parsed, extension, expected_sha, {
        "problem_id": canonical_id, "decision": decision, "status": problem["status"],
        "diagnostic_continued": decision == "continue", "diagnostics": diagnostics,
    })


def diagnostic_report(root, adapter_arg, work_item: str, problem_id: str | None = None,
                      *, now: datetime | None = None) -> dict:
    from .diff import build_diff_report

    git_root, _, adapter, _, _, parsed = _load_target(root, adapter_arg, work_item)
    extension = parsed["extension"]
    diagnostics = extension.get("diagnostics", _empty_diagnostics()) if extension else _empty_diagnostics()
    current = _now(now)
    if problem_id:
        canonical_id, problem = _resolve(diagnostics, problem_id)
        selected = [(canonical_id, problem)]
    else:
        selected = list(diagnostics["problems"].items())
    report = build_diff_report(git_root, adapter, work_item, extension)
    output = []
    for canonical_id, problem in selected:
        view = _view(problem, current)
        escalated = view["status"] in {"escalated", "needs_review"}
        output.append({
            **view,
            "attempts": problem["attempts"],
            "waits": problem["waits"],
            "decisions": problem["decisions"],
            "candidate": {
                "fingerprint": report["candidate"]["candidate_fingerprint"],
                "complete": report["completeness"]["complete"],
                "changed_file_count": report["counts"]["cumulative"],
                "slice_file_count": report["counts"]["slice"],
                "files": [item["path"] for item in report["files"]],
            },
            "failures_and_observations": [attempt["result"] for attempt in problem["attempts"]],
            "unknowns": [
                reason for reason in view["trigger_reasons"]
            ] + (["历史诊断时间含未核实区间"] if view["time_uncertain"] else [])
              + (["外部检查来源尚未实时复核"] if any(e.get("input_identity") for e in extension.get("evidence", [])) else []),
            "next_step_cost": {
                "requires_user_decision": escalated,
                "one_round_seconds_remaining": max(0, DIAGNOSTIC_LIMIT_SECONDS - view["seconds_since_progress"]),
                "no_progress_rounds_remaining": max(0, NO_PROGRESS_LIMIT - view["no_progress_rounds"]),
                "continuation_grant": "最多新增1800秒及3轮无进展预算" if escalated else None,
            },
        })
    return {
        "repository": adapter["repository"], "work_item_id": work_item,
        "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
        "diff_completeness": report["completeness"], "problems": output,
    }
