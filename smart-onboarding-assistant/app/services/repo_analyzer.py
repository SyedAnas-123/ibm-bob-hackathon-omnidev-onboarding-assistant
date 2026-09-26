"""
Repository Analyser Service
===========================
Inspects a local or remote Git repository and produces a structured
RepoAnalysisResult without relying on any LLM — pure static analysis.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.schemas import DependencyInfo, FileInfo, RepoAnalysisResult

# ---------------------------------------------------------------------------
# Language detection (extension → language name)
# ---------------------------------------------------------------------------
EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".r": "R",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
}

# Directories to always skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", "dist", "build", ".next", ".nuxt", "target", "vendor",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
}

# Files that indicate CI/CD pipelines
CI_FILES = {
    ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
    ".circleci/config.yml", ".travis.yml", "azure-pipelines.yml",
    ".drone.yml", "bitbucket-pipelines.yml",
}

# Files that suggest a test suite exists
TEST_PATTERNS = re.compile(
    r"(^test_|_test\.|\.spec\.|\.test\.|/tests?/|/spec/)", re.IGNORECASE
)

# Common environment variable patterns
ENV_VAR_PATTERN = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|process\.env|getenv)\s*\(?\s*['"]([A-Z_][A-Z0-9_]*)['"]"""
)

# Framework fingerprints  {keyword_in_deps → framework_name}
FRAMEWORK_KEYWORDS: Dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "nextjs": "Next.js",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "spring": "Spring",
    "rails": "Ruby on Rails",
    "gin": "Gin (Go)",
    "fiber": "Fiber (Go)",
    "actix": "Actix (Rust)",
    "rocket": "Rocket (Rust)",
    "laravel": "Laravel",
    "symfony": "Symfony",
}


