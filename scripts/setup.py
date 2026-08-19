"""Create local runtimes, install locked dependencies, and prepare canonical data."""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
FRONTEND = PROJECT_ROOT / "frontend"
VENV = BACKEND / ".venv"


def run(command: list[str], cwd: Path) -> None:
    print(f"\n→ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def venv_python() -> Path:
    executable = "python.exe" if sys.platform == "win32" else "python"
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return VENV / directory / executable


def main() -> None:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm 11+ is required. Install it with: corepack enable pnpm")

    if not VENV.exists():
        print("→ creating backend virtual environment")
        venv.EnvBuilder(with_pip=True).create(VENV)

    python = str(venv_python())
    run([python, "-m", "pip", "install", "-e", ".[dev]"], BACKEND)
    run([pnpm, "install", "--frozen-lockfile"], FRONTEND)
    run([python, "-m", "app.cli", "ingest", "--workspace", "moneki"], BACKEND)
    run([python, "-m", "app.cli", "process", "--workspace", "moneki"], BACKEND)
    print("\n✓ setup complete — run: python scripts/dev.py")


if __name__ == "__main__":
    main()
