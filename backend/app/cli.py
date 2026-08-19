import argparse

from app.ingestion import RawIngestionService
from app.processing import ProcessingService
from app.processing.registry import ProcessorRegistry
from app.storage.database import SessionLocal, engine
from app.storage.models import Base
from app.workspaces import WorkspaceRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofline", description="Proofline 数据管道命令行工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="摄取工作空间原始数据")
    ingest_parser.add_argument("--workspace", required=True, help="工作空间标识")
    ingest_parser.add_argument(
        "--append",
        action="store_true",
        help="保留以往原始摄取批次，而不是替换它们",
    )
    process_parser = subparsers.add_parser("process", help="清洗、校验并规范化最新原始摄取批次")
    process_parser.add_argument("--workspace", required=True, help="工作空间标识")
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
            f"已为工作空间 '{ingestion_result.workspace_slug}' 摄取 "
            f"{ingestion_result.total_records} 条原始记录，"
            f"批次 {ingestion_result.run_id}"
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
            f"已处理工作空间 '{processing_result.workspace_slug}' 的原始批次 "
            f"{processing_result.raw_run_id}，生成处理批次 "
            f"{processing_result.processing_run_id}：{processing_result.summary}"
        )


if __name__ == "__main__":
    main()
