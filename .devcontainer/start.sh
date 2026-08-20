#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="/tmp/proofline"
mkdir -p "$runtime_dir"

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

cd "$repo_root/backend"
start_if_stopped api \
  "$repo_root/backend/.venv/bin/python" -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000

cd "$repo_root/frontend"
start_if_stopped web pnpm exec vite --host 0.0.0.0

echo "Proofline 网页：http://localhost:5173"
echo "Proofline API：http://localhost:8000/api/health"
echo "运行日志：$runtime_dir/web.log 与 $runtime_dir/api.log"
