"""
Onboarding Router
=================
Provides the following endpoints:

  POST /api/v1/onboarding/analyze             — analyse a local or remote repository
  POST /api/v1/onboarding/generate-docs       — generate setup documentation
  POST /api/v1/onboarding/architecture-diagram — generate a Mermaid.js diagram
  POST /api/v1/onboarding/good-first-issues   — generate tailored starter tasks
  POST /api/v1/onboarding/full-pipeline       — analyse + generate docs in one call
  POST /api/v1/onboarding/chat                — Q&A over generated documentation context
"""

from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException, status

from app.models.schemas import (
    ArchitectureDiagramResponse,
    ChatRequest,
    ChatResponse,
    GoodFirstIssuesRequest,
    GoodFirstIssuesResponse,
    RepoAnalysisRequest,
    RepoAnalysisResult,
    RepoSource,
    SetupDocRequest,
    SetupDocResponse,
)
from app.services.chat_service import answer_codebase_question
from app.services.diagram_service import build_architecture_diagram
from app.services.doc_generator import generate_setup_docs
from app.services.good_first_issues_service import generate_good_first_issues
from app.services.repo_analyzer import RepoAnalyzer, clone_and_analyze

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AUTH_ERROR_PHRASES = ("invalid or missing groq api key", "invalid api key", "authentication")


def _is_auth_error_message(msg: str) -> bool:
    """Return True when the error message signals an API key problem."""
    lower = msg.lower()
    return any(phrase in lower for phrase in _AUTH_ERROR_PHRASES)


def _maybe_raise_auth_http(exc: Exception) -> None:
    """If *exc* is an openai.AuthenticationError, raise an HTTPException(401)."""
    try:
        from openai import AuthenticationError
    except ImportError:
        return
    if isinstance(exc, AuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid or missing Groq API Key. "
                "Please check your key and try again."
            ),
        ) from exc


def _cleanup_dir(path: str) -> None:
    """Background task: remove a temporary cloned repository directory."""
    shutil.rmtree(path, ignore_errors=True)


async def _run_analysis(req: RepoAnalysisRequest) -> tuple[RepoAnalysisResult, str | None]:
    """
    Dispatch analysis to the correct backend.
    Returns (result, tmp_clone_path_or_None).
    """
    if req.source == RepoSource.LOCAL:
        if not req.path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="'path' is required when source is 'local'.",
            )
        try:
            analyzer = RepoAnalyzer(max_file_size_bytes=req.max_file_size_kb * 1024)
            result = analyzer.analyze(req.path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {exc}",
            ) from exc
        return result, None

    # Remote GitHub source
    if not req.github_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'github_url' is required when source is 'github'.",
        )
    try:
        from app.config import get_settings
        settings = get_settings()
        result, clone_path = await clone_and_analyze(
            github_url=req.github_url,
            branch=req.branch,
            clone_base=settings.clone_base_dir,
            max_file_size_kb=req.max_file_size_kb,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Remote analysis failed: {exc}",
        ) from exc
    return result, clone_path


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=RepoAnalysisResult,
    summary="Analyse a code repository",
    description=(
        "Performs static analysis on a local filesystem path or a remote GitHub "
        "repository. Returns structured metadata including languages, dependencies, "
        "frameworks, entry points, and environment variables."
    ),
)
async def analyze_repository(
    background_tasks: BackgroundTasks,
    req: Annotated[RepoAnalysisRequest, Body()],
) -> RepoAnalysisResult:
    result, clone_path = await _run_analysis(req)
    if clone_path:
        background_tasks.add_task(_cleanup_dir, clone_path)
    return result


@router.post(
    "/generate-docs",
    response_model=SetupDocResponse,
    summary="Generate setup documentation",
    description=(
        "Accepts a pre-computed RepoAnalysisResult and produces onboarding "
        "documentation in Markdown, HTML, or plain text. Supports Groq, OpenAI, "
        "or a deterministic mock template. Pass X-Groq-Api-Key to supply a Groq "
        "key at request time — no .env required."
    ),
)
async def generate_documentation(
    req: Annotated[SetupDocRequest, Body()],
    x_groq_api_key: Annotated[str | None, Header()] = None,
) -> SetupDocResponse:
    try:
        return await generate_setup_docs(req, groq_api_key_override=x_groq_api_key)
    except (ValueError, RuntimeError) as exc:
        _status = status.HTTP_401_UNAUTHORIZED if _is_auth_error_message(str(exc)) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=_status, detail=str(exc)) from exc
    except Exception as exc:
        _maybe_raise_auth_http(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Documentation generation failed: {exc}",
        ) from exc


