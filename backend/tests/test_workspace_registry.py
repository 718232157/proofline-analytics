from pathlib import Path

import pytest

from app.workspaces.registry import (
    WorkspaceNotFoundError,
    WorkspaceRegistry,
    default_project_root,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_registry_loads_validated_moneki_manifest() -> None:
    manifest = WorkspaceRegistry(PROJECT_ROOT).load("moneki")

    assert manifest.workspace.name == "Moneki Operations"
    assert [source.name for source in manifest.sources] == ["sales", "stores", "products"]
    assert {metric.key for metric in manifest.metrics} == {
        "revenue",
        "order_count",
        "average_order_value",
    }
    assert WorkspaceRegistry(PROJECT_ROOT).list_slugs() == ("moneki",)
    assert default_project_root() == PROJECT_ROOT


def test_registry_rejects_unknown_workspace() -> None:
    with pytest.raises(WorkspaceNotFoundError, match="does not exist"):
        WorkspaceRegistry(PROJECT_ROOT).load("missing")


def test_source_path_cannot_escape_project_root() -> None:
    with pytest.raises(ValueError, match="escapes"):
        WorkspaceRegistry(PROJECT_ROOT).source_path("../outside.csv")
