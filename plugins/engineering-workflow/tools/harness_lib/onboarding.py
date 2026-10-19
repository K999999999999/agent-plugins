"""Read-only project discovery and explicitly confirmed local onboarding."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import tomllib

from .budget import SUSPECT_SECRET
from .diff import _is_sensitive
from .state import HarnessError, _validate_timestamp


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
REMOTE_SSH = re.compile(r"^(?:[^@/]+@)?([^:/]+)[:/]([^?#]+)$")
MAX_FILE_BYTES = 2_000_000
MAX_DISCOVERED_FILES = 200
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "dist", "build",
    "coverage", ".scratch", ".codex", "__pycache__", ".pytest_cache", ".next",
}
STACK_MARKERS = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java-maven",
    "build.gradle": "java-gradle",
    "build.gradle.kts": "java-gradle",
}
TEST_COMMAND_MARKERS = {
    "pytest": re.compile(r"\bpytest\b", re.IGNORECASE),
    "python-unittest": re.compile(r"\bpython(?:3(?:\.\d+)?)?\s+-m\s+unittest\b", re.IGNORECASE),
    "npm-test": re.compile(r"\bnpm\s+(?:run\s+)?test\b", re.IGNORECASE),
    "pnpm-test": re.compile(r"\bpnpm\s+(?:run\s+)?test\b", re.IGNORECASE),
    "yarn-test": re.compile(r"\byarn\s+test\b", re.IGNORECASE),
    "go-test": re.compile(r"\bgo\s+test\b", re.IGNORECASE),
    "cargo-test": re.compile(r"\bcargo\s+test\b", re.IGNORECASE),
    "dotnet-test": re.compile(r"\bdotnet\s+test\b", re.IGNORECASE),
    "maven-test": re.compile(r"\bmvn\s+(?:[^\n;&|]*\s)?test\b", re.IGNORECASE),
    "gradle-test": re.compile(r"\bgradle\s+(?:[^\n;&|]*\s)?test\b", re.IGNORECASE),
}
REMOTE_CHECK_KEYS = {
    "schema_version", "provider", "repository", "head_sha", "base_ref", "base_sha",
    "captured_at", "source", "rules_status", "strict_required", "required_checks",
    "observed_jobs", "verification", "unverified_reasons",
}


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HarnessError("无法核实项目 Git 身份") from exc
    return result.stdout.strip()


def _git_root(root_arg: Path) -> Path:
    root = root_arg.expanduser().resolve()
    try:
        result = _git(root, "rev-parse", "--show-toplevel")
    except HarnessError as exc:
        raise HarnessError("项目接入检查需要一个 Git 仓库") from exc
    return Path(result).resolve()


def _safe_relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise HarnessError("目标文件必须使用仓库内相对路径")
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or path.as_posix() != value
            or any(part in {".", ".."} for part in path.parts)):
        raise HarnessError("目标文件路径不规范或越出仓库")
    if path.parts[0] == ".git":
        raise HarnessError("不允许修改 Git 公共目录")
    return path


def _guard_path(root: Path, relative: str) -> Path:
    safe = _safe_relative(relative)
    path = root.joinpath(*safe.parts)
    cursor = root
    for part in safe.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise HarnessError("目标路径包含符号链接；拒绝读取或写入")
    if not path.parent.is_dir():
        raise HarnessError("目标文件的父目录必须已存在；工具不会创建未确认目录")
    cursor = path.parent
    while cursor != root:
        if (cursor / ".git").exists():
            raise HarnessError("目标位于嵌套 Git 仓库 / submodule；需由该仓库单独接入")
        cursor = cursor.parent
    if path.exists() and not path.is_file():
        raise HarnessError("目标必须是普通文件")
    if not path.resolve().is_relative_to(root):
        raise HarnessError("目标文件越出仓库")
    return path


def _target_identity(path: Path) -> dict | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise HarnessError("目标在检查期间变成符号链接或非普通文件")
    return {"device": info.st_dev, "inode": info.st_ino, "mode": stat.S_IMODE(info.st_mode)}


def _repo_path_no_symlink(root: Path, relative: str) -> Path | None:
    safe = _safe_relative(relative)
    path = root.joinpath(*safe.parts)
    cursor = root
    for part in safe.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return None
    return path


def _porcelain_paths(root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain=v1",
             "-z", "--untracked-files=all"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HarnessError("无法检查项目当前改动") from exc
    records = result.stdout.split(b"\0")
    changed: dict[str, str] = {}
    index = 0
    while index < len(records) and records[index]:
        record = records[index]
        if len(record) < 4 or record[2:3] != b" ":
            raise HarnessError("Git status 输出无法安全解析")
        status = record[:2].decode("ascii", errors="replace")
        path = os.fsdecode(record[3:]).replace(os.sep, "/")
        changed[path] = status
        index += 1
        if "R" in status or "C" in status:
            index += 1
    return changed


def _tracked_path_state(root: Path, relative: str) -> tuple[bool, bool]:
    try:
        indexed = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            capture_output=True,
        )
        flags = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "ls-files", "-v", "--", relative],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HarnessError("无法核实目标文件的 Git 索引状态") from exc
    tracked = indexed.returncode == 0 and bool(indexed.stdout.strip())
    special = bool(flags and (flags[0].islower() or flags[0] == "S"))
    return tracked, special


def _is_ignored(root: Path, relative: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "check-ignore", "-q", "--", relative],
            capture_output=True,
        )
    except OSError as exc:
        raise HarnessError("无法检查目标路径的 Git ignore 规则") from exc
    if result.returncode not in {0, 1}:
        raise HarnessError("Git ignore 检查失败")
    return result.returncode == 0


def _remote_target(root: Path) -> dict:
    try:
        raw = _git(root, "remote", "get-url", "origin")
    except HarnessError:
        return {"configured": False, "provider": None, "repository": None}
    host = ""
    path = ""
    if "://" in raw:
        from urllib.parse import urlsplit

        parsed = urlsplit(raw)
        host, path = parsed.hostname or "", parsed.path.lstrip("/")
    else:
        match = REMOTE_SSH.match(raw)
        if match:
            host, path = match.groups()
    path = path.removesuffix(".git").strip("/")
    if not host or not path or any(part in {".", ".."} for part in path.split("/")):
        return {"configured": True, "provider": "unknown", "repository": None}
    host = host.lower()
    provider = "github" if host == "github.com" else host
    target = f"{host}/{path}" if provider == "github" and len(path.split("/")) == 2 else host
    repository = target if provider == "github" and target != host else None
    return {
        "configured": True, "provider": provider,
        "repository": repository,
        "target": target,
    }


def _walk_files(root: Path) -> list[str]:
    found: list[str] = []
    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS
                   and not (current / name).is_symlink()
                   and not (current / name / ".git").exists()]
        for name in files:
            path = current / name
            if name in {"AGENTS.md", "CLAUDE.md"} and not path.is_symlink():
                found.append(path.relative_to(root).as_posix())
            if len(found) > MAX_DISCOVERED_FILES:
                raise HarnessError("Agent instructions 数量超过安全发现上限")
    copilot_instructions = _repo_path_no_symlink(root, ".github/copilot-instructions.md")
    if copilot_instructions is not None and copilot_instructions.is_file():
        found.append(".github/copilot-instructions.md")
    return sorted(set(found))


def _read_small(path: Path) -> bytes | None:
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size > MAX_FILE_BYTES:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_repo_small(root: Path, relative: str) -> bytes | None:
    path = _repo_path_no_symlink(root, relative)
    return _read_small(path) if path is not None else None


def _test_markers(text: str) -> list[str]:
    return sorted(name for name, pattern in TEST_COMMAND_MARKERS.items() if pattern.search(text))


def _ci_test_command_markers(text: str) -> list[str]:
    commands = []
    block_indent = None
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip())
        if block_indent is not None:
            if line.strip() and indent > block_indent:
                commands.append(line)
                continue
            block_indent = None
        match = re.match(r"^(\s*)(?:-\s*)?(?:run|script)\s*:\s*(.*)$", line)
        if not match:
            continue
        indent = len(match.group(1))
        value = match.group(2).strip()
        if value in {"", "|", "|-", ">", ">-"}:
            block_indent = indent
        elif value:
            commands.append(value)
    return _test_markers("\n".join(commands))


def _discover_ci_files(root: Path) -> list[Path]:
    files: list[Path] = []
    workflow_dir = _repo_path_no_symlink(root, ".github/workflows")
    if workflow_dir is not None and workflow_dir.is_dir():
        files.extend(path for path in workflow_dir.iterdir()
                     if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".yml", ".yaml"})
    for relative in (".gitlab-ci.yml", ".circleci/config.yml", ".buildkite/pipeline.yml",
                     ".azure-pipelines.yml", "azure-pipelines.yml", "appveyor.yml"):
        path = _repo_path_no_symlink(root, relative)
        if path is not None and path.is_file():
            files.append(path)
    if len(files) > MAX_DISCOVERED_FILES:
        raise HarnessError("CI 配置数量超过安全发现上限")
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def discover_project(root_arg: Path) -> dict:
    root = _git_root(root_arg)
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current") or "detached"
    remote = _remote_target(root)
    changed = _porcelain_paths(root)
    from .diff import _risk

    changed_files = []
    for path, status in sorted(changed.items()):
        sensitive = _is_sensitive(path, {})
        changed_files.append({
            "path": "<sensitive-path>" if sensitive else path,
            "status": status,
            "sensitive": sensitive,
            "risks": ["sensitive"] if sensitive else _risk(path),
        })

    stack_markers = []
    for relative, stack in STACK_MARKERS.items():
        path = _repo_path_no_symlink(root, relative)
        if path is not None and path.is_file():
            stack_markers.append({"stack": stack, "source": relative, "status": "observed"})

    test_entries = []
    pyproject = _read_repo_small(root, "pyproject.toml")
    if pyproject is not None:
        try:
            data = tomllib.loads(pyproject.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            data = None
        tool = data.get("tool") if isinstance(data, dict) else None
        pytest_config = tool.get("pytest") if isinstance(tool, dict) else None
        if isinstance(pytest_config, dict) and isinstance(pytest_config.get("ini_options"), dict):
            test_entries.append({"kind": "pytest", "source": "pyproject.toml [tool.pytest.ini_options]",
                                 "status": "declared-needs-confirmation"})
    for relative in ("pytest.ini", "tox.ini", "setup.cfg"):
        raw = _read_repo_small(root, relative)
        if raw is not None and re.search(rb"(?im)^\s*\[tool:pytest\]|^\s*\[pytest\]", raw):
            test_entries.append({"kind": "pytest", "source": relative, "status": "declared-needs-confirmation"})
    package_raw = _read_repo_small(root, "package.json")
    if package_raw is not None:
        try:
            package = json.loads(package_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            package = None
        scripts = package.get("scripts") if isinstance(package, dict) else None
        if isinstance(scripts, dict):
            for name in sorted(scripts):
                if (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", name)
                        and re.search(r"(?:^|:)(?:test|check|lint)(?:$|:)", name, re.IGNORECASE)):
                    test_entries.append({"kind": "package-script", "source": f"package.json#/scripts/{name}",
                                         "status": "declared-needs-confirmation"})
    makefile = _read_repo_small(root, "Makefile")
    if makefile is not None:
        targets = set()
        for line in makefile.decode("utf-8", errors="replace").splitlines():
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])", line)
            if match and re.search(r"test|check|lint", match.group(1), re.IGNORECASE):
                targets.add(match.group(1))
        test_entries.extend({"kind": "make-target", "source": f"Makefile:{name}",
                             "status": "declared-needs-confirmation"}
                            for name in sorted(targets))

    ci_files = []
    for path in _discover_ci_files(root):
        relative = path.relative_to(root).as_posix()
        raw = _read_repo_small(root, relative)
        ci_files.append({
            "path": "<sensitive-path>" if _is_sensitive(relative, {}) else relative,
            "sha256": _hash(raw) if raw is not None else None,
            "test_command_markers": _ci_test_command_markers(raw.decode("utf-8", errors="replace")) if raw is not None else [],
            "status": "observed-not-remotely-verified",
        })

    changed_files_truncated = len(changed_files) > 500
    return {
        "repository_root": str(root),
        "repository": remote,
        "branch": branch,
        "head_sha": head,
        "agent_instructions": _walk_files(root),
        "stack_markers": stack_markers,
        "test_entries": sorted(test_entries, key=lambda item: (item["source"], item["kind"])),
        "ci_files": ci_files,
        "changed_files": changed_files[:500],
        "changed_files_count": len(changed_files),
        "changed_files_truncated": changed_files_truncated,
        "unknowns": [
            "Declared test entries require a human to confirm command, scope and actual execution.",
            "Workflow files do not prove a run succeeded or a check is required by the remote repository.",
            "Remote branch rules are not read by this local discovery command.",
        ],
        "complete": False,
    }


def _parse_plan_request(value: object) -> tuple[str, str, str | None, dict | None]:
    if not isinstance(value, dict) or set(value) - {"schema_version", "path", "content", "expected_sha256", "remote_plan"}:
        raise HarnessError("接入计划字段无效")
    if value.get("schema_version") != 1 or isinstance(value.get("schema_version"), bool):
        raise HarnessError("接入计划 schema_version 无效")
    relative = value.get("path")
    _safe_relative(relative)
    content = value.get("content")
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise HarnessError("接入计划内容必须是 UTF-8 文本且不超过2MB")
    if "\x00" in content:
        raise HarnessError("不支持二进制接入文件")
    expected = value.get("expected_sha256")
    if expected is not None and (not isinstance(expected, str) or not SHA256.fullmatch(expected)):
        raise HarnessError("expected_sha256 必须为完整小写 SHA-256 或 null")
    if SUSPECT_SECRET.search(content):
        raise HarnessError("接入内容疑似含凭据；拒绝生成可展示Diff")
    remote_plan = value.get("remote_plan")
    if remote_plan is not None:
        remote_plan = _validate_remote_plan(remote_plan)
    return relative, content, expected, remote_plan


def _validate_remote_plan(value: object) -> dict:
    keys = {"provider", "target", "base_ref", "required_checks", "checks_source", "source_verification",
            "strict_required", "rollback"}
    if not isinstance(value, dict) or set(value) != keys:
        raise HarnessError("远端计划字段无效；必须说明目标、检查来源、strict 与回退")
    if value.get("provider") != "github":
        raise HarnessError("当前只支持准备 GitHub 远端计划；其他平台需明确标记为待适配")
    for field in ("target", "base_ref", "checks_source", "rollback"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise HarnessError(f"远端计划缺少 {field}")
        if SUSPECT_SECRET.search(value[field]):
            raise HarnessError(f"远端计划 {field} 疑似含凭据")
    if ("://" in value["target"] or value["target"].startswith("git@")
            or _normalize_repository(value["target"]) is None):
        raise HarnessError("远端计划 target 必须是 GitHub 仓库身份，不得包含任意 URL 或凭据")
    if not isinstance(value.get("required_checks"), list) or not value["required_checks"]:
        raise HarnessError("远端计划必须引用本仓库实际已核实的 required checks，不能生成空绿色 job")
    if any(not isinstance(item, str) or not item.strip() for item in value["required_checks"]):
        raise HarnessError("required_checks 条目无效")
    if any(SUSPECT_SECRET.search(item) for item in value["required_checks"]):
        raise HarnessError("required_checks 名称疑似含凭据")
    if len(set(value["required_checks"])) != len(value["required_checks"]):
        raise HarnessError("required_checks 不能重复")
    if not isinstance(value.get("strict_required"), bool):
        raise HarnessError("strict_required 必须是明确布尔值")
    if (not isinstance(value.get("source_verification"), str)
            or value["source_verification"] not in {"attested", "unverified"}):
        raise HarnessError("source_verification 必须明确区分 attested / unverified")
    return {
        "provider": "github", "target": value["target"].strip(), "base_ref": value["base_ref"].strip(),
        "required_checks": [item.strip() for item in value["required_checks"]],
        "checks_source": value["checks_source"].strip(), "source_verification": value["source_verification"],
        "strict_required": value["strict_required"], "rollback": value["rollback"].strip(),
        "status": "proposed-not-applied", "remote_apply_supported": False,
    }


def _redacted_diff(root: Path, path: Path, relative: str, new_content: str) -> list[str]:
    if _is_sensitive(relative, {}):
        raise HarnessError("敏感路径不能进入接入Diff")
    current = path.read_bytes() if path.exists() else b""
    try:
        old_lines = current.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise HarnessError("现有目标不是 UTF-8 文本；拒绝覆盖") from exc
    new_lines = new_content.splitlines(keepends=True)
    generated = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{relative}", tofile=f"b/{relative}")
    output = []
    for line in generated:
        if SUSPECT_SECRET.search(line):
            output.append("[REDACTED: secret-like line]\n")
        else:
            output.append(line)
    return output


def plan_local_file(root_arg: Path, request: object) -> dict:
    root = _git_root(root_arg)
    relative, content, expected, remote_plan = _parse_plan_request(request)
    path = _guard_path(root, relative)
    if _is_sensitive(relative, {}):
        raise HarnessError("敏感路径不能作为接入目标")
    current_raw = path.read_bytes() if path.exists() else None
    target_identity = _target_identity(path)
    if current_raw is not None and len(current_raw) > MAX_FILE_BYTES:
        raise HarnessError("现有目标超过2MB安全读取上限")
    current_sha = _hash(current_raw) if current_raw is not None else None
    modified = relative in _porcelain_paths(root)
    tracked, special_index_state = _tracked_path_state(root, relative)
    ignored = _is_ignored(root, relative)
    expected_matches = current_sha == expected
    desired_sha = _hash(content.encode("utf-8"))
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "branch", "--show-current") or "detached"
    remote = _remote_target(root)
    plan_identity = {
        "schema_version": 1, "repository_root": str(root), "repository": remote.get("repository"),
        "branch": branch, "head_sha": head, "path": relative,
        "expected_sha256": expected, "current_sha256": current_sha,
        "desired_sha256": desired_sha, "target_identity": target_identity,
        "remote_plan": remote_plan,
    }
    fingerprint = _canonical_hash(plan_identity)
    conflicts = []
    if modified:
        conflicts.append("target_has_user_or_uncommitted_changes")
    if current_raw is not None and not tracked:
        conflicts.append("existing_target_is_not_tracked_and_cannot_be_restored_from_git")
    if special_index_state:
        conflicts.append("target_uses_assume_unchanged_or_skip_worktree_index_state")
    if current_raw is None and ignored:
        conflicts.append("new_target_would_be_hidden_by_git_ignore")
    if not expected_matches:
        conflicts.append("expected_file_identity_does_not_match")
    if current_raw is not None and current_raw == content.encode("utf-8"):
        action = "already-present"
    else:
        action = "create" if current_raw is None else "update"
    return {
        "repository_root": str(root), "repository": remote,
        "path": relative, "action": action,
        "current_sha256": current_sha, "desired_sha256": desired_sha,
        "target_identity": target_identity,
        "tracked": tracked, "ignored": ignored,
        "expected_sha256_matches": expected_matches,
        "target_has_uncommitted_changes": modified,
        "applicable": not conflicts and action != "already-present",
        "conflicts": conflicts,
        "plan_fingerprint": fingerprint,
        "diff": _redacted_diff(root, path, relative, content),
        "remote_plan": remote_plan or {"status": "not-provided", "complete": False},
        "rollback": {
            "original_sha256": current_sha,
            "method": "tracked-clean-file-can-be-restored-from-HEAD" if current_sha and tracked and not modified
                      else "new-file-removal-requires-human-confirmation" if current_sha is None
                      else "unavailable-until-original-file-is-tracked-and-clean",
            "automatic_rollback": False,
        },
    }


def apply_local_file(root_arg: Path, request: object, expected_plan_fingerprint: str,
                     confirmed_path: str) -> dict:
    if not isinstance(expected_plan_fingerprint, str) or not SHA256.fullmatch(expected_plan_fingerprint):
        raise HarnessError("必须提供接入计划的 SHA-256")
    relative, content, expected, _ = _parse_plan_request(request)
    if confirmed_path != relative:
        raise HarnessError("确认路径必须与计划中的唯一目标文件完全一致")
    plan = plan_local_file(root_arg, request)
    root = Path(plan["repository_root"])
    path = _guard_path(root, relative)
    current_raw = path.read_bytes() if path.exists() else None
    desired_raw = content.encode("utf-8")
    if current_raw == desired_raw:
        return {"status": "already-present", "path": relative,
                "sha256": _hash(desired_raw), "writes_performed": False,
                "plan_fingerprint": plan["plan_fingerprint"]}
    if plan["plan_fingerprint"] != expected_plan_fingerprint:
        raise HarnessError("接入计划身份已变化；请重新展示Diff并确认")
    if not plan["applicable"]:
        raise HarnessError(f"接入计划不可应用：{', '.join(plan['conflicts']) or plan['action']}")
    if _is_sensitive(relative, {}) or relative in _porcelain_paths(root):
        raise HarnessError("目标敏感或已出现未提交改动；拒绝覆盖")
    current_sha = _hash(current_raw) if current_raw is not None else None
    if current_sha != expected:
        raise HarnessError("目标文件在计划后发生变化；拒绝覆盖")
    target_identity = _target_identity(path)
    if target_identity != plan["target_identity"]:
        raise HarnessError("目标文件系统身份在计划后发生变化；拒绝覆盖")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.onboard-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(desired_raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, mode)
        latest_raw = path.read_bytes() if path.exists() else None
        latest_sha = _hash(latest_raw) if latest_raw is not None else None
        if (latest_sha != expected or _target_identity(path) != target_identity
                or relative in _porcelain_paths(root)):
            raise HarnessError("应用前目标再次变化；临时文件已清理且未覆盖")
        os.replace(temp_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if path.read_bytes() != desired_raw:
            raise HarnessError("写入后读回与计划内容不一致")
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"status": "applied-and-read-back", "path": relative,
            "original_sha256": expected, "sha256": _hash(desired_raw),
            "writes_performed": True, "plan_fingerprint": plan["plan_fingerprint"]}


def _normalize_repository(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if "://" in text:
        from urllib.parse import urlsplit

        parsed = urlsplit(text)
        if parsed.hostname and parsed.hostname.lower() == "github.com":
            text = f"github.com/{parsed.path.lstrip('/')}"
    elif text.startswith("git@"):
        match = REMOTE_SSH.match(text)
        if match:
            text = f"{match.group(1)}/{match.group(2)}"
    text = text.removesuffix(".git").strip("/").lower()
    if text.startswith("github.com/"):
        text = text[len("github.com/"):]
    parts = text.split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    return "/".join(parts)


def validate_github_snapshot(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != REMOTE_CHECK_KEYS:
        raise HarnessError("GitHub配置快照字段无效")
    if value.get("schema_version") != 1 or isinstance(value.get("schema_version"), bool):
        raise HarnessError("GitHub配置快照版本无效")
    if value.get("provider") != "github":
        return {"supported": False, "complete": False, "reason": "unsupported_provider"}
    for field in ("head_sha", "base_sha"):
        if not isinstance(value.get(field), str) or not GIT_SHA.fullmatch(value[field]):
            raise HarnessError(f"GitHub配置快照 {field} 无效")
    repo = _normalize_repository(value.get("repository"))
    if repo is None:
        raise HarnessError("GitHub配置快照 repository 无效")
    base_ref = value.get("base_ref")
    if (not isinstance(base_ref, str) or not base_ref.strip() or base_ref.startswith("-")
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref)):
        raise HarnessError("GitHub配置快照 base_ref 无效")
    _validate_timestamp(value.get("captured_at"), "GitHub配置快照")
    source = value.get("source")
    if not isinstance(source, dict) or set(source) != {"kind", "identity"}:
        raise HarnessError("GitHub配置快照 source 无效")
    if not isinstance(source.get("kind"), str) or source["kind"] not in {"branch-protection", "repository-ruleset"}:
        raise HarnessError("GitHub配置快照 source.kind 不受支持")
    if (not isinstance(source.get("identity"), str) or not source["identity"].strip()
            or SUSPECT_SECRET.search(source["identity"])):
        raise HarnessError("GitHub配置快照缺少配置来源身份")
    if (not isinstance(value.get("rules_status"), str)
            or value["rules_status"] not in {"available", "not-configured", "permission-denied", "unknown"}):
        raise HarnessError("GitHub配置快照 rules_status 无效")
    strict = value.get("strict_required")
    if strict is not None and not isinstance(strict, bool):
        raise HarnessError("GitHub配置快照 strict_required 无效")
    if source["kind"] == "branch-protection" and strict is None:
        raise HarnessError("Branch protection 快照必须声明 strict_required")
    checks = value.get("required_checks")
    if not isinstance(checks, list):
        raise HarnessError("GitHub配置快照 required_checks 必须是数组")
    normalized_checks = []
    seen = set()
    for item in checks:
        if not isinstance(item, dict) or set(item) != {"context", "app_id"}:
            raise HarnessError("GitHub required check 条目无效")
        context = item.get("context")
        app_id = item.get("app_id")
        if (not isinstance(context, str) or not context.strip() or context in seen
                or SUSPECT_SECRET.search(context)):
            raise HarnessError("GitHub required check 名称为空或重复")
        if app_id is not None and (not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0):
            raise HarnessError("GitHub required check app_id 无效")
        seen.add(context)
        normalized_checks.append({"context": context, "app_id": app_id})
    jobs = value.get("observed_jobs")
    if not isinstance(jobs, list):
        raise HarnessError("GitHub observed_jobs 必须是数组")
    normalized_jobs = []
    for item in jobs:
        if not isinstance(item, dict) or set(item) != {"name", "conclusion", "source", "app_id", "head_sha"}:
            raise HarnessError("GitHub observed job 条目无效")
        if any(not isinstance(item.get(field), str) or not item[field].strip()
               for field in ("name", "conclusion", "source")):
            raise HarnessError("GitHub observed job 缺少名称、结论或来源")
        if any(SUSPECT_SECRET.search(item[field]) for field in ("name", "source")):
            raise HarnessError("GitHub observed job 名称 / 来源疑似含凭据")
        if item["conclusion"].lower() not in {
            "success", "failure", "cancelled", "skipped", "neutral", "action_required", "timed_out", "stale",
            "queued", "in_progress", "pending", "requested", "waiting", "completed",
        }:
            raise HarnessError("GitHub observed job conclusion 不受支持")
        if not isinstance(item.get("head_sha"), str) or not GIT_SHA.fullmatch(item["head_sha"]):
            raise HarnessError("GitHub observed job head_sha 无效")
        job_app_id = item.get("app_id")
        if job_app_id is not None and (not isinstance(job_app_id, int) or isinstance(job_app_id, bool) or job_app_id <= 0):
            raise HarnessError("GitHub observed job app_id 无效")
        normalized_jobs.append({field: item[field] for field in ("name", "conclusion", "source", "app_id", "head_sha")})
    verification = value.get("verification")
    if not isinstance(verification, str) or verification not in {"attested", "unverified"}:
        raise HarnessError("远端快照只能使用 attested 或 unverified；不能伪造 machine-verified")
    unverified = value.get("unverified_reasons")
    if (not isinstance(unverified, list)
            or any(not isinstance(item, str) or not item.strip() or SUSPECT_SECRET.search(item) for item in unverified)):
        raise HarnessError("GitHub配置快照 unverified_reasons 无效")
    return {
        "supported": True, "repository": repo, "head_sha": value["head_sha"],
        "base_ref": base_ref, "base_sha": value["base_sha"],
        "captured_at": value["captured_at"], "source": source,
        "rules_status": value["rules_status"], "strict_required": strict,
        "required_checks": normalized_checks, "observed_jobs": normalized_jobs,
        "verification": verification, "unverified_reasons": list(unverified),
    }


def check_github_snapshot(root_arg: Path, snapshot: object, *, expected_repository: str | None = None,
                          expected_base_ref: str | None = None, expected_base_sha: str | None = None) -> dict:
    root = _git_root(root_arg)
    value = validate_github_snapshot(snapshot)
    if not value.get("supported"):
        return value
    remote = _remote_target(root)
    local_repo = _normalize_repository(remote.get("repository"))
    asserted_repo = _normalize_repository(expected_repository) if expected_repository is not None else None
    repository_matches = (
        local_repo is not None and local_repo == value["repository"]
        and (asserted_repo is None or asserted_repo == value["repository"])
    )
    expected_ref = expected_base_ref
    if expected_ref is None:
        try:
            expected_ref = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
        except HarnessError:
            expected_ref = None
    ref_matches = expected_ref is not None and expected_ref == value["base_ref"]
    local_base_sha = None
    if expected_ref:
        candidate_refs = [expected_ref]
        if not expected_ref.startswith("refs/"):
            candidate_refs.insert(0, f"refs/remotes/origin/{expected_ref}")
        for candidate in candidate_refs:
            try:
                local_base_sha = _git(root, "rev-parse", "--verify", f"{candidate}^{{commit}}")
                break
            except HarnessError:
                continue
    if expected_base_sha is not None and (not isinstance(expected_base_sha, str) or not GIT_SHA.fullmatch(expected_base_sha)):
        raise HarnessError("expected_base_sha 必须是完整 Git SHA")
    sha_sources = []
    if local_base_sha is not None:
        sha_sources.append(local_base_sha == value["base_sha"])
    if expected_base_sha is not None:
        sha_sources.append(expected_base_sha == value["base_sha"])
    sha_matches = bool(sha_sources) and all(sha_sources)
    current_jobs = [item for item in value["observed_jobs"] if item["head_sha"] == value["head_sha"]]
    check_results = []
    for required in value["required_checks"]:
        matches = [job for job in current_jobs if job["name"] == required["context"]
                   and (required["app_id"] is None or job["app_id"] == required["app_id"])]
        check_results.append({
            "context": required["context"], "app_id": required["app_id"],
            "sources": sorted({job["source"] for job in matches}),
            "observed_success_on_snapshot_head": any(job["conclusion"].lower() == "success" for job in matches),
        })
    other_successes = [
        {"name": job["name"], "source": job["source"], "app_id": job["app_id"], "head_sha": job["head_sha"]}
        for job in current_jobs if job["conclusion"].lower() == "success"
        and not any(job["name"] == required["context"]
                    and (required["app_id"] is None or job["app_id"] == required["app_id"])
                    for required in value["required_checks"])
    ]
    unresolved = []
    if not repository_matches:
        unresolved.append("repository_identity_unverified_or_mismatched")
    if not ref_matches:
        unresolved.append("base_ref_unverified_or_mismatched")
    if not sha_sources:
        unresolved.append("base_sha_not_locally_verifiable")
    elif not sha_matches:
        unresolved.append("base_sha_stale_or_mismatched")
    if value["verification"] != "attested":
        unresolved.append("snapshot_source_not_attested")
    unresolved.extend(value["unverified_reasons"])
    if value["rules_status"] != "available":
        unresolved.append(f"rules_status_{value['rules_status']}")
    if not value["required_checks"]:
        unresolved.append("no_required_checks_observed")
    if value["strict_required"] is not True:
        unresolved.append("strict_required_not_enabled_or_unknown")
    if any(not item["observed_success_on_snapshot_head"] for item in check_results):
        unresolved.append("required_check_not_observed_success_for_snapshot_head")
    return {
        "supported": True, "repository": value["repository"], "source": value["source"],
        "rules_status": value["rules_status"], "base_ref": value["base_ref"],
        "base_sha": value["base_sha"], "head_sha": value["head_sha"],
        "captured_at": value["captured_at"], "verification": value["verification"],
        "repository_matches": repository_matches, "base_ref_matches": ref_matches,
        "base_sha_matches": sha_matches if sha_sources else None,
        "strict_required": value["strict_required"],
        "required_checks": value["required_checks"],
        "required_check_observations": check_results,
        "observed_jobs": value["observed_jobs"],
        "successful_jobs_not_required": other_successes,
        "snapshot_claim_consistent": not unresolved,
        "complete": False,
        "unresolved": sorted(set(unresolved + ["live_remote_read_not_performed"])),
        "live_remote_read_performed": False,
    }
