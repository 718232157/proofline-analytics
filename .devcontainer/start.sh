#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="/tmp/proofline"
mkdir -p "$runtime_dir"

exec 9>"$runtime_dir/start.lock"
flock 9

# postCreateCommand 可能被浏览器关闭、网络波动或休眠中断。每次启动都先核验
# 完整环境标记；缺失或过期时由同一幂等脚本自动恢复，不能带病开放产品端口。
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
if ! curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null; then
  start_if_stopped api \
    "$repo_root/backend/.venv/bin/python" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000
fi
wait_for_http api http://127.0.0.1:8000/api/health

cd "$repo_root/frontend"
if ! curl --fail --silent http://127.0.0.1:5173/ >/dev/null; then
  start_if_stopped web pnpm exec vite --host 0.0.0.0
fi
wait_for_http web http://127.0.0.1:5173/

echo "Proofline 网页：http://localhost:5173"
echo "Proofline API：http://localhost:8000/api/health"
echo "运行日志：$runtime_dir/web.log 与 $runtime_dir/api.log"
