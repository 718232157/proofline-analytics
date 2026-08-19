from importlib import import_module
from typing import cast

from app.processing.models import WorkspaceProcessor
from app.workspaces.registry import WorkspaceRegistry


class ProcessorRegistry:
    """Creates the first-party processor declared by a validated workspace."""

    def __init__(self, workspace_registry: WorkspaceRegistry) -> None:
        self.workspace_registry = workspace_registry

    def create(self, workspace_slug: str) -> WorkspaceProcessor:
        manifest = self.workspace_registry.load(workspace_slug)
        module_name, class_name = manifest.workspace.processor.split(":", maxsplit=1)
        module = import_module(module_name)
        processor_class = getattr(module, class_name, None)
        if processor_class is None:
            raise LookupError(
                f"workspace processor '{manifest.workspace.processor}' does not exist"
            )
        return cast(WorkspaceProcessor, processor_class())
