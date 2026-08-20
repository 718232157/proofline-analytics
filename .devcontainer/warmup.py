"""Serve a useful first-load page while a Codespace prepares Proofline."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PORT = int(os.environ.get("PROOFLINE_WARMUP_PORT", "5173"))
STATUS_FILE = Path(
    os.environ.get("PROOFLINE_STATUS_FILE", "/tmp/proofline/status.json")
)

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Proofline 正在准备</title>
  <style>
    :root { color-scheme: light; font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; color: #102018;
      background: radial-gradient(circle at 50% 20%, #f8ffe8 0, #f3f7f2 45%, #edf2ed 100%); }
    main { width: min(560px, calc(100% - 40px)); padding: 42px; border: 1px solid #dce5dc;
      border-radius: 28px; background: rgba(255,255,255,.92); box-shadow: 0 24px 80px rgba(16,32,24,.08); }
    .brand { display: flex; align-items: center; gap: 14px; font-size: 18px; font-weight: 750; }
    .mark { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 14px;
      color: #baff3f; background: #102018; font-size: 22px; }
    h1 { margin: 34px 0 12px; font-size: clamp(30px, 6vw, 44px); line-height: 1.12; letter-spacing: -.04em; }
    p { margin: 0; color: #617067; font-size: 16px; line-height: 1.75; }
    .progress { height: 8px; margin: 30px 0 18px; overflow: hidden; border-radius: 99px; background: #e9eee9; }
    .progress::after { content: ""; display: block; width: 42%; height: 100%; border-radius: inherit;
      background: #93ca20; animation: move 1.5s ease-in-out infinite; }
    #message { color: #314139; font-weight: 650; }
    #detail { margin-top: 8px; font-size: 14px; }
    .error .progress::after { width: 100%; background: #d45a45; animation: none; }
    .error #message { color: #a33b2c; }
    @keyframes move { 0% { transform: translateX(-110%); } 100% { transform: translateX(260%); } }
  </style>
</head>
<body>
  <main id="card">
    <div class="brand"><span class="mark">P</span>Proofline 可信分析</div>
    <h1>正在准备经营工作台</h1>
    <p>首次启动会自动安装锁定依赖、清洗原始数据并构建可审计指标。完成后将自动进入看板，无需手动操作。</p>
    <div class="progress"></div>
    <p id="message">正在连接运行环境…</p>
    <p id="detail">通常需要数分钟，请保留此页面。</p>
  </main>
  <script>
    const card = document.querySelector('#card');
    const message = document.querySelector('#message');
    const detail = document.querySelector('#detail');
    async function check() {
      try {
        const health = await fetch('/api/health', { cache: 'no-store' });
        if (health.ok) { location.reload(); return; }
      } catch (_) {}
      try {
        const response = await fetch('/status', { cache: 'no-store' });
        const status = await response.json();
        message.textContent = status.message;
        detail.textContent = status.detail || '通常需要数分钟，请保留此页面。';
        card.classList.toggle('error', status.state === 'error');
      } catch (_) {}
      setTimeout(check, 1500);
    }
    check();
  </script>
</body>
</html>
"""


def read_status() -> dict[str, Any]:
    try:
        value = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
    except (OSError, json.JSONDecodeError):
        pass
    return {"state": "starting", "message": "正在启动初始化流程…"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        status_code = 200
        if path == "/status":
            body = json.dumps(read_status(), ensure_ascii=False).encode()
            content_type = "application/json; charset=utf-8"
        elif path.startswith("/api/"):
            status_code = 503
            body = json.dumps(
                {"status": "starting", "detail": "Proofline API is not ready"}
            ).encode()
            content_type = "application/json; charset=utf-8"
        else:
            body = PAGE.encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
