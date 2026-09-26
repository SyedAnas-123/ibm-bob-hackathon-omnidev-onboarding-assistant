"""
Good First Issues Service
=========================
Generates tailored 'Good First Issue' starter tasks for a new developer by
inspecting a RepoAnalysisResult.  Supports three backends:

  • "groq"   — LLaMA-3 via Groq's OpenAI-compatible endpoint
  • "openai" — GPT-based generation via the OpenAI Python SDK
  • "mock"   — deterministic, template-driven generation (no API key needed)
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Dict, List, Optional

from app.config import get_settings
from app.models.schemas import (
    GoodFirstIssuesRequest,
    GoodFirstIssuesResponse,
    RepoAnalysisResult,
    StarterTask,
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    return textwrap.dedent("""
        You are a senior open-source maintainer who excels at writing contribution tasks
        for developers of all experience levels.  When asked, you produce a JSON array of
        starter tasks for a new developer joining the project.

        Rules:
        - Each task must be specific to the actual files and technology in the repository.
        - Steps must be concrete and actionable — no vague "improve the code" instructions.
        - Avoid duplicating what a README already covers.
        - Respond with ONLY a valid JSON array.  No markdown fences, no prose.
        - Each element must have exactly these keys:
            title, objective, target, difficulty, steps
          where "steps" is a JSON array of strings and "difficulty" is one of:
            "beginner", "intermediate", or "advanced".
        - Assign difficulty honestly:
            beginner    — < 30 min, no deep domain knowledge required (e.g. docs, tests, config)
            intermediate — 30–90 min, requires understanding one subsystem (e.g. add a feature, add CI)
            advanced    — > 90 min, requires cross-cutting changes or deep domain knowledge (e.g. refactor, new service, performance work)
        - Vary the difficulty across the tasks so the set covers multiple skill levels.
    """).strip()


def _build_user_prompt(request: GoodFirstIssuesRequest) -> str:
    a = request.analysis

    dep_list = (
        ", ".join(f"{d.name}" for d in a.dependencies[:20])
        or "none detected"
    )
    frameworks = ", ".join(a.detected_frameworks) or "none detected"
    env_vars = ", ".join(a.env_vars_referenced[:15]) or "none detected"
    entry_pts = ", ".join(a.entry_points) or "none detected"

    # Build a compact file-tree snapshot (top 40 files by path)
    file_sample = "\n".join(
        f"  {f.path} ({f.language}, {f.line_count} lines)"
        for f in a.file_tree_summary[:40]
    ) or "  (no files detected)"

    missing_items: List[str] = []
    if not a.has_tests:
        missing_items.append("no test suite detected")
    if not a.has_ci:
        missing_items.append("no CI pipeline detected")
    if not a.has_docker:
        missing_items.append("no Docker setup detected")
    if not a.has_readme:
        missing_items.append("no README detected")
    missing_str = "; ".join(missing_items) or "none (project is fairly complete)"

    return textwrap.dedent(f"""
        Generate exactly {request.num_tasks} Good First Issues for the repository
        **{a.repo_name}** targeting a {request.audience}.

        ### Repository facts
        - Primary language : {a.primary_language or "unknown"}
        - All languages    : {", ".join(a.languages_detected) or "unknown"}
        - Frameworks       : {frameworks}
        - Key dependencies : {dep_list}
        - Entry points     : {entry_pts}
        - Has tests        : {a.has_tests}
        - Has CI pipeline  : {a.has_ci}
        - Has Docker       : {a.has_docker}
        - Has README       : {a.has_readme}
        - Env vars used    : {env_vars}
        - Gaps / missing   : {missing_str}

        ### File tree sample (first 40 files)
        {file_sample}

        ### Output format
        Return ONLY a JSON array of {request.num_tasks} objects, each with keys:
          title, objective, target, difficulty, steps
        where `steps` is an array of strings and `difficulty` is one of "beginner", "intermediate", or "advanced".
        Vary the difficulty across the {request.num_tasks} tasks — do not make them all the same level.
    """).strip()


# ---------------------------------------------------------------------------
# Shared JSON parser
# ---------------------------------------------------------------------------

def _parse_tasks(raw: str) -> List[StarterTask]:
    """
    Extract a JSON array of task objects from the LLM's raw response string.
    Handles cases where the model wraps the array in markdown fences.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array from the LLM, got something else.")

    tasks: List[StarterTask] = []
    for item in data:
        tasks.append(StarterTask(
            title=item.get("title", "Untitled Task"),
            objective=item.get("objective", ""),
            target=item.get("target", ""),
            difficulty=item.get("difficulty", "beginner"),
            steps=item.get("steps", []),
        ))
    return tasks


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

