"""
Architecture Diagram Service
=============================
Generates a Mermaid.js flowchart from a RepoAnalysisResult.

The diagram captures:
  • Entry points  → the system's "surface" (user-facing nodes)
  • Top-level source directories  → major functional layers
  • Detected frameworks  → technology stack decorators
  • Dependency ecosystem  → external package registries
  • Infrastructure flags  → Docker, CI, Tests
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import List, Set

from app.models.schemas import RepoAnalysisResult


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_architecture_diagram(analysis: RepoAnalysisResult) -> str:
    """
    Return a Mermaid flowchart (TB direction) that visualises the high-level
    architecture of *analysis*.  The result is a raw Mermaid source string,
    ready to be embedded in a ```mermaid``` fence or rendered client-side.
    """
    lines: List[str] = ["flowchart TD"]

    node_id = _NodeIdAllocator()

    # ── 1. Entry points ───────────────────────────────────────────────────────
    entry_ids: List[str] = []
    if analysis.entry_points:
        for ep in analysis.entry_points[:6]:
            nid = node_id.get(ep)
            label = PurePosixPath(ep).name
            lines.append(f'    {nid}(["🚀 {_esc(label)}"])')
            entry_ids.append(nid)
    else:
        nid = node_id.get("entry_main")
        lines.append(f'    {nid}(["🚀 Application"])')
        entry_ids.append(nid)

    # ── 2. Source layer nodes (top-level dirs only) ────────────────────────────
    top_dirs: list[str] = _collect_top_dirs(analysis)
    layer_ids: List[str] = []
    for d in top_dirs[:8]:
        nid = node_id.get(f"dir_{d}")
        lines.append(f'    {nid}["📁 {_esc(d)}/"]')
        layer_ids.append(nid)

    # ── 3. Frameworks sub-graph ───────────────────────────────────────────────
    fw_ids: List[str] = []
    if analysis.detected_frameworks:
        lines.append("")
        lines.append("    subgraph STACK [\" 🛠️ Tech Stack \"]")
        for fw in analysis.detected_frameworks[:6]:
            nid = node_id.get(f"fw_{fw}")
            lines.append(f'        {nid}["{_esc(fw)}"]')
            fw_ids.append(nid)
        lines.append("    end")

    # ── 4. Dependency ecosystem nodes ─────────────────────────────────────────
    eco_ids: List[str] = []
    ecosystems: Set[str] = {d.ecosystem for d in analysis.dependencies}
    if ecosystems:
        lines.append("")
        lines.append("    subgraph DEPS [\" 📦 Package Registries \"]")
        for eco in sorted(ecosystems)[:4]:
            nid = node_id.get(f"eco_{eco}")
            dep_count = sum(1 for d in analysis.dependencies if d.ecosystem == eco)
            lines.append(f'        {nid}(("{_esc(eco)}<br/>{dep_count} deps"))')
            eco_ids.append(nid)
        lines.append("    end")

    # ── 5. Infrastructure nodes ───────────────────────────────────────────────
    infra_ids: List[str] = []
    lines.append("")
    lines.append("    subgraph INFRA [\" ⚙️ Infrastructure \"]")
    if analysis.has_docker:
        nid = node_id.get("docker")
        lines.append(f'        {nid}["🐳 Docker"]')
        infra_ids.append(nid)
    if analysis.has_ci:
        nid = node_id.get("ci")
        lines.append(f'        {nid}["🔄 CI Pipeline"]')
        infra_ids.append(nid)
    if analysis.has_tests:
        nid = node_id.get("tests")
        lines.append(f'        {nid}["🧪 Test Suite"]')
        infra_ids.append(nid)
    if not infra_ids:
        nid = node_id.get("no_infra")
        lines.append(f'        {nid}["⚠️ No infra detected"]')
        infra_ids.append(nid)
    lines.append("    end")

    # ── 6. Edges ──────────────────────────────────────────────────────────────
    lines.append("")

    # Entry → layers (or direct to STACK if no dirs)
    if layer_ids:
        for eid in entry_ids:
            lines.append(f"    {eid} --> {layer_ids[0]}")
        for i in range(len(layer_ids) - 1):
            lines.append(f"    {layer_ids[i]} --> {layer_ids[i + 1]}")
        last_layer = layer_ids[-1]
    else:
        last_layer = entry_ids[0] if entry_ids else None

    # Layers → framework stack
    if fw_ids and last_layer:
        lines.append(f"    {last_layer} --> STACK")

    # Framework stack → package registries
    if eco_ids and fw_ids:
        lines.append(f"    STACK --> DEPS")
    elif eco_ids and last_layer:
        lines.append(f"    {last_layer} --> DEPS")

    # Entry / layers → infra (dotted style)
    if infra_ids:
        source = entry_ids[0] if entry_ids else (layer_ids[0] if layer_ids else None)
        if source:
            lines.append(f"    {source} -.-> INFRA")

    # ── 7. Styling ────────────────────────────────────────────────────────────
    lines.append("")
    lines.append("    classDef entryStyle fill:#1e3a5f,stroke:#3b82f6,color:#e0f0ff,font-weight:bold")
    lines.append("    classDef dirStyle  fill:#1e293b,stroke:#475569,color:#e2e8f0")
    lines.append("    classDef infraStyle fill:#14532d,stroke:#16a34a,color:#dcfce7")

    for eid in entry_ids:
        lines.append(f"    class {eid} entryStyle")
    for lid in layer_ids:
        lines.append(f"    class {lid} dirStyle")
    for iid in infra_ids:
        lines.append(f"    class {iid} infraStyle")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_top_dirs(analysis: RepoAnalysisResult) -> list[str]:
    """Return unique top-level directory names from file_tree_summary, ordered
    by descending file count.  Filters out venv / build / cache directories."""
    SKIP = {
        "__pycache__", ".git", "node_modules", "venv", ".venv", "env",
        "dist", "build", "target", "vendor", ".next", ".nuxt",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
    }
    counter: dict[str, int] = {}
    for fi in analysis.file_tree_summary:
        parts = fi.path.split("/")
        if len(parts) > 1:
            top = parts[0]
            if top not in SKIP:
                counter[top] = counter.get(top, 0) + 1

    return sorted(counter, key=lambda k: counter[k], reverse=True)


def _esc(text: str) -> str:
    """Escape characters that would break Mermaid node labels."""
    return (
        text.replace('"', "'")
            .replace("[", "(")
            .replace("]", ")")
            .replace("{", "(")
            .replace("}", ")")
    )


class _NodeIdAllocator:
    """Generates stable, safe alphanumeric Mermaid node IDs."""

    def __init__(self) -> None:
        self._map: dict[str, str] = {}
        self._counter = 0

    def get(self, key: str) -> str:
        if key not in self._map:
            self._counter += 1
            safe = "N" + str(self._counter)
            self._map[key] = safe
        return self._map[key]
