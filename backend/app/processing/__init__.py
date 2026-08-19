"""Workspace processing protocol and orchestration."""

from app.processing.models import ProcessingResult, WorkspaceProcessor
from app.processing.registry import ProcessorRegistry
from app.processing.service import ProcessingService

__all__ = ["ProcessingResult", "ProcessingService", "ProcessorRegistry", "WorkspaceProcessor"]
