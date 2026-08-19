"""同时启动 API 与 Web 应用，并在退出时安全关闭。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
FRONTEND = PROJECT_ROOT / "frontend"


def venv_python() -> Path:
    executable = "python.exe" if sys.platform == "win32" else "python"
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return BACKEND / ".venv" / directory / executable


def main() -> None:
    python = venv_python()
    if not python.is_file():
        raise SystemExit("未找到本地运行环境。请先执行：python scripts/setup.py")
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("需要 pnpm 11+。请执行：corepack enable pnpm")

    processes = [
        subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--port",
                "8000",
            ],
            cwd=BACKEND,
        ),
        subprocess.Popen([pnpm, "dev"], cwd=FRONTEND),
    ]
    print("\n✓ Proofline API：http://localhost:8000")
    print("✓ Proofline 网页：http://localhost:5173")
    print("按 Ctrl+C 停止两个服务。\n")
    try:
        exit_code = processes[0].wait()
        if exit_code:
            raise SystemExit(exit_code)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
