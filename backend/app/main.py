from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

    return app


app = create_app()