async def _generate_with_groq(
    request: GoodFirstIssuesRequest,
    groq_api_key_override: Optional[str] = None,
) -> GoodFirstIssuesResponse:
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
            max_tokens=settings.groq_max_tokens,
            temperature=0.4,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(request)},
            ],
        )
    except Exception as exc:
        _raise_if_auth_error(exc)
        raise

    raw = response.choices[0].message.content or "[]"
    tasks = _parse_tasks(raw)

    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return GoodFirstIssuesResponse(
        repo_name=request.analysis.repo_name,
        tasks=tasks,
        model_used=settings.groq_model,
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

async def _generate_with_openai(request: GoodFirstIssuesRequest) -> GoodFirstIssuesResponse:
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
        max_tokens=settings.openai_max_tokens,
        temperature=0.4,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": _build_user_prompt(request)},
        ],
    )

    raw = response.choices[0].message.content or "[]"
    tasks = _parse_tasks(raw)

    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return GoodFirstIssuesResponse(
        repo_name=request.analysis.repo_name,
        tasks=tasks,
        model_used=settings.openai_model,
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# Mock / template backend
# ---------------------------------------------------------------------------

def _mock_tasks(a: RepoAnalysisResult, num_tasks: int) -> List[StarterTask]:
    """Return deterministic starter tasks derived purely from the analysis."""
    candidates: List[StarterTask] = []

    # Task 1 — Tests (only if no tests detected)
    if not a.has_tests:
        candidates.append(StarterTask(
            title=f"Add a unit-test suite to {a.repo_name}",
            objective=(
                f"The repository currently has no automated tests. "
                f"Adding tests for the core logic improves confidence when making changes."
            ),
            target="tests/",
            difficulty="beginner",
            steps=[
                f"Create a `tests/` directory in the repository root.",
                f"Install a test framework (e.g. `pytest` for Python, `jest` for JS).",
                f"Write a test file `tests/test_core.py` (or `tests/core.test.js`).",
                f"Add at least three test cases covering the happy path of the main entry point (`{'  ,  '.join(a.entry_points[:2]) or 'main file'}`).",
                "Run the tests locally to confirm they all pass.",
                "Update the README with the command used to run the tests.",
            ],
        ))

    # Task 2 — README (only if missing)
    if not a.has_readme:
        candidates.append(StarterTask(
            title=f"Write a README for {a.repo_name}",
            objective=(
                "A README is the first thing a new contributor reads. "
                "Creating one makes the project more welcoming and searchable."
            ),
            target="README.md",
            difficulty="beginner",
            steps=[
                "Create `README.md` in the repository root.",
                f"Add a title and one-paragraph project description.",
                f"Document prerequisites: {a.primary_language or 'runtime'} version, any required tools.",
                "Add an installation section with copy-paste commands.",
                "Add a 'Running Locally' section covering the main entry points.",
                "Optionally add a 'Contributing' section pointing to PR guidelines.",
            ],
        ))

    # Task 3 — CI (only if missing)
    if not a.has_ci:
        candidates.append(StarterTask(
            title="Set up a GitHub Actions CI workflow",
            objective=(
                "Continuous integration automatically checks code on every push, "
                "catching regressions before they reach the main branch."
            ),
            target=".github/workflows/ci.yml",
            difficulty="intermediate",
            steps=[
                "Create the directory `.github/workflows/` in the repository root.",
                "Create `.github/workflows/ci.yml`.",
                f"Configure the workflow to trigger on `push` and `pull_request` to `main`.",
                f"Add a job that sets up {a.primary_language or 'the project runtime'} and installs dependencies.",
                "Add a step to run the test suite (or a lint check if no tests exist).",
                "Commit and push — verify the Actions tab on GitHub shows a passing run.",
            ],
        ))

    # Task 4 — Docker (only if missing)
    if not a.has_docker:
        candidates.append(StarterTask(
            title=f"Containerise {a.repo_name} with Docker",
            objective=(
                "A Dockerfile lets any developer run the project identically regardless "
                "of their local environment."
            ),
            target="Dockerfile",
            difficulty="advanced",
            steps=[
                "Create a `Dockerfile` in the repository root.",
                f"Choose a suitable base image for {a.primary_language or 'the project'} (e.g. `python:3.12-slim`).",
                "Copy source files, install dependencies, and set the `CMD` to the main entry point.",
                f"Build the image locally: `docker build -t {a.repo_name.lower()} .`",
                f"Run it and verify it works: `docker run --rm {a.repo_name.lower()}`",
                "Add a `.dockerignore` to exclude `venv/`, `__pycache__/`, and test files.",
                "Optionally add a `docker-compose.yml` for multi-service setups.",
            ],
        ))

    # Task 5 — .env.example
    if a.env_vars_referenced:
        candidates.append(StarterTask(
            title="Add a .env.example file documenting required environment variables",
            objective=(
                "New developers need to know which environment variables to set. "
                "A `.env.example` file makes this self-documenting."
            ),
            target=".env.example",
            difficulty="beginner",
            steps=[
                "Create `.env.example` in the repository root.",
                "Add an entry for each env var detected in the codebase:",
                *[f"  {var}=<description>" for var in a.env_vars_referenced[:8]],
                "Add a note in the README: 'Copy `.env.example` to `.env` and fill in values.'",
            ],
        ))

    # Task 6 — Code quality: add type hints / docstrings
    if a.primary_language == "Python":
        entry = a.entry_points[0] if a.entry_points else (a.file_tree_summary[0].path if a.file_tree_summary else "main.py")
        candidates.append(StarterTask(
            title=f"Add type annotations to {entry}",
            objective=(
                "Type annotations improve IDE support, catch bugs early, "
                "and make the codebase easier to understand for new contributors."
            ),
            target=entry,
            difficulty="beginner",
            steps=[
                f"Open `{entry}` and identify functions that lack type hints.",
                "Add parameter and return type annotations to each function signature.",
                "Run `mypy` (or `pyright`) to verify there are no type errors: `pip install mypy && mypy .'",
                "Fix any type errors reported before committing.",
                "Open a pull request with the annotated file.",
            ],
        ))

    # Fallback generic task if we somehow have nothing yet
    if not candidates:
        candidates.append(StarterTask(
            title=f"Improve inline documentation in {a.repo_name}",
            objective=(
                "Well-documented code reduces the time new contributors spend "
                "understanding the codebase before making their first change."
            ),
            target=a.file_tree_summary[0].path if a.file_tree_summary else "src/",
            difficulty="beginner",
            steps=[
                "Identify the three most important source files by line count.",
                "Add or improve module-level docstrings explaining purpose and usage.",
                "Add inline comments for non-obvious logic blocks.",
                "Verify no docstring exceeds 80 characters per line for readability.",
                "Open a pull request with only documentation changes.",
            ],
        ))

    return candidates[:num_tasks]


async def _generate_mock(request: GoodFirstIssuesRequest) -> GoodFirstIssuesResponse:
    tasks = _mock_tasks(request.analysis, request.num_tasks)
    return GoodFirstIssuesResponse(
        repo_name=request.analysis.repo_name,
        tasks=tasks,
        model_used="mock-template-v1",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_good_first_issues(
    request: GoodFirstIssuesRequest,
    groq_api_key_override: Optional[str] = None,
) -> GoodFirstIssuesResponse:
    """
    Generate Good First Issues / starter tasks from a RepoAnalysisResult.

    Dispatches to the appropriate backend based on request.llm_provider:
      • "groq"   → LLaMA-3 via Groq
      • "openai" → GPT-based generation
      • "mock"   → deterministic template (no API key required)

    groq_api_key_override: when provided, takes precedence over GROQ_API_KEY.
    """
    if request.llm_provider == "groq":
        return await _generate_with_groq(request, groq_api_key_override=groq_api_key_override)
    if request.llm_provider == "openai":
        return await _generate_with_openai(request)
    return await _generate_mock(request)
