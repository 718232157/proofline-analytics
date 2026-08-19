from pathlib import Path
from tomllib import load

from app.workspaces.models import WorkspaceManifest


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class WorkspaceNotFoundError(LookupError):
    """Raised when a requested workspace manifest does not exist."""


class WorkspaceRegistry:
    """Loads and validates workspace manifests from the project tree."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or default_project_root()).resolve()
        self.workspace_root = self.project_root / "workspaces"

    def load(self, slug: str) -> WorkspaceManifest:
        manifest_path = self.workspace_root / slug / "workspace.toml"
        if not manifest_path.is_file():
            raise WorkspaceNotFoundError(f"workspace '{slug}' does not exist")
        with manifest_path.open("rb") as manifest_file:
            return WorkspaceManifest.model_validate(load(manifest_file))

    def source_path(self, source_path: str) -> Path:
        resolved = (self.project_root / source_path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("workspace source path escapes the project root") from exc
        return resolved

    def list_slugs(self) -> tuple[str, ...]:
        if not self.workspace_root.is_dir():
            return ()
        return tuple(
            sorted(
                path.parent.name
                for path in self.workspace_root.glob("*/workspace.toml")
                if path.is_file()
            )
        )
