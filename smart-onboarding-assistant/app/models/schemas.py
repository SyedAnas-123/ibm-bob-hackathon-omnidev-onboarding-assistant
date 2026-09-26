"""
Pydantic schemas for request/response models used across the onboarding assistant API.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RepoSource(str, Enum):
    LOCAL = "local"
    GITHUB = "github"


class DocFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN = "plain"


# ---------------------------------------------------------------------------
# Repository Analysis
# ---------------------------------------------------------------------------

class RepoAnalysisRequest(BaseModel):
    """Input for analysing a code repository."""

    source: RepoSource = Field(
        default=RepoSource.LOCAL,
        description="Whether the repo is on the local filesystem or a remote GitHub URL.",
    )
    path: Optional[str] = Field(
        default=None,
        description="Absolute or relative path to a local repository.",
        examples=["/home/dev/my-project"],
    )
    github_url: Optional[str] = Field(
        default=None,
        description="HTTPS clone URL of a GitHub repository.",
        examples=["https://github.com/owner/repo"],
    )
    branch: str = Field(default="main", description="Branch to analyse.")
    max_file_size_kb: int = Field(
        default=100,
        ge=1,
        le=2048,
        description="Skip individual files larger than this size (kilobytes).",
    )

    model_config = {"json_schema_extra": {"examples": [
        {"source": "github", "github_url": "https://github.com/tiangolo/fastapi", "branch": "master"}
    ]}}


class FileInfo(BaseModel):
    path: str
    language: Optional[str] = None
    size_bytes: int
    line_count: int


class DependencyInfo(BaseModel):
    name: str
    version: Optional[str] = None
    ecosystem: str = Field(description="e.g. pip, npm, maven")


class RepoAnalysisResult(BaseModel):
    """Structured summary produced by the repository analyser."""

    repo_name: str
    primary_language: Optional[str] = None
    languages_detected: List[str] = Field(default_factory=list)
    total_files: int
    total_lines: int
    entry_points: List[str] = Field(default_factory=list)
    dependencies: List[DependencyInfo] = Field(default_factory=list)
    has_tests: bool = False
    has_ci: bool = False
    has_docker: bool = False
    has_readme: bool = False
    readme_content: Optional[str] = None
    file_tree_summary: List[FileInfo] = Field(default_factory=list)
    env_vars_referenced: List[str] = Field(default_factory=list)
    detected_frameworks: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Documentation Generation
# ---------------------------------------------------------------------------

class SetupDocRequest(BaseModel):
    """Request to generate onboarding/setup documentation for a repository."""

    analysis: RepoAnalysisResult = Field(
        description="Pre-computed analysis result (from /analyze endpoint)."
    )
    doc_format: DocFormat = Field(
        default=DocFormat.MARKDOWN,
        description="Output format of the generated documentation.",
    )
    include_sections: List[str] = Field(
        default_factory=lambda: [
            "overview",
            "prerequisites",
            "installation",
            "environment_setup",
            "running_locally",
            "testing",
            "project_structure",
            "contributing",
        ],
        description="Ordered list of sections to include in the document.",
    )
    audience: str = Field(
        default="junior developer",
        description="Target audience for the documentation (influences tone & detail level).",
    )
    llm_provider: str = Field(
        default="groq",
        description="LLM backend to use for generation (groq | openai | mock).",
    )


class SetupDocResponse(BaseModel):
    """Generated setup documentation."""

    doc_format: DocFormat
    content: str = Field(description="Full documentation text in the requested format.")
    sections_generated: List[str]
    token_usage: Optional[Dict[str, int]] = None
    model_used: Optional[str] = None


class ArchitectureDiagramResponse(BaseModel):
    """Mermaid.js architecture diagram generated from repository analysis."""

    mermaid_source: str = Field(description="Raw Mermaid flowchart source code.")
    repo_name: str


# ---------------------------------------------------------------------------
# Good First Issues
# ---------------------------------------------------------------------------

class StarterTask(BaseModel):
    """A single 'Good First Issue' tailored for a new developer."""

    title: str = Field(description="Short, imperative task title (e.g. 'Add input validation to the login endpoint').")
    objective: str = Field(description="One- or two-sentence explanation of what the task achieves and why it matters.")
    target: str = Field(description="File path or directory the developer should edit (e.g. 'app/routers/auth.py').")
    difficulty: str = Field(
        default="beginner",
        description="Estimated difficulty: beginner | intermediate.",
    )
    steps: List[str] = Field(
        description="Ordered, concrete implementation steps. Each step should be a single actionable instruction.",
    )


class GoodFirstIssuesRequest(BaseModel):
    """Request to generate starter tasks from a pre-computed RepoAnalysisResult."""

    analysis: RepoAnalysisResult = Field(
        description="Pre-computed analysis result (from /analyze endpoint)."
    )
    num_tasks: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Number of starter tasks to generate (1–6).",
    )
    llm_provider: str = Field(
        default="groq",
        description="LLM backend to use for generation (groq | openai | mock).",
    )
    audience: str = Field(
        default="junior developer",
        description="Target skill level of the developer (influences task difficulty and detail).",
    )


class GoodFirstIssuesResponse(BaseModel):
    """Generated Good First Issues / starter tasks."""

    repo_name: str
    tasks: List[StarterTask]
    model_used: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None


# ---------------------------------------------------------------------------
# Codebase Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single turn in the chat conversation."""

    role: str = Field(description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    """Request to ask a question about a repository using generated doc context."""

    question: str = Field(description="The developer's question about the codebase.")
    doc_context: str = Field(
        description="Generated documentation text to use as context (from /full-pipeline).",
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous turns of the conversation for multi-turn coherence.",
    )
    llm_provider: str = Field(
        default="groq",
        description="LLM backend to use (groq | openai | mock).",
    )
    repo_name: str = Field(default="", description="Repository name (for context framing).")


class ChatResponse(BaseModel):
    """Answer returned from the chat endpoint."""

    answer: str
    model_used: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
