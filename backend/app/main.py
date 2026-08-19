import json
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse
from starlette.staticfiles import StaticFiles

from app.analytics import AnalyticsQuery, AnalyticsService, MetricResult
from app.analytics.service import InvalidAnalyticsQuery
from app.assistant import AssistantService, ChatRequest, ChatResponse
from app.core.config import get_settings
from app.insights import InsightFeed, InsightService
from app.quality import QualityService, QualitySummary
from app.storage.database import get_session
from app.workspaces import WorkspaceRegistry
from app.workspaces.models import WorkspaceManifest

settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    assistant_mode: str
    llm_model: str | None
    numeric_source: str


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="以证据为先的可信分析与可溯源 AI 回答。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
            assistant_mode="hybrid_llm" if settings.llm_api_key else "deterministic",
            llm_model=settings.llm_model if settings.llm_api_key else None,
            numeric_source="governed_analytics_api",
        )

    @app.get(
        "/api/workspaces/{workspace_slug}",
        response_model=WorkspaceManifest,
        tags=["workspaces"],
    )
    async def workspace_manifest(workspace_slug: str) -> WorkspaceManifest:
        try:
            return WorkspaceRegistry().load(workspace_slug)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/workspaces/{workspace_slug}/analytics/query",
        response_model=MetricResult,
        tags=["analytics"],
    )
    async def analytics_query(
        workspace_slug: str,
        query: AnalyticsQuery,
        session: Annotated[Session, Depends(get_session)],
    ) -> MetricResult:
        try:
            return AnalyticsService(WorkspaceRegistry()).query(session, workspace_slug, query)
        except InvalidAnalyticsQuery as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get(
        "/api/workspaces/{workspace_slug}/quality/summary",
        response_model=QualitySummary,
        tags=["quality"],
    )
    async def quality_summary(
        workspace_slug: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> QualitySummary:
        try:
            return QualityService().summary(session, workspace_slug)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/workspaces/{workspace_slug}/assistant/chat",
        response_model=ChatResponse,
        tags=["assistant"],
    )
    async def assistant_chat(
        workspace_slug: str,
        request: ChatRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ChatResponse:
        try:
            return AssistantService(WorkspaceRegistry()).answer(session, workspace_slug, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/workspaces/{workspace_slug}/assistant/chat/stream",
        response_class=StreamingResponse,
        tags=["assistant"],
    )
    async def assistant_chat_stream(
        workspace_slug: str,
        request: ChatRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        def events() -> Iterator[str]:
            yield _sse("status", {"message": "正在识别问题与经营实体"})
            yield _sse("status", {"message": "正在查询治理后的真实指标"})
            try:
                response = AssistantService(WorkspaceRegistry()).answer(
                    session, workspace_slug, request
                )
            except LookupError as error:
                yield _sse("error", {"message": str(error)})
                return
            yield _sse("status", {"message": "数字核验完成"})
            yield _sse("result", response.model_dump(mode="json"))

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get(
        "/api/workspaces/{workspace_slug}/insights",
        response_model=InsightFeed,
        tags=["insights"],
    )
    async def proactive_insights(
        workspace_slug: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> InsightFeed:
        try:
            return InsightService(WorkspaceRegistry()).generate(session, workspace_slug)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    if settings.static_dir:
        static_path = Path(settings.static_dir).resolve()
        if not static_path.is_dir():
            raise RuntimeError(f"STATIC_DIR does not exist: {static_path}")
        app.mount("/", StaticFiles(directory=static_path, html=True), name="frontend")

    return app


app = create_app()


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
