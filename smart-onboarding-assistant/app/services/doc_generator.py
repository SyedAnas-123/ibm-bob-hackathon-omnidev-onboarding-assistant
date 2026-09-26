"""
Documentation Generator Service
================================
Converts a RepoAnalysisResult into human-readable setup documentation.
Supports three backends:
  • "groq"   — calls Llama-3 (or whichever model is configured) via Groq's
               OpenAI-compatible endpoint using the OpenAI Python SDK.
  • "openai" — calls GPT-4o-mini (or whichever model is configured) via the
               OpenAI Python SDK.
  • "mock"   — deterministic template-based generation (useful for testing
               and when no API key is available).
"""

from __future__ import annotations

import textwrap
from typing import Dict, List, Optional

from app.config import get_settings
from app.models.schemas import (
    DocFormat,
    RepoAnalysisResult,
    SetupDocRequest,
    SetupDocResponse,
)


# ---------------------------------------------------------------------------
# Section-level prompt builders
# ---------------------------------------------------------------------------

_SECTION_DESCRIPTIONS: Dict[str, str] = {
    "overview": "A concise project overview (what it does, why it exists).",
    "prerequisites": "System-level prerequisites (language runtimes, tools, OS notes).",
    "installation": "Step-by-step installation instructions.",
    "environment_setup": "How to configure environment variables and secrets.",
    "running_locally": "How to start the application locally.",
    "testing": "How to run the test suite.",
    "project_structure": "A guided tour of the directory layout.",
    "contributing": "Contribution guidelines (branching, PR process, code style).",
}


def _build_system_prompt(audience: str) -> str:
    return (
        f"You are a senior software engineer writing clear, friendly developer "
        f"documentation for a {audience}. "
        "Be precise and practical. Use numbered steps where order matters. "
        "Format code commands inside fenced code blocks. "
        "Do not add placeholder text like <YOUR_VALUE> without explanation."
    )


def _build_user_prompt(request: SetupDocRequest) -> str:
    a = request.analysis
    sections_detail = "\n".join(
        f"  - **{s}**: {_SECTION_DESCRIPTIONS.get(s, s)}"
        for s in request.include_sections
    )

    dep_list = (
        ", ".join(f"{d.name} ({d.ecosystem})" for d in a.dependencies[:20])
        or "none detected"
    )
    frameworks = ", ".join(a.detected_frameworks) or "none detected"
    env_vars = ", ".join(a.env_vars_referenced[:20]) or "none detected"
    entry_pts = ", ".join(a.entry_points) or "none detected"

    return textwrap.dedent(f"""
        Generate setup documentation for the repository **{a.repo_name}**.

        ### Repository facts
        - Primary language: {a.primary_language or "unknown"}
        - Languages detected: {", ".join(a.languages_detected) or "unknown"}
        - Frameworks/libraries: {frameworks}
        - Key dependencies: {dep_list}
        - Entry points: {entry_pts}
        - Has tests: {a.has_tests}
        - Has CI pipeline: {a.has_ci}
        - Has Docker setup: {a.has_docker}
        - Environment variables referenced: {env_vars}
        {"- Existing README (summarised):" + a.readme_content[:800] if a.readme_content else ""}

        ### Sections to generate (in order)
        {sections_detail}

        ### Output format
        Produce the document in **{request.doc_format.value}** format.
        Start directly with the document content — no preamble.
    """).strip()


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
# Groq backend  (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

async def _generate_with_groq(
    request: SetupDocRequest,
    groq_api_key_override: Optional[str] = None,
) -> SetupDocResponse:
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
            temperature=settings.groq_temperature,
            messages=[
                {"role": "system", "content": _build_system_prompt(request.audience)},
                {"role": "user", "content": _build_user_prompt(request)},
            ],
        )
    except Exception as exc:
        _raise_if_auth_error(exc)
        raise

    content = response.choices[0].message.content or ""
    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return SetupDocResponse(
        doc_format=request.doc_format,
        content=content,
        sections_generated=request.include_sections,
        token_usage=token_usage,
        model_used=settings.groq_model,
    )


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

