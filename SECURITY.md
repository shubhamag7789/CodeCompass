# Security Policy

CodeCompass is engineered to provide deep codebase intelligence while upholding strict security standards for authentication, data privacy, and local execution.

---

## 🛡️ Supported Versions

Security patches and updates are actively maintained on the latest stable releases:

| Version | Supported | Status |
| :--- | :--- | :--- |
| `0.3.x` | ✅ | Current Stable Release |
| `0.2.x` | ⚠️ | Critical Security Fixes Only |
| `< 0.2` | ❌ | End of Life |

---

## 🔐 Core Security Architecture

### 1. Authentication & Password Hashing
* **PBKDF2-HMAC-SHA256**: All user passwords are encrypted using salted PBKDF2 with SHA-256 and **100,000 iterations** via Python's standard `hashlib`. Plaintext passwords are never logged, stored, or transmitted in responses.
* **Cryptographic Salt**: Each account is generated with a unique 16-byte random salt (`secrets.token_hex(16)`).
* **Timing-Safe Verification**: Password hash evaluations use constant-time comparisons (`hmac.compare_digest`) to prevent timing side-channel attacks.

### 2. Session Management & Bearer Tokens
* **High-Entropy Tokens**: Authentication sessions issue 64-character bearer tokens generated via `secrets.token_hex(32)`.
* **Stateful Revocation**: Tokens are validated against the `sessions` table in the local SQLite database. Calling `POST /api/auth/logout` or resetting a password immediately invalidates active tokens.
* **Expiration**: Tokens have an enforced 30-day expiration window.

### 3. Password Recovery & Account Protection
* **Salted Security Questions**: Security questions and answers are protected with unique random salts and PBKDF2-HMAC-SHA256 hashing (answers are normalized case-insensitively). Plaintext answers are never stored in the database.
* **4-Word Cryptographic Recovery Passphrases**: High-entropy multi-word recovery passphrases (generated via `secrets` and BIP-style dictionaries) provide offline-ready account recovery without external SMTP mail server dependencies.
* **Instant Session Invalidation**: Successfully resetting a password immediately invalidates all active sessions across devices (`DELETE FROM sessions WHERE user_id = ?`), requiring immediate re-authentication.
* **Enumeration Defense**: Forgot Password requests provide standardized verification responses to avoid user email enumeration attacks.

### 4. Multi-Tenant Workspace & Data Isolation
* **Per-User SQLite Partitioning**: Repositories, analysis snapshots, and conversation turns are strictly associated with the authenticated `user_id`.
* **Fresh-Slate Isolation**: Newly registered accounts start with an empty workspace (0 repositories). Users cannot enumerate, access, or modify projects belonging to other accounts.
* **Path Traversal Defenses**: File content retrieval endpoints (`/api/file`) enforce strict directory boundary checks to ensure file reads cannot escape the target repository root path.

### 5. Local Execution & Network Exposure
* **Default Loopback Binding**: The CodeCompass server binds by default to `127.0.0.1:8765`, preventing unauthorized incoming network access on public Wi-Fi or untrusted networks.
* **CORS & Preflight Handling**: Only sanctioned headers (`Authorization`, `Content-Type`, `X-Auth-Token`) and HTTP methods (`GET`, `POST`, `DELETE`, `OPTIONS`) are permitted.
* **Non-Executing Static Analysis**: Codebase scanning parses abstract syntax trees (AST) and regex patterns statically as text. CodeCompass never executes or runs untrusted repository code during analysis.

### 6. Privacy & Telemetry
* **Zero Telemetry**: CodeCompass collects zero analytics, telemetry, or tracking metrics.
* **Offline-First**: Core parsing, graph computation, blast radius analysis, and BM25 search run 100% locally on your machine without requiring an external internet connection or cloud service.
* **Protected Secrets**: API keys (e.g. `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) reside in a git-ignored `.env` file and are never checked into version control.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in CodeCompass, please report it responsibly:

1. **Do not create a public issue** on GitHub.
2. Email your findings directly to the maintainers at **security@codecompass.dev** (or submit privately through GitHub Security Advisories).
3. Include the following details to help us investigate:
   * Description of the vulnerability and its potential impact.
   * Clear, step-by-step reproduction instructions or a minimal proof of concept.
   * Affected version or commit hash.
   * Any suggested remediations or mitigations.

### Response Commitment
* **Initial Acknowledgment**: Within 48 hours.
* **Status Update & Assessment**: Within 5 business days.
* **Patch Release**: We prioritize verified vulnerabilities and release patches as promptly as possible before coordinated disclosure.
