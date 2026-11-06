"""CodeCompass repository-aware Q&A: retrieval-grounded answers with dual cloud LLM support.

Architecture:
1. Search SQLite BM25 code index for semantic chunks matching the question.
2. Assemble grounded context from repository layers, AST symbols, and code chunks.
3. If an LLM provider is configured (Google Gemini or OpenRouter):
   - Ask the cloud LLM with strict grounding instructions and exact source citations.
4. If no API key is set or cloud call fails:
   - Return high-precision local extractive answers built from retrieval and AST signals.
"""

from __future__ import annotations

from typing import Any

from codecompass.integrations import LLMProvider, get_llm_provider
from codecompass.retrieval import SearchIndex

MAX_CONTEXT_CHUNKS = 8
MAX_SNIPPET_CHARS = 1400


def answer_question(
    analysis: dict[str, Any],
    index: SearchIndex | None,
    question: str,
    assistant: LLMProvider | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"answer": "Ask a question about this repository.", "sources": [], "mode": "empty"}

    results = index.search(question, k=MAX_CONTEXT_CHUNKS) if index else []
    sources = [
        {
            "file": item["file"],
            "start_line": item["start_line"],
            "end_line": item["end_line"],
            "label": item["label"],
            "score": item.get("score"),
        }
        for item in results
    ]

    provider = assistant if assistant is not None else get_llm_provider()
    if provider and provider.configured:
        context = _build_context(analysis, results)
        try:
            try:
                resp = provider.answer(question, context, prior_turns=history)
            except TypeError:
                resp = provider.answer(question, context)

            if isinstance(resp, str):
                answer_text = resp
                model_name = getattr(provider, "model", getattr(provider, "model_name", "llm"))
                provider_name = getattr(provider, "provider_name", "llm")
                tokens = None
            else:
                answer_text = resp.answer
                model_name = resp.model
                provider_name = resp.provider
                tokens = resp.tokens_used

            return {
                "answer": answer_text,
                "sources": sources,
                "mode": "llm",
                "provider": provider_name,
                "model": model_name,
                "tokens": tokens,
            }
        except Exception as exc:
            # Fall back to local answer gracefully
            local = _local_answer(analysis, results, question)
            local["answer"] = f"(Cloud LLM unavailable: {exc})\n\n{local['answer']}"
            local["mode"] = "local-fallback"
            return local

    return _local_answer(analysis, results, question)


def _build_context(
    analysis: dict[str, Any],
    results: list[dict[str, Any]],
    history: list[tuple[str, str]] | None = None,
) -> str:
    lines: list[str] = []
    if history:
        lines.append("Conversation so far (oldest first):")
        for q, a in history:
            lines.append(f"Q: {q}")
            lines.append(f"A: {a}")
        lines.append("")

    summary = analysis.get("summary", {})
    lines += [
        "Repository Architecture Summary:",
        f"- Name: {analysis.get('repository', {}).get('name', 'unknown')}",
        f"- Headline: {summary.get('headline', 'n/a')}",
        f"- Primary Languages: {', '.join(item['name'] for item in summary.get('languages', [])) or 'n/a'}",
        f"- Core Components: {', '.join(summary.get('primary_components', [])) or 'n/a'}",
    ]
    apis = analysis.get("apis", [])
    if apis:
        preview = ", ".join(f"{api.get('method', 'GET')} {api.get('path', '')}" for api in apis[:10])
        lines.append(f"- Key API Endpoints: {preview}")

    lines.append("")
    if results:
        lines.append("Retrieved Code Chunks (BM25 Semantic Retrieval):")
        for item in results:
            snippet = item["text"][:MAX_SNIPPET_CHARS]
            lines.append(f"\n--- File: {item['file']} (Lines {item['start_line']}-{item['end_line']}, Symbol: {item['label']}) ---")
            lines.append(snippet)
    else:
        lines.append("No direct code snippet matches found in repository index.")

    return "\n".join(lines)


def _local_answer(analysis: dict[str, Any], results: list[dict[str, Any]], question: str) -> dict[str, Any]:
    """Extractive answer used when no cloud LLM key is configured."""
    q = question.lower()
    sources = [
        {
            "file": item["file"],
            "start_line": item["start_line"],
            "end_line": item["end_line"],
            "label": item["label"],
            "score": item.get("score"),
        }
        for item in results
    ]

    if any(term in q for term in ("route", "api", "endpoint")):
        apis = analysis.get("apis", [])
        if apis:
            listed = "\n".join(f"{api.get('method', 'GET')} {api.get('path', '')}  ({api.get('file', '')})" for api in apis[:15])
            return {"answer": f"Detected API routes:\n{listed}", "sources": sources, "mode": "local"}

    if any(term in q for term in ("entry", "start", "run", "main")):
        entry = analysis.get("summary", {}).get("entry_points", [])
        if entry:
            return {"answer": "Entry points:\n" + "\n".join(entry), "sources": sources, "mode": "local"}

    if any(term in q for term in ("impact", "break", "affect", "depend", "risk")):
        risky = [
            f"{item['label']} — {item['risk']} risk, {len(item.get('affected_files', []))} files affected"
            for item in analysis.get("impact_index", {}).values()
            if item.get("risk") != "Low"
        ][:10]
        if risky:
            return {"answer": "High-risk impact areas:\n" + "\n".join(risky), "sources": sources, "mode": "local"}

    if results:
        header = "Relevant code locations retrieved from codebase index:"
        listed = "\n".join(
            f"- {item['file']}:{item['start_line']} ({item['label']})" for item in results
        )
        return {"answer": f"{header}\n{listed}", "sources": sources, "mode": "local"}

    summary = analysis.get("summary", {})
    fallback = "\n".join(
        [
            summary.get("headline", "No summary available."),
            f"Primary components: {', '.join(summary.get('primary_components', [])) or 'none detected'}",
            "No direct code match. Try specifying a file, function, or architectural keyword.",
        ]
    )
    return {"answer": fallback, "sources": sources, "mode": "local"}
