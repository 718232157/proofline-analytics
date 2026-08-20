#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="/tmp/proofline"
mkdir -p "$runtime_dir"
status_file="$runtime_dir/status.json"

write_status() {
  local state="$1"
  local message="$2"
  local detail="${3:-}"
  STATUS_FILE="$status_file" STATE="$state" MESSAGE="$message" DETAIL="$detail" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["STATUS_FILE"])
path.write_text(
    json.dumps(
        {
            "state": os.environ["STATE"],
            "message": os.environ["MESSAGE"],
            "detail": os.environ["DETAIL"],
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
PY
}

on_error() {
  local line="$1"
  write_status \
    "error" \
    "运行环境初始化失败" \
    "启动脚本在第 ${line} 行停止。请在 Codespace 中执行 bash .devcontainer/start.sh 重试。"
}
trap 'on_error "$LINENO"' ERR

exec 9>"$runtime_dir/start.lock"
flock 9

# 依赖安装和数据构建前先占住产品端口。首次访问看到可解释、可自动恢复的
# 启动页，服务就绪后该页面会自行切换到真实看板，而不是暴露平台 502。
if ! curl --fail --silent http://127.0.0.1:5173/ >/dev/null 2>&1; then
  write_status "starting" "正在准备可信数据层…" "正在校验依赖、原始数据与本地数据库。"
  nohup python3 "$repo_root/.devcontainer/warmup.py" \
    >"$runtime_dir/warmup.log" 2>&1 &
  echo "$!" >"$runtime_dir/warmup.pid"
fi

# postCreateCommand 可能被浏览器关闭、网络波动或休眠中断。每次启动都先核验
# 完整环境标记；缺失或过期时由同一幂等脚本自动恢复，不能带病开放产品端口。
write_status "starting" "正在清洗并校验经营数据…" "所有指标会从规范化数据库重新计算。"
bash "$repo_root/.devcontainer/bootstrap.sh"

start_if_stopped() {
  local name="$1"
  local pid_file="$runtime_dir/$name.pid"
  local log_file="$runtime_dir/$name.log"
  shift

  if [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null; then
    return
  fi

  nohup "$@" >"$log_file" 2>&1 &
  echo "$!" >"$pid_file"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local pid_file="$runtime_dir/$name.pid"
  local log_file="$runtime_dir/$name.log"

  for _ in {1..60}; do
    if curl --fail --silent --show-error "$url" >/dev/null; then
      return
    fi
    if [[ -f "$pid_file" ]] && ! kill -0 "$(<"$pid_file")" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  echo "✗ $name 未能通过就绪检查：$url" >&2
  tail -n 80 "$log_file" >&2 || true
  exit 1
}

cd "$repo_root/backend"
write_status "starting" "正在启动可信查询 API…" "数据层已经就绪，正在开放查询服务。"
if ! curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null; then
  start_if_stopped api \
    "$repo_root/backend/.venv/bin/python" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000
fi
wait_for_http api http://127.0.0.1:8000/api/health

cd "$repo_root/frontend"
write_status "starting" "正在启动经营工作台…" "即将自动进入产品。"
if [[ -f "$runtime_dir/warmup.pid" ]] && kill -0 "$(<"$runtime_dir/warmup.pid")" 2>/dev/null; then
  kill "$(<"$runtime_dir/warmup.pid")"
  wait "$(<"$runtime_dir/warmup.pid")" 2>/dev/null || true
  rm -f "$runtime_dir/warmup.pid"
fi
if ! curl --fail --silent http://127.0.0.1:5173/ >/dev/null; then
  start_if_stopped web pnpm exec vite --host 0.0.0.0
fi
wait_for_http web http://127.0.0.1:5173/
write_status "ready" "经营工作台已就绪" "正在进入产品。"
trap - ERR

echo "Proofline 网页：http://localhost:5173"
echo "Proofline API：http://localhost:8000/api/health"
echo "运行日志：$runtime_dir/web.log 与 $runtime_dir/api.log"
