from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import pytest


def load_warmup_module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / ".devcontainer" / "warmup.py"
    spec = importlib.util.spec_from_file_location("proofline_codespaces_warmup", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载启动页模块：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def running_server(module: ModuleType) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_warmup_page_exposes_progress_without_faking_api_health(tmp_path: Path) -> None:
    module = load_warmup_module()
    module.STATUS_FILE = tmp_path / "status.json"
    expected = {
        "state": "starting",
        "message": "正在清洗并校验经营数据…",
        "detail": "测试详情",
    }
    module.STATUS_FILE.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")

    with running_server(module) as base_url:
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            assert response.status == 200
            assert "Proofline 可信分析" in response.read().decode()

        with urllib.request.urlopen(f"{base_url}/status", timeout=2) as response:
            assert json.loads(response.read()) == expected

        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"{base_url}/api/health", timeout=2)
        assert error.value.code == 503
