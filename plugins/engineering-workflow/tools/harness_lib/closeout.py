"""Dynamic-document checks, evidence-bound closeout, and safe recovery views."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re

from .state import (
    HarnessError,
    _check_expected,
    _load_target,
    _parse_record,
    _project,
    _render,
    _replace_under_lock,
    _sha,
    _validate_timestamp,
    _work_item_path,
)


MANIFEST_KEYS = {"schema_version", "delivery_required", "files", "tickets", "child_work_items"}
FILE_KEYS = {"id", "path", "owner", "authority", "triggers", "history_path"}
TICKET_KEYS = {"id", "path"}
CLOSEOUT_KEYS = {"schema_version", "manifest_sha256", "file_assessments", "local_completion", "overall_completion"}
ASSESSMENT_KEYS = {
    "disposition", "reason", "update_location", "reviewer", "review_summary", "file_sha256",
    "manifest_sha256", "candidate_fingerprint", "report_sha256", "assessed_at",
}
COMPLETION_KEYS = {
    "candidate_fingerprint", "manifest_sha256", "report_sha256", "closeout_sha256",
    "recorded_at", "recorded_by", "reason",
}
FILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9 _/-]*):\s*(.*?)\s*$")


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise HarnessError(f"{label} 必须是仓库内相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(part in {".", ".."} for part in path.parts):
        raise HarnessError(f"{label} 必须是规范仓库相对路径")
    return path


def _repo_file(root: Path, relative: str, label: str, *, required: bool = True) -> Path | None:
    path = _safe_relative(relative, label)
    full = root.joinpath(*path.parts)
    cursor = root
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise HarnessError(f"{label} 路径含符号链接；拒绝读取")
    if not full.exists():
        if required:
            raise HarnessError(f"{label} 不存在：{relative}")
        return None
    resolved = full.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise HarnessError(f"{label} 必须是仓库内普通文件")
    if resolved.stat().st_size > 2_000_000:
        raise HarnessError(f"{label} 超过2MB安全读取上限")
    return resolved


def _read_manifest(root: Path, adapter: dict) -> tuple[dict, str, str]:
    configured = adapter.get("dynamic_file_manifest")
    if not configured:
        raise HarnessError("项目 adapter 未配置 dynamic_file_manifest")
    path = _repo_file(root, configured, "dynamic file manifest")
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("dynamic file manifest 不可读取") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise HarnessError("dynamic file manifest 字段无效")
    if (
        manifest.get("schema_version") != 1
        or isinstance(manifest.get("schema_version"), bool)
        or not isinstance(manifest.get("delivery_required"), bool)
        or not isinstance(manifest.get("files"), list)
        or not isinstance(manifest.get("tickets"), list)
        or not isinstance(manifest.get("child_work_items"), list)
    ):
        raise HarnessError("dynamic file manifest 版本或内容无效")
    file_ids = set()
    for item in manifest["files"]:
        if not isinstance(item, dict) or set(item) != FILE_KEYS:
            raise HarnessError("dynamic file manifest files 条目无效")
        if not isinstance(item.get("id"), str) or not FILE_ID.fullmatch(item["id"]) or item["id"] in file_ids:
            raise HarnessError("dynamic file manifest 文件 ID 无效或重复")
        file_ids.add(item["id"])
        _safe_relative(item.get("path"), f"manifest file {item['id']}")
        _safe_relative(item.get("history_path"), f"manifest history {item['id']}")
        if _repo_file(root, item["history_path"], f"manifest history {item['id']}", required=False) is None:
            raise HarnessError(f"dynamic file manifest 历史去向不存在：{item['history_path']}")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in ("owner", "authority")):
            raise HarnessError("dynamic file manifest 缺少 Owner / 权威来源")
        if not isinstance(item.get("triggers"), list) or not item["triggers"] or any(
            not isinstance(value, str) or not value.strip() for value in item["triggers"]
        ):
            raise HarnessError("dynamic file manifest 缺少更新触发条件")
    ticket_ids = set()
    for item in manifest["tickets"]:
        if not isinstance(item, dict) or set(item) != TICKET_KEYS:
            raise HarnessError("dynamic file manifest Ticket 条目无效")
        if not isinstance(item.get("id"), str) or not FILE_ID.fullmatch(item["id"]) or item["id"] in ticket_ids:
            raise HarnessError("dynamic file manifest Ticket ID 无效或重复")
        ticket_ids.add(item["id"])
        _safe_relative(item.get("path"), f"ticket {item['id']}")
    if any(not isinstance(value, str) or not FILE_ID.fullmatch(value) for value in manifest["child_work_items"]):
        raise HarnessError("dynamic file manifest child_work_items 无效")
    if len(set(manifest["child_work_items"])) != len(manifest["child_work_items"]):
        raise HarnessError("dynamic file manifest child work item 重复")
    return manifest, _sha(raw), configured


def _empty_closeout() -> dict:
    return {"schema_version": 1, "manifest_sha256": None, "file_assessments": {},
            "local_completion": None, "overall_completion": None}


def validate_closeout(value: object) -> None:
    if not isinstance(value, dict) or set(value) != CLOSEOUT_KEYS or value.get("schema_version") != 1:
        raise HarnessError("状态扩展 closeout 格式无效")
    if isinstance(value.get("schema_version"), bool):
        raise HarnessError("状态扩展 closeout schema_version 无效")
    manifest_sha = value.get("manifest_sha256")
    if manifest_sha is not None and (not isinstance(manifest_sha, str) or not SHA256.fullmatch(manifest_sha)):
        raise HarnessError("状态扩展 closeout manifest 摘要无效")
    assessments = value.get("file_assessments")
    if not isinstance(assessments, dict):
        raise HarnessError("状态扩展 closeout 文件核对无效")
    for file_id, item in assessments.items():
        if not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id) or not isinstance(item, dict) or set(item) != ASSESSMENT_KEYS:
            raise HarnessError("状态扩展 closeout 文件核对条目无效")
        if (not isinstance(item.get("disposition"), str)
                or item.get("disposition") not in {"updated", "reviewed-no-change", "not-applicable"}):
            raise HarnessError("状态扩展 closeout disposition 无效")
        if any(not isinstance(item.get(key), str) or not item[key].strip()
               for key in ("reason", "reviewer", "review_summary")):
            raise HarnessError("状态扩展 closeout 文件核对缺少理由或Review")
        if item.get("update_location") is not None and not isinstance(item["update_location"], str):
            raise HarnessError("状态扩展 closeout update_location 无效")
        for key in ("file_sha256", "manifest_sha256", "candidate_fingerprint", "report_sha256"):
            if not isinstance(item.get(key), str) or not SHA256.fullmatch(item[key]):
                raise HarnessError(f"状态扩展 closeout {key} 无效")
        if item["disposition"] == "updated" and not item["update_location"]:
            raise HarnessError("状态扩展 closeout updated 缺少更新位置")
        if item["disposition"] != "updated" and item["update_location"] is not None:
            raise HarnessError("未更新 disposition 不能声明 update_location")
        _validate_timestamp(item.get("assessed_at"), "closeout assessment")
    for key in ("local_completion", "overall_completion"):
        record = value.get(key)
        if record is None:
            continue
        if not isinstance(record, dict) or set(record) != COMPLETION_KEYS:
            raise HarnessError(f"状态扩展 closeout {key} 无效")
        for field in ("candidate_fingerprint", "manifest_sha256", "report_sha256"):
            if not isinstance(record.get(field), str) or not SHA256.fullmatch(record[field]):
                raise HarnessError(f"状态扩展 closeout {key} {field} 无效")
        if not isinstance(record.get("closeout_sha256"), str) or not SHA256.fullmatch(record["closeout_sha256"]):
            raise HarnessError(f"状态扩展 closeout {key} closeout_sha256 无效")
        for field in ("recorded_by", "reason"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise HarnessError(f"状态扩展 closeout {key} 缺少 {field}")
        _validate_timestamp(record.get("recorded_at"), f"closeout {key}")


def _markdown_fields(raw: bytes, label: str) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessError(f"{label} 不是有效 UTF-8") from exc
    fields = {}
    for line in text.splitlines():
        if not line.strip():
            if fields:
                break
            continue
        match = FIELD.match(line)
        if match:
            key, value = match.groups()
            if key in fields:
                raise HarnessError(f"{label} 含重复字段：{key}")
            fields[key] = value
        elif fields:
            break
    return fields


def _ticket_result(raw: bytes) -> str:
    text = raw.decode("utf-8")
    matches = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            current = marker.group(1)[0]
            fence = None if fence == current else current
            continue
        if fence:
            continue
        match = re.match(r"^Result:\s*(.*?)\s*$", line)
        if match:
            matches.append(match.group(1))
    return matches[0] if len(matches) == 1 else ""


def _evidence_current(extension: dict, report: dict, evidence_type: str) -> bool:
    return any(
        item.get("type") == evidence_type
        and item.get("verification") == "attested"
        and item.get("candidate_fingerprint") == report["candidate"]["candidate_fingerprint"]
        and not item.get("input_identity")
        and (not item.get("report_sha256") or item["report_sha256"] == report["report_sha256"])
        for item in extension.get("evidence", [])
    )


def _completion_identity(report: dict, manifest_sha: str) -> dict:
    return {
        "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
        "manifest_sha256": manifest_sha,
        "report_sha256": report["report_sha256"],
    }


def _completion_state_sha256(*, identity: dict, closeout: dict, manifest: dict,
                             tickets: list[dict], child_items: list[dict],
                             extension: dict, validation_ok: bool, review_ok: bool,
                             manifest_review_ok: bool, followups: list[dict],
                             delivery_status: str, missing_remote: list[str],
                             publication_authorization: str, prs: str) -> str:
    relevant_types = {
        "validation-report", "code-review", "manifest-review",
        "review-confirmation", "merge-confirmation", "cleanup-confirmation",
        "maintenance-effect",
    }
    context = {
        "identity": identity,
        "file_assessments": closeout.get("file_assessments", {}),
        "tickets": tickets,
        "child_work_items": child_items,
        "diagnostics": extension.get("diagnostics", {}),
        "evidence": [item for item in extension.get("evidence", []) if item.get("type") in relevant_types],
        "maintenance": extension.get("maintenance", {"schema_version": 1, "items": {}}),
        "validation_evidence_current": validation_ok,
        "code_review_evidence_current": review_ok,
        "manifest_review_evidence_current": manifest_review_ok,
        "followups": followups,
        "delivery": {
            "required": manifest["delivery_required"],
            "status": delivery_status,
            "missing_evidence": missing_remote,
            "publication_authorization": publication_authorization,
            "prs": prs,
        },
    }
    encoded = json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha(encoded)


def check_closeout(root, adapter_arg, work_item: str) -> dict:
    from .budget import summaries as budget_summaries
    from .diff import build_diff_report

    git_root, records_root, adapter, _, _, parsed = _load_target(root, adapter_arg, work_item)
    extension = parsed["extension"] or {}
    report = build_diff_report(git_root, adapter, work_item, extension or None)
    try:
        manifest, manifest_sha, manifest_path = _read_manifest(git_root, adapter)
    except HarnessError as exc:
        if "未配置 dynamic_file_manifest" not in str(exc):
            raise
        reason = "dynamic_file_manifest_not_configured"
        return {
            "repository": adapter["repository"], "work_item_id": work_item,
            "manifest": {"configured": False},
            "candidate": {"fingerprint": report["candidate"]["candidate_fingerprint"],
                          "report_sha256": report["report_sha256"], "complete": report["completeness"]["complete"],
                          "counts": report["counts"]},
            "dynamic_files": [], "tickets": [], "child_work_items": [],
            "diagnostic_budgets": [], "active_diagnostics": [],
            "validation_evidence_current": False, "code_review_evidence_current": False,
            "maintenance_followups_open": [], "maintenance_followups_needing_recheck": [],
            "local_ready": False, "local_reasons": [reason], "local_completion_valid": False,
            "delivery_required": None, "delivery_status": "unknown",
            "missing_remote_evidence": [], "overall_ready": False,
            "overall_completion_valid": False, "current_lifecycle_status": parsed["fields"].get("Status"),
            "lifecycle_claim_valid": parsed["fields"].get("Status") != "done",
        }
    closeout = extension.get("closeout", _empty_closeout())
    assessments = closeout.get("file_assessments", {})
    file_results = []
    files_ok = True
    for item in manifest["files"]:
        assessment = assessments.get(item["id"])
        reasons = []
        if not assessment:
            reasons.append("missing_assessment")
        else:
            if assessment["manifest_sha256"] != manifest_sha:
                reasons.append("manifest_changed")
            if assessment["candidate_fingerprint"] != report["candidate"]["candidate_fingerprint"]:
                reasons.append("candidate_changed")
            if assessment["report_sha256"] != report["report_sha256"]:
                reasons.append("report_changed")
            path = _repo_file(git_root, item["path"], f"dynamic file {item['id']}", required=False)
            if path is None:
                reasons.append("file_missing")
            elif _sha(path.read_bytes()) != assessment["file_sha256"]:
                reasons.append("file_changed")
        files_ok = files_ok and not reasons
        file_results.append({
            "id": item["id"], "path": item["path"], "owner": item["owner"],
            "authority": item["authority"], "triggers": item["triggers"],
            "history_path": item["history_path"],
            "disposition": assessment.get("disposition") if assessment else None,
            "update_location": assessment.get("update_location") if assessment else None,
            "reviewer": assessment.get("reviewer") if assessment else None,
            "review_summary": assessment.get("review_summary") if assessment else None,
            "reasons": reasons,
        })
    tickets = []
    tickets_ok = True
    for item in manifest["tickets"]:
        path = _repo_file(git_root, item["path"], f"ticket {item['id']}", required=False)
        if path is None:
            fields, digest = {}, None
            status, result = "missing", ""
        else:
            raw = path.read_bytes()
            fields, digest = _markdown_fields(raw, f"ticket {item['id']}"), _sha(raw)
            status, result = fields.get("Status", "unknown"), _ticket_result(raw)
        complete = status == "done" and bool(result.strip())
        tickets_ok = tickets_ok and complete
        tickets.append({"id": item["id"], "path": item["path"], "status": status,
                        "result_present": bool(result.strip()), "sha256": digest, "complete": complete})
    child_items = []
    children_ok = True
    for child_id in manifest["child_work_items"]:
        try:
            child_path = _work_item_path(records_root, child_id)
            child_raw = child_path.read_bytes()
            child_parsed = _parse_record(child_raw, adapter, child_id)
            status = child_parsed["fields"].get("Status", "unknown")
            child_sha = _sha(child_raw)
        except (HarnessError, OSError):
            status, child_sha = "missing-or-invalid", None
        complete = status == "done"
        children_ok = children_ok and complete
        child_items.append({"id": child_id, "status": status, "sha256": child_sha, "complete": complete})
    budgets = budget_summaries(extension)
    active_diagnostics = [item for item in budgets if item["status"] in {"active", "waiting", "escalated", "needs_review"}]
    validation_ok = _evidence_current(extension, report, "validation-report")
    review_ok = _evidence_current(extension, report, "code-review")
    manifest_touched = any(change["path"] == manifest_path for change in report["files"])
    manifest_review_ok = not manifest_touched or _evidence_current(extension, report, "manifest-review")
    from .maintenance import list_followups

    followups = list_followups(extension, report)
    open_followups = [item for item in followups if item["status"] != "closed"]
    stale_closed_followups = [item for item in followups if item["status"] == "closed" and not item["effect_current"]]
    maintenance_ok = not open_followups and not stale_closed_followups
    local_reasons = []
    if not report["completeness"]["complete"]:
        local_reasons.append("candidate_diff_incomplete")
    if not files_ok:
        local_reasons.append("dynamic_files_unreviewed_or_stale")
    if not tickets_ok:
        local_reasons.append("unfinished_or_missing_ticket")
    if not children_ok:
        local_reasons.append("unfinished_or_missing_child_work_item")
    if active_diagnostics:
        local_reasons.append("diagnostic_budget_unresolved")
    if not validation_ok:
        local_reasons.append("current_validation_evidence_missing")
    if not review_ok:
        local_reasons.append("current_code_review_evidence_missing")
    if not manifest_review_ok:
        local_reasons.append("changed_manifest_needs_semantic_review")
    if open_followups:
        local_reasons.append("maintenance_follow_up_open")
    if stale_closed_followups:
        local_reasons.append("maintenance_effect_evidence_stale")
    local_ready = not local_reasons
    fields = parsed["fields"]
    delivery_status = "not_required"
    if manifest["delivery_required"]:
        auth_missing = fields.get("Publication authorization", "None").strip().lower() in {"none", "unknown", ""}
        if auth_missing:
            delivery_status = "pending_authorization"
            missing_remote = ["publication authorization"]
        elif fields.get("PRs", "None").strip().lower() not in {"none", ""}:
            required_remote = ("review-confirmation", "merge-confirmation", "cleanup-confirmation")
            missing_remote = [item_type for item_type in required_remote if not _evidence_current(extension, report, item_type)]
            delivery_status = "pending_remote_evidence" if missing_remote else "complete"
        else:
            delivery_status = "pending_delivery"
            missing_remote = ["PR identity"]
    else:
        missing_remote = []
    overall_ready = local_ready and delivery_status in {"not_required", "complete"}
    identity = _completion_identity(report, manifest_sha)
    identity["closeout_sha256"] = _completion_state_sha256(
        identity=identity, closeout=closeout, manifest=manifest, tickets=tickets,
        child_items=child_items, extension=extension, validation_ok=validation_ok,
        review_ok=review_ok, manifest_review_ok=manifest_review_ok, followups=followups,
        delivery_status=delivery_status, missing_remote=missing_remote,
        publication_authorization=fields.get("Publication authorization", "None"),
        prs=fields.get("PRs", "None"),
    )
    local_completion = closeout.get("local_completion")
    overall_completion = closeout.get("overall_completion")
    local_completion_valid = bool(
        local_completion and local_ready
        and all(local_completion.get(key) == value for key, value in identity.items())
    )
    overall_completion_valid = bool(overall_completion and all(overall_completion.get(key) == value for key, value in identity.items()) and overall_ready)
    lifecycle_claim_valid = parsed["fields"].get("Status") != "done" or overall_completion_valid
    return {
        "repository": adapter["repository"], "work_item_id": work_item,
        "manifest": {"configured": True, "path": manifest_path, "sha256": manifest_sha},
        "candidate": {"fingerprint": identity["candidate_fingerprint"], "report_sha256": identity["report_sha256"],
                      "complete": report["completeness"]["complete"], "counts": report["counts"]},
        "dynamic_files": file_results, "tickets": tickets, "child_work_items": child_items,
        "diagnostic_budgets": budgets, "active_diagnostics": active_diagnostics,
        "validation_evidence_current": validation_ok, "code_review_evidence_current": review_ok,
        "manifest_changed_in_candidate": manifest_touched, "manifest_review_evidence_current": manifest_review_ok,
        "maintenance_followups_open": open_followups,
        "maintenance_followups_needing_recheck": stale_closed_followups,
        "local_ready": local_ready, "local_reasons": local_reasons,
        "local_completion_valid": local_completion_valid,
        "delivery_required": manifest["delivery_required"], "delivery_status": delivery_status,
        "missing_remote_evidence": missing_remote, "overall_ready": overall_ready,
        "overall_completion_valid": overall_completion_valid,
        "closeout_sha256": identity["closeout_sha256"],
        "current_lifecycle_status": fields.get("Status"), "lifecycle_claim_valid": lifecycle_claim_valid,
    }


def record_dynamic_file(root, adapter_arg, work_item: str, file_id: str, disposition: str,
                        reason: str, reviewer: str, review_summary: str,
                        expected_sha: str) -> dict:
    from .diff import build_diff_report

    if disposition not in {"updated", "reviewed-no-change", "not-applicable"}:
        raise HarnessError("文件 disposition 必须为 updated、reviewed-no-change 或 not-applicable")
    if any(not isinstance(value, str) or not value.strip() for value in (reason, reviewer, review_summary)):
        raise HarnessError("动态文件核对必须记录理由、Reviewer 和语义核对摘要")
    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    manifest, manifest_sha, _ = _read_manifest(git_root, adapter)
    item = next((entry for entry in manifest["files"] if entry["id"] == file_id), None)
    if item is None:
        raise HarnessError("manifest 中不存在该 dynamic file id")
    file_path = _repo_file(git_root, item["path"], f"dynamic file {file_id}")
    report = build_diff_report(git_root, adapter, work_item, extension)
    if not report["completeness"]["complete"]:
        raise HarnessError("候选Diff不完整；不能登记收尾核对")
    update_location = None
    if disposition == "updated":
        if not reason.strip():
            raise HarnessError("updated disposition 必须说明更新内容")
        if not any(change["path"] == item["path"] and "cumulative" in change["scopes"] for change in report["files"]):
            raise HarnessError("updated 文件未出现在任务累计Diff；不能声明本次已更新")
        update_location = item["path"]
    closeout = json.loads(json.dumps(extension.get("closeout", _empty_closeout())))
    closeout["schema_version"] = 1
    closeout["manifest_sha256"] = manifest_sha
    closeout["file_assessments"][file_id] = {
        "disposition": disposition, "reason": reason.strip(), "update_location": update_location,
        "reviewer": reviewer.strip(), "review_summary": review_summary.strip(),
        "file_sha256": _sha(file_path.read_bytes()), "manifest_sha256": manifest_sha,
        "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
        "report_sha256": report["report_sha256"], "assessed_at": _timestamp(),
    }
    extension = dict(extension)
    extension["closeout"] = closeout
    extension["revision"] += 1
    content = _render(parsed["text"], parsed, extension, updates={"Last updated": _timestamp()})
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {"work_item_id": work_item, "file_id": file_id, "disposition": disposition,
            "record_sha256": new_hash}


def finalize_closeout(root, adapter_arg, work_item: str, scope: str,
                      recorded_by: str, reason: str, expected_sha: str) -> dict:
    if scope not in {"local", "overall"} or not recorded_by.strip() or not reason.strip():
        raise HarnessError("closeout finalize 必须指定 local / overall、记录人和理由")
    result = check_closeout(root, adapter_arg, work_item)
    if scope == "local" and not result["local_ready"]:
        raise HarnessError(f"本地范围未满足完成条件：{', '.join(result['local_reasons'])}")
    if scope == "overall" and not result["overall_ready"]:
        raise HarnessError(f"总体目标未满足完成条件；本地原因={','.join(result['local_reasons'])}；delivery={result['delivery_status']}")
    _, _, _, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    identity = {key: result["candidate"][key] for key in ("fingerprint", "report_sha256")}
    closeout = json.loads(json.dumps(extension.get("closeout", _empty_closeout())))
    manifest_sha = result["manifest"]["sha256"]
    record = {
        "candidate_fingerprint": identity["fingerprint"], "manifest_sha256": manifest_sha,
        "report_sha256": identity["report_sha256"], "closeout_sha256": result["closeout_sha256"],
        "recorded_at": _timestamp(),
        "recorded_by": recorded_by.strip(), "reason": reason.strip(),
    }
    closeout["schema_version"] = 1
    closeout["manifest_sha256"] = manifest_sha
    closeout["local_completion"] = record
    if scope == "overall":
        closeout["overall_completion"] = dict(record)
    extension = dict(extension)
    extension["closeout"] = closeout
    extension["revision"] += 1
    updates = {"Last updated": _timestamp()}
    if scope == "overall":
        updates["Status"] = "done"
    content = _render(parsed["text"], parsed, extension, updates=updates)
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {"work_item_id": work_item, "scope": scope,
            "status": "local-complete" if scope == "local" else "done",
            "delivery_status": result["delivery_status"], "record_sha256": new_hash}


def recover_view(root, adapter_arg, work_item: str) -> dict:
    from .budget import evidence_id
    from .diff import _is_sensitive, _risk, build_diff_report, current_snapshot

    configured = _project(root, adapter_arg)
    if configured is None:
        return {"connected": False, "checked": False, "status": "adapter-missing", "writes_performed": False}
    git_root, records_root, adapter = configured
    raw = None
    parsed = None
    record_state = "missing"
    try:
        path = _work_item_path(records_root, work_item)
        raw = path.read_bytes()
        record_sha = _sha(raw)
        try:
            parsed = _parse_record(raw, adapter, work_item)
            record_state = "valid"
        except HarnessError:
            record_state = "damaged-or-unsupported"
    except (HarnessError, OSError):
        record_sha = None
    report = build_diff_report(git_root, adapter, work_item, parsed["extension"] if parsed else None)
    snapshot = current_snapshot(git_root, adapter, work_item)
    current_tree_changes = []
    for path, item in snapshot["files"].items():
        sensitive = item["sensitive"] or _is_sensitive(path, adapter)
        locations = []
        if item.get("staged"):
            locations.append("staged")
        if item.get("unstaged"):
            locations.append("worktree")
        if item.get("untracked"):
            locations.append("untracked")
        current_tree_changes.append({
            "path": "[敏感路径已隐藏]" if sensitive else path,
            "locations": locations,
            "risk": ["sensitive_content_withheld"] if sensitive else _risk(path),
            "content_read": not sensitive and item.get("readable", False),
        })
    extension = parsed["extension"] if parsed else None
    evidence = extension.get("evidence", []) if extension else []
    fields = parsed["fields"] if parsed else {}
    primary_reference = fields.get("Primary record", "Self")
    if primary_reference.strip().lower() in {"self", ""}:
        primary_state = record_state
    else:
        primary_state = "external-reference-needs-check"
    related_items = []
    raw_related = fields.get("Related work items", "")
    if raw_related.strip().lower() not in {"", "none"}:
        for related_id in (value.strip() for value in raw_related.split(",")):
            if not related_id:
                continue
            try:
                related_path = _work_item_path(records_root, related_id)
                related_raw = related_path.read_bytes()
                related_parsed = _parse_record(related_raw, adapter, related_id)
                related_items.append({"id": related_id, "status": related_parsed["fields"].get("Status", "unknown"),
                                      "record_sha256": _sha(related_raw), "authorization_inherited": False})
            except (HarnessError, OSError):
                related_items.append({"id": related_id, "status": "missing-or-invalid", "authorization_inherited": False})
    return {
        "connected": True, "checked": True, "status_record": record_state,
        "record_sha256": record_sha, "writes_performed": False,
        "primary_record_reference": primary_reference, "primary_record_status": primary_state,
        "related_work_items": related_items,
        "repository": adapter["repository"], "work_item_id": work_item,
        "branch": report["candidate"]["branch"], "head_sha": report["candidate"]["head_sha"],
        "candidate_fingerprint": report["candidate"]["candidate_fingerprint"],
        "candidate_complete": report["completeness"]["complete"],
        "current_authorization": parsed["fields"].get("Implementation authorization", "Unknown") if parsed else "Unknown",
        "publication_authorization": parsed["fields"].get("Publication authorization", "Unknown") if parsed else "Unknown",
        "current_diff_counts": report["counts"], "changed_paths": report["files"],
        "current_tree_changes": current_tree_changes,
        "evidence_ids": [evidence_id(item) for item in evidence],
        "recovery_action": "先复制保留原件并核对主记录、Git候选与用户改动；此命令不会修复、覆盖或删除记录。",
    }
