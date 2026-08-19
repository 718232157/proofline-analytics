import pytest

from app.cli import build_parser


def test_ingest_command_defaults_to_replacement_mode() -> None:
    args = build_parser().parse_args(["ingest", "--workspace", "moneki"])

    assert args.command == "ingest"
    assert args.workspace == "moneki"
    assert args.append is False


def test_cli_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_process_command_selects_workspace() -> None:
    args = build_parser().parse_args(["process", "--workspace", "moneki"])

    assert args.command == "process"
    assert args.workspace == "moneki"
