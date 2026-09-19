#!/usr/bin/env bash
#
# Wizard（交互式向导）逐步引导用户完成人工操作。
# 由 /wizard Skill 生成。
#
# “STAGES”标记之前是通用向导库，不要手动修改。
# 只在标记之后编写每个 Stage。

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# 通用向导库：所有本地向导保持一致的交互体验。
# ──────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

# 在 STAGES 区域设置为实际 Stage 数量。
TOTAL_STAGES=0

_STAGE_INDEX=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()  # 本次写入 ENV_FILE 的变量名
SKIPPED=()      # 无法由向导完成、需要用户手动处理的事项

# _clear 清理终端，只保留当前 Stage。输出被管道接收时不清理。
_clear() {
  [[ -t 1 ]] || return 0
  if command -v tput >/dev/null 2>&1; then tput clear; else printf '\033[2J\033[3J\033[H'; fi
}

# banner "标题" 显示向导开场。
banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s  共 %s 个 Stage%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"
  printf '%s  你负责完成浏览器或后台中的人工操作，向导会说明步骤并接收你复制的值。\n' "$DIM"
  printf '  可以随时使用 Ctrl-C 停止，稍后重新运行；已写入的本地值会被复用。%s\n' "$RESET"
  pause "准备开始？"
}

# stage "名称" 清理终端并显示当前进度。
stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  printf '\n%s%s▸ Stage %s/%s · %s%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"
}

say()  { printf '  %s\n' "$1"; }
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }

# open_url URL 尝试用用户的浏览器打开 URL。
open_url() {
  local url="$1"
  printf '  %s↗ 正在打开%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview      >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open     >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open         >/dev/null 2>&1; then open "$url"
    else warn "无法自动打开浏览器，请手动访问：$url"; fi
  } >/dev/null 2>&1 || warn "无法自动打开浏览器，请手动访问：$url"
}

# pause "提示" 等待用户完成人工步骤。
pause() {
  printf '  %s%s%s ' "$DIM" "${1:-完成后按 Enter 继续}" "$RESET"
  read -r _ || true
}

# confirm "问题" 是一个 y/N 确认门。
confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

# _validate_key KEY 确认 KEY 是合法的环境变量名。
_validate_key() {
  local key="$1"
  if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    printf '  %s✗ 非法环境变量名：%s%s\n' "$RED" "$key" "$RESET" >&2
    return 1
  fi
}

# _validate_env_file 确认 ENV_FILE 位于当前工作目录内，且不是符号链接。
_validate_env_file() {
  local root dir resolved_dir filename resolved_file
  if [[ "$ENV_FILE" == *$'\n'* || "$ENV_FILE" == *$'\r'* ]]; then
    printf '  %s✗ ENV_FILE 不能包含换行。%s\n' "$RED" "$RESET" >&2
    return 1
  fi

  root=$(pwd -P) || return 1
  dir=$(dirname -- "$ENV_FILE") || return 1
  if [[ ! -d "$dir" ]]; then
    printf '  %s✗ ENV_FILE 的父目录不存在：%s%s\n' "$RED" "$dir" "$RESET" >&2
    return 1
  fi
  resolved_dir=$(cd -- "$dir" && pwd -P) || return 1
  case "$resolved_dir" in
    "$root"|"$root"/*) ;;
    *)
      printf '  %s✗ ENV_FILE 必须位于当前工作目录内：%s%s\n' "$RED" "$ENV_FILE" "$RESET" >&2
      return 1
      ;;
  esac

  filename=$(basename -- "$ENV_FILE") || return 1
  resolved_file="$resolved_dir/$filename"
  if [[ -L "$ENV_FILE" || -L "$resolved_file" ]]; then
    printf '  %s✗ ENV_FILE 不能是符号链接：%s%s\n' "$RED" "$ENV_FILE" "$RESET" >&2
    return 1
  fi
  ENV_FILE="$resolved_file"
}

# _dotenv_quote VALUE 生成单行、可被常见 dotenv parser 读取的双引号值。
_dotenv_quote() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '"%s"' "$value"
}

# _existing KEY 读取 ENV_FILE 中 KEY 的现有值，仅供重复运行复用。
_existing() {
  _validate_key "$1" || return 1
  _validate_env_file || return 1
  [[ -f "$ENV_FILE" ]] || return 1
  local line
  line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

# ask KEY "提示" 读取公开值。直接按 Enter 会复用已有值。
ask() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter 保留当前值]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -r input || true
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# ask_secret KEY "提示" 隐藏读取敏感值。直接按 Enter 会复用已有值。
ask_secret() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter 保留当前值]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -rs input || true
  printf '\n'
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# write_env KEY VALUE 在 ENV_FILE 中幂等写入或替换一行 KEY=quoted-value。
write_env() {
  local key="$1" value="$2" encoded tmp
  _validate_key "$key" || return 1
  _validate_env_file || return 1
  if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    printf '  %s✗ 配置值不能包含换行：%s%s\n' "$RED" "$key" "$RESET" >&2
    return 1
  fi
  if [[ -e "$ENV_FILE" && ! -f "$ENV_FILE" ]]; then
    printf '  %s✗ ENV_FILE 不是普通文件：%s%s\n' "$RED" "$ENV_FILE" "$RESET" >&2
    return 1
  fi
  [[ -f "$ENV_FILE" ]] || : > "$ENV_FILE" || return 1
  encoded=$(_dotenv_quote "$value")
  # 临时文件与 ENV_FILE 放在同一目录，避免跨文件系统移动导致替换失败。
  tmp=$(mktemp "${ENV_FILE}.tmp.XXXXXX") || return 1
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$encoded" >> "$tmp"
  if ! mv -- "$tmp" "$ENV_FILE"; then
    rm -f -- "$tmp"
    return 1
  fi
  WRITTEN_ENV+=("$key")
  printf '  %s✓ 已写入%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"
}

# finish 清理终端并显示不包含敏感值的本地配置汇总。
finish() {
  _clear
  printf '\n%s%s  ✓ 向导完成%s\n' "$BOLD" "$GREEN" "$RESET"
  (( ${#WRITTEN_ENV[@]} )) && note "本次写入 ${#WRITTEN_ENV[@]} 个变量：${WRITTEN_ENV[*]} → $ENV_FILE"
  if (( ${#SKIPPED[@]} )); then
    printf '\n'; warn "仍需手动完成："
    for item in "${SKIPPED[@]}"; do note "  - $item"; done
  fi
  printf '\n'
}

# ──────────────────────────────────────────────────────────────────────────
# STAGES：只编辑以下区域。每个 Stage 对应一个人工步骤。
# 替换示例并同步设置 TOTAL_STAGES。
# ──────────────────────────────────────────────────────────────────────────

TOTAL_STAGES=1

banner "本地配置向导"

# ── 示例 Stage：运行前请替换为真实人工步骤 ──────────────────────────────
stage "示例：替换此 Stage"
say "请在运行前将本示例替换为实际的人工步骤。"
say "本模板不会自动写入任何配置，也不会连接外部系统。"
pause "已完成脚本编辑？"
# ──────────────────────────────────────────────────────────────────────────

finish
