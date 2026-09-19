#!/usr/bin/env bash
# 人工参与的复现循环模板。
# 复制本文件后，只编辑下方的复现步骤；不要把凭证或真实敏感数据写入脚本。
#
# Usage:
#   bash hitl-loop.template.sh
#
# 两个辅助函数：
#   step "<instruction>"          → 显示步骤并等待 Enter
#   capture VAR "<question>"      → 显示问题并把回答保存到 VAR
#
# 结束时会打印 KEY=VALUE，供诊断过程读取。

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [完成后按 Enter] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

# --- 在下方编辑复现步骤 -----------------------------------------------

step "打开隔离的开发环境，并执行最小复现步骤。"

capture REPRODUCED "是否复现了用户描述的准确症状？(y/n)"

capture SYMPTOM "记录脱敏后的错误或异常现象（没有则填写 none）："

# --- 编辑到此为止 ------------------------------------------------------

printf '\n--- Captured ---\n'
printf 'REPRODUCED=%s\n' "$REPRODUCED"
printf 'SYMPTOM=%s\n' "$SYMPTOM"
