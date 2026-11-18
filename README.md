<div align="center">

# 🧭 CodeCompass

### Autonomous Codebase Intelligence & Architectural Impact Platform

**CodeCompass turns any repository into an interactive dependency graph, an execution flow tracer, and a change blast radius analyzer — with production-grade authentication, multi-tenant isolation, and zero-configuration local execution.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Frontend](https://img.shields.io/badge/frontend-React%20%7C%20TypeScript%20%7C%20Vite%20%7C%20Tailwind-cyan.svg)](frontend/)
[![Database](https://img.shields.io/badge/database-SQLite%20WAL-emerald.svg)](#-storage-architecture)
[![Test Suite](https://img.shields.io/badge/tests-76%20passing-brightgreen.svg)](#-testing)
[![Version](https://img.shields.io/badge/version-0.3.0-informational.svg)](CHANGELOG.md)

[Quick Start](#-quick-start) · [Key Capabilities](#-key-capabilities) · [Architecture](#-architecture-overview) · [Security](#-security--data-isolation) · [API Documentation](#-api-endpoints)

</div>

---

## 💡 The Problem

Opening an unfamiliar, large codebase is disorienting. Developers spend hours guessing entry points, manually tracing calls across folders, and wondering *"What will break if I modify this file?"* Onboarding takes weeks, documentation drifts out of date, and regression risks in central services are identified only after deployment.

## 🚀 The Solution

CodeCompass autonomously analyzes any local folder or public GitHub repository. It builds a bidirectional architectural call-graph, measures change blast radiuses, maps REST/HTTP APIs, traces end-to-end execution flows, and generates role-based Day 1–3 onboarding guides — backed by an offline-first SQLite database and an AI copilot.

---

## ✨ Key Capabilities

| Capability | What You Get | Implementation |
| :--- | :--- | :--- |
| **Interactive Dependency Graph** | Real-time visual canvas with nodes for files, functions, classes, and REST endpoints with incoming and outgoing dependency edges. | `@xyflow/react` + `analyzer.py` |
| **Change Impact & Blast Radius** | 2-hop reverse call-graph traversal ranking components into **High**, **Medium**, and **Low** risk, calculating affected files, APIs, and test suites before code commits. | `codecompass/graph/impact.py` |
| **Universal Framework Extraction** | Automated AST route discovery for **NestJS decorators** (`@Controller`, `@Get`, `@Post`, `@Delete`), **Fastify**, **Express**, **Next.js route handlers**, **FastAPI**, **Flask**, and **Django**. | `codecompass/analyzer.py` |
| **Path-Aware Relative Import Resolver** | True context-aware resolution of `./` and `../` imports across `.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `/index`, and monorepos. | `codecompass/analyzer.py` |
| **End-to-End Feature Flow Tracer** | Step-by-step execution sequences tracing public HTTP endpoints down to service models and database repositories. | `codecompass/tracing/flow_tracer.py` |
| **Role-Based Onboarding Engine** | Dynamic Day 1, Day 2, and Day 3 learning roadmaps tailored for **Frontend**, **Backend**, **Fullstack**, and **DevOps / QA** roles with must-read files. | `codecompass/onboarding/` |
| **Multi-Tenant User Isolation** | Separate user accounts with private workspaces. New accounts start with a clean slate; users never see or modify other developers' repositories. | `codecompass/auth/` |
| **Production Authentication** | PBKDF2-HMAC-SHA256 password hashing with unique random salts, 64-char bearer session tokens, self-contained Security Questions, and 4-word Recovery Passphrases. | `codecompass/auth/security.py` |
| **Codebase-Aware AI Copilot** | Multi-turn contextual chat citing exact file names and line numbers. Works offline with BM25 lexical retrieval and integrates with Gemini or OpenRouter. | `codecompass/assistant.py` |
| **Offline-First SQLite WAL Storage** | High-performance relational database with Write-Ahead Logging (`codecompass.db`) ensuring zero data loss and instant reload. | `codecompass/storage/` |

---

## 🏗️ Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      React 18 Frontend                      │
 │     Vite · TypeScript · Tailwind CSS · XYFlow Canvas        │
 └──────────────────────────────┬──────────────────────────────┘
                                │ JSON API (Bearer Token Auth)
 ┌──────────────────────────────▼──────────────────────────────┐
 │               CodeCompass HTTP Server Engine                │
 │       stdlib http.server · ThreadingHTTPServer (port 8765)  │
 ├─────────────────────────────────────────────────────────────┤
 │ • AuthManager (PBKDF2 SHA-256 / Sessions / Password Resets) │
 │ • Universal AST & Decorator Analyzer (Python / TS / JS)     │
 │ • FlowTracer (HTTP Entrypoints ──► Services ──► Models)     │
 │ • ImpactAnalyzer (2-Hop Reverse Graph Walk & Blast Radius)  │
 │ • RoleOnboardingGenerator (Day 1 / 2 / 3 Progression)       │
 │ • ConversationManager (Multi-Turn Chat with AST Citations)  │
 └──────┬───────────────────────┬───────────────────────┬──────┘
        │                       │                       │
 ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
 │   SQLite    │         │  Per-Repo   │         │ BM25 Index  │
 │  Database   │         │  Artifacts  │         │ (Lexical)   │
 │ (WAL Mode)  │         │  (analysis) │         │ (Tokens)    │
 └─────────────┘         └─────────────┘         └─────────────┘
```

---

## 🔒 Security & Data Isolation

* **PBKDF2-HMAC-SHA256 Cryptography**: Passwords are never stored in plaintext. They are salted with 16-byte random salts and hashed through 100,000 iterations using Python's standard `hashlib`.
* **Timing-Safe Evaluation**: Constant-time hash verification via `hmac.compare_digest` to prevent side-channel timing attacks.
* **Multi-Tenant Data Privacy**: Every repository and chat history is strictly mapped to the owning `user_id` in SQLite. When deploying or running as an `.exe`, new users start with an empty dashboard and cannot access other users' repositories.
* **Two-Step Password Recovery**: Secure self-service password reset using time-limited (15-minute) 6-digit one-time recovery codes stored in `password_resets`.
* **Safe Local Defaults**: By default, the HTTP daemon binds exclusively to loopback (`127.0.0.1:8765`).

---

## 🚀 Quick Start

### Prerequisites
* **Python 3.11+**
* **Node.js 18+** (for frontend development/building)
* **Git** (only required if cloning public GitHub links)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/YourOrg/CodeCompass.git
cd CodeCompass

# (Optional) Install as an editable CLI tool
pip install -e .
```

### 2. Launch the Platform

```bash
# Start the CodeCompass server
python -m codecompass serve

# Open in your browser:
# http://127.0.0.1:8765
```

### 3. Analyze from the Command Line

```bash
# Analyze current working directory
python -m codecompass analyze .

# Analyze any local directory
python -m codecompass analyze D:/Projects/MyBackend

# Analyze a remote GitHub repository
python -m codecompass analyze https://github.com/org/repo
```

---

## 🖥️ CLI Usage

```text
codecompass analyze <target> [--output PATH] [--json]
codecompass serve   [--analysis PATH] [--host HOST] [--port PORT]
codecompass --version
```

| Command | Description |
| :--- | :--- |
| `analyze <target>` | Scans AST entities, imports, routes, and impact indexes. |
| `analyze -o, --output PATH` | Saves the output `analysis.json` to a custom destination. |
| `analyze --json` | Outputs the complete architectural JSON directly to stdout. |
| `serve` | Launches the intelligence dashboard daemon (default: `127.0.0.1:8765`). |
| `serve --host / --port` | Customizes the listening interface and port. |

---

## 📡 API Endpoints

### Authentication
* `POST /api/auth/register` — Creates a new account with a clean workspace, custom security question, and recovery passphrase.
* `POST /api/auth/login` — Authenticates credentials and returns a bearer session token.
* `POST /api/auth/logout` — Invalidates the current session token.
* `GET /api/auth/me` — Fetches current user profile and role (`admin` or `user`).
* `POST /api/auth/forgot-password` — Fetches recovery requirements (security question prompt & passphrase availability).
* `POST /api/auth/reset-password` — Resets password via verified security question answer or recovery passphrase.

### Codebase Intelligence
* `GET /api/repositories` — Returns all repositories belonging to the authenticated user.
* `POST /api/analyze` — Analyzes a new project (local path or GitHub URL).
* `POST /api/switch-repo` — Switches the user's active workspace repository.
* `POST /api/repositories/delete` — Removes a repository and cleans up artifacts.
* `GET /api/analysis` — Returns the architectural graph, summary stats, and API map.
* `GET /api/impact?id=<nodeId>` — Computes 2-hop reverse dependencies and blast radius for a symbol.
* `GET /api/flow/discover` — Discovers traceable HTTP feature flows.
* `GET /api/flow/trace?id=<entryId>` — Returns end-to-end execution steps for a specific endpoint.
* `GET /api/onboarding?role=<role>` — Returns curated Day 1–3 reading paths and gotchas for a role.
* `POST /api/chat` — Multi-turn conversation endpoint with AST citation grounding.

---

## 💾 Storage Architecture

All data is stored locally inside the `.codecompass` directory:

```
.codecompass/
├── codecompass.db          # SQLite relational database (WAL mode)
├── codecompass.db-wal      # High-performance write-ahead transaction log
├── registry.json           # Catalog of tracked repositories
├── repositories/           # Per-repository isolated graph artifacts
│   ├── caw_assignment/
│   │   ├── analysis.json   # Graph nodes, edges, API routes, impact index
│   │   └── index.json      # BM25 lexical token index
│   └── prepwise/
│       ├── analysis.json
│       └── index.json
└── workspaces/             # Cloned GitHub repositories
```

---

## 🧪 Testing

CodeCompass includes an automated test suite covering unit parsers, graph algorithms, tokenizers, authentication lifecycles, and HTTP endpoints:

```bash
# Run the complete test suite (76 tests)
python -B -m unittest discover -s tests -v
```

---

## 📄 License

CodeCompass is open-source software licensed under the [MIT License](LICENSE).
