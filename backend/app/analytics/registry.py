from importlib import import_module
from typing import cast

from app.analytics.models import SemanticProvider
from app.workspaces.registry import WorkspaceRegistry


class SemanticProviderRegistry:
    def __init__(self, workspace_registry: WorkspaceRegistry) -> None:
        self.workspace_registry = workspace_registry

    def create(self, workspace_slug: str) -> SemanticProvider:
        manifest = self.workspace_registry.load(workspace_slug)
        provider_path = manifest.workspace.semantic_provider
        module_name, class_name = provider_path.split(":", maxsplit=1)
        module = import_module(module_name)
        provider_class = getattr(module, class_name, None)
        if provider_class is None:
            raise LookupError(f"semantic provider '{provider_path}' does not exist")
        return cast(SemanticProvider, provider_class())