class FullPipelineRequest(RepoAnalysisRequest, SetupDocRequest):
    """Combined request: analyse a repo AND generate docs in one round-trip."""

    # Override the analysis field inherited from SetupDocRequest so it becomes
    # optional — we will populate it from the live analysis step.
    analysis: RepoAnalysisResult | None = None  # type: ignore[assignment]

    model_config = {"json_schema_extra": {"examples": [
        {
            "source": "github",
            "github_url": "https://github.com/tiangolo/fastapi",
            "branch": "master",
            "doc_format": "markdown",
            "llm_provider": "mock",
        }
    ]}}


@router.post(
    "/architecture-diagram",
    response_model=ArchitectureDiagramResponse,
    summary="Generate a Mermaid.js architecture diagram from repository analysis",
    description=(
        "Analyses a local or remote repository and returns a Mermaid.js flowchart "
        "string that visualises entry points, source layers, tech stack, dependencies, "
        "and infrastructure. Render this diagram in any Mermaid-compatible viewer."
    ),
)
async def generate_architecture_diagram(
    background_tasks: BackgroundTasks,
    req: Annotated[RepoAnalysisRequest, Body()],
) -> ArchitectureDiagramResponse:
    result, clone_path = await _run_analysis(req)
    if clone_path:
        background_tasks.add_task(_cleanup_dir, clone_path)
    mermaid_src = build_architecture_diagram(result)
    return ArchitectureDiagramResponse(
        mermaid_source=mermaid_src,
        repo_name=result.repo_name,
    )


@router.post(
    "/good-first-issues",
    response_model=GoodFirstIssuesResponse,
    summary="Generate Good First Issues for a new developer",
    description=(
        "Accepts a pre-computed RepoAnalysisResult and produces 3 (or more) tailored "
        "starter tasks for a new developer joining the project.  Each task includes a "
        "title, objective, target file/directory, and step-by-step instructions.  "
        "Supports Groq, OpenAI, or a deterministic mock backend.  Pass "
        "X-Groq-Api-Key to supply a Groq key at request time."
    ),
)
async def generate_good_first_issues_endpoint(
    req: Annotated[GoodFirstIssuesRequest, Body()],
    x_groq_api_key: Annotated[str | None, Header()] = None,
) -> GoodFirstIssuesResponse:
    try:
        return await generate_good_first_issues(req, groq_api_key_override=x_groq_api_key)
    except (ValueError, RuntimeError) as exc:
        _status = status.HTTP_401_UNAUTHORIZED if _is_auth_error_message(str(exc)) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=_status, detail=str(exc)) from exc
    except Exception as exc:
        _maybe_raise_auth_http(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Good first issues generation failed: {exc}",
        ) from exc


@router.post(
    "/full-pipeline",
    response_model=SetupDocResponse,
    summary="Analyse repository and generate docs in one call",
    description=(
        "Convenience endpoint: performs repository analysis and documentation "
        "generation in a single HTTP request. Pass an optional "
        "X-Groq-Api-Key header to override the server-side GROQ_API_KEY."
    ),
)
async def full_pipeline(
    background_tasks: BackgroundTasks,
    req: Annotated[FullPipelineRequest, Body()],
    x_groq_api_key: Annotated[str | None, Header()] = None,
) -> SetupDocResponse:
    analysis_req = RepoAnalysisRequest(
        source=req.source,
        path=req.path,
        github_url=req.github_url,
        branch=req.branch,
        max_file_size_kb=req.max_file_size_kb,
    )
    analysis_result, clone_path = await _run_analysis(analysis_req)
    if clone_path:
        background_tasks.add_task(_cleanup_dir, clone_path)

    doc_req = SetupDocRequest(
        analysis=analysis_result,
        doc_format=req.doc_format,
        include_sections=req.include_sections,
        audience=req.audience,
        llm_provider=req.llm_provider,
    )
    try:
        return await generate_setup_docs(doc_req, groq_api_key_override=x_groq_api_key)
    except (ValueError, RuntimeError) as exc:
        _status = status.HTTP_401_UNAUTHORIZED if _is_auth_error_message(str(exc)) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=_status, detail=str(exc)) from exc
    except Exception as exc:
        _maybe_raise_auth_http(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {exc}",
        ) from exc


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with your codebase",
    description=(
        "Accepts a developer question, the generated documentation context, and an "
        "optional conversation history. Returns a context-aware answer from the selected "
        "LLM. Pass X-Groq-Api-Key to supply a Groq key at request time — no .env required."
    ),
)
async def chat_with_codebase(
    req: Annotated[ChatRequest, Body()],
    x_groq_api_key: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    try:
        return await answer_codebase_question(req, groq_api_key_override=x_groq_api_key)
    except (ValueError, RuntimeError) as exc:
        _status = status.HTTP_401_UNAUTHORIZED if _is_auth_error_message(str(exc)) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=_status, detail=str(exc)) from exc
    except Exception as exc:
        _maybe_raise_auth_http(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {exc}",
        ) from exc
