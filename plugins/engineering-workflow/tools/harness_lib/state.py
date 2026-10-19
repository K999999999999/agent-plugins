"""Safe, file-backed project state and workflow transition handling."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import subprocess
import tempfile
import uuid


EXTENSION_OPEN = "<!-- harness-state-extension:v1 -->"
EXTENSION_CLOSE = "<!-- /harness-state-extension -->"
EXTENSION_PATTERN = re.compile(
    r"(?ms)^<!-- harness-state-extension:v(\d+) -->\r?\n(.*?)^<!-- /harness-state-extension -->\r?$"
)
HISTORY_HEADING = re.compile(r"^#{1,6}\s+(历史|History\b)", re.IGNORECASE)
FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 _/-]*):\s*(.*?)(?:\r?\n)?$")
WORK_ITEM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RUNTIME_STATUSES = {
    "running", "waiting-tool", "waiting-ci", "waiting-user",
    "blocked", "paused", "idle", "unknown",
}
VERIFICATIONS = {"machine-verified", "attested", "unverified"}
TOP_LEVEL_FACTS = {
    "ID", "Status", "Stage", "Owner", "Target repository", "Spec", "Tickets",
    "Last updated", "Confirmed decisions", "Implementation authorization", "Publication authorization",
    "Experiment authorization", "PRs", "Verification", "Last stop", "Next",
}
EXTENSION_KEYS = {
    "schema_version", "revision", "runtime_status", "runtime_reason",
    "evidence", "transition_history", "migration", "task_baseline", "slice_baseline", "diagnostics",
    "closeout", "maintenance",
}
BASELINE_KEYS = {
    "schema_version", "repository", "work_item_id", "branch", "head_sha", "base_ref",
    "base_sha", "index_sha256", "worktree_sha256", "classifier_sha256",
    "candidate_fingerprint", "complete", "files", "captured_at",
}
FILE_STATE_KEYS = {
    "staged", "unstaged", "untracked", "index_objects", "head_object",
    "worktree_object", "worktree_mode", "present", "sensitive", "readable",
}
EVIDENCE_REQUIRED_KEYS = {
    "type", "verification", "verified_by", "source", "repository", "subject",
    "collected_at", "coverage",
}
EVIDENCE_OPTIONAL_KEYS = {"candidate_fingerprint", "report_sha256", "input_identity", "git_snapshot"}


class HarnessError(Exception):
    """A safe, expected state validation or transition failure."""


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HarnessError("无法核实项目 Git 身份") from exc
    return result.stdout.strip()


def _project(root_arg: Path, adapter_arg: Path | None) -> tuple[Path, Path, dict] | None:
    root = root_arg.expanduser().resolve()
    requested = adapter_arg if adapter_arg is not None else Path(".harness/project.json")
    if not requested.is_absolute():
        requested = root / requested
    if requested.is_symlink():
        raise HarnessError("项目适配文件不能是符号链接")
    adapter_path = requested.resolve()
    if not adapter_path.is_relative_to(root):
        raise HarnessError("项目适配文件必须位于项目仓库内")
    if not adapter_path.exists():
        return None
    if not adapter_path.is_file():
        raise HarnessError("项目适配文件必须是普通文件")
    try:
        adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("项目适配 JSON 不可读取") from exc
    if not isinstance(adapter, dict) or adapter.get("schema_version") != 1:
        raise HarnessError("不支持的项目适配格式")
    repository = adapter.get("repository")
    record_dir = adapter.get("work_item_record_directory")
    workflow = adapter.get("workflow")
    if not isinstance(repository, str) or not repository.strip():
        raise HarnessError("项目适配缺少仓库身份")
    record_path = Path(record_dir) if isinstance(record_dir, str) else None
    if (
        record_path is None or not record_dir or record_path.is_absolute()
        or ".." in record_path.parts
    ):
        raise HarnessError("项目适配中的状态目录必须是 Git 公共目录下的相对路径")
    if not isinstance(workflow, dict):
        raise HarnessError("项目适配缺少阶段规则")
    sensitive_paths = adapter.get("sensitive_paths", [])
    if not isinstance(sensitive_paths, list) or any(
        not isinstance(pattern, str) or not pattern for pattern in sensitive_paths
    ):
        raise HarnessError("项目适配 sensitive_paths 必须是字符串数组")
    if "base_branch" in adapter and (
        not isinstance(adapter["base_branch"], str) or not adapter["base_branch"]
    ):
        raise HarnessError("项目适配 base_branch 无效")
    stages, transitions = workflow.get("stages"), workflow.get("transitions")
    if (
        not isinstance(stages, list) or not stages
        or any(not isinstance(stage, str) or not stage for stage in stages)
        or len(set(stages)) != len(stages) or not isinstance(transitions, list)
    ):
        raise HarnessError("项目适配阶段列表无效")
    edges = []
    seen_edges = set()
    for edge in transitions:
        if not isinstance(edge, dict):
            raise HarnessError("项目适配转换规则无效")
        source, target, required = edge.get("from"), edge.get("to"), edge.get("required_evidence")
        candidate_required = edge.get("candidate_required", False)
        if (
            source not in stages or target not in stages or source == target
            or not isinstance(required, list)
            or any(not isinstance(item, str) or not item for item in required)
            or not isinstance(candidate_required, bool)
        ):
            raise HarnessError("项目适配转换边或必需依据无效")
        if (source, target) in seen_edges:
            raise HarnessError("项目适配包含重复阶段转换边")
        seen_edges.add((source, target))
        edges.append({
            "from": source, "to": target, "required_evidence": required,
            "candidate_required": candidate_required,
        })
    try:
        git_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        common_dir = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    except HarnessError:
        raise
    if not git_root.is_dir() or not common_dir.is_dir():
        raise HarnessError("无法核实 Git 仓库根目录或公共目录")
    records_root = common_dir / record_path
    if not records_root.resolve().is_relative_to(common_dir):
        raise HarnessError("项目状态目录通过符号链接越出 Git 公共目录")
    adapter["_validated_transitions"] = edges
    return git_root, records_root, adapter


def _work_item_path(records_root: Path, work_item: str) -> Path:
    if not WORK_ITEM_PATTERN.fullmatch(work_item) or work_item in {".", ".."}:
        raise HarnessError("工作项 ID 格式无效")
    root = records_root.resolve()
    path = root / work_item / "status.md"
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise HarnessError("工作项记录路径越界或为符号链接")
    if not path.is_file():
        raise HarnessError("找不到当前工作项状态记录")
    return path


def _validate_timestamp(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise HarnessError(f"{label} 时间缺失")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HarnessError(f"{label} 时间格式无效") from exc
    if parsed.tzinfo is None:
        raise HarnessError(f"{label} 时间必须含时区")


def _validate_git_snapshot(value: object, repository: str) -> dict:
    keys = {"repository", "head_sha", "base_ref", "base_sha", "captured_at"}
    if not isinstance(value, dict) or set(value) != keys:
        raise HarnessError("依据 git_snapshot 字段无效")
    if value.get("repository") != repository:
        raise HarnessError("依据 git_snapshot 仓库身份不匹配")
    for field in ("head_sha", "base_sha"):
        if not isinstance(value.get(field), str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value[field]):
            raise HarnessError(f"依据 git_snapshot {field} 无效")
    if not isinstance(value.get("base_ref"), str) or not value["base_ref"] or value["base_ref"].startswith("-"):
        raise HarnessError("依据 git_snapshot base_ref 无效")
    _validate_timestamp(value.get("captured_at"), "git_snapshot capture")
    return value


def _git_snapshot_identity(snapshot: dict) -> str:
    encoded = json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"git-snapshot-sha256:{_sha(encoded)}"


def _validate_evidence_items(items: object, repository: str) -> None:
    if not isinstance(items, list):
        raise HarnessError("状态扩展 evidence 必须是数组")
    for item in items:
        if (
            not isinstance(item, dict)
            or not EVIDENCE_REQUIRED_KEYS.issubset(item)
            or set(item) - EVIDENCE_REQUIRED_KEYS - EVIDENCE_OPTIONAL_KEYS
        ):
            raise HarnessError("状态扩展依据字段无效")
        if any(not isinstance(item[key], str) or not item[key].strip() for key in (
            "type", "verified_by", "source", "repository", "subject", "collected_at"
        )):
            raise HarnessError("状态扩展依据含空字段")
        if not isinstance(item["verification"], str) or item["verification"] not in VERIFICATIONS:
            raise HarnessError("状态扩展依据核实方式无效")
        if item["repository"] != repository:
            raise HarnessError("状态扩展依据仓库身份不匹配")
        for key in ("candidate_fingerprint", "report_sha256"):
            if key in item and (
                not isinstance(item[key], str) or not re.fullmatch(r"[0-9a-f]{64}", item[key])
            ):
                raise HarnessError(f"状态扩展依据 {key} 无效")
        if "input_identity" in item and not isinstance(item["input_identity"], str):
            raise HarnessError("状态扩展依据 input_identity 无效")
        if "git_snapshot" in item:
            snapshot = _validate_git_snapshot(item["git_snapshot"], repository)
            if item.get("input_identity") != _git_snapshot_identity(snapshot):
                raise HarnessError("状态扩展 git_snapshot 与 input_identity 不匹配")
        if not isinstance(item["coverage"], list) or any(
            not isinstance(value, str) or not value for value in item["coverage"]
        ):
            raise HarnessError("状态扩展依据 coverage 无效")
        _validate_timestamp(item["collected_at"], "依据采集")


def _validate_extension(extension: object, adapter: dict) -> dict:
    if (
        not isinstance(extension, dict)
        or extension.get("schema_version") != 1
        or isinstance(extension.get("schema_version"), bool)
    ):
        raise HarnessError("状态扩展格式无效")
    required_keys = {
        "schema_version", "revision", "runtime_status", "runtime_reason",
        "evidence", "transition_history",
    }
    if not required_keys.issubset(extension) or set(extension) - EXTENSION_KEYS:
        raise HarnessError("状态扩展字段集合无效")
    if set(extension) & TOP_LEVEL_FACTS:
        raise HarnessError("状态扩展重复定义顶层事实")
    if (
        not isinstance(extension["revision"], int)
        or isinstance(extension["revision"], bool)
        or extension["revision"] < 0
        or not isinstance(extension["runtime_status"], str)
        or extension["runtime_status"] not in RUNTIME_STATUSES
        or not isinstance(extension["runtime_reason"], str)
        or not isinstance(extension["transition_history"], list)
    ):
        raise HarnessError("状态扩展字段无效")
    _validate_evidence_items(extension["evidence"], adapter["repository"])
    if "diagnostics" in extension:
        from .budget import validate_diagnostics

        validate_diagnostics(extension["diagnostics"])
    if "closeout" in extension:
        from .closeout import validate_closeout

        validate_closeout(extension["closeout"])
    if "maintenance" in extension:
        from .maintenance import validate_maintenance

        validate_maintenance(extension["maintenance"])
    stages = adapter["workflow"]["stages"]
    for event in extension["transition_history"]:
        if (
            not isinstance(event, dict)
            or set(event) != {"from", "to", "at", "evidence_types"}
            or event["from"] not in stages
            or event["to"] not in stages
            or not isinstance(event["evidence_types"], list)
            or any(not isinstance(value, str) or not value for value in event["evidence_types"])
        ):
            raise HarnessError("状态扩展阶段历史无效")
        _validate_timestamp(event["at"], "阶段转换")
    if "migration" in extension:
        migration = extension["migration"]
        if (
            not isinstance(migration, dict)
            or set(migration) != {"from_sha256", "at"}
            or not isinstance(migration["from_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", migration["from_sha256"])
        ):
            raise HarnessError("状态扩展迁移来源无效")
        _validate_timestamp(migration["at"], "迁移")
    for key in ("task_baseline", "slice_baseline"):
        if key in extension:
            baseline = extension[key]
            if not isinstance(baseline, dict) or set(baseline) != BASELINE_KEYS:
                raise HarnessError(f"状态扩展 {key} 格式无效")
            if (
                baseline.get("schema_version") != 1
                or isinstance(baseline.get("schema_version"), bool)
                or baseline.get("repository") != adapter["repository"]
                or not isinstance(baseline.get("work_item_id"), str)
                or not isinstance(baseline.get("branch"), str)
                or not isinstance(baseline.get("base_ref"), str)
                or not isinstance(baseline.get("complete"), bool)
                or not isinstance(baseline.get("files"), dict)
            ):
                raise HarnessError(f"状态扩展 {key} 身份字段无效")
            if baseline["work_item_id"] == "":
                raise HarnessError(f"状态扩展 {key} 缺少工作项 ID")
            for field in ("head_sha", "base_sha"):
                value = baseline.get(field)
                if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
                    raise HarnessError(f"状态扩展 {key} 的 {field} 无效")
            for field in ("index_sha256", "worktree_sha256", "classifier_sha256", "candidate_fingerprint"):
                value = baseline.get(field)
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                    raise HarnessError(f"状态扩展 {key} 的 {field} 无效")
            _validate_timestamp(baseline.get("captured_at"), f"{key} capture")
            for relative, state in baseline["files"].items():
                relative_path = PurePosixPath(relative) if isinstance(relative, str) else None
                if (
                    relative_path is None
                    or not relative
                    or "\\" in relative
                    or "\x00" in relative
                    or relative_path.as_posix() != relative
                    or relative_path.is_absolute()
                    or any(part in {".", ".."} for part in relative_path.parts)
                    or not isinstance(state, dict)
                    or set(state) != FILE_STATE_KEYS
                    or not isinstance(state["index_objects"], list)
                    or any(
                        not isinstance(value, str)
                        or not re.fullmatch(r"(?:100644|100755|120000|160000):[0-9a-f]{40,64}:[0-3]", value)
                        for value in state["index_objects"]
                    )
                    or any(state[name] is not None and not isinstance(state[name], str)
                           for name in ("staged", "unstaged", "head_object", "worktree_object", "worktree_mode"))
                    or any(not isinstance(state[name], bool)
                           for name in ("untracked", "present", "sensitive", "readable"))
                    or state["head_object"] is not None and not re.fullmatch(
                        r"(?:100644|100755|120000):[0-9a-f]{40,64}", state["head_object"]
                    )
                    or state["worktree_object"] is not None and not re.fullmatch(
                        r"[0-9a-f]{40,64}", state["worktree_object"]
                    )
                    or state["worktree_mode"] not in {None, "100644", "100755", "120000"}
                    or state["sensitive"] and (state["readable"] or state["worktree_object"] is not None)
                ):
                    raise HarnessError(f"状态扩展 {key} 的文件快照无效")
    return extension


def _parse_record(raw: bytes, adapter: dict, work_item: str) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessError("状态记录不是有效 UTF-8") from exc
    matches = list(EXTENSION_PATTERN.finditer(text))
    if not matches and (
        "<!-- harness-state-extension:" in text
        or "<!-- /harness-state-extension -->" in text
    ):
        raise HarnessError("状态扩展标记格式无效")
    if len(matches) > 1:
        raise HarnessError("状态记录包含多个当前扩展块")
    extension = None
    extension_lines: set[int] = set()
    if matches:
        match = matches[0]
        if match.group(1) != "1":
            raise HarnessError("不支持的状态扩展版本")
        try:
            extension = json.loads(match.group(2))
        except json.JSONDecodeError as exc:
            raise HarnessError("状态扩展 JSON 格式无效") from exc
        extension = _validate_extension(extension, adapter)
        start_line = text.count("\n", 0, match.start())
        end_line = text.count("\n", 0, match.end())
        extension_lines.update(range(start_line, end_line + 1))

    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    fence_char = None
    header_started = False
    for line_number, line in enumerate(text.splitlines(keepends=True)):
        if line_number in extension_lines:
            continue
        stripped = line.strip()
        if not stripped:
            if header_started:
                break
            continue
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if marker:
            current = marker.group(1)[0]
            fence_char = None if fence_char == current else current
            continue
        if fence_char:
            continue
        if HISTORY_HEADING.match(line):
            break
        field = FIELD_PATTERN.match(line)
        if not field:
            if header_started:
                break
            if stripped.startswith("#"):
                continue
            continue
        header_started = True
        key, value = field.groups()
        if key in fields:
            raise HarnessError(f"状态记录含重复字段：{key}")
        fields[key] = value.strip()
        field_lines[key] = line_number
    if fields.get("ID") != work_item:
        raise HarnessError("状态记录 ID 与请求的工作项不一致")
    if extension:
        for key in ("task_baseline", "slice_baseline"):
            if key in extension and extension[key]["work_item_id"] != work_item:
                raise HarnessError(f"状态扩展 {key} 归属其他工作项")
    if fields.get("Status") not in {"open", "in-progress", "blocked", "done"}:
        raise HarnessError("未知或缺失的工作项生命周期状态")
    stage = fields.get("Stage")
    if stage not in adapter["workflow"]["stages"]:
        raise HarnessError("状态记录包含未知或缺失的阶段")
    return {
        "text": text, "fields": fields, "field_lines": field_lines,
        "stage": stage, "extension": extension,
        "legacy_read_only": extension is None,
    }


def _extension_block(extension: dict) -> str:
    data = json.dumps(extension, ensure_ascii=False, sort_keys=True, indent=2)
    return f"{EXTENSION_OPEN}\n{data}\n{EXTENSION_CLOSE}"


def _render(text: str, parsed: dict, extension: dict, *, updates: dict[str, str] | None = None) -> str:
    if updates:
        lines = text.splitlines(keepends=True)
        for key, value in updates.items():
            index = parsed["field_lines"].get(key)
            if index is None:
                if key == "Next":
                    raise HarnessError("状态记录缺少可更新的 Next 字段")
                continue
            line = lines[index]
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            lines[index] = f"{key}: {value}{ending}"
        text = "".join(lines)
    block = _extension_block(extension)
    matches = list(EXTENSION_PATTERN.finditer(text))
    if matches:
        match = matches[0]
        return text[:match.start()] + block + text[match.end():]
    if text and not text.endswith(("\n", "\r")):
        text += "\n"
    return text + block + "\n"


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_target(root: Path, adapter_arg: Path | None, work_item: str):
    configured = _project(root, adapter_arg)
    if configured is None:
        raise HarnessError("项目未接入 Harness adapter")
    git_root, records_root, adapter = configured
    path = _work_item_path(records_root, work_item)
    raw = path.read_bytes()
    parsed = _parse_record(raw, adapter, work_item)
    return git_root, records_root, adapter, path, raw, parsed


def get_state(root: Path, adapter_arg: Path | None, work_item: str | None) -> dict:
    configured = _project(root, adapter_arg)
    if configured is None:
        return {"connected": False, "reason": "project adapter is not configured", "checked": False}
    git_root, records_root, adapter = configured
    if not work_item:
        raise HarnessError("已接入项目必须显式指定 --work-item")
    path = _work_item_path(records_root, work_item)
    raw = path.read_bytes()
    parsed = _parse_record(raw, adapter, work_item)
    extension = parsed["extension"]
    fields = parsed["fields"]
    history = extension.get("transition_history", []) if extension else []
    evidence = extension.get("evidence", []) if extension else []
    common = _git(git_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    from .diff import build_diff_report

    current_report = build_diff_report(git_root, adapter, work_item, extension)
    current_fingerprint = current_report["candidate"]["candidate_fingerprint"]
    report_complete = current_report["completeness"]["complete"]
    evidence_summary = []
    from .budget import evidence_id, summaries as diagnostic_summaries

    for item in evidence:
        if not isinstance(item, dict):
            continue
        fingerprint = item.get("candidate_fingerprint")
        if item.get("verification") == "unverified":
            validity = "unverified"
        elif not fingerprint:
            validity = "unbound"
        elif not report_complete:
            validity = "needs_review_incomplete_candidate"
        elif fingerprint != current_fingerprint:
            validity = "stale_candidate"
        elif item.get("report_sha256") and item["report_sha256"] != current_report["report_sha256"]:
            validity = "stale_report"
        elif item.get("input_identity"):
            validity = "input_identity_needs_recheck"
        elif item.get("verification") == "machine-verified":
            validity = "source_needs_recheck"
        else:
            validity = "current_candidate_attested"
        evidence_summary.append({
            "evidence_id": evidence_id(item),
            "type": item.get("type"),
            "verification_claim": item.get("verification"),
            "source_validation": "not_checked_by_state_reader",
            "subject": item.get("subject"),
            "collected_at": item.get("collected_at"),
            "validity": validity,
        })
    diagnostic_budget_summary = diagnostic_summaries(extension)
    from .maintenance import list_followups

    maintenance_summary = list_followups(extension, current_report)
    from .closeout import check_closeout

    try:
        closeout_summary = check_closeout(root, adapter_arg, work_item)
    except HarnessError as exc:
        closeout_summary = {
            "local_ready": False, "overall_ready": False,
            "lifecycle_claim_valid": fields.get("Status") != "done",
            "error": str(exc),
        }
    return {
        "connected": True,
        "checked": True,
        "repository": adapter["repository"],
        "work_item_id": work_item,
        "lifecycle_status": fields["Status"],
        "stage": parsed["stage"],
        "runtime_status": extension.get("runtime_status", "unknown") if extension else "unknown",
        "runtime_reason": extension.get("runtime_reason", "") if extension else "",
        "owner": fields.get("Owner", ""),
        "next": fields.get("Next", ""),
        "last_stop": fields.get("Last stop", ""),
        "last_updated": fields.get("Last updated", ""),
        "confirmed_decisions": fields.get("Confirmed decisions", ""),
        "scope_authorization": fields.get("Implementation authorization", ""),
        "publication_authorization": fields.get("Publication authorization", ""),
        "record_sha256": _sha(raw),
        "candidate": current_report["candidate"],
        "diff_report_sha256": current_report["report_sha256"],
        "diff_completeness": current_report["completeness"],
        "revision": extension.get("revision") if extension else None,
        "legacy_read_only": parsed["legacy_read_only"],
        "transition_history": [
            {"from": e.get("from"), "to": e.get("to"), "at": e.get("at"),
             "evidence_types": e.get("evidence_types", [])}
            for e in history if isinstance(e, dict)
        ],
        "evidence_summary": evidence_summary,
        "diagnostic_budgets": diagnostic_budget_summary,
        "maintenance_followups": maintenance_summary,
        "closeout": closeout_summary,
        "git_root": str(git_root),
        "git_common_dir": str(Path(common).resolve()),
    }


def _validate_evidence(
    raw_json: str, adapter: dict, required: list[str], *, allow_machine_verified: bool = False
) -> list[dict]:
    try:
        items = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HarnessError("依据必须是有效 JSON 数组") from exc
    if not isinstance(items, list):
        raise HarnessError("依据必须是 JSON 数组")
    for item in items:
        if not isinstance(item, dict):
            raise HarnessError("依据项必须是 JSON 对象")
        for key in ("type", "verified_by", "source", "repository", "subject", "collected_at"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise HarnessError(f"依据缺少有效字段：{key}")
        if not isinstance(item.get("verification"), str) or item["verification"] not in VERIFICATIONS:
            raise HarnessError("依据核实方式无效")
        if item["verification"] == "machine-verified" and not allow_machine_verified:
            raise HarnessError("CLI 声明不能伪装机器核实；须由实际采集器生成 machine-verified 依据")
        if item["repository"] != adapter["repository"]:
            raise HarnessError("依据仓库身份与项目适配不一致")
        if not isinstance(item.get("coverage"), list) or any(
            not isinstance(value, str) or not value for value in item["coverage"]
        ):
            raise HarnessError("依据 coverage 必须是字符串数组")
        _validate_timestamp(item["collected_at"], "依据采集")
        if (
            not EVIDENCE_REQUIRED_KEYS.issubset(item)
            or set(item) - EVIDENCE_REQUIRED_KEYS - EVIDENCE_OPTIONAL_KEYS
        ):
            raise HarnessError("依据包含未知字段")
        for key in ("candidate_fingerprint", "report_sha256"):
            if key in item and (
                not isinstance(item[key], str) or not re.fullmatch(r"[0-9a-f]{64}", item[key])
            ):
                raise HarnessError(f"依据 {key} 必须是完整 SHA-256")
        if "input_identity" in item and not isinstance(item["input_identity"], str):
            raise HarnessError("依据 input_identity 必须是字符串")
        if "git_snapshot" in item:
            snapshot = _validate_git_snapshot(item["git_snapshot"], adapter["repository"])
            if item.get("input_identity") not in (None, _git_snapshot_identity(snapshot)):
                raise HarnessError("依据 git_snapshot 与 input_identity 不匹配")
    for item_type in required:
        if not any(
            item["type"] == item_type and item["verification"] != "unverified"
            for item in items
        ):
            raise HarnessError(f"缺少可用的必需依据：{item_type}")
    return items


def _acquire_lock(path: Path) -> tuple[Path, str]:
    lock = path.with_name(path.name + ".lock")
    nonce = uuid.uuid4().hex
    body = (
        f"nonce={nonce}\nhost={socket.gethostname()}\npid={os.getpid()}\n"
        f"created_at={_timestamp()}\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock, flags, 0o600)
    except FileExistsError as exc:
        raise HarnessError("状态写锁已存在；不会自动判断或删除遗留锁") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            lock.unlink()
        except OSError:
            pass
        raise
    return lock, nonce


def _release_lock(lock: Path, nonce: str) -> None:
    try:
        if f"nonce={nonce}\n" in lock.read_text(encoding="utf-8"):
            lock.unlink()
    except OSError:
        pass


def _atomic_replace(path: Path, content: bytes, original_mode: int) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, stat.S_IMODE(original_mode))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _replace_under_lock(path: Path, original: bytes, content: str, expected_sha: str) -> str:
    lock, nonce = _acquire_lock(path)
    try:
        current = path.read_bytes()
        if _sha(current) != expected_sha or current != original:
            raise HarnessError("状态记录在读取后发生变化；拒绝覆盖")
        _atomic_replace(path, content.encode("utf-8"), path.stat().st_mode)
        return _sha(content.encode("utf-8"))
    finally:
        _release_lock(lock, nonce)


def _check_expected(raw: bytes, expected_sha: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise HarnessError("--expected-sha 必须是完整 SHA-256")
    if _sha(raw) != expected_sha:
        raise HarnessError("状态记录摘要已变化；请重新读取后再操作")


def migrate_record(root: Path, adapter_arg: Path | None, work_item: str, expected_sha: str) -> dict:
    _, _, _, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    if parsed["extension"] is not None:
        raise HarnessError("状态记录已包含 v1 扩展，无需迁移")
    original_hash = _sha(raw)
    backup = path.with_name(f"{path.name}.pre-harness-{original_hash}.bak")
    extension = {
        "schema_version": 1, "revision": 0, "runtime_status": "unknown",
        "runtime_reason": "", "evidence": [], "transition_history": [],
        "migration": {"from_sha256": original_hash, "at": _timestamp()},
    }
    content = _render(parsed["text"], parsed, extension)
    lock, nonce = _acquire_lock(path)
    try:
        current = path.read_bytes()
        if _sha(current) != expected_sha or current != raw:
            raise HarnessError("状态记录在读取后发生变化；拒绝迁移")
        if backup.is_symlink():
            raise HarnessError("迁移备份路径是符号链接；保留原件并停止")
        if backup.exists():
            if backup.read_bytes() != raw:
                raise HarnessError("迁移备份已存在且内容不同；保留原件并停止")
        else:
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{backup.name}.", suffix=".tmp", dir=backup.parent)
            temporary_backup = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary_backup, backup)
                except FileExistsError:
                    if backup.is_symlink() or backup.read_bytes() != raw:
                        raise HarnessError("迁移备份并发冲突；保留原件并停止")
            finally:
                try:
                    temporary_backup.unlink()
                except OSError:
                    pass
        _atomic_replace(path, content.encode("utf-8"), path.stat().st_mode)
    finally:
        _release_lock(lock, nonce)
    return {"work_item_id": work_item, "record_sha256": _sha(content.encode("utf-8")), "backup": str(backup)}


def transition_stage(
    root: Path, adapter_arg: Path | None, work_item: str,
    target: str, expected_sha: str, evidence_json: str,
    next_step: str, *, allow_machine_verified: bool = False,
) -> dict:
    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    if not next_step.strip():
        raise HarnessError("阶段转换必须记录下一步")
    edge = next((item for item in adapter["_validated_transitions"]
                 if item["from"] == parsed["stage"] and item["to"] == target), None)
    if edge is None:
        raise HarnessError(f"阶段转换不在项目规则中：{parsed['stage']} → {target}")
    evidence = _validate_evidence(
        evidence_json, adapter, edge["required_evidence"],
        allow_machine_verified=allow_machine_verified,
    )
    if edge["candidate_required"]:
        from .diff import build_diff_report

        report = build_diff_report(git_root, adapter, work_item, extension)
        if not report["completeness"]["complete"]:
            raise HarnessError("候选Diff不完整；敏感或不可读文件需先处理并重新生成证据")
        if any(reason.endswith("_baseline_missing") for reason in report["completeness"]["stale_reasons"]):
            raise HarnessError("任务起点与本轮基线都必须先记录")
        candidate_fingerprint = report["candidate"]["candidate_fingerprint"]
        for required_type in edge["required_evidence"]:
            if not any(
                item["type"] == required_type
                and item.get("candidate_fingerprint") == candidate_fingerprint
                and item["verification"] != "unverified"
                and (not item.get("report_sha256") or item["report_sha256"] == report["report_sha256"])
                for item in evidence
            ):
                raise HarnessError(f"阶段转换缺少绑定当前候选的依据：{required_type}")
    updated = dict(extension)
    updated["revision"] += 1
    updated["evidence"] = [*extension["evidence"], *evidence]
    updated["transition_history"] = [
        *extension["transition_history"],
        {"from": parsed["stage"], "to": target, "at": _timestamp(),
         "evidence_types": [item["type"] for item in evidence]},
    ]
    content = _render(
        parsed["text"], parsed, updated,
        updates={"Stage": target, "Next": next_step.strip(), "Last updated": _timestamp()},
    )
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {"work_item_id": work_item, "from": parsed["stage"], "to": target, "record_sha256": new_hash}


def capture_baseline_record(
    root: Path, adapter_arg: Path | None, work_item: str, scope: str, expected_sha: str
) -> dict:
    from .diff import capture_baseline

    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    field = "task_baseline" if scope == "task" else "slice_baseline" if scope == "slice" else None
    if field is None:
        raise HarnessError("baseline scope 必须是 task 或 slice")
    if scope == "task" and field in extension:
        raise HarnessError("task baseline 已存在；不得重置任务起点")
    baseline = capture_baseline(git_root, adapter, work_item, scope)
    updated = dict(extension)
    updated["revision"] += 1
    updated[field] = baseline
    content = _render(parsed["text"], parsed, updated, updates={"Last updated": _timestamp()})
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {
        "work_item_id": work_item,
        "scope": scope,
        "candidate_fingerprint": baseline["candidate_fingerprint"],
        "record_sha256": new_hash,
    }


def get_diff(root: Path, adapter_arg: Path | None, work_item: str) -> dict:
    from .diff import build_diff_report

    git_root, _, adapter, _, _, parsed = _load_target(root, adapter_arg, work_item)
    return build_diff_report(git_root, adapter, work_item, parsed["extension"])


def attest_evidence(
    root: Path, adapter_arg: Path | None, work_item: str, expected_sha: str, evidence_json: str
) -> dict:
    from .diff import build_diff_report

    git_root, _, adapter, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    try:
        submitted = json.loads(evidence_json)
    except json.JSONDecodeError as exc:
        raise HarnessError("依据必须是有效 JSON") from exc
    if isinstance(submitted, dict):
        submitted = [submitted]
    if not isinstance(submitted, list):
        raise HarnessError("依据必须是 JSON 对象或数组")
    items = _validate_evidence(
        json.dumps(submitted, ensure_ascii=False), adapter, [], allow_machine_verified=False
    )
    if len(items) != 1:
        raise HarnessError("每次 attest-evidence 只接受一项依据")
    item = items[0]
    if item["type"] == "candidate-approval" and item["verification"] != "attested":
        raise HarnessError("candidate-approval 必须是明确来源的 attested 人工声明")
    if not item.get("candidate_fingerprint"):
        raise HarnessError("候选依据必须包含 candidate_fingerprint")
    report = build_diff_report(git_root, adapter, work_item, extension)
    if not report["completeness"]["complete"]:
        raise HarnessError("当前候选不完整；不能登记其审批或验证依据")
    if any(reason.endswith("_baseline_missing") for reason in report["completeness"]["stale_reasons"]):
        raise HarnessError("任务起点与本轮基线都必须先记录")
    if item["candidate_fingerprint"] != report["candidate"]["candidate_fingerprint"]:
        raise HarnessError("依据绑定了过期候选；请重读Diff并取得当前候选依据")
    if item.get("report_sha256") and item["report_sha256"] != report["report_sha256"]:
        raise HarnessError("依据引用的Diff报告已变化；请重新核实")
    if "git_snapshot" in item:
        snapshot = item["git_snapshot"]
        expected = {
            "repository": report["candidate"]["repository"],
            "head_sha": report["candidate"]["head_sha"],
            "base_ref": report["candidate"]["base_ref"],
            "base_sha": report["candidate"]["base_sha"],
        }
        if any(snapshot[field] != value for field, value in expected.items()):
            raise HarnessError("远端 Git 快照与当前仓库、HEAD 或 base 身份不相容")
        if any(set(change["locations"]) & {"staged", "worktree", "untracked"} for change in report["files"]):
            raise HarnessError("远端 Git 快照只适用于工作树、index 和未跟踪文件均干净的候选")
        item["input_identity"] = _git_snapshot_identity(snapshot)
    updated = dict(extension)
    updated["revision"] += 1
    updated["evidence"] = [*extension["evidence"], item]
    content = _render(parsed["text"], parsed, updated, updates={"Last updated": _timestamp()})
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {
        "work_item_id": work_item,
        "evidence_type": item["type"],
        "candidate_fingerprint": item["candidate_fingerprint"],
        "record_sha256": new_hash,
    }


def set_runtime_status(
    root: Path, adapter_arg: Path | None, work_item: str,
    status: str, reason: str, expected_sha: str,
) -> dict:
    _, _, _, path, raw, parsed = _load_target(root, adapter_arg, work_item)
    _check_expected(raw, expected_sha)
    extension = parsed["extension"]
    if extension is None:
        raise HarnessError("旧格式记录只读；请先显式执行 migrate")
    if status not in RUNTIME_STATUSES:
        raise HarnessError("未知的运行状态")
    if not reason.strip():
        raise HarnessError("运行状态变更必须说明原因")
    updated = dict(extension)
    updated["revision"] += 1
    updated["runtime_status"] = status
    updated["runtime_reason"] = reason.strip()
    content = _render(parsed["text"], parsed, updated, updates={"Last updated": _timestamp()})
    new_hash = _replace_under_lock(path, raw, content, expected_sha)
    return {"work_item_id": work_item, "runtime_status": status, "record_sha256": new_hash}