class RepoAnalyzer:
    """Performs static analysis on a checked-out repository directory."""

    def __init__(self, max_file_size_bytes: int = 100 * 1024) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, repo_path: str | Path) -> RepoAnalysisResult:
        """
        Walk *repo_path* and return a fully populated RepoAnalysisResult.
        Raises FileNotFoundError if the path does not exist.
        """
        root = Path(repo_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Repository path not found: {root}")

        lang_counter: Dict[str, int] = {}
        all_files: List[FileInfo] = []
        total_lines = 0
        has_tests = False
        has_ci = False
        has_docker = False
        has_readme = False
        readme_content: Optional[str] = None
        env_vars: set[str] = set()
        entry_points: List[str] = []
        raw_dep_lines: List[str] = []

        for file_path in self._iter_files(root):
            rel = file_path.relative_to(root)
            rel_str = rel.as_posix()

            # ── CI detection ──────────────────────────────────────────
            if any(ci in rel_str for ci in CI_FILES):
                has_ci = True

            # ── Docker detection ──────────────────────────────────────
            if file_path.name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
                has_docker = True

            # ── README ────────────────────────────────────────────────
            if file_path.stem.lower() == "readme":
                has_readme = True
                try:
                    readme_content = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass

            # ── Dependency manifests ──────────────────────────────────
            raw_dep_lines.extend(self._extract_dep_lines(file_path))

            # ── Entry point heuristics ────────────────────────────────
            if file_path.name in ("main.py", "app.py", "server.py", "index.js",
                                  "index.ts", "main.go", "main.rs", "app.rb"):
                entry_points.append(rel_str)

            # ── Language + line count ─────────────────────────────────
            language = EXTENSION_MAP.get(file_path.suffix.lower())
            if language:
                size = file_path.stat().st_size
                if size > self.max_file_size_bytes:
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                lines = text.count("\n") + 1
                total_lines += lines
                lang_counter[language] = lang_counter.get(language, 0) + lines
                all_files.append(FileInfo(
                    path=rel_str,
                    language=language,
                    size_bytes=size,
                    line_count=lines,
                ))

                # ── Test detection ────────────────────────────────────
                if TEST_PATTERNS.search(rel_str):
                    has_tests = True

                # ── Env var scraping ──────────────────────────────────
                env_vars.update(ENV_VAR_PATTERN.findall(text))

        # ── Rank languages by line count ──────────────────────────────────
        ranked_langs = sorted(lang_counter, key=lambda k: lang_counter[k], reverse=True)
        primary_language = ranked_langs[0] if ranked_langs else None

        # ── Parse dependencies ────────────────────────────────────────────
        dependencies = self._parse_dependencies(root)

        # ── Detect frameworks ─────────────────────────────────────────────
        detected_frameworks = self._detect_frameworks(dependencies, raw_dep_lines)

        return RepoAnalysisResult(
            repo_name=root.name,
            primary_language=primary_language,
            languages_detected=ranked_langs,
            total_files=len(all_files),
            total_lines=total_lines,
            entry_points=entry_points,
            dependencies=dependencies,
            has_tests=has_tests,
            has_ci=has_ci,
            has_docker=has_docker,
            has_readme=has_readme,
            readme_content=readme_content,
            file_tree_summary=all_files[:200],   # cap to avoid huge payloads
            env_vars_referenced=sorted(env_vars),
            detected_frameworks=detected_frameworks,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_files(self, root: Path):
        """Yield all file paths under *root*, skipping ignored directories."""
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place (os.walk respects this)
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                yield Path(dirpath) / fname

    def _extract_dep_lines(self, file_path: Path) -> List[str]:
        """Return raw text lines from known dependency manifest files."""
        name = file_path.name
        if name in ("requirements.txt", "Pipfile", "pyproject.toml",
                    "package.json", "pom.xml", "build.gradle",
                    "Cargo.toml", "go.mod", "Gemfile"):
            try:
                return file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                pass
        return []

    def _parse_dependencies(self, root: Path) -> List[DependencyInfo]:
        """Detect and parse dependencies from common manifests."""
        deps: List[DependencyInfo] = []

        # ── Python: requirements.txt ──────────────────────────────────────
        req_file = root / "requirements.txt"
        if req_file.exists():
            deps.extend(self._parse_requirements_txt(req_file))

        # ── Node: package.json ────────────────────────────────────────────
        pkg_json = root / "package.json"
        if pkg_json.exists():
            deps.extend(self._parse_package_json(pkg_json))

        # ── Go: go.mod ────────────────────────────────────────────────────
        go_mod = root / "go.mod"
        if go_mod.exists():
            deps.extend(self._parse_go_mod(go_mod))

        # ── Rust: Cargo.toml ──────────────────────────────────────────────
        cargo = root / "Cargo.toml"
        if cargo.exists():
            deps.extend(self._parse_cargo_toml(cargo))

        return deps

    def _parse_requirements_txt(self, path: Path) -> List[DependencyInfo]:
        deps = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*(?:[><=!~^]+\s*([\w.\-*]+))?", line)
            if match:
                deps.append(DependencyInfo(
                    name=match.group(1),
                    version=match.group(2),
                    ecosystem="pip",
                ))
        return deps

    def _parse_package_json(self, path: Path) -> List[DependencyInfo]:
        import json
        deps = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return deps
        for section in ("dependencies", "devDependencies"):
            for name, version in data.get(section, {}).items():
                deps.append(DependencyInfo(name=name, version=version, ecosystem="npm"))
        return deps

    def _parse_go_mod(self, path: Path) -> List[DependencyInfo]:
        deps = []
        in_require = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("require ("):
                in_require = True
                continue
            if in_require and line == ")":
                in_require = False
                continue
            if in_require or line.startswith("require "):
                parts = line.replace("require ", "").split()
                if len(parts) >= 2:
                    deps.append(DependencyInfo(name=parts[0], version=parts[1], ecosystem="go"))
        return deps

    def _parse_cargo_toml(self, path: Path) -> List[DependencyInfo]:
        deps = []
        in_deps = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line in ("[dependencies]", "[dev-dependencies]"):
                in_deps = True
                continue
            if line.startswith("[") and in_deps:
                in_deps = False
            if in_deps and "=" in line:
                name, _, version = line.partition("=")
                deps.append(DependencyInfo(
                    name=name.strip(),
                    version=version.strip().strip('"').strip("'"),
                    ecosystem="cargo",
                ))
        return deps

    def _detect_frameworks(
        self, dependencies: List[DependencyInfo], raw_lines: List[str]
    ) -> List[str]:
        found: set[str] = set()
        combined = " ".join(
            [d.name.lower() for d in dependencies] +
            [line.lower() for line in raw_lines]
        )
        for keyword, framework in FRAMEWORK_KEYWORDS.items():
            if keyword in combined:
                found.add(framework)
        return sorted(found)


# ---------------------------------------------------------------------------
# Convenience: clone + analyse a remote GitHub repository
# ---------------------------------------------------------------------------

async def clone_and_analyze(
    github_url: str,
    branch: str = "main",
    clone_base: str = "/tmp/onboarding_repos",
    max_file_size_kb: int = 100,
) -> Tuple[RepoAnalysisResult, str]:
    """
    Clone *github_url* into a temp directory, run analysis, and return
    (result, cloned_path).  Caller is responsible for cleaning up the path.
    """
    try:
        import git  # gitpython
    except ImportError as exc:
        raise RuntimeError("gitpython is required for remote repo analysis.") from exc

    os.makedirs(clone_base, exist_ok=True)
    clone_dir = tempfile.mkdtemp(dir=clone_base)
    try:
        git.Repo.clone_from(github_url, clone_dir, branch=branch, depth=1)
    except git.GitCommandError as exc:
        shutil.rmtree(clone_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed: {exc}") from exc

    analyzer = RepoAnalyzer(max_file_size_bytes=max_file_size_kb * 1024)
    result = analyzer.analyze(clone_dir)
    return result, clone_dir
