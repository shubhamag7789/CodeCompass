from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codecompass import __version__
from codecompass.config import DEFAULT_DB_DIR, DEFAULT_DB_NAME
from codecompass.scanner.walker import detect_changes, walk_repository
from codecompass.storage.database import Database
from codecompass.storage.repositories import FileDAL, RepositoryDAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codecompass",
        description="CodeCompass: AI-powered developer onboarding and codebase intelligence platform.",
    )
    parser.add_argument("--version", action="version", version=f"codecompass {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze repository architecture, APIs, and dependencies.")
    analyze_parser.add_argument("target", nargs="?", default=".", help="Target repository directory (default: current directory).")
    analyze_parser.add_argument("--output", help="Path to write analysis JSON file.")

    scan_parser = subparsers.add_parser("scan", help="Scan repository files and store them in SQLite.")
    scan_parser.add_argument("target", nargs="?", default=".", help="Target repository directory (default: current directory).")
    scan_parser.add_argument("--db", help="Path to SQLite database file.")

    serve_parser = subparsers.add_parser("serve", help="Launch the CodeCompass web dashboard.")
    serve_parser.add_argument("--analysis", default=".codecompass/analysis.json", help="Path to analysis JSON file.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind to (default: 8765).")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        return _run_analyze(args.target, args.output)
    if args.command == "scan":
        return _run_scan(args.target, args.db)
    if args.command == "serve":
        from codecompass.server import serve_dashboard
        serve_dashboard(Path(args.analysis), host=args.host, port=args.port)
        return 0
    return 1


def _run_analyze(target: str, output_override: str | None = None) -> int:
    from codecompass.analyzer import analyze_repository, default_output_path, write_analysis
    from codecompass.retrieval import build_index, default_index_path, write_index
    root = Path(target).resolve()
    if not root.exists():
        print(f"Error: Target path does not exist: {root}", file=sys.stderr)
        return 1
    out_path = Path(output_override) if output_override else default_output_path(root)
    print(f"Analyzing repository: {root}")
    analysis = analyze_repository(root)
    write_analysis(analysis, out_path)
    write_index(build_index(root), default_index_path(out_path))
    stats = analysis.get("summary", {}).get("stats", {})
    print(f"Analysis complete -> {out_path}")
    print(f"Files: {stats.get('files', 0)} | Functions: {stats.get('functions', 0)} | Classes: {stats.get('classes', 0)} | APIs: {stats.get('apis', 0)}")
    return 0


def _run_scan(target: str, db_override: str | None = None) -> int:
    root = Path(target).resolve()
    if not root.exists():
        print(f"Error: Target path does not exist: {root}", file=sys.stderr)
        return 1

    db_path = Path(db_override) if db_override else root / DEFAULT_DB_DIR / DEFAULT_DB_NAME
    db = Database(db_path)
    repo_dal = RepositoryDAL(db)
    file_dal = FileDAL(db)

    print(f"Scanning repository: {root}")
    scan_result = walk_repository(root)

    # Check for incremental changes
    existing_files = file_dal.get_files_for_repo(scan_result.repository.id)
    changes = detect_changes(existing_files, scan_result.files)

    # Persist repository & files
    repo_dal.upsert_repository(scan_result.repository)
    file_dal.upsert_files(scan_result.files)
    file_dal.delete_missing_files(scan_result.repository.id, {f.path for f in scan_result.files})

    stats = scan_result.stats
    print(f"Scan complete. Database: {db_path}")
    print(f"Total files: {stats['total_files']} | Lines: {stats['total_lines']} | Size: {stats['total_bytes']} bytes")
    print(f"Languages: {', '.join(f'{k}: {v}' for k, v in scan_result.language_counts.items()) or 'None'}")
    if changes.has_changes:
        print(f"Changes detected - Added: {len(changes.added)}, Modified: {len(changes.modified)}, Deleted: {len(changes.deleted)}")
    else:
        print("All files unchanged since last scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