async def _generate_with_openai(request: SetupDocRequest) -> SetupDocResponse:
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
        temperature=settings.openai_temperature,
        messages=[
            {"role": "system", "content": _build_system_prompt(request.audience)},
            {"role": "user", "content": _build_user_prompt(request)},
        ],
    )

    content = response.choices[0].message.content or ""
    token_usage: Optional[Dict[str, int]] = None
    if response.usage:
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return SetupDocResponse(
        doc_format=request.doc_format,
        content=content,
        sections_generated=request.include_sections,
        token_usage=token_usage,
        model_used=settings.openai_model,
    )


# ---------------------------------------------------------------------------
# Mock / template backend (no LLM required)
# ---------------------------------------------------------------------------

def _render_mock_markdown(request: SetupDocRequest) -> str:
    a = request.analysis
    lines: List[str] = [f"# {a.repo_name} — Developer Setup Guide\n"]

    section_renderers = {
        "overview": lambda: _section_overview(a),
        "prerequisites": lambda: _section_prerequisites(a),
        "installation": lambda: _section_installation(a),
        "environment_setup": lambda: _section_env_setup(a),
        "running_locally": lambda: _section_running(a),
        "testing": lambda: _section_testing(a),
        "project_structure": lambda: _section_structure(a),
        "contributing": lambda: _section_contributing(a),
    }

    for section in request.include_sections:
        renderer = section_renderers.get(section)
        if renderer:
            lines.append(renderer())

    return "\n".join(lines)


def _section_overview(a: RepoAnalysisResult) -> str:
    readme_snippet = ""
    if a.readme_content:
        first_para = a.readme_content.strip().split("\n\n")[0]
        readme_snippet = f"\n> {first_para[:300]}\n"
    return textwrap.dedent(f"""
        ## Overview
        **{a.repo_name}** is a {a.primary_language or "multi-language"} project.
        {readme_snippet}
        - **Languages**: {", ".join(a.languages_detected) or "N/A"}
        - **Detected frameworks**: {", ".join(a.detected_frameworks) or "N/A"}
        - **Total source files**: {a.total_files:,} ({a.total_lines:,} lines)
    """).strip() + "\n"


def _section_prerequisites(a: RepoAnalysisResult) -> str:
    prereqs = []
    lang_prereq = {
        "Python": "Python 3.10+",
        "JavaScript": "Node.js 18+ and npm/yarn",
        "TypeScript": "Node.js 18+ and npm/yarn",
        "Go": "Go 1.21+",
        "Rust": "Rust (latest stable via rustup)",
        "Java": "JDK 17+",
        "Ruby": "Ruby 3.2+",
    }
    if a.primary_language and a.primary_language in lang_prereq:
        prereqs.append(f"- {lang_prereq[a.primary_language]}")
    if a.has_docker:
        prereqs.append("- Docker & Docker Compose")
    prereqs.append("- Git")
    return "## Prerequisites\n\n" + "\n".join(prereqs) + "\n"


def _section_installation(a: RepoAnalysisResult) -> str:
    cmds = [
        "```bash",
        "# 1. Clone the repository",
        f"git clone <repository-url>",
        f"cd {a.repo_name}",
    ]

    if a.primary_language == "Python":
        cmds += [
            "",
            "# 2. Create and activate a virtual environment",
            "python -m venv .venv",
            "source .venv/bin/activate  # Windows: .venv\\Scripts\\activate",
            "",
            "# 3. Install dependencies",
            "pip install -r requirements.txt",
        ]
    elif a.primary_language in ("JavaScript", "TypeScript"):
        cmds += ["", "# 2. Install dependencies", "npm install"]
    elif a.primary_language == "Go":
        cmds += ["", "# 2. Download modules", "go mod download"]
    elif a.primary_language == "Rust":
        cmds += ["", "# 2. Build the project", "cargo build"]

    cmds.append("```")
    return "## Installation\n\n" + "\n".join(cmds) + "\n"


def _section_env_setup(a: RepoAnalysisResult) -> str:
    lines = ["## Environment Setup\n"]
    lines.append("Copy the example environment file and fill in your values:\n")
    lines.append("```bash\ncp .env.example .env\n```\n")
    if a.env_vars_referenced:
        lines.append("The following environment variables are used by this project:\n")
        lines.append("| Variable | Description |")
        lines.append("|----------|-------------|")
        for var in a.env_vars_referenced:
            lines.append(f"| `{var}` | *(fill in description)* |")
    else:
        lines.append("No environment variables were detected automatically.")
    return "\n".join(lines) + "\n"


