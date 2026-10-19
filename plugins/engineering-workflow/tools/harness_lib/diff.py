"""Read-only Git candidate snapshots and safe cumulative diff summaries."""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

from .state import HarnessError


DEFAULT_SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*secret*",
    "*credential*",
    "*token*",
)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True,
            capture_output=True,
            input=input_bytes,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HarnessError(f"Git 查询失败：{args[0] if args else 'unknown'}") from exc
    return result.stdout


def _text(root: Path, *args: str) -> str:
    return _git(root, *args).decode("utf-8", errors="replace").strip()


def _path(raw: bytes) -> str:
    return os.fsdecode(raw).replace(os.sep, "/")


def _names(raw: bytes) -> dict[str, str]:
    tokens = raw.split(b"\0")
    result: dict[str, str] = {}
    index = 0
    while index + 1 < len(tokens):
        status, name = tokens[index], tokens[index + 1]
        if not name:
            break
        result[_path(name)] = status.decode("ascii", errors="replace")
        index += 2
    return result


def _untracked(raw: bytes) -> list[str]:
    return [_path(item) for item in raw.split(b"\0") if item]


def _index_objects(root: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for record in _git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
        except (ValueError, UnicodeDecodeError) as exc:
            raise HarnessError("Git index 条目格式不可解析") from exc
        result.setdefault(_path(raw_path), []).append(f"{mode}:{object_id}:{stage}")
    return result


def _tree_objects(root: Path, revision: str) -> dict[str, str]:
    result: dict[str, str] = {}
    output = _git(root, "ls-tree", "-r", "-z", "--full-tree", revision)
    for record in output.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
        except (ValueError, UnicodeDecodeError) as exc:
            raise HarnessError("Git tree 条目格式不可解析") from exc
        if object_type == "blob":
            result[_path(raw_path)] = f"{mode}:{object_id}"
    return result


def _status_files(root: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    staged = _names(
        _git(root, "diff", "--cached", "--name-status", "-z", "--no-renames", "HEAD", "--")
    )
    unstaged = _names(
        _git(root, "diff", "--name-status", "-z", "--no-renames", "--")
    )
    untracked = _untracked(_git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    return staged, unstaged, untracked


def _is_sensitive(path: str, adapter: dict) -> bool:
    configured = adapter.get("sensitive_paths", [])
    patterns = (*DEFAULT_SENSITIVE_PATTERNS, *configured)
    name = PurePosixPath(path).name.lower()
    normalized = path.lower()
    if name in {".env.example", ".env.sample"}:
        return any(fnmatch.fnmatchcase(normalized, p.lower()) for p in configured)
    return any(
        fnmatch.fnmatchcase(normalized, pattern.lower())
        or fnmatch.fnmatchcase(name, pattern.lower())
        for pattern in patterns
    )


def _risk(path: str) -> list[str]:
    lower = path.lower()
    name = PurePosixPath(lower).name
    parts = set(PurePosixPath(lower).parts)
    risks: set[str] = set()
    if name in {"pyproject.toml", "uv.lock", "requirements.txt", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"} or name.startswith("requirements"):
        risks.add("dependency")
    if any(part in {"auth", "authorization", "permissions", "security"} for part in parts) or any(term in name for term in ("auth", "permission", "security")):
        risks.add("authorization")
    if any(part in {"migrations", "database", "schema"} for part in parts) or "migration" in name:
        risks.add("data")
    if ".github/workflows/" in lower or lower.startswith(".harness/"):
        risks.add("gate_or_adapter")
    if any(part in {"evaluation", "evals"} for part in parts) or "threshold" in name or "test" in name:
        risks.add("verification_or_threshold")
    if any(term in name for term in ("api", "openapi", "contract")) or "routes" in parts:
        risks.add("public_interface")
    if not risks:
        risks.add("requires_semantic_review")
    if "harness_lib" in parts and name in {"diff.py", "risk.py", "classification.py"}:
        risks.add("classification_rule")
    return sorted(risks)


def _classifiers_hash(adapter: dict) -> str:
    return _canonical_hash({
        "version": 1,
        "sensitive": list(DEFAULT_SENSITIVE_PATTERNS),
        "project_sensitive": adapter.get("sensitive_paths", []),
        "risk_rules": "harness-diff-v1",
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })


def _worktree_blob(root: Path, path: str) -> tuple[str | None, bool, bool, str | None]:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HarnessError("Git 返回了越界路径")
    full = root.joinpath(*relative.parts)
    try:
        resolved_parent = full.parent.resolve()
        if not resolved_parent.is_relative_to(root.resolve()):
            raise HarnessError("Git 工作树路径越界")
        if full.is_symlink():
            content = os.readlink(full).encode("utf-8", errors="surrogateescape")
            object_id = _git(root, "hash-object", "--no-filters", "--stdin", input_bytes=content).decode().strip()
            return object_id, True, True, "120000"
        if not full.exists():
            return None, False, False, None
        if not full.is_file():
            return None, True, False, None
        mode = "100755" if full.stat().st_mode & 0o111 else "100644"
        with full.open("rb") as stream:
            object_id = _git(root, "hash-object", "--no-filters", "--stdin", input_bytes=stream.read()).decode().strip()
        return object_id, True, True, mode
    except OSError as exc:
        return None, full.exists(), False, None


def _index_digest(root: Path) -> str:
    git_path = Path(_text(root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    try:
        raw = git_path.read_bytes()
    except OSError as exc:
        raise HarnessError("无法读取 Git index 身份") from exc
    return hashlib.sha256(raw).hexdigest()


def current_snapshot(root: Path, adapter: dict, work_item: str) -> dict:
    root = root.resolve()
    head = _text(root, "rev-parse", "HEAD")
    branch = _text(root, "branch", "--show-current") or "(detached)"
    base_ref = adapter.get("base_branch", "master")
    if not isinstance(base_ref, str) or not base_ref or base_ref.startswith("-"):
        raise HarnessError("项目 adapter 的 base_branch 无效")
    checked_ref = _text(root, "check-ref-format", "--branch", base_ref)
    if checked_ref != base_ref:
        raise HarnessError("项目 adapter 的 base_branch 不是有效分支")
    base_sha = _text(root, "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}")
    if len(head) < 40 or len(base_sha) < 40:
        raise HarnessError("Git HEAD / base 身份格式无效")
    staged, unstaged, untracked = _status_files(root)
    index = _index_objects(root)
    head_tree = _tree_objects(root, head)
    all_paths = sorted(set(staged) | set(unstaged) | set(untracked))
    files: dict[str, dict] = {}
    complete = True
    withheld = 0
    for path in all_paths:
        sensitive = _is_sensitive(path, adapter)
        if sensitive:
            complete = False
            withheld += 1
            worktree_object, present, read_ok, worktree_mode = None, True, False, None
        else:
            worktree_object, present, read_ok, worktree_mode = _worktree_blob(root, path)
            if not read_ok:
                complete = False
        files[path] = {
            "staged": staged.get(path),
            "unstaged": unstaged.get(path),
            "untracked": path in untracked,
            "index_objects": index.get(path, []),
            "head_object": head_tree.get(path),
            "worktree_object": worktree_object,
            "worktree_mode": worktree_mode,
            "present": present,
            "sensitive": sensitive,
            "readable": read_ok,
        }
    index_digest = _index_digest(root)
    worktree_digest = _canonical_hash(files)
    classifier_sha = _classifiers_hash(adapter)
    identity = {
        "schema_version": 1,
        "repository": adapter["repository"],
        "work_item_id": work_item,
        "branch": branch,
        "head_sha": head,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "index_sha256": index_digest,
        "worktree_sha256": worktree_digest,
        "classifier_sha256": classifier_sha,
        "complete": complete,
    }
    fingerprint = _canonical_hash(identity)
    return {
        **identity,
        "candidate_fingerprint": fingerprint,
        "files": files,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "complete": complete,
        "withheld_sensitive_count": withheld,
        "head_tree": head_tree,
    }


def _clean_state(path: str, tree: dict[str, str], adapter: dict) -> dict:
    if _is_sensitive(path, adapter):
        return {"index_objects": [], "head_object": tree.get(path), "worktree_object": None,
                "worktree_mode": None,
                "untracked": False, "present": path in tree, "sensitive": True, "readable": False}
    head = tree.get(path)
    mode, _, object_id = head.partition(":") if head else (None, None, None)
    return {"index_objects": [f"{head}:0"] if head else [], "head_object": head,
            "worktree_object": object_id if head else None,
            "worktree_mode": mode if head else None,
            "untracked": False, "present": bool(head),
            "sensitive": False, "readable": True}


def _state_for(path: str, snapshot: dict, tree: dict[str, str], adapter: dict) -> dict:
    return snapshot["files"].get(path) or _clean_state(path, tree, adapter)


def _state_key(state: dict) -> tuple:
    return (
        tuple(state.get("index_objects", [])),
        state.get("head_object"),
        state.get("worktree_object"),
        state.get("worktree_mode"),
        state.get("untracked", False),
        state.get("present", False),
    )


def _committed_paths(root: Path, base: str, head: str) -> dict[str, str]:
    if base == head:
        return {}
    return _names(_git(root, "diff", "--name-status", "-z", "--no-renames", base, head, "--"))


def _commit_ids(root: Path, base: str, head: str) -> list[str]:
    if base == head:
        return []
    output = _text(root, "log", "--format=%H", f"{base}..{head}")
    return [line for line in output.splitlines() if line]


def _path_change(path: str, current: dict, adapter: dict, scopes: list[str], committed: dict[str, dict[str, str]]) -> dict:
    sensitive = current.get("sensitive", False) or _is_sensitive(path, adapter)
    locations = []
    if current.get("staged"):
        locations.append("staged")
    if current.get("unstaged"):
        locations.append("worktree")
    if current.get("untracked"):
        locations.append("untracked")
    if "base_movement" in scopes:
        locations.append("base")
    if any(path in committed.get(scope, {}) for scope in scopes if scope != "base_movement"):
        locations.append("committed")
    change = current.get("staged") or current.get("unstaged")
    if change is None:
        change = next((committed[scope][path] for scope in scopes if path in committed.get(scope, {})), "?")
    return {
        "path": "[敏感路径已隐藏]" if sensitive else path,
        "change": change,
        "locations": locations,
        "scopes": scopes,
        "risk": ["sensitive_content_withheld"] if sensitive else _risk(path),
        "content_read": not sensitive and current.get("readable", True),
    }


def build_diff_report(root: Path, adapter: dict, work_item: str, extension: dict | None) -> dict:
    snapshot = current_snapshot(root, adapter, work_item)
    task = extension.get("task_baseline") if extension else None
    slice_start = extension.get("slice_baseline") if extension else None
    if task and not isinstance(task, dict):
        raise HarnessError("task baseline 格式无效")
    if slice_start and not isinstance(slice_start, dict):
        raise HarnessError("slice baseline 格式无效")
    current_tree = snapshot["head_tree"]
    changed: list[dict] = []
    stale_reasons: list[str] = []
    scope_paths: dict[str, set[str]] = {"cumulative": set(), "slice": set(), "base_movement": set()}
    committed_by_scope: dict[str, dict[str, str]] = {"cumulative": {}, "slice": {}, "base_movement": {}}
    sensitive_base_paths: set[str] = set()
    baselines = (("cumulative", task), ("slice", slice_start))
    for scope, baseline in baselines:
        if baseline is None:
            stale_reasons.append(f"{scope}_baseline_missing")
            continue
        expected = {
            "repository": adapter["repository"],
            "work_item_id": work_item,
            "classifier_sha256": snapshot["classifier_sha256"],
        }
        if any(baseline.get(key) != value for key, value in expected.items()):
            stale_reasons.append(f"{scope}_baseline_identity_mismatch")
            continue
        if baseline.get("base_ref") != snapshot["base_ref"]:
            stale_reasons.append(f"{scope}_base_ref_changed")
        if baseline.get("base_sha") != snapshot["base_sha"]:
            stale_reasons.append(f"{scope}_base_sha_changed")
            base_changes = _committed_paths(root, baseline["base_sha"], snapshot["base_sha"])
            committed_by_scope["base_movement"].update(base_changes)
            old_base_tree = _tree_objects(root, baseline["base_sha"])
            new_base_tree = _tree_objects(root, snapshot["base_sha"])
            for path in base_changes:
                old_state = _clean_state(path, old_base_tree, adapter)
                new_state = _clean_state(path, new_base_tree, adapter)
                if old_state.get("sensitive") or new_state.get("sensitive"):
                    sensitive_base_paths.add(path)
                    scope_paths["base_movement"].add(path)
                elif _state_key(old_state) != _state_key(new_state):
                    scope_paths["base_movement"].add(path)
        previous_head = baseline.get("head_sha")
        if not isinstance(previous_head, str):
            stale_reasons.append(f"{scope}_baseline_head_missing")
            continue
        committed = _committed_paths(root, previous_head, snapshot["head_sha"])
        committed_by_scope[scope] = committed
        paths = set(committed) | set(baseline.get("files", {})) | set(snapshot["files"])
        baseline_tree = _tree_objects(root, previous_head)
        for path in sorted(paths):
            old_state = _state_for(path, baseline, baseline_tree, adapter)
            new_state = _state_for(path, snapshot, current_tree, adapter)
            if old_state.get("sensitive") or new_state.get("sensitive"):
                if path not in scope_paths[scope]:
                    scope_paths[scope].add(path)
                continue
            if _state_key(old_state) != _state_key(new_state):
                scope_paths[scope].add(path)

    all_changed_paths = set().union(*scope_paths.values())
    for path in sorted(all_changed_paths):
        scopes = [name for name, paths in scope_paths.items() if path in paths]
        changed.append(
            _path_change(path, _state_for(path, snapshot, current_tree, adapter), adapter, scopes, committed_by_scope)
        )
    commits = {
        "cumulative": _commit_ids(root, task["head_sha"], snapshot["head_sha"]) if task and task.get("head_sha") else [],
        "slice": _commit_ids(root, slice_start["head_sha"], snapshot["head_sha"]) if slice_start and slice_start.get("head_sha") else [],
    }
    report = {
        "schema_version": 1,
        "connected": True,
        "repository": snapshot["repository"],
        "work_item_id": work_item,
        "candidate": {key: snapshot[key] for key in (
            "repository", "work_item_id", "branch", "head_sha", "base_ref", "base_sha", "index_sha256",
            "worktree_sha256", "classifier_sha256", "candidate_fingerprint", "complete",
        )},
        "baselines": {
            "cumulative": task.get("candidate_fingerprint") if task else None,
            "slice": slice_start.get("candidate_fingerprint") if slice_start else None,
        },
        "commits": commits,
        "files": changed,
        "counts": {
            "cumulative": sum("cumulative" in item["scopes"] for item in changed),
            "slice": sum("slice" in item["scopes"] for item in changed),
            "base_movement": sum("base_movement" in item["scopes"] for item in changed),
        },
        "completeness": {
            "complete": snapshot["complete"] and not sensitive_base_paths
            and not any(reason.endswith("_baseline_missing") for reason in stale_reasons)
            and not any("identity_mismatch" in reason or "baseline_head_missing" in reason for reason in stale_reasons)
            and not any(
                "sensitive_content_withheld" in item["risk"] for item in changed
            ),
            "sensitive_paths_withheld": snapshot["withheld_sensitive_count"] + len(sensitive_base_paths),
            "ignored_paths": "excluded by Git ignore rules and not inspected",
            "stale_reasons": sorted(set(stale_reasons)),
        },
    }
    report["report_sha256"] = _canonical_hash(report)
    return report


def capture_baseline(root: Path, adapter: dict, work_item: str, scope: str) -> dict:
    if scope not in {"task", "slice"}:
        raise HarnessError("baseline scope 必须是 task 或 slice")
    snapshot = current_snapshot(root, adapter, work_item)
    if scope == "task" and (snapshot["staged"] or snapshot["unstaged"] or snapshot["untracked"]):
        raise HarnessError("task baseline 要求工作树、index 和未跟踪文件均干净")
    if not snapshot["complete"]:
        raise HarnessError("候选含未读取的敏感 / 不可读文件；不能建立完整基线")
    return {
        key: snapshot[key]
        for key in (
            "schema_version", "repository", "work_item_id", "branch", "head_sha",
            "base_ref", "base_sha", "index_sha256", "worktree_sha256",
            "classifier_sha256", "candidate_fingerprint", "complete", "files",
        )
    } | {"captured_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
