"""
Smart Developer Onboarding Assistant — Streamlit Frontend
==========================================================
Run with:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime
from typing import Any

import httpx
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Developer Onboarding Assistant",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Smart Developer Onboarding Assistant — AI-powered onboarding docs generator.",
    },
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = "http://localhost:8000"
API_TIMEOUT = 300  # seconds — repo clone + LLM can be slow
DIAGRAM_TIMEOUT = 120  # seconds — clone + static analysis only
ISSUES_TIMEOUT = 300   # seconds — clone + LLM for good-first-issues
CHAT_TIMEOUT = 60      # seconds — single-turn LLM response

ALL_SECTIONS = [
    "overview",
    "prerequisites",
    "installation",
    "environment_setup",
    "running_locally",
    "testing",
    "project_structure",
    "contributing",
]

SECTION_LABELS = {
    "overview": "📋 Overview",
    "prerequisites": "📦 Prerequisites",
    "installation": "⚙️ Installation",
    "environment_setup": "🔑 Environment Setup",
    "running_locally": "▶️ Running Locally",
    "testing": "🧪 Testing",
    "project_structure": "🗂️ Project Structure",
    "contributing": "🤝 Contributing",
}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
# Difficulty badge colours used in the Good First Issues renderer
DIFFICULTY_COLOURS: dict[str, tuple[str, str]] = {
    "beginner":     ("#dcfce7", "#166534"),   # green bg, dark-green text
    "intermediate": ("#fef9c3", "#854d0e"),   # yellow bg, brown text
}

st.markdown(
    """
