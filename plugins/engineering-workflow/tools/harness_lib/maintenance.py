"""Evidence-backed Harness maintenance follow-ups."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from .state import (
    HarnessError,
    _check_expected,
    _load_target,
    _render,
    _replace_under_lock,
    _validate_timestamp,
)


ITEM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CATEGORIES = {"rule-missing", "rule-not-followed", "tool-defect", "insufficient-evidence", "product-issue"}
ROOT_KEYS = {"schema_version", "items"}
ITEM_KEYS = {
    "id", "category", "problem", "owner", "scope", "authorization", "acceptance", "action",
    "replacement_coverage", "history_location", "recheck_trigger", "status", "created_at",
    "deferred_reason", "effect_evidence_id", "effect_summary", "closed_at",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _empty() -> dict:
    return {"schema_version": 1, "items": {}}


def validate_maintenance(value: object) -> None:
    if (not isinstance(value, dict) or set(value) != ROOT_KEYS or value.get("schema_version") != 1
            or isinstance(value.get("schema_version"), bool) or not isinstance(value.get("items"), dict)):
        raise HarnessError("状态扩展 maintenance 格式无效")
    for item_id, item in value["items"].items():
        if not isinstance(item_id, str) or not ITEM_ID.fullmatch(item_id) or not isinstance(item, dict) or set(item) != ITEM_KEYS:
            raise HarnessError("状态扩展 maintenance 项目字段无效")
        if (item.get("id") != item_id or not isinstance(item.get("category"), str)
                or item.get("category") not in CATEGORIES):
            raise HarnessError("状态扩展 maintenance ID / category 无效")
        for field in (
            "problem", "owner", "scope", "authorization", "acceptance", "action",
            "replacement_coverage", "history_location", "recheck_trigger",
        ):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise HarnessError(f"状态扩展 maintenance 缺少 {field}")
        if not isinstance(item.get("status"), str) or item.get("status") not in {"open", "deferred", "closed"}:
            raise HarnessError("状态扩展 maintenance status 无效")
        for field in ("deferred_reason", "effect_evidence_id", "effect_summary"):
            if not isinstance(item.get(field), str):
                raise HarnessError(f"状态扩展 maintenance {field} 无效")
        if item.get("status") == "closed":
            if not item["effect_evidence_id"] or not item["effect_summary"] or not item["closed_at"]:
                raise HarnessError("关闭的 maintenance follow-up 缺少效果证据")
            _validate_timestamp(item["closed_at"], "maintenance close")
        elif item["effect_evidence_id"] or item["effect_summary"] or item["closed_at"]:
            raise HarnessError("未关闭的 maintenance follow-up 不能声明效果验证")
        if item["status"] == "deferred" and not item["deferred_reason"].strip():
            raise HarnessError("deferred follow-up 缺少暂缓理由")
        _validate_timestamp(item.get("created_at"), "maintenance creation")


def _load(extension: dict) -> dict:
    value = extension.get("maintenance", _empty())
    if not isinstance(value, dict):
        raise HarnessError("maintenance 记录格式无效")
    cloned = json.loads(json.dumps(value, ensure_ascii=True))
    validate_maintenance(cloned)
    return cloned


def _save(path, raw, parsed, extension, expected_sha, maintenance, result):
    extension["maintenance"] = maintenance
    extension["revision"] += 1
    content = _render(parsed["text"], parsed, extension, updates={"Last updated": _timestamp()})
    record_sha = _replace_under_lock(path, raw, content, expected_sha)
    return result | {"record_sha256": record_sha}


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise HarnessError(f"{label} 必须是非空安全摘要且不超过4000字符")
    if re.search(r"(?i)(?:token|password|secret|credential|api[_-]?key)\s*[:=]\s*\S+|\bbearer\s+\S+", value):
        raise HarnessError(f"{label} 疑似包含凭据；请先改为安全摘要")
    return value.strip()


def open_followup(root, adapter_arg, work_item: str, item_id: str, category: str,
                  problem: str, owner: str, scope: str, authorization: str,
                  acceptance: str, action: str, replacement_coverage: str,
                  history_location: str, recheck_trigger: str, expected_sha: str) -> dict:
    if not isinstance(item_id, str) or not ITEM_ID.fullmatch(item_id) or category not in CATEGORIES:
        raise HarnessError("maintenance ID 或 category 无效")
    values = {
        "problem": problem, "owner": owner, "scope": scope, "authorization": authorization,
        "acceptance": acceptance, "action": action, "replacement_coverage": replacement_coverage,
        "history_location": history_location, "recheck_trigger": recheck_trigger,
    }
    values = {key: _text(value, key) for key, value in values.items()}
    _, _, _, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    maintenance = _load(extension)
    if item_id in maintenance["items"]:
        raise HarnessError("maintenance ID 已存在；不会重置原问题")
    maintenance["items"][item_id] = {
        "id": item_id, "category": category, **values, "status": "open",
        "created_at": _timestamp(), "deferred_reason": "", "effect_evidence_id": "",
        "effect_summary": "", "closed_at": "",
    }
    return _save(path, raw, parsed, dict(extension), expected_sha, maintenance,
                 {"item_id": item_id, "status": "open"})


def defer_followup(root, adapter_arg, work_item: str, item_id: str, reason: str,
                   recheck_trigger: str, expected_sha: str) -> dict:
    reason = _text(reason, "defer reason")
    recheck_trigger = _text(recheck_trigger, "recheck trigger")
    _, _, _, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    maintenance = _load(extension)
    item = maintenance["items"].get(item_id)
    if item is None or item["status"] == "closed":
        raise HarnessError("找不到可暂缓的 maintenance follow-up")
    item["status"] = "deferred"
    item["deferred_reason"] = reason
    item["recheck_trigger"] = recheck_trigger
    return _save(path, raw, parsed, dict(extension), expected_sha, maintenance,
                 {"item_id": item_id, "status": "deferred"})


def close_followup(root, adapter_arg, work_item: str, item_id: str,
                   effect_evidence_id: str, effect_summary: str, expected_sha: str) -> dict:
    from .budget import evidence_id
    from .diff import build_diff_report

    effect_summary = _text(effect_summary, "effect summary")
    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    maintenance = _load(extension)
    item = maintenance["items"].get(item_id)
    if item is None or item["status"] == "closed":
        raise HarnessError("找不到可关闭的 maintenance follow-up")
    evidence = next((record for record in extension["evidence"] if evidence_id(record) == effect_evidence_id), None)
    if evidence is None or evidence.get("type") != "maintenance-effect" or evidence.get("verification") != "attested":
        raise HarnessError("关闭 follow-up 需要已有的 maintenance-effect attested 依据")
    if evidence.get("input_identity"):
        raise HarnessError("maintenance-effect 外部输入仍需复核")
    report = build_diff_report(git_root, adapter, work_item, extension)
    if evidence.get("candidate_fingerprint") != report["candidate"]["candidate_fingerprint"]:
        raise HarnessError("maintenance-effect 依据绑定了旧候选")
    if evidence.get("report_sha256") and evidence["report_sha256"] != report["report_sha256"]:
        raise HarnessError("maintenance-effect 依据绑定了旧报告")
    item["status"] = "closed"
    item["effect_evidence_id"] = effect_evidence_id
    item["effect_summary"] = effect_summary
    item["closed_at"] = _timestamp()
    return _save(path, raw, parsed, dict(extension), expected_sha, maintenance,
                 {"item_id": item_id, "status": "closed", "effect_evidence_id": effect_evidence_id})


def list_followups(extension: dict | None, report: dict | None = None) -> list[dict]:
    from .budget import evidence_id

    maintenance = _load(extension or {})
    results = []
    for item in maintenance["items"].values():
        effect_current = False
        if item["status"] == "closed":
            record = next((e for e in (extension or {}).get("evidence", [])
                           if evidence_id(e) == item["effect_evidence_id"]), None)
            effect_current = bool(
                record and record.get("type") == "maintenance-effect"
                and record.get("verification") == "attested" and not record.get("input_identity")
                and (report is None or record.get("candidate_fingerprint") == report["candidate"]["candidate_fingerprint"])
                and (report is None or not record.get("report_sha256") or record.get("report_sha256") == report["report_sha256"])
            )
        results.append({
            "id": item["id"], "category": item["category"], "problem": item["problem"],
            "owner": item["owner"], "scope": item["scope"], "authorization": item["authorization"],
            "acceptance": item["acceptance"], "action": item["action"],
            "replacement_coverage": item["replacement_coverage"], "history_location": item["history_location"],
            "recheck_trigger": item["recheck_trigger"], "status": item["status"],
            "deferred_reason": item["deferred_reason"], "effect_summary": item["effect_summary"],
            "effect_current": effect_current if item["status"] == "closed" else None,
        })
    return results
