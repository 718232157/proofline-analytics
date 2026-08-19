import argparse

from app.ingestion import RawIngestionService
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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "ingest":
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            result = RawIngestionService(WorkspaceRegistry()).ingest(
                session,
                args.workspace,
                replace=not args.append,
            )
        print(
            f"ingested {result.total_records} raw records "
            f"for workspace '{result.workspace_slug}' in run {result.run_id}"
        )


if __name__ == "__main__":
    main()