<style>
/* ── Global ── */
html, body, [class*="css"] { font-family: "Inter", "Segoe UI", system-ui, sans-serif; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0f172a; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stSlider label { color: #94a3b8 !important; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #f1f5f9 !important; }

/* ── Header banner ── */
.header-banner {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a2f4a 50%, #0f1e30 100%);
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid #2d4a6b;
}
.header-banner h1 { color: #f0f6ff; font-size: 2rem; margin: 0 0 0.3rem; font-weight: 700; }
.header-banner p  { color: #94b8d4; margin: 0; font-size: 1rem; }

/* ── Cards ── */
.card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.card-title { font-weight: 600; color: #1e293b; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.75rem; }

/* ── Metric pills ── */
.metric-row { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; }
.metric-pill {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9999px;
    padding: 0.3rem 0.85rem;
    font-size: 0.82rem;
    color: #1d4ed8;
    font-weight: 500;
}
.metric-pill.green  { background:#f0fdf4; border-color:#bbf7d0; color:#15803d; }
.metric-pill.yellow { background:#fefce8; border-color:#fde68a; color:#92400e; }
.metric-pill.red    { background:#fef2f2; border-color:#fecaca; color:#b91c1c; }

/* ── Badge row ── */
.badge-row { display:flex; flex-wrap:wrap; gap:0.5rem; margin:0.5rem 0; }
.badge {
    background:#1e40af;
    color:#eff6ff;
    border-radius:6px;
    padding:0.2rem 0.6rem;
    font-size:0.75rem;
    font-weight:600;
    letter-spacing:0.03em;
}
.badge.gray  { background:#475569; color:#f1f5f9; }
.badge.green { background:#166534; color:#dcfce7; }
.badge.amber { background:#92400e; color:#fef3c7; }

/* ── Doc output ── */
.doc-output-container {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    background: #ffffff;
    padding: 0.5rem 1.5rem 1.5rem;
    margin-top: 1rem;
}

/* ── Export bar ── */
.export-bar {
    display:flex; align-items:center; justify-content:space-between;
    padding:0.6rem 0.75rem;
    background:#f1f5f9;
    border-radius:8px;
    margin-bottom:1rem;
    font-size:0.82rem;
    color:#475569;
}

/* ── Status ── */
.status-ok   { color:#16a34a; font-weight:600; }
.status-fail { color:#dc2626; font-weight:600; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-size:0.9rem; font-weight:500; }

/* ── Divider ── */
hr { border:none; border-top:1px solid #e2e8f0; margin:1.5rem 0; }

/* ── Generated time stamp ── */
.timestamp { font-size:0.75rem; color:#94a3b8; }

/* ── Good First Issues ── */
.gfi-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    background: #ffffff;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
}
.gfi-card:hover { border-color: #93c5fd; box-shadow: 0 0 0 3px rgba(147,197,253,.15); }
.gfi-header {
    display: flex; align-items: flex-start; justify-content: space-between;
    margin-bottom: 0.6rem;
    gap: 0.75rem;
}
.gfi-title { font-size: 1rem; font-weight: 700; color: #1e293b; line-height: 1.4; }
.gfi-badge {
    border-radius: 9999px;
    padding: 0.2rem 0.65rem;
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
}
.gfi-objective { color: #475569; font-size: 0.88rem; margin-bottom: 0.75rem; line-height: 1.6; }
.gfi-target {
    font-size: 0.8rem; color: #6366f1; background: #eef2ff;
    border-radius: 5px; padding: 0.2rem 0.55rem; display: inline-block;
    margin-bottom: 0.85rem; font-family: monospace;
}
.gfi-steps-title { font-size: 0.78rem; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.45rem; }
.gfi-steps ol { margin: 0; padding-left: 1.3rem; color: #334155; font-size: 0.875rem; line-height: 1.75; }

/* ── Chat interface ── */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 0.5rem 0;
}
.chat-bubble {
    max-width: 85%;
    padding: 0.75rem 1rem;
    border-radius: 12px;
    font-size: 0.9rem;
    line-height: 1.65;
    word-break: break-word;
}
.chat-bubble.user {
    align-self: flex-end;
    background: #1e3a5f;
    color: #e0f0ff;
    border-bottom-right-radius: 4px;
    margin-left: auto;
}
.chat-bubble.assistant {
    align-self: flex-start;
    background: #f1f5f9;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-bottom-left-radius: 4px;
}
.chat-meta { font-size: 0.72rem; color: #94a3b8; margin-bottom: 0.15rem; }
.chat-empty {
    text-align: center;
    padding: 2.5rem 1rem;
    color: #94a3b8;
    font-size: 0.9rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults: dict[str, Any] = {
        "result": None,
        "analysis_meta": None,
        "last_request": None,
        "api_base": DEFAULT_API_BASE,
        # groq_api_key is owned exclusively by the widget key "groq_api_key_widget";
        # do NOT initialise it here so Streamlit's widget state is the single source
        # of truth (avoids the value= / key= double-binding that causes autofill glitches).
        "history": [],
        "api_healthy": None,
        "arch_diagram": None,        # stores ArchitectureDiagramResponse dict
        "good_first_issues": None,   # stores GoodFirstIssuesResponse dict
        "chat_messages": [],         # list of {"role": str, "content": str}
        # ── Deferred-dispatch concurrency model ─────────────────────────────
        #
        # HOW IT WORKS (read this before touching any of these keys):
        #
        # Streamlit reruns the entire script on every user interaction.
        # Setting a lock flag and making an HTTP call in the SAME code path
        # (the `if generate_btn:` block) does NOT prevent a concurrent click
        # because:
        #   1. The button widget is rendered BEFORE the `if generate_btn:`
        #      block runs, so `disabled=` has no effect on the current rerun.
        #   2. If a user interaction arrives while the blocking HTTP call is
        #      executing, Streamlit can interrupt and restart the script.
        #      When it does, the new rerun starts from the top — the `if`
        #      block is False, the call never happens, but any state already
        #      written (e.g. pending_task="docs") persists forever.
        #
        # THE FIX — two-rerun deferred dispatch:
        #   Rerun A (button click):
        #     • Only writes "queued_task" + "queued_params" to session state.
        #     • Does NOT make any HTTP call.
        #     • Calls st.rerun() immediately to trigger Rerun B.
        #   Rerun B (task execution rerun):
        #     • Detected at the TOP of the script (before any widget renders).
        #     • Sets is_running=True (sidebar reads this → all widgets disabled).
        #     • Renders the full locked UI via _render_locked_sidebar().
        #     • Makes the HTTP call in a try/finally that ALWAYS clears
        #       queued_task and is_running before the rerun ends.
        #     • Calls st.rerun() on success so results render on a clean page.
        #
        # This guarantees:
        #   • is_running is True for exactly one full rerun — the one doing work.
        #   • Widgets are disabled before any button can be read (they render
        #     after is_running is known at the top of the script).
        #   • No interaction during the blocking call can queue another task
        #     because all buttons are disabled=True during Rerun B.
        #   • pending_task / is_running can NEVER be left set permanently.
        "is_running": False,   # True for exactly the rerun that makes HTTP calls
        "queued_task": None,   # "docs" | "gfi" | "arch" | "chat" — set on click rerun
        "queued_params": None, # dict of snapshotted form values for the queued task
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()

# ---------------------------------------------------------------------------
# Deferred-dispatch executor — runs at top of script before any widget renders
# ---------------------------------------------------------------------------

def _run_queued_task() -> None:
    """Execute whatever task was queued on the previous rerun.

    Called unconditionally near the top of the script.  Returns immediately
    if no task is queued.  When a task IS queued this function:
      1. Sets is_running=True (sidebar will read this and lock all widgets).
      2. Executes the blocking HTTP call.
      3. Clears queued_task / queued_params / is_running in a finally block.
      4. Calls st.rerun() so the results page renders cleanly.
    """
    if not st.session_state.queued_task:
        return

    task   = st.session_state.queued_task
    params = st.session_state.queued_params or {}

    # Mark running BEFORE any widget renders on this rerun
    st.session_state.is_running = True

    # ── Locked sidebar — rendered while the task runs ──────────────────────
    with st.sidebar:
        st.markdown("## 🚀 Onboarding Assistant")
        st.markdown("---")
        st.info(f"⏳ **{task}** in progress…\n\nAll controls are locked until the task completes.")

    # ── Execute ────────────────────────────────────────────────────────────
    try:
        if task == "Generating docs":
            _exec_docs(params)
        elif task == "Generating Good First Issues":
            _exec_gfi(params)
        elif task == "Generating architecture diagram":
            _exec_arch(params)
        elif task == "Chat":
            _exec_chat(params)
    finally:
        st.session_state.queued_task   = None
        st.session_state.queued_params = None
        st.session_state.is_running    = False

    # Rerun so the results render on a fully fresh, unlocked page
    st.rerun()


def _exec_docs(p: dict) -> None:
    """Full-pipeline documentation generation."""
    with st.status("⏳ Running onboarding pipeline…", expanded=True) as status_box:
        st.write("📡 Connecting to API server…")
        if not _check_health(p["api_base"]):
            st.session_state.api_healthy = False
            status_box.update(label="❌ API server is not reachable.", state="error", expanded=True)
            st.error(
                f"Cannot reach the API at **{p['api_base']}**. "
                "Make sure the FastAPI server is running (`python main.py`) and the URL is correct."
            )
            return
        st.session_state.api_healthy = True
        st.write(f"🔍 Analysing repository: `{p['repo_label']}`…")
        t_start = time.time()
        try:
            response = _call_full_pipeline(
                p["api_base"], p["payload"], groq_api_key=p["key"]
            )
            elapsed = time.time() - t_start
            st.session_state.result        = response
            st.session_state.analysis_meta = None
            st.session_state.history.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "repo":      p["repo_label"],
                "format":    p["format"],
                "provider":  p["provider"],
                "sections":  len(p["sections"]),
                "elapsed_s": round(elapsed, 1),
            })
            status_box.update(
                label=f"✅ Done — documentation generated in {elapsed:.1f}s",
                state="complete",
                expanded=False,
            )
            st.success(f"Documentation generated in **{elapsed:.1f}s**.")
        except RuntimeError as exc:
            status_box.update(label="❌ Pipeline failed", state="error", expanded=True)
            st.error(f"**Error:** {exc}")
            st.session_state.result = None
        except Exception as exc:
            status_box.update(label="❌ Unexpected error", state="error", expanded=True)
            st.exception(exc)
            st.session_state.result = None


def _exec_gfi(p: dict) -> None:
    """Good First Issues generation."""
    with st.status("⏳ Generating Good First Issues…", expanded=True) as gfi_status:
        st.write("📡 Connecting to API server…")
        if not _check_health(p["api_base"]):
            st.session_state.api_healthy = False
            gfi_status.update(label="❌ API server is not reachable.", state="error", expanded=True)
            st.error(
                f"Cannot reach the API at **{p['api_base']}**. "
                "Make sure the FastAPI server is running (`python main.py`)."
            )
            return
        st.session_state.api_healthy = True
        st.write(f"🔍 Analysing repository: `{p['repo_label']}`…")
        try:
            with httpx.Client(timeout=API_TIMEOUT) as client:
                ar = client.post(
                    f"{p['api_base']}/api/v1/onboarding/analyze",
                    json=p["analysis_payload"],
                )
            if ar.status_code != 200:
                try:
                    detail = ar.json().get("detail", ar.text)
                except Exception:
                    detail = ar.text
                raise RuntimeError(f"Analysis failed ({ar.status_code}): {detail}")
            analysis_result = ar.json()

            st.write("🤖 Generating starter tasks with LLM…")
            gfi_payload = {
                "analysis":    analysis_result,
                "num_tasks":   p["num_tasks"],
                "llm_provider": p["provider"],
                "audience":    p["audience"],
            }
            gfi_response = _call_good_first_issues(
                p["api_base"], gfi_payload, groq_api_key=p["key"]
            )
            st.session_state.good_first_issues = gfi_response
            gfi_status.update(
                label=(
                    f"✅ {len(gfi_response.get('tasks', []))} Good First Issues ready "
                    f"for **{gfi_response.get('repo_name', p['repo_label'])}**"
                ),
                state="complete",
                expanded=False,
            )
        except RuntimeError as exc:
            gfi_status.update(label="❌ Generation failed", state="error", expanded=True)
            st.error(f"**Error:** {exc}")
            st.session_state.good_first_issues = None
        except Exception as exc:
            gfi_status.update(label="❌ Unexpected error", state="error", expanded=True)
            st.exception(exc)
            st.session_state.good_first_issues = None


def _exec_arch(p: dict) -> None:
    """Architecture diagram generation."""
    with st.status("⏳ Scanning repository for architecture diagram…", expanded=True) as arch_status:
        st.write("📡 Connecting to API server…")
        if not _check_health(p["api_base"]):
            st.session_state.api_healthy = False
            arch_status.update(label="❌ API server is not reachable.", state="error", expanded=True)
            st.error(
                f"Cannot reach the API at **{p['api_base']}**. "
                "Make sure the FastAPI server is running (`python main.py`)."
            )
            return
        st.session_state.api_healthy = True
        st.write(f"🔍 Analysing structure of `{p['repo_label']}`…")
        try:
            arch_response = _call_architecture_diagram(p["api_base"], p["arch_payload"])
            st.session_state.arch_diagram = arch_response
            arch_status.update(
                label=f"✅ Architecture diagram ready for **{arch_response.get('repo_name', p['repo_label'])}**",
                state="complete",
                expanded=False,
            )
        except RuntimeError as exc:
            arch_status.update(label="❌ Diagram generation failed", state="error", expanded=True)
            st.error(f"**Error:** {exc}")
            st.session_state.arch_diagram = None
        except Exception as exc:
            arch_status.update(label="❌ Unexpected error", state="error", expanded=True)
            st.exception(exc)
            st.session_state.arch_diagram = None


def _exec_chat(p: dict) -> None:
    """Single chat turn."""
    with st.spinner("🤖 Thinking…"):
        try:
            chat_payload = {
                "question":    p["question"],
                "doc_context": p["doc_content"],
                "repo_name":   p["repo_name"],
                "llm_provider": p["provider"],
                "history":     p["history"],
            }
            chat_response = _call_chat(p["api_base"], chat_payload, groq_api_key=p["key"])
            answer: str = chat_response.get("answer", "No answer returned.")
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
        except RuntimeError as exc:
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": f"⚠️ Error: {exc}"}
            )
        except Exception as exc:
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": f"⚠️ Unexpected error: {exc}"}
            )


# ---------------------------------------------------------------------------
# Helper — API calls
# ---------------------------------------------------------------------------

def _check_health(base: str) -> bool:
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _call_full_pipeline(base: str, payload: dict, groq_api_key: str = "") -> dict:
    headers: dict[str, str] = {}
    if groq_api_key:
        headers["X-Groq-Api-Key"] = groq_api_key
    with httpx.Client(timeout=API_TIMEOUT) as client:
        r = client.post(f"{base}/api/v1/onboarding/full-pipeline", json=payload, headers=headers)
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"API returned {r.status_code}: {detail}")
    return r.json()


def _call_good_first_issues(
    base: str,
    payload: dict,
    groq_api_key: str = "",
) -> dict:
    """Call the /good-first-issues endpoint and return the JSON response."""
    headers: dict[str, str] = {}
    if groq_api_key:
        headers["X-Groq-Api-Key"] = groq_api_key
    with httpx.Client(timeout=ISSUES_TIMEOUT) as client:
        r = client.post(
            f"{base}/api/v1/onboarding/good-first-issues",
            json=payload,
            headers=headers,
        )
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"API returned {r.status_code}: {detail}")
    return r.json()


def _call_architecture_diagram(base: str, payload: dict) -> dict:
    """Call the /architecture-diagram endpoint and return the JSON response."""
    with httpx.Client(timeout=DIAGRAM_TIMEOUT) as client:
        r = client.post(
            f"{base}/api/v1/onboarding/architecture-diagram",
            json=payload,
        )
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"API returned {r.status_code}: {detail}")
    return r.json()


def _call_chat(base: str, payload: dict, groq_api_key: str = "") -> dict:
    """Call the /chat endpoint and return the JSON response."""
    headers: dict[str, str] = {}
    if groq_api_key:
        headers["X-Groq-Api-Key"] = groq_api_key
    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        r = client.post(
            f"{base}/api/v1/onboarding/chat",
            json=payload,
            headers=headers,
        )
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"API returned {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Helper — build request payload from form values
# ---------------------------------------------------------------------------

def _build_payload(
    source: str,
    local_path: str,
    github_url: str,
    branch: str,
    max_file_size_kb: int,
    doc_format: str,
    llm_provider: str,
    audience: str,
    sections: list[str],
) -> dict:
    payload: dict[str, Any] = {
        "source": source,
        "branch": branch,
        "max_file_size_kb": max_file_size_kb,
        "doc_format": doc_format,
        "llm_provider": llm_provider,
        "audience": audience,
        "include_sections": sections,
    }
    if source == "local":
        payload["path"] = local_path.strip()
    else:
        payload["github_url"] = github_url.strip()
    return payload


# ---------------------------------------------------------------------------
# Helper — build a "lite" repo analysis payload (no LLM fields needed)
# ---------------------------------------------------------------------------

def _build_analysis_payload(
    source: str,
    local_path: str,
    github_url: str,
    branch: str,
    max_file_size_kb: int,
) -> dict:
    payload: dict[str, Any] = {
        "source": source,
        "branch": branch,
        "max_file_size_kb": max_file_size_kb,
    }
    if source == "local":
        payload["path"] = local_path.strip()
    else:
        payload["github_url"] = github_url.strip()
    return payload


# ---------------------------------------------------------------------------
# Helper — render a Mermaid diagram inside an HTML component
# ---------------------------------------------------------------------------

def _render_mermaid(mermaid_source: str, height: int = 520) -> None:
    """Render *mermaid_source* inside a self-contained HTML component using
    the Mermaid CDN.  Works with any Streamlit version that supports
    st.components.v1.html (i.e., all current versions)."""
    escaped = mermaid_source.replace("`", "\\`")
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0;
    padding: 12px;
    background: #0f172a;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  #diagram {{
    width: 100%;
    max-width: 900px;
    background: #1e293b;
    border-radius: 10px;
    padding: 1.5rem;
    box-sizing: border-box;
  }}
  .mermaid svg {{
    width: 100% !important;
    height: auto !important;
  }}
  #copy-btn {{
    margin-top: 12px;
    padding: 6px 18px;
    background: #1e40af;
    color: #eff6ff;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    font-family: system-ui, sans-serif;
  }}
  #copy-btn:hover {{ background: #1d4ed8; }}
  #copy-btn:active {{ background: #1e3a8a; }}
</style>
</head>
<body>
<div id="diagram">
  <div class="mermaid">
{mermaid_source}
  </div>
</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    flowchart: {{ curve: 'basis', padding: 20 }},
    themeVariables: {{
      primaryColor: '#1e3a5f',
      primaryTextColor: '#e0f0ff',
      primaryBorderColor: '#3b82f6',
      lineColor: '#64748b',
      secondaryColor: '#1e293b',
      tertiaryColor: '#0f172a',
      background: '#0f172a',
    }}
  }});
</script>
</body>
</html>"""
    st.components.v1.html(html, height=height, scrolling=True)


# ---------------------------------------------------------------------------
# Helper — render analysis metadata card
# ---------------------------------------------------------------------------

def _render_analysis_card(meta: dict) -> None:
    repo_name = meta.get("repo_name", "—")
    lang = meta.get("primary_language") or "Unknown"
    langs = meta.get("languages_detected", [])
    total_files = meta.get("total_files", 0)
    total_lines = meta.get("total_lines", 0)
    frameworks = meta.get("detected_frameworks", [])
    deps = meta.get("dependencies", [])
    has_tests = meta.get("has_tests", False)
    has_ci = meta.get("has_ci", False)
    has_docker = meta.get("has_docker", False)
    has_readme = meta.get("has_readme", False)
    env_vars = meta.get("env_vars_referenced", [])

    st.markdown(
        f"""
<div class="card">
  <div class="card-title">📊 Repository Snapshot — {repo_name}</div>
  <div class="metric-row">
    <span class="metric-pill"><b>Primary&nbsp;Lang</b>&nbsp;{lang}</span>
    <span class="metric-pill"><b>Files</b>&nbsp;{total_files:,}</span>
    <span class="metric-pill"><b>Lines</b>&nbsp;{total_lines:,}</span>
    <span class="metric-pill {'green' if has_tests else 'red'}">{'✅' if has_tests else '❌'}&nbsp;Tests</span>
    <span class="metric-pill {'green' if has_ci else 'yellow'}">{'✅' if has_ci else '⚠️'}&nbsp;CI</span>
    <span class="metric-pill {'green' if has_docker else 'yellow'}">{'✅' if has_docker else '⚠️'}&nbsp;Docker</span>
    <span class="metric-pill {'green' if has_readme else 'red'}">{'✅' if has_readme else '❌'}&nbsp;README</span>
  </div>
""",
        unsafe_allow_html=True,
    )

    if langs:
        badges = "".join(f'<span class="badge">{l}</span>' for l in langs)
        st.markdown(
            f'<div style="margin:0.4rem 0 0.2rem"><span style="font-size:0.78rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Languages</span></div>'
            f'<div class="badge-row">{badges}</div>',
            unsafe_allow_html=True,
        )

    if frameworks:
        badges = "".join(f'<span class="badge green">{f}</span>' for f in frameworks)
        st.markdown(
            f'<div style="margin:0.5rem 0 0.2rem"><span style="font-size:0.78rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Frameworks / Tools</span></div>'
            f'<div class="badge-row">{badges}</div>',
            unsafe_allow_html=True,
        )

    if deps:
        top_deps = deps[:12]
        badges = "".join(
            f'<span class="badge gray">{d["name"]}{"@" + d["version"] if d.get("version") else ""}</span>'
            for d in top_deps
        )
        more = f'<span style="font-size:0.78rem;color:#94a3b8"> +{len(deps)-12} more</span>' if len(deps) > 12 else ""
        st.markdown(
            f'<div style="margin:0.5rem 0 0.2rem"><span style="font-size:0.78rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Dependencies ({len(deps)})</span></div>'
            f'<div class="badge-row">{badges}{more}</div>',
            unsafe_allow_html=True,
        )

    if env_vars:
        badges = "".join(f'<span class="badge amber">{v}</span>' for v in env_vars[:15])
        more = f'<span style="font-size:0.78rem;color:#94a3b8"> +{len(env_vars)-15} more</span>' if len(env_vars) > 15 else ""
        st.markdown(
            f'<div style="margin:0.5rem 0 0.2rem"><span style="font-size:0.78rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Env Variables ({len(env_vars)})</span></div>'
            f'<div class="badge-row">{badges}{more}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper — render Good First Issues
# ---------------------------------------------------------------------------

def _render_good_first_issues(data: dict) -> None:
    """Render a GoodFirstIssuesResponse dict as styled task cards."""
    repo_name: str = data.get("repo_name", "")
    tasks: list = data.get("tasks", [])
    model_used: str | None = data.get("model_used")
    token_usage: dict | None = data.get("token_usage")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not tasks:
        st.info("No tasks returned. Try a different repository or LLM provider.")
        return

    # ── Meta bar ────────────────────────────────────────────────────────────
    model_str = f" | Model: **{model_used}**" if model_used else ""
    token_str = ""
    if token_usage:
        t = token_usage.get("total_tokens", 0)
        token_str = f" | Tokens: {t:,}"
    st.markdown(
        f'<div class="export-bar">'
        f'<span><b>{len(tasks)}</b> starter task{"s" if len(tasks) != 1 else ""} for <code>{repo_name}</code></span>'
        f'<span class="timestamp">Generated {generated_at}{model_str}{token_str}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── One card per task ────────────────────────────────────────────────────
    for i, task in enumerate(tasks, 1):
        title: str = task.get("title", f"Task {i}")
        objective: str = task.get("objective", "")
        target: str = task.get("target", "")
        difficulty: str = task.get("difficulty", "beginner").lower()
        steps: list[str] = task.get("steps", [])

        diff_bg, diff_fg = DIFFICULTY_COLOURS.get(difficulty, ("#f1f5f9", "#475569"))
        difficulty_label = difficulty.capitalize()

        steps_html = "".join(f"<li>{s}</li>" for s in steps)

        st.markdown(
            f"""
<div class="gfi-card">
  <div class="gfi-header">
    <div class="gfi-title">#{i} — {title}</div>
    <span class="gfi-badge" style="background:{diff_bg};color:{diff_fg};">{difficulty_label}</span>
  </div>
  <div class="gfi-objective">{objective}</div>
  <div>📁 <span class="gfi-target">{target}</span></div>
  <div class="gfi-steps">
    <div class="gfi-steps-title">Implementation steps</div>
    <ol>{steps_html}</ol>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    # ── Download JSON ────────────────────────────────────────────────────────
    st.markdown("---")
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Good First Issues (.json)",
        data=json_bytes,
        file_name=f"{repo_name}_good_first_issues.json",
        mime="application/json",
    )


# ---------------------------------------------------------------------------
# Helper — render doc output
# ---------------------------------------------------------------------------

def _render_doc_output(response: dict) -> None:
    content: str = response.get("content", "")
    doc_format: str = response.get("doc_format", "markdown")
    sections_generated: list[str] = response.get("sections_generated", [])
    token_usage: dict | None = response.get("token_usage")
    model_used: str | None = response.get("model_used")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Tab layout ──────────────────────────────────────────────────────────
    tab_preview, tab_raw, tab_export = st.tabs(["📄 Preview", "🔤 Raw Source", "💾 Export"])

    with tab_preview:
        st.markdown('<div class="doc-output-container">', unsafe_allow_html=True)

        # Meta bar
        sections_str = " · ".join(SECTION_LABELS.get(s, s) for s in sections_generated)
        model_str = f" | Model: **{model_used}**" if model_used else ""
        token_str = ""
        if token_usage:
            p = token_usage.get("prompt_tokens", 0)
            c = token_usage.get("completion_tokens", 0)
            t = token_usage.get("total_tokens", 0)
            token_str = f" | Tokens: {p:,} prompt / {c:,} completion / {t:,} total"

        st.markdown(
            f'<div class="export-bar">'
            f'<span>Sections: {sections_str}</span>'
            f'<span class="timestamp">Generated {generated_at}{model_str}{token_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if doc_format == "html":
            st.components.v1.html(content, height=700, scrolling=True)
        elif doc_format == "plain":
            st.text(content)
        else:
            st.markdown(content)

        st.markdown("</div>", unsafe_allow_html=True)

    with tab_raw:
        st.code(content, language="markdown" if doc_format == "markdown" else "html" if doc_format == "html" else "text")

    with tab_export:
        st.markdown("### Download the generated documentation")
        col_a, col_b, col_c = st.columns(3)

        # Markdown download
        md_bytes = content.encode("utf-8")
        with col_a:
            st.download_button(
                label="⬇️ Download Markdown (.md)",
                data=md_bytes,
                file_name="onboarding.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # HTML download
        if doc_format == "html":
            html_bytes = content.encode("utf-8")
        else:
            # Wrap markdown in minimal HTML
            html_bytes = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Onboarding Documentation</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1.5rem; color: #1f2328; line-height: 1.7; }}
  pre  {{ background:#f6f8fa; border-radius:6px; padding:1em; overflow-x:auto; }}
  code {{ font-size: 0.88em; }}
  h1,h2,h3 {{ border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3em; }}
</style>
</head>
<body>
<pre style="white-space:pre-wrap">{content.replace("<","&lt;").replace(">","&gt;")}</pre>
</body>
</html>""".encode("utf-8")

        with col_b:
            st.download_button(
                label="⬇️ Download HTML (.html)",
                data=html_bytes,
                file_name="onboarding.html",
                mime="text/html",
                use_container_width=True,
            )

        # JSON payload download
        json_bytes = json.dumps(response, indent=2, ensure_ascii=False).encode("utf-8")
        with col_c:
            st.download_button(
                label="⬇️ Download JSON (.json)",
                data=json_bytes,
                file_name="onboarding_response.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown("#### Copy to Clipboard")
        st.text_area(
            "Full document text (select all → copy)",
            value=content,
            height=250,
            label_visibility="collapsed",
        )


# ---------------------------------------------------------------------------
# Helper — render chat interface
# ---------------------------------------------------------------------------

def _render_chat_interface(doc_content: str, repo_name: str) -> None:
    """Render the 'Chat with your Codebase' UI panel.

    Uses st.session_state.chat_messages as the conversation store so the
    history persists across Streamlit reruns within the same session.

    Follows the deferred-dispatch pattern: on submit the question and params
    are stored in queued_task/queued_params, then st.rerun() is called so
    _run_queued_task() executes the HTTP call on the next rerun with all
    widgets already locked.
    """
    st.markdown(
        "Ask questions about the repository architecture, setup, or code and get "
        "instant, context-aware answers powered by the LLM you selected.",
        help="Answers are grounded in the generated documentation for this repo.",
    )

    _locked = st.session_state.is_running

    # ── Clear button ─────────────────────────────────────────────────────────
    col_hdr, col_clr = st.columns([4, 1])
    with col_hdr:
        st.markdown(
            f'<div style="font-size:0.82rem;color:#64748b;">Conversation for '
            f'<code>{repo_name}</code></div>',
            unsafe_allow_html=True,
        )
    with col_clr:
        if st.button("🗑 Clear", key="chat_clear_btn", use_container_width=True,
                     disabled=_locked):
            st.session_state.chat_messages = []
            st.rerun()

    # ── Render existing messages ──────────────────────────────────────────────
    messages: list[dict] = st.session_state.chat_messages
    if messages:
        bubbles_html = '<div class="chat-container">'
        for msg in messages:
            role = msg["role"]
            content_escaped = (
                msg["content"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            label = "You" if role == "user" else "Assistant"
            bubbles_html += (
                f'<div style="display:flex;flex-direction:column;'
                f'align-items:{"flex-end" if role == "user" else "flex-start"};">'
                f'<div class="chat-meta">{label}</div>'
                f'<div class="chat-bubble {role}">{content_escaped}</div>'
                f"</div>"
            )
        bubbles_html += "</div>"
        st.markdown(bubbles_html, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="chat-empty">💬 No messages yet — ask your first question below!</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form(key="chat_input_form", clear_on_submit=True):
        user_input = st.text_area(
            "Your question",
            placeholder=(
                "e.g. How do I run the tests? "
                "What does the repo_analyzer module do? "
                "How do I add a new API endpoint?"
            ),
            height=80,
            label_visibility="collapsed",
            disabled=_locked,
        )
        submitted = st.form_submit_button(
            "➤ Send",
            use_container_width=True,
            type="primary",
            disabled=_locked,
        )

    if submitted and user_input.strip() and not _locked:
        question = user_input.strip()
        # Optimistically append user message so it shows immediately
        st.session_state.chat_messages.append({"role": "user", "content": question})
        # Queue the chat task — _run_queued_task() will execute it on next rerun
        st.session_state.queued_task = "Chat"
        st.session_state.queued_params = {
            "question":   question,
            "doc_content": doc_content,
            "repo_name":  repo_name,
            "provider":   st.session_state.get("llm_provider", "groq"),
            "api_base":   st.session_state.api_base,
            "key":        st.session_state.get("groq_api_key_widget", ""),
            "history": [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.chat_messages[:-1]  # exclude the just-appended msg
            ],
        }
        st.rerun()


# ---------------------------------------------------------------------------
# Run any queued task BEFORE any widget is rendered on this rerun.
# All helper functions are now defined above, so this call is safe.
# If a task is queued, _run_queued_task() sets is_running=True, renders
# a locked sidebar, executes the HTTP call, clears state, and calls
# st.rerun() — so the rest of this script only executes when idle.
# ---------------------------------------------------------------------------

_run_queued_task()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🚀 Onboarding Assistant")
    st.markdown("---")

    # ── Groq API Key ─────────────────────────────────────────────────────────
    # Use key= as the sole source of truth.  Do NOT pass value= here — that
    # dual-binding fights browser password managers and causes stray autofill
    # text to appear when the field is focused while empty.
    #
    # Lock source: is_running is True for the ENTIRE task-execution rerun,
    # set at the very top of the script by _run_queued_task() before any
    # widget renders.  This is the only correct lock source.
    _sb_locked = st.session_state.is_running

    st.markdown("### 🔑 Groq API Key")
    st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_...",
        help="Your Groq API key. Required when LLM Provider is set to Groq. "
             "Sent to the backend via a request header — never stored persistently.",
        key="groq_api_key_widget",
        label_visibility="collapsed",
        disabled=_sb_locked,
    )
    _groq_key_set = bool(st.session_state.get("groq_api_key_widget", ""))
    if _groq_key_set:
        st.markdown(
            '<span style="color:#16a34a;font-size:0.82rem;">✔ Key provided</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span style="color:#94a3b8;font-size:0.82rem;">No key — use Mock provider to skip</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── API Server ──────────────────────────────────────────────────────────
    st.markdown("### 🔌 API Server")
    api_base = st.text_input(
        "Base URL",
        value=st.session_state.api_base,
        placeholder="http://localhost:8000",
        help="URL of the running FastAPI backend.",
        disabled=_sb_locked,
    )
    if not _sb_locked:
        st.session_state.api_base = api_base.rstrip("/")

    check_col, status_col = st.columns([1, 2])
    with check_col:
        if st.button("Check", use_container_width=True, disabled=_sb_locked):
            st.session_state.api_healthy = _check_health(st.session_state.api_base)
    with status_col:
        if st.session_state.api_healthy is True:
            st.markdown('<span class="status-ok">● Online</span>', unsafe_allow_html=True)
        elif st.session_state.api_healthy is False:
            st.markdown('<span class="status-fail">● Offline</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:#94a3b8">● Not checked</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Repository Source ────────────────────────────────────────────────────
    st.markdown("### 📁 Repository Source")
    source = st.selectbox(
        "Source type",
        options=["local", "github"],
        format_func=lambda s: "🖥️ Local Path" if s == "local" else "🐙 GitHub URL",
        key="source",
        disabled=_sb_locked,
    )

    if source == "local":
        local_path = st.text_input(
            "Local Path",
            value="",
            placeholder="/home/dev/my-project",
            help="Absolute path to a local repository on the server's filesystem.",
            key="local_path",
            disabled=_sb_locked,
        )
        github_url = ""
        branch = "main"
    else:
        github_url = st.text_input(
            "GitHub URL",
            value="",
            placeholder="https://github.com/owner/repo",
            help="HTTPS clone URL of the GitHub repository.",
            key="github_url",
            disabled=_sb_locked,
        )
        branch = st.text_input("Branch", value="main", key="branch", disabled=_sb_locked)
        local_path = ""

    max_file_size_kb = st.slider(
        "Max file size (KB)",
        min_value=10,
        max_value=2048,
        value=100,
        step=10,
        help="Files larger than this will be skipped during analysis.",
        key="max_file_size_kb",
        disabled=_sb_locked,
    )

    st.markdown("---")

    # ── Documentation Options ────────────────────────────────────────────────
    st.markdown("### 📝 Documentation Options")

    doc_format = st.selectbox(
        "Output format",
        options=["markdown", "html", "plain"],
        format_func=lambda f: {"markdown": "📝 Markdown", "html": "🌐 HTML", "plain": "📄 Plain Text"}[f],
        key="doc_format",
        disabled=_sb_locked,
    )

    llm_provider = st.selectbox(
        "LLM Provider",
        options=["groq", "openai", "mock"],
        format_func=lambda p: {"groq": "⚡ Groq", "openai": "🤖 OpenAI", "mock": "🎭 Mock (no API key)"}[p],
        key="llm_provider",
        help="'Mock' generates template-based docs without an API key.",
        disabled=_sb_locked,
    )

    audience = st.text_input(
        "Target audience",
        value="junior developer",
        help="Influences the tone and detail level of the generated docs.",
        key="audience",
        disabled=_sb_locked,
    )

    st.markdown("---")

    # ── Sections ─────────────────────────────────────────────────────────────
    st.markdown("### 🗂️ Sections to Include")
    selected_sections = []
    for sec in ALL_SECTIONS:
        if st.checkbox(SECTION_LABELS[sec], value=True, key=f"sec_{sec}", disabled=_sb_locked):
            selected_sections.append(sec)

    st.markdown("---")

    # ── Generate button ──────────────────────────────────────────────────────
    # _sb_locked == is_running, already set above.
    generate_disabled = len(selected_sections) == 0 or _sb_locked
    _generate_help = (
        "At least one section must be selected." if len(selected_sections) == 0
        else f"Task in progress: {st.session_state.queued_task} — please wait." if _sb_locked
        else ""
    )
    generate_btn = st.button(
        "🚀 Generate Onboarding Docs",
        type="primary",
        use_container_width=True,
        disabled=generate_disabled,
        help=_generate_help,
    )

    if len(selected_sections) == 0:
        st.warning("Select at least one section above.")

    st.markdown("---")

    # ── Good First Issues button ──────────────────────────────────────────────
    st.markdown("### 🎯 Good First Issues")
    st.markdown(
        '<span style="font-size:0.8rem;color:#94a3b8;">'
        "Generate tailored starter tasks for a new developer. "
        "Uses the selected LLM Provider above."
        "</span>",
        unsafe_allow_html=True,
    )
    gfi_num_tasks = st.slider(
        "Number of tasks",
        min_value=1,
        max_value=6,
        value=3,
        step=1,
        help="How many Good First Issues to generate.",
        key="gfi_num_tasks",
        disabled=_sb_locked,
    )
    gfi_btn = st.button(
        "🎯 Generate Good First Issues",
        use_container_width=True,
        disabled=_sb_locked,
        help="Scans the repository and suggests beginner-friendly contribution tasks.",
    )

    st.markdown("---")

    # ── Architecture Diagram button ───────────────────────────────────────────
    st.markdown("### 🏗️ Architecture Diagram")
    st.markdown(
        '<span style="font-size:0.8rem;color:#94a3b8;">'
        "Visualise system structure without generating docs. "
        "No API key required."
        "</span>",
        unsafe_allow_html=True,
    )
    arch_btn = st.button(
        "🗺️ Generate Architecture Diagram",
        use_container_width=True,
        disabled=_sb_locked,
        help="Scans the repository and builds a Mermaid.js flowchart — no LLM needed.",
    )

    st.markdown("---")

    # ── Chat with your Codebase ───────────────────────────────────────────────
    st.markdown("### 💬 Chat with your Codebase")
    st.markdown(
        '<span style="font-size:0.8rem;color:#94a3b8;">'
        "After generating documentation, switch to the "
        "<b>💬 Chat with Codebase</b> tab in the main panel to ask questions "
        "about architecture, setup, or code. Requires your Groq API key above."
        "</span>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("chat_messages"):
        num_msgs = len(st.session_state.chat_messages)
        st.markdown(
            f'<span style="font-size:0.8rem;color:#16a34a;">✔ {num_msgs} message{"s" if num_msgs != 1 else ""} in current session</span>',
            unsafe_allow_html=True,
        )
        if st.button("🗑 Clear Chat History", use_container_width=True, key="sidebar_chat_clear",
                     disabled=_sb_locked):
            st.session_state.chat_messages = []
            st.rerun()

# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------

st.markdown(
    """
<div class="header-banner">
  <h1>🚀 Smart Developer Onboarding Assistant</h1>
  <p>AI-powered setup documentation generator for any code repository — local or GitHub.</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Resolve the Groq API key from the widget (single source of truth) ─────────
_groq_api_key: str = st.session_state.get("groq_api_key_widget", "") or ""

# ── Button handlers — queue a task and immediately rerun ──────────────────────
# These blocks run on the BUTTON-CLICK rerun.  They do NOT make HTTP calls.
# They snapshot all form values, write them into queued_task / queued_params,
# and call st.rerun().  On the next rerun _run_queued_task() (called at the
# very top of the script) picks them up, locks the UI, executes, and reruns
# again to show results.  This guarantees the buttons are always rendered with
# disabled=is_running=True during the execution rerun.

if generate_btn:
    if source == "local" and not local_path.strip():
        st.error("⚠️ Please provide a **local path** in the sidebar.")
    elif source == "github" and not github_url.strip():
        st.error("⚠️ Please provide a **GitHub URL** in the sidebar.")
    elif not selected_sections:
        st.error("⚠️ Select at least one documentation section in the sidebar.")
    else:
        _src       = source
        _lp        = local_path.strip()
        _gu        = github_url.strip()
        _br        = branch
        _kb        = max_file_size_kb
        _fmt       = doc_format
        _prov      = llm_provider
        _aud       = audience
        _secs      = list(selected_sections)
        _base      = st.session_state.api_base
        _key       = _groq_api_key
        _repo_lbl  = _lp if _src == "local" else _gu
        _payload   = _build_payload(
            source=_src, local_path=_lp, github_url=_gu, branch=_br,
            max_file_size_kb=_kb, doc_format=_fmt, llm_provider=_prov,
            audience=_aud, sections=_secs,
        )
        st.session_state.last_request      = _payload
        st.session_state.arch_diagram      = None   # clear stale sibling results
        st.session_state.good_first_issues = None
        st.session_state.queued_task   = "Generating docs"
        st.session_state.queued_params = {
            "api_base":   _base,
            "key":        _key,
            "repo_label": _repo_lbl,
            "payload":    _payload,
            "format":     _fmt,
            "provider":   _prov,
            "sections":   _secs,
        }
        st.rerun()

if gfi_btn:
    if source == "local" and not local_path.strip():
        st.error("⚠️ Please provide a **local path** in the sidebar.")
    elif source == "github" and not github_url.strip():
        st.error("⚠️ Please provide a **GitHub URL** in the sidebar.")
    else:
        _src      = source
        _lp       = local_path.strip()
        _gu       = github_url.strip()
        _br       = branch
        _kb       = max_file_size_kb
        _prov     = llm_provider
        _aud      = audience
        _num      = gfi_num_tasks
        _base     = st.session_state.api_base
        _key      = _groq_api_key
        _repo_lbl = _lp if _src == "local" else _gu
        _analysis_payload = _build_analysis_payload(
            source=_src, local_path=_lp, github_url=_gu,
            branch=_br, max_file_size_kb=_kb,
        )
        st.session_state.good_first_issues = None
        st.session_state.queued_task   = "Generating Good First Issues"
        st.session_state.queued_params = {
            "api_base":        _base,
            "key":             _key,
            "repo_label":      _repo_lbl,
            "analysis_payload": _analysis_payload,
            "provider":        _prov,
            "audience":        _aud,
            "num_tasks":       _num,
        }
        st.rerun()

if arch_btn:
    if source == "local" and not local_path.strip():
        st.error("⚠️ Please provide a **local path** in the sidebar.")
    elif source == "github" and not github_url.strip():
        st.error("⚠️ Please provide a **GitHub URL** in the sidebar.")
    else:
        _src      = source
        _lp       = local_path.strip()
        _gu       = github_url.strip()
        _br       = branch
        _kb       = max_file_size_kb
        _base     = st.session_state.api_base
        _repo_lbl = _lp if _src == "local" else _gu
        _arch_payload = _build_analysis_payload(
            source=_src, local_path=_lp, github_url=_gu,
            branch=_br, max_file_size_kb=_kb,
        )
        st.session_state.arch_diagram  = None
        st.session_state.queued_task   = "Generating architecture diagram"
        st.session_state.queued_params = {
            "api_base":     _base,
            "repo_label":   _repo_lbl,
            "arch_payload": _arch_payload,
        }
        st.rerun()

# ---------------------------------------------------------------------------
# Results area
# ---------------------------------------------------------------------------
if st.session_state.result:
    response = st.session_state.result
    content: str = response.get("content", "")
    sections_generated: list = response.get("sections_generated", [])
    model_used: str | None = response.get("model_used")
    token_usage: dict | None = response.get("token_usage")

    # ── Summary strip ────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sections", len(sections_generated))
    col2.metric("Characters", f"{len(content):,}")
    if token_usage:
        col3.metric("Total Tokens", f"{token_usage.get('total_tokens', 0):,}")
    else:
        col3.metric("Total Tokens", "—")
    col4.metric("LLM Model", model_used or "—")

    st.markdown("---")

    # ── Tabbed output: docs + good first issues + architecture diagram + chat ─
    tab_docs, tab_gfi, tab_arch, tab_chat = st.tabs(
        ["📄 Documentation", "🎯 Good First Issues", "🏗️ Architecture Diagram", "💬 Chat with Codebase"]
    )

    with tab_docs:
        _render_doc_output(response)

    with tab_gfi:
        gfi_data = st.session_state.good_first_issues
        if gfi_data:
            _render_good_first_issues(gfi_data)
        else:
            st.info(
                "Good First Issues not yet generated.  \n"
                "Click **🎯 Generate Good First Issues** in the sidebar to create "
                "tailored starter tasks — uses the selected LLM Provider."
            )

    with tab_arch:
        arch_data = st.session_state.arch_diagram
        if arch_data:
            mermaid_src: str = arch_data.get("mermaid_source", "")
            repo_nm: str = arch_data.get("repo_name", "")
            st.markdown(
                f'<div class="card-title" style="margin-bottom:0.5rem;">System Architecture — '
                f'<code>{repo_nm}</code></div>',
                unsafe_allow_html=True,
            )
            _render_mermaid(mermaid_src, height=560)
            with st.expander("🔤 Mermaid Source", expanded=False):
                st.code(mermaid_src, language="text")
                st.download_button(
                    label="⬇️ Download Mermaid (.mmd)",
                    data=mermaid_src.encode("utf-8"),
                    file_name=f"{repo_nm}_architecture.mmd",
                    mime="text/plain",
                    use_container_width=True,
                )
        else:
            st.info(
                "Architecture diagram not yet generated.  \n"
                "Click **🗺️ Generate Architecture Diagram** in the sidebar to build it "
                "— no API key required."
            )

    with tab_chat:
        st.markdown("### 💬 Chat with your Codebase")
        _chat_repo_name = response.get("repo_name", "") or st.session_state.get("last_request", {}).get(
            "github_url", st.session_state.get("last_request", {}).get("path", "")
        )
        _render_chat_interface(doc_content=content, repo_name=_chat_repo_name)

# ── Standalone panels (when no docs result yet) ───────────────────────────────
elif (st.session_state.arch_diagram or st.session_state.good_first_issues) and not generate_btn:
    # Show whichever standalone results are available as tabs
    available_tabs: list[str] = []
    if st.session_state.good_first_issues:
        available_tabs.append("🎯 Good First Issues")
    if st.session_state.arch_diagram:
        available_tabs.append("🏗️ Architecture Diagram")

    standalone_tabs = st.tabs(available_tabs)
    tab_idx = 0

    if st.session_state.good_first_issues:
        with standalone_tabs[tab_idx]:
            gfi_data = st.session_state.good_first_issues
            repo_nm_gfi = gfi_data.get("repo_name", "")
            st.markdown(f"### 🎯 Good First Issues — `{repo_nm_gfi}`")
            st.caption("AI-generated starter tasks. Generate full docs with the sidebar button above.")
            _render_good_first_issues(gfi_data)
        tab_idx += 1

    if st.session_state.arch_diagram:
        with standalone_tabs[tab_idx]:
            arch_data = st.session_state.arch_diagram
            mermaid_src = arch_data.get("mermaid_source", "")
            repo_nm = arch_data.get("repo_name", "")
            st.markdown(f"### 🏗️ System Architecture — `{repo_nm}`")
            st.caption("Static analysis diagram — no LLM required. Generate full docs with the sidebar button above.")
            _render_mermaid(mermaid_src, height=560)
            with st.expander("🔤 Mermaid Source", expanded=False):
                st.code(mermaid_src, language="text")
                st.download_button(
                    label="⬇️ Download Mermaid (.mmd)",
                    data=mermaid_src.encode("utf-8"),
                    file_name=f"{repo_nm}_architecture.mmd",
                    mime="text/plain",
                )

# ── Chat-only standalone panel (when docs were generated in a prior run but result was cleared) ──
# This condition is never hit since result is cleared only by new generate button presses.
# The chat tab lives inside the main `if st.session_state.result` block above.

elif not generate_btn and not arch_btn and not gfi_btn:
    # ── Empty state ───────────────────────────────────────────────────────────
    st.markdown(
        """
<div class="card" style="text-align:center; padding:3rem 2rem;">
  <div style="font-size:3.5rem; margin-bottom:1rem;">📋</div>
  <div style="font-size:1.15rem; font-weight:600; color:#1e293b; margin-bottom:0.5rem;">No documentation generated yet</div>
  <div style="color:#64748b; font-size:0.95rem;">Configure a repository in the sidebar and click <b>Generate Onboarding Docs</b>, <b>Generate Good First Issues</b>, or <b>Generate Architecture Diagram</b> to get started. Then use the <b>💬 Chat with Codebase</b> tab to ask questions about the repo.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Quick-start guide ────────────────────────────────────────────────────
    with st.expander("📖 Quick-start guide", expanded=True):
        st.markdown(
            """
**1. Start both servers with a single command**
```bash
cd smart-onboarding-assistant
python run.py
# FastAPI  → http://localhost:8000/docs
# Streamlit → http://localhost:8501
```
> Or start them separately:
> ```bash
> python main.py          # FastAPI backend
> streamlit run frontend/app.py   # Streamlit UI
> ```

**2. Enter your Groq API key** *(top of sidebar)*
- Paste your key (starts with `gsk_`) — it is sent securely per-request and never saved to disk.
- No `.env` file needed. Use **Mock** provider to skip the key entirely.

**3. Configure a repository** *(sidebar)*
- Choose **Local Path** for a repo already on disk, or **GitHub URL** to clone on-the-fly.
- Pick your **LLM Provider** — **Groq** for AI-generated docs, **Mock** for instant template docs.
- Adjust sections and target audience as needed.

**4. Click "Generate Onboarding Docs"**
- The assistant analyses the repository structure, detects languages, frameworks, and dependencies, then produces tailored setup documentation.

**5. Generate Good First Issues** *(new!)*
- Click **🎯 Generate Good First Issues** in the sidebar to get tailored starter tasks for a new developer.
- Each task includes a title, objective, target file, difficulty badge, and step-by-step instructions.
- Uses the selected LLM Provider (or Mock for instant template-based tasks — no API key needed).

**6. View the Architecture Diagram**
- Click **🗺️ Generate Architecture Diagram** (bottom of sidebar) for an instant Mermaid.js flowchart — no API key needed.
- After generating docs, switch to the **🏗️ Architecture Diagram** tab in the results area.

**7. Chat with your Codebase** *(Feature 3)*
- After generating documentation, open the **💬 Chat with Codebase** tab in the results area.
- Ask natural-language questions such as: *"How do I run the tests?"*, *"What does the repo_analyzer module do?"*, or *"How do I add a new API endpoint?"*
- The LLM answers using the generated documentation as context — no extra API calls to analyse the repo.
- Conversation history is preserved across questions within the same session. Use **🗑 Clear** to start fresh.

**8. Export**
- Download docs as `.md`, `.html`, or `.json` from the **Export** tab.
- Download Good First Issues as `.json`.
- Download the Mermaid diagram source as `.mmd` for use in any compatible tool.
"""
        )

# ---------------------------------------------------------------------------
# Sidebar — history panel (below the fold)
# ---------------------------------------------------------------------------
if st.session_state.history:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🕑 Session History")
        for i, h in enumerate(reversed(st.session_state.history[-8:]), 1):
            st.markdown(
                f"**{i}.** `{h['timestamp']}` — {h['repo'][:30]}{'…' if len(h['repo']) > 30 else ''}  \n"
                f"Format: {h['format']} · Provider: {h['provider']} · {h['sections']} sections · {h['elapsed_s']}s"
            )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    """
<hr style="margin-top:3rem">
<p style="text-align:center; font-size:0.75rem; color:#94a3b8;">
  Smart Developer Onboarding Assistant &nbsp;·&nbsp; IBM BOB 2.0 Hackathon &nbsp;·&nbsp;
  Powered by FastAPI &amp; Streamlit
</p>
""",
    unsafe_allow_html=True,
)
