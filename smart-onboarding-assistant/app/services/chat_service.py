"""
Codebase Chat Service
=====================
Provides LLM-backed Q&A over generated repository documentation.

Supported backends:
  • "groq"   — Groq via OpenAI-compatible endpoint (same key as doc_generator).
  • "openai" — OpenAI GPT via the OpenAI Python SDK.
  • "mock"   — deterministic echo reply (no API key required).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.config import get_settings
from app.models.schemas import ChatMessage, ChatRequest, ChatResponse

# Maximum characters of doc_context passed to the LLM to stay within context limits.
_MAX_CONTEXT_CHARS = 12_000

_SYSTEM_TEMPLATE = """\
You are an expert software engineering assistant helping a new developer understand \
the repository "{repo_name}".

Below is the auto-generated onboarding documentation for this repository. Use it as \
your primary source of truth when answering questions. If the answer is not covered by \
the documentation, say so honestly and offer general best-practice guidance.

--- REPOSITORY DOCUMENTATION ---
{doc_context}
--- END OF DOCUMENTATION ---

Answer questions clearly and concisely. Use code blocks for commands or code snippets. \
Be friendly and encouraging toward new contributors.\
"""


def _build_messages(req: ChatRequest) -> List[dict]:
    """Assemble the messages list for the LLM API call."""
    doc_ctx = req.doc_context[:_MAX_CONTEXT_CHARS]
    system_content = _SYSTEM_TEMPLATE.format(
        repo_name=req.repo_name or "the repository",
        doc_context=doc_ctx,
    )
    messages: List[dict] = [{"role": "system", "content": system_content}]

    # Include prior conversation turns for multi-turn coherence
    for turn in req.history[-10:]:  # cap at last 10 turns
        messages.append({"role": turn.role, "content": turn.content})

    messages.append({"role": "user", "content": req.question})
    return messages


# ---------------------------------------------------------------------------
# Auth-error helper
# ---------------------------------------------------------------------------

def _raise_if_auth_error(exc: Exception) -> None:
    """Re-raise exc as a ValueError with a clear API-key message when it is a
    Groq / OpenAI 401 AuthenticationError, so the router maps it to HTTP 401."""
    try:
        from openai import AuthenticationError
    except ImportError:
        return
    if isinstance(exc, AuthenticationError):
        raise ValueError(
            "Invalid or missing Groq API Key. "
            "Please check your key and try again."
        ) from exc


# ---------------------------------------------------------------------------
# Groq backend
# ---------------------------------------------------------------------------

async def _chat_with_groq(
    req: ChatRequest,
    groq_api_key_override: Optional[str] = None,
) -> ChatResponse:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required. Run: pip install openai") from exc

    settings = get_settings()
    api_key = groq_api_key_override or settings.groq_api_key
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your .env file, environment, "
            "or supply it via the X-Groq-Api-Key request header."
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=1024,
            temperature=0.4,
            messages=_build_messages(req),
        )
    except Exception as exc:
        _raise_if_auth_error(exc)
        raise

    answer = response.choices[0].message.content or ""
    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return ChatResponse(
        answer=answer,
        model_used=settings.groq_model,
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

async def _chat_with_openai(req: ChatRequest) -> ChatResponse:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required. Run: pip install openai") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to your .env file or environment."
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=1024,
        temperature=0.4,
        messages=_build_messages(req),
    )

    answer = response.choices[0].message.content or ""
    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return ChatResponse(
        answer=answer,
        model_used=settings.openai_model,
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------

def _chat_mock(req: ChatRequest) -> ChatResponse:
    """Return a helpful placeholder answer without calling any external API."""
    repo = req.repo_name or "this repository"
    answer = (
        f"*(Mock answer — no API key used)*\n\n"
        f"You asked: **{req.question}**\n\n"
        f"Based on the generated documentation for `{repo}`, I can see the "
        f"repository has been analysed. Switch to **Groq** or **OpenAI** in the "
        f"sidebar and provide a valid API key to receive a real AI-powered answer."
    )
    return ChatResponse(answer=answer, model_used="mock")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def answer_codebase_question(
    req: ChatRequest,
    groq_api_key_override: Optional[str] = None,
) -> ChatResponse:
    """Route the request to the appropriate LLM backend."""
    provider = req.llm_provider.lower()
    if provider == "groq":
        return await _chat_with_groq(req, groq_api_key_override=groq_api_key_override)
    if provider == "openai":
        return await _chat_with_openai(req)
    return _chat_mock(req)
