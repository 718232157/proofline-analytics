"""Workspace manifests and registry."""

from app.workspaces.models import WorkspaceManifest
from app.workspaces.registry import WorkspaceRegistry

__all__ = ["WorkspaceManifest", "WorkspaceRegistry"]
