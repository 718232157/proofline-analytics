import argparse

from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.database import SessionLocal, engine
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="ingest workspace sources")
    ingest_parser.add_argument("--workspace", required=True)
    ingest_parser.add_argument(
        "--append",
        action="store_true",
        help="retain previous raw ingestion runs instead of replacing them",
    )
    process_parser = subparsers.add_parser(
        "process", help="clean, validate, and canonicalize the latest raw ingestion"
    )
    process_parser.add_argument("--workspace", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    workspace_registry = WorkspaceRegistry()
    if args.command == "ingest":
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            ingestion_result = RawIngestionService(workspace_registry).ingest(
                session,
                args.workspace,
                replace=not args.append,
            )
        print(
            f"ingested {ingestion_result.total_records} raw records "
            f"for workspace '{ingestion_result.workspace_slug}' "
            f"in run {ingestion_result.run_id}"
        )
    elif args.command == "process":
        # Loading the adapter registers its canonical SQLAlchemy models before
        # create_all. Core remains unaware of workspace-specific tables.
        ProcessorRegistry(workspace_registry).create(args.workspace)
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            processing_result = ProcessingService(workspace_registry).process(
                session, args.workspace
            )
        print(
            f"processed raw run {processing_result.raw_run_id} for workspace "
            f"'{processing_result.workspace_slug}' in run "
            f"{processing_result.processing_run_id}: {processing_result.summary}"
        )


if __name__ == "__main__":
    main()
