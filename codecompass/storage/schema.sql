-- CodeCompass SQLite Database Schema
-- Optimized for SQLite with WAL mode enabled

PRAGMA foreign_keys = ON;

-- Repositories indexed by CodeCompass
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now')),
    last_scanned_at TEXT
);

-- Tracked files with content hashing for incremental scanning
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    path TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    lines INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    is_test BOOLEAN NOT NULL DEFAULT 0,
    last_scanned_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE (repo_id, path)
);

-- Extracted code entities (Classes, Functions, Methods, Endpoints)
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    signature TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_byte INTEGER,
    end_byte INTEGER,
    docstring TEXT,
    scope TEXT,
    metadata_json TEXT,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Knowledge graph relationships (CONTAINS, IMPORTS, CALLS, EXTENDS, TESTS)
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE (repo_id, source_id, target_id, type)
);

-- Search chunks for BM25 lexical search (AST-aware)
CREATE TABLE IF NOT EXISTS search_chunks (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    entity_id TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    label TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens_json TEXT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Multi-turn conversation sessions
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Individual turns within conversations
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    mode TEXT NOT NULL,
    sources_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Feature execution flows traced across entities
CREATE TABLE IF NOT EXISTS feature_flows (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    entry_point_id TEXT,
    steps_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Users for Authentication & RBAC Authorization
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    security_question TEXT DEFAULT NULL,
    security_answer_hash TEXT DEFAULT NULL,
    security_answer_salt TEXT DEFAULT NULL,
    recovery_passphrase_hash TEXT DEFAULT NULL,
    recovery_passphrase_salt TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_login_at TEXT
);

-- Active user sessions (Bearer tokens)
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Password reset recovery codes
CREATE TABLE IF NOT EXISTS password_resets (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used BOOLEAN NOT NULL DEFAULT 0
);

-- Multi-user repository associations and permissions
CREATE TABLE IF NOT EXISTS user_repositories (
    user_id TEXT NOT NULL,
    repo_id TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, repo_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_files_repo_path ON files(repo_id, path);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
CREATE INDEX IF NOT EXISTS idx_entities_repo ON entities(repo_id);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(type);
CREATE INDEX IF NOT EXISTS idx_rel_repo ON relationships(repo_id);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON search_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_repo ON search_chunks(repo_id);
CREATE INDEX IF NOT EXISTS idx_turns_conv ON conversation_turns(conversation_id);
CREATE INDEX IF NOT EXISTS idx_feature_flows_repo ON feature_flows(repo_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_repos_user ON user_repositories(user_id);
