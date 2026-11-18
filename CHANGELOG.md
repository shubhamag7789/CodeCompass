# Changelog

All notable changes to CodeCompass are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-11-19

### Added
- **Multi-Tenant User Isolation & Auth**: PBKDF2-HMAC-SHA256 salted password hashing, 64-character session bearer tokens, and per-user database partitioning.
- **Self-Contained Security Recovery**: Offline account recovery using salted security questions and 4-word mnemonic recovery passphrases with zero external SMTP dependencies.
- **In-App Security Modal**: User profile dropdown modal to review, change, and update security questions and recovery keys directly from the dashboard.
- **Tree-sitter AST Engines**: High-performance AST parsing across Python, TypeScript, TSX, and JavaScript.
- **Universal Route Discovery**: Automated detection for NestJS decorators (`@Controller`, `@Get`, `@Post`), Express, Fastify, Next.js, and Flask.
- **Modern React + Vite Dashboard**: Built on React 18, TypeScript, Tailwind CSS, and `@xyflow/react` for interactive dependency graph visualization.

## [0.2.0] — 2026-10-15

### Added
- **SQLite WAL Storage**: High-performance relational database storage (`codecompass.db`) with Write-Ahead Logging and automatic schema migrations.
- **2-Hop Blast Radius Engine**: Change impact analysis evaluating upstream affected files, endpoints, and test suites with risk scoring.
- **Feature Flow Tracer**: End-to-end execution flow diagrams tracing routes down to models.
- **Role-Based Onboarding Roadmaps**: Dynamic Day 1–3 guides tailored for Frontend, Backend, Fullstack, and QA roles.

## [0.1.0] — 2026-09-20

### Added
- Initial project architecture, CLI interface, and Okapi BM25 lexical ranking engine.