def _section_running(a: RepoAnalysisResult) -> str:
    if a.has_docker:
        cmd = "```bash\ndocker-compose up --build\n```"
    elif a.primary_language == "Python" and a.entry_points:
        ep = a.entry_points[0]
        module = ep.replace("/", ".").removesuffix(".py")
        cmd = f"```bash\nuvicorn {module}:app --reload\n```"
    elif a.primary_language in ("JavaScript", "TypeScript"):
        cmd = "```bash\nnpm run dev\n```"
    elif a.primary_language == "Go":
        cmd = "```bash\ngo run .\n```"
    else:
        cmd = "```bash\n# See entry points: " + ", ".join(a.entry_points) + "\n```"

    return f"## Running Locally\n\n{cmd}\n"


def _section_testing(a: RepoAnalysisResult) -> str:
    if not a.has_tests:
        return "## Testing\n\nNo test suite was detected in this repository.\n"

    if a.primary_language == "Python":
        cmd = "```bash\npytest\n```"
    elif a.primary_language in ("JavaScript", "TypeScript"):
        cmd = "```bash\nnpm test\n```"
    elif a.primary_language == "Go":
        cmd = "```bash\ngo test ./...\n```"
    elif a.primary_language == "Rust":
        cmd = "```bash\ncargo test\n```"
    else:
        cmd = "```bash\n# Refer to project docs for test commands\n```"

    return f"## Testing\n\n{cmd}\n"


def _section_structure(a: RepoAnalysisResult) -> str:
    lines = ["## Project Structure\n"]
    lines.append("Below is a high-level overview of the key directories:\n")
    dirs: set[str] = set()
    for f in a.file_tree_summary[:100]:
        parts = f.path.split("/")
        if len(parts) > 1:
            dirs.add(parts[0])
    for d in sorted(dirs):
        lines.append(f"- `{d}/`")
    if a.entry_points:
        lines.append(f"\n**Entry points**: {', '.join(f'`{e}`' for e in a.entry_points)}")
    return "\n".join(lines) + "\n"


def _section_contributing(a: RepoAnalysisResult) -> str:
    ci_note = (
        "CI checks must pass before merging." if a.has_ci
        else "Consider adding a CI pipeline (GitHub Actions, GitLab CI, etc.)."
    )
    return textwrap.dedent(f"""
        ## Contributing

        1. Fork the repository and create a feature branch:
           ```bash
           git checkout -b feature/your-feature-name
           ```
        2. Make your changes with clear, atomic commits.
        3. Ensure tests pass locally.
        4. Open a Pull Request against `main` (or `master`).
        5. {ci_note}
    """).strip() + "\n"


async def _generate_mock(request: SetupDocRequest) -> SetupDocResponse:
    content = _render_mock_markdown(request)

    if request.doc_format == DocFormat.HTML:
        # Minimal HTML wrapping
        content = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{request.analysis.repo_name} Setup</title></head>"
            f"<body><pre>{content}</pre></body></html>"
        )
    elif request.doc_format == DocFormat.PLAIN:
        # Strip Markdown markers
        import re
        content = re.sub(r"[#*`>]", "", content)

    return SetupDocResponse(
        doc_format=request.doc_format,
        content=content,
        sections_generated=request.include_sections,
        model_used="mock-template-v1",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_setup_docs(
    request: SetupDocRequest,
    groq_api_key_override: Optional[str] = None,
) -> SetupDocResponse:
    """
    Generate setup documentation from a RepoAnalysisResult.

    Dispatches to the appropriate backend based on request.llm_provider:
      • "groq"   → Llama-3 via Groq's OpenAI-compatible endpoint
      • "openai" → GPT-based generation
      • "mock"   → deterministic template (no API key required)

    groq_api_key_override: when provided, takes precedence over the
      GROQ_API_KEY environment variable (supplied via X-Groq-Api-Key header).
    """
    if request.llm_provider == "groq":
        return await _generate_with_groq(request, groq_api_key_override=groq_api_key_override)
    if request.llm_provider == "openai":
        return await _generate_with_openai(request)
    return await _generate_mock(request)
