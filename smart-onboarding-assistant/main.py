"""
Smart Developer Onboarding Assistant — FastAPI Application Entry Point
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routers.onboarding import router as onboarding_router

# Resolve frontend directory (sits next to main.py)
_FRONTEND_DIR = Path(__file__).parent / "frontend"


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[API] {settings.app_name} v{settings.app_version} starting up ...")
    yield
    print("[API] Shutting down ...")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "An AI-powered assistant that analyses code repositories and generates "
            "clear, actionable onboarding documentation for new developers."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(onboarding_router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health check",
    )
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=settings.app_version)

    # ── Serve the HTML frontend at root AND /ui ───────────────────────────────
    def _serve_index():
        index = _FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return JSONResponse(
            {"message": "Frontend not found. Visit /docs for the API reference."},
            status_code=404,
        )

    @app.get("/", include_in_schema=False)
    async def root():
        """Serve the enterprise frontend at the root URL."""
        return _serve_index()

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    async def serve_ui():
        """Alias — also serves the frontend at /ui for backwards compatibility."""
        return _serve_index()

    return app


# ---------------------------------------------------------------------------
# Application instance (used by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()


# ---------------------------------------------------------------------------
# Dev-mode runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
