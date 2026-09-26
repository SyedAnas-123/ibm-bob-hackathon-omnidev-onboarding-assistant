<div align="center">

# OmniDev — User & Testing Guide

### Enterprise AI Developer Onboarding Platform

*From zero context to productive contributor — in under two minutes.*

</div>

---

## Table of Contents

1. [Project Overview & Vision](#1-project-overview--vision)
2. [UI Architecture & Design Philosophy](#2-ui-architecture--design-philosophy)
3. [Feature Deep-Dive](#3-feature-deep-dive)
   - [Documentation Tab](#31-documentation-tab)
   - [Architecture Tab](#32-architecture-tab)
   - [Good First Issues Tab](#33-good-first-issues-tab)
   - [Chat Tab](#34-chat-tab)
4. [Prerequisites](#4-prerequisites)
5. [Cloning & Environment Setup](#5-cloning--environment-setup)
   - [Clone the repository](#51-clone-the-repository)
   - [Create the virtual environment](#52-create-the-virtual-environment)
   - [Install dependencies](#53-install-dependencies)
   - [Configure your Groq API key](#54-configure-your-groq-api-key)
6. [Running the Application](#6-running-the-application)
7. [Testing the Dashboard — Walkthrough](#7-testing-the-dashboard--walkthrough)
   - [Health check verification](#71-health-check-verification)
   - [Testing with a GitHub repository](#72-testing-with-a-github-repository)
   - [Testing with a local repository](#73-testing-with-a-local-repository)
   - [Verifying error handling & toast notifications](#74-verifying-error-handling--toast-notifications)
8. [API Endpoint Reference](#8-api-endpoint-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Project Overview & Vision

Developer onboarding is one of the most expensive, repetitive, and error-prone processes in software engineering. The average new contributor spends **3–5 days** just orientating themselves in an unfamiliar codebase before writing a single meaningful line of code. Tribal knowledge locked inside engineers' heads, outdated READMEs, and the absence of curated starting points are the root cause.

**OmniDev** eliminates this bottleneck entirely.

Point OmniDev at any Git repository — a GitHub URL or a local path — and it automatically:

- **Analyses** the codebase statically (languages, frameworks, dependencies, entry points, environment variables, CI/Docker configuration) without ever sending your source code to an LLM.
- **Generates** a structured, multi-section onboarding document in Markdown, HTML, or plain text, using Groq or OpenAI as the LLM backbone.
- **Renders** an interactive Mermaid.js architecture diagram that visualises the system's layers, entry points, tech stack, and infrastructure.
- **Produces** a curated list of Good First Issues — real, targeted starter tasks mapped directly to the repo's actual files — with difficulty-rated badges.
- **Answers** follow-up questions through a context-grounded RAG (retrieval-augmented generation) chat interface that maintains conversation history.

> **Hackathon note:** OmniDev was built to demonstrate that enterprise-grade developer tooling — the kind normally requiring months of engineering — can be assembled rapidly when a strong architecture is in place. Every part of the system (API design, LLM integration, frontend, error handling) is production-ready.

---

## 2. UI Architecture & Design Philosophy

OmniDev's frontend is a single-page application served directly by FastAPI at `/`. It follows a **Google Cloud Console / n8n workflow editor** design language:

| Design Decision | Rationale |
|---|---|
| Deep obsidian dark theme (`#04060b` void black) | Reduces cognitive fatigue during extended sessions; standard for enterprise dev tooling |
| Google Cloud Blue (`#1a73e8`) as primary accent | Immediate visual trust signal; consistent with industry-leading developer consoles |
| Ambient radial glow animations | Adds depth without distraction; signals "AI-powered" at a glance |
| Inter typeface + JetBrains Mono for code | The exact combination used by Linear, Vercel, and other best-in-class SaaS products |
| Fixed sidebar + tabbed main panel layout | Mirrors VS Code / Google Cloud Console; users know exactly where controls live |
| Toast notification system with persistence on critical errors | Ensures auth and API failures are never silently swallowed |

The layout is structured as three zones:

```
┌─────────────────────────────────────────────────────────────────┐
│  TOPBAR  — OmniDev logo · breadcrumb · version badge · status   │
├───────────────────┬─────────────────────────────────────────────┤
│                   │  TAB BAR  — Documentation · Architecture ·  │
│  SIDEBAR          │           Good First Issues · Chat          │
│                   ├─────────────────────────────────────────────┤
│  • Groq API Key   │                                             │
│  • Server URL     │  CONTENT PANEL                              │
│  • Health check   │  (tab-specific output area)                 │
│  • Repository     │                                             │
│    source config  │                                             │
│  • Doc settings   │                                             │
│  • Action button  │                                             │
│                   │                                             │
└───────────────────┴─────────────────────────────────────────────┘
```

---

## 3. Feature Deep-Dive

### 3.1 Documentation Tab

**What it does:** Performs a full repository analysis followed by LLM-powered documentation generation in a single pipeline call (`POST /api/v1/onboarding/full-pipeline`).

**Output sections (all configurable):**

| Section | Content |
|---|---|
| `overview` | What the project does, its purpose, primary language |
| `prerequisites` | Runtime versions, system dependencies, API keys needed |
| `installation` | Step-by-step setup from clone to running |
| `environment_setup` | Every env var the repo references, with explanations |
| `running_locally` | Exact commands to start the server/app |
| `testing` | How to run the test suite, what frameworks are used |
| `project_structure` | Annotated directory tree of the key files |
| `contributing` | Branch conventions, PR guidelines, code style |

**Output formats:**
- **Markdown** — rendered live in the browser with `marked.js`; switch between Preview and Raw tabs
- **HTML** — ready to embed in internal wikis or Confluence
- **Plain text** — for CI pipelines or terminal output

**Export:** A Download button appears after generation, allowing you to save the documentation file locally.

**Audience targeting:** The `Audience` field in the sidebar adjusts the LLM's tone and detail level — a `senior engineer` gets terse, assumption-heavy output, while a `junior developer` gets verbose, hand-held steps.

---

### 3.2 Architecture Tab

**What it does:** Analyses a repository and returns a Mermaid.js `flowchart TD` diagram, then renders it live in the browser using Mermaid's JavaScript runtime.

The diagram automatically captures:

- **Entry points** — detected `main.py`, `index.js`, `App.java`, `cmd/` directories, etc.
- **Source layers** — top-level directories (`src/`, `app/`, `lib/`, `api/`, etc.) shown as grouped subgraphs
- **Frameworks** — detected frameworks (FastAPI, Django, React, Spring, etc.) overlaid as decorator nodes
- **Dependencies** — ecosystem registries (`pip`, `npm`, `maven`) shown as external dependency nodes
- **Infrastructure** — Docker, CI/CD, and test suite nodes when detected

**Why this matters:** Architecture diagrams are the single highest-value onboarding artefact — they give a new developer a mental model of the system in under 30 seconds. OmniDev generates them automatically from static analysis alone, requiring no manual diagramming.

**Interactive rendering:** The diagram is rendered as an SVG inside the browser. You can zoom and pan without any additional tools. The raw Mermaid source is also displayed below for copy/paste into any Mermaid-compatible viewer (GitHub, Notion, GitLab).

---

### 3.3 Good First Issues Tab

**What it does:** Analyses the repository, then calls the LLM to generate 1–6 curated starter tasks specifically tailored to the repo's actual codebase — referencing real file paths, not generic advice.

**Each task card contains:**

| Field | Description |
|---|---|
| **Title** | Short imperative task name (e.g. "Add input validation to the registration endpoint") |
| **Difficulty badge** | `Beginner` (green) · `Intermediate` (amber) · `Advanced` (red) — dynamically assigned by the LLM |
| **Objective** | 1–2 sentences explaining what the task achieves and why it matters |
| **Target** | The exact file or directory the developer should edit |
| **Steps** | Numbered, concrete implementation instructions |

**Why this is better than GitHub Issues:** Traditional "good first issues" are manually curated, often stale, and disconnected from the codebase's current structure. OmniDev generates them fresh from the live repository state on every run.

**Configurable task count:** The sidebar slider lets you request 1–6 tasks. Three is the default — enough to give a new developer options without overwhelming them.

---

### 3.4 Chat Tab

**What it does:** Provides a context-grounded Q&A interface where developers can ask questions about the repository in natural language. The LLM is given the generated documentation as its primary source of truth, ensuring answers are grounded in the actual codebase rather than hallucinated.

**Key characteristics:**

- **RAG pattern:** Up to 12,000 characters of the generated documentation are injected into the system prompt as context.
- **Conversation memory:** Up to 10 previous turns are included in each request, enabling coherent multi-turn dialogues.
- **Context framing:** The model is told it is an expert assistant for the specific repository — not a general-purpose chatbot.
- **Fallback honesty:** The system prompt instructs the model to say "I don't know" when the answer isn't covered by the documentation, rather than hallucinating.

**Typical use cases:**
- *"What environment variables does this project need?"*
- *"How do I run the test suite?"*
- *"What does the `repo_analyzer.py` service do?"*
- *"Which framework does this project use for HTTP routing?"*

> **To use Chat:** Generate documentation first (Documentation tab). Chat is automatically loaded with that documentation as context.

---

## 4. Prerequisites

Before setting up OmniDev, ensure the following are installed on your machine:

| Requirement | Version | Check Command | Download |
|---|---|---|---|
| Python | 3.11 or newer | `python --version` | [python.org](https://www.python.org/downloads/) |
| Git | Any recent version | `git --version` | [git-scm.com](https://git-scm.com/) |
| Groq API key | — | — | [console.groq.com/keys](https://console.groq.com/keys) (free tier) |

> **No API key?** OmniDev ships with a `mock` provider that generates deterministic, template-based documentation entirely offline. You can test the full UI flow without any API key — just set `LLM Provider` to `mock` in the sidebar.

---

## 5. Cloning & Environment Setup

### 5.1 Clone the repository

```bash
git clone https://github.com/your-org/omnidev.git
cd omnidev/smart-onboarding-assistant
```

### 5.2 Create the virtual environment

It is strongly recommended to isolate OmniDev's dependencies in a virtual environment to avoid conflicts with other Python projects on your machine.

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows — Command Prompt
python -m venv venv
venv\Scripts\activate.bat

# Windows — PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

When activated, your terminal prompt will be prefixed with `(venv)`, confirming isolation is active.

### 5.3 Install dependencies

```bash
pip install -r requirements.txt
```

This installs the nine direct production dependencies and their transitive requirements. Expected install time: **30–90 seconds** on a standard internet connection.

You can verify the key packages are present:

```bash
pip show fastapi uvicorn openai pydantic gitpython
```

### 5.4 Configure your Groq API key

No configuration files needed. The Groq API key is entered directly in the **sidebar** of the web interface — no `.env` file required.

1. Get a free key at [console.groq.com/keys](https://console.groq.com/keys).
2. Start the server (see Section 6).
3. Open `http://127.0.0.1:8000/` in your browser.
4. In the **Groq API Key** field in the left sidebar, paste your key (`gsk_...`). The label changes to **✓ Key set**.

The key travels to the backend as the `X-Groq-Api-Key` HTTP request header on every API call — it is **never written to disk** and does not require a server restart.

> **No key?** Set **LLM Provider** to `mock` in the sidebar. Every feature — docs, diagrams, Good First Issues, and chat — works offline with deterministic template output. No API key required.

---

## 6. Running the Application

From inside `smart-onboarding-assistant/` (with your virtual environment active):

```bash
python run.py
```

You will see:

```
══════════════════════════════════════════════════════════════
  Smart Developer Onboarding Assistant
══════════════════════════════════════════════════════════════
  App  (UI)  ->  http://127.0.0.1:8000/
  API  docs  ->  http://127.0.0.1:8000/docs
══════════════════════════════════════════════════════════════
  Press Ctrl-C to stop.

[API] INFO:     Started server process [...]
[API] INFO:     Application startup complete.
[API] INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open **`http://127.0.0.1:8000/`** in your browser. The enterprise UI loads immediately — no separate frontend server is required.

**Alternative launch commands:**

```bash
# Invoke uvicorn directly (with hot-reload for development)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Or run main.py directly
python main.py
```

**Stopping the server:** Press `Ctrl-C` in the terminal. `run.py` handles graceful shutdown automatically on all platforms.

---

## 7. Testing the Dashboard — Walkthrough

### 7.1 Health check verification

Before running any analysis, confirm the backend is reachable:

1. In the **sidebar**, locate the **Backend** section.
2. Confirm the Server URL is `http://localhost:8000` (or `http://127.0.0.1:8000`).
3. Click **Check Health**.
4. The indicator should turn **green** and display **Online**.

You can also verify directly in your browser or terminal:

```bash
curl http://127.0.0.1:8000/health
# Expected: {"status":"ok","version":"0.1.0"}
```

---

### 7.2 Testing with a GitHub repository

This is the most common and most impressive demo flow.

**Step 1 — Set your Groq API key**

In the sidebar under **Groq API Key**, paste your key (`gsk_...`). The label changes to **Key set** with a green checkmark. The key is sent per-request via the `X-Groq-Api-Key` header; it is never stored server-side.

**Step 2 — Select a repository**

1. Under **Repository**, click the **GitHub** toggle.
2. Paste a repository URL into the **Repository URL** field. Good public repos for testing:

   | Repository | Why it's a good test |
   |---|---|
   | `https://github.com/tiangolo/fastapi` | Python · well-structured · large codebase |
   | `https://github.com/expressjs/express` | JavaScript · Node.js framework |
   | `https://github.com/pallets/flask` | Python · minimal structure |
   | `https://github.com/vercel/next.js` | TypeScript · monorepo · complex |

3. Set **Branch** to `main` or `master` depending on the repository.
4. Leave **Max file size** at `100 KB` (the default is appropriate for most repos).

**Step 3 — Generate documentation**

1. Ensure you are on the **Documentation** tab.
2. In the sidebar under **Documentation**, set:
   - **LLM Provider** → `groq`
   - **Audience** → `junior developer`
   - **Format** → `markdown`
3. Click **Generate Onboarding Docs**.
4. The status banner changes to **Analysing repository…**, then **Generating documentation with LLM…**
5. After 15–60 seconds (depending on repo size), the documentation renders in the main panel.

**Step 4 — Explore the Architecture diagram**

1. Switch to the **Architecture** tab.
2. Click **Generate Diagram**.
3. The Mermaid.js flowchart renders as an interactive SVG. Verify:
   - Entry points appear at the top of the graph.
   - Source layers and frameworks appear as intermediate nodes.
   - Infrastructure nodes (Docker, CI, Tests) appear when present in the repo.

**Step 5 — Generate Good First Issues**

1. Switch to the **Good First Issues** tab.
2. Set the task count to `3` (default).
3. Click **Generate Issues**.
4. Three task cards appear, each with a coloured difficulty badge and numbered implementation steps.

**Step 6 — Chat with the codebase**

1. Switch to the **Chat** tab.
2. Type a question such as: *"How do I run the tests for this project?"*
3. The assistant responds with a context-grounded answer derived from the documentation generated in Step 3.
4. Ask a follow-up: *"What environment variables do I need to set?"* — the model remembers the conversation.

---

### 7.3 Testing with a local repository

**Step 1 — Select local mode**

1. Under **Repository** in the sidebar, click the **Local** toggle.
2. In the **Local Path** field, enter an absolute path to a project on your machine. Examples:

   ```
   # Windows
   C:\Users\yourname\projects\my-api

   # macOS / Linux
   /home/yourname/projects/my-api
   ```

3. The repository must exist on the **same machine as the server**. For local testing this is your own machine.

**Step 2 — Run the same flow**

Follow Steps 3–6 from the GitHub walkthrough above. Local analysis is typically faster because no cloning is required.

---

### 7.4 Verifying error handling & toast notifications

OmniDev has robust error handling at both the backend (HTTP status codes) and frontend (toast notification system) layers. The following tests verify each failure path.

#### Test A — Invalid Groq API key

1. In the sidebar, replace your real Groq API key with a fake value: `gsk_fake1234`.
2. Click **Generate Onboarding Docs** with `llm_provider` set to `groq`.
3. **Expected result:** After the repository analysis completes (which succeeds — it uses no LLM), the LLM call fails with HTTP 401. A persistent **red toast banner** appears:
   > **Invalid API Key** — Invalid or missing Groq API Key. Please check your key for deep AI analysis.
4. The toast does **not** auto-dismiss (timeout = 0) because it is a configuration error requiring user action.
5. Dismiss it with the `×` button, correct the key, and retry.

#### Test B — Empty API key with Groq provider

1. Clear the Groq API Key field entirely.
2. Click **Generate Onboarding Docs** with provider `groq`.
3. **Expected result:** The backend returns HTTP 400. The toast shows:
   > **Pipeline failed** — GROQ_API_KEY is not set. Enter your key in the sidebar or switch the provider to `mock`.

#### Test C — Mock provider (no API key required)

1. Clear the Groq API Key field.
2. Set **LLM Provider** to `mock`.
3. Click **Generate Onboarding Docs**.
4. **Expected result:** Documentation is generated instantly from a deterministic template. No LLM call is made. This verifies the full UI pipeline works independently of external services.

#### Test D — Invalid repository URL

1. In the GitHub URL field, enter: `https://github.com/thisuser/thisrepodoesnotexist9999`
2. Click **Generate Onboarding Docs**.
3. **Expected result:** The server returns HTTP 502 (Bad Gateway — clone failed). The toast shows:
   > **Pipeline failed** — [error detail from git clone]

#### Test E — Invalid local path

1. Switch to **Local** mode.
2. Enter a path that does not exist: `/tmp/definitely/not/a/real/path`
3. Click **Generate Onboarding Docs**.
4. **Expected result:** HTTP 404. The toast shows:
   > **Pipeline failed** — [path] does not exist or is not a directory.

#### Test F — Health check with server down

1. Stop the server with `Ctrl-C`.
2. Click **Check Health** in the sidebar.
3. **Expected result:** The indicator turns **red** and shows **Offline**.

---

## 8. API Endpoint Reference

All endpoints are available via the interactive Swagger UI at `http://127.0.0.1:8000/docs`.

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Server health check | None |
| `GET` | `/` | Enterprise web UI | None |
| `POST` | `/api/v1/onboarding/analyze` | Static repository analysis | Optional `X-Groq-Api-Key` |
| `POST` | `/api/v1/onboarding/generate-docs` | Generate documentation from analysis | `X-Groq-Api-Key` (if groq) |
| `POST` | `/api/v1/onboarding/architecture-diagram` | Generate Mermaid diagram from repo | None |
| `POST` | `/api/v1/onboarding/good-first-issues` | Generate starter tasks from analysis | `X-Groq-Api-Key` (if groq) |
| `POST` | `/api/v1/onboarding/full-pipeline` | Analyse + generate docs in one call | `X-Groq-Api-Key` (if groq) |
| `POST` | `/api/v1/onboarding/chat` | Context-grounded codebase Q&A | `X-Groq-Api-Key` (if groq) |

**Supplying the Groq API key via header (no `.env` required):**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/onboarding/full-pipeline \
  -H "Content-Type: application/json" \
  -H "X-Groq-Api-Key: gsk_your_key_here" \
  -d '{
    "source": "github",
    "github_url": "https://github.com/pallets/flask",
    "branch": "main",
    "doc_format": "markdown",
    "llm_provider": "groq"
  }'
```

---

## 9. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Virtual environment not activated, or `pip install` not run | Run `source venv/bin/activate` then `pip install -r requirements.txt` |
| `Address already in use` on startup | Port 8000 is occupied by another process | `lsof -i :8000` (macOS/Linux) or `netstat -ano \| findstr :8000` (Windows), then kill the offending process and restart |
| Health check shows **Offline** | Server URL mismatch or server not running | Ensure `run.py` is running; check the Server URL in the sidebar matches the actual port |
| Toast: "Invalid or missing Groq API Key" | Key is expired, revoked, or typed incorrectly | Re-copy the key from [console.groq.com/keys](https://console.groq.com/keys) |
| Toast: "GROQ_API_KEY is not set" | API key field is empty and provider is `groq` | Enter the key in the sidebar, or switch provider to `mock` |
| Architecture diagram shows "Render error" | Malformed Mermaid output from a very unusual repo structure | Copy the raw Mermaid source from the text area and paste into [mermaid.live](https://mermaid.live) for diagnosis |
| GitHub clone times out | Repository is very large or network is slow | Increase `Max file size` limit only; or try a smaller repository first |
| Chat gives generic answers | Documentation was not generated first | Switch to the Documentation tab, generate docs, then return to Chat |
| `UserWarning: Field "model_used" has conflict` | Pydantic v2 namespace warning — cosmetic only | Safe to ignore; does not affect functionality |

---

<div align="center">
  <sub>OmniDev — Built for the IBM BoB 2.0 Hackathon &nbsp;·&nbsp; Accelerating developer onboarding with AI</sub>
</div>
