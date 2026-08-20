#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="/tmp/proofline"
ready_file="$repo_root/backend/var/.codespaces-ready"
mkdir -p "$runtime_dir" "$(dirname "$ready_file")"

fingerprint="$({
  cd "$repo_root"
  sha256sum \
    scripts/setup.py \
    backend/pyproject.toml \
    frontend/pnpm-lock.yaml \
    workspaces/moneki/workspace.toml \
    data/*.csv
} | sha256sum | cut -d ' ' -f 1)"

is_ready() {
  [[ -x "$repo_root/backend/.venv/bin/python" ]] &&
    [[ -x "$repo_root/frontend/node_modules/.bin/vite" ]] &&
    [[ -s "$repo_root/backend/var/proofline.db" ]] &&
    [[ -f "$ready_file" ]] &&
    [[ "$(<"$ready_file")" == "$fingerprint" ]]
}

if is_ready; then
  echo "✓ Codespaces 运行环境已就绪"
  exit 0
fi

echo "→ 首次启动：正在安装锁定依赖并构建可信数据层"
if ! command -v pnpm >/dev/null 2>&1; then
  sudo corepack enable
  corepack prepare pnpm@11.19.0 --activate
fi

rm -f "$ready_file"
(
  cd "$repo_root"
  python scripts/setup.py
) 2>&1 | tee "$runtime_dir/setup.log"
printf '%s\n' "$fingerprint" >"$ready_file"
echo "✓ Codespaces 初始化完成"
