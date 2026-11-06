"""Multi-turn repository conversations with dual cloud LLM (Gemini & OpenRouter) support.

Adds multi-turn conversation memory, pronoun/reference resolution, and grounded context assembly.
Works in-process and can persist turns across server restarts.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from codecompass.assistant import _build_context, _local_answer
from codecompass.integrations import LLMProvider, get_llm_provider
from codecompass.retrieval import SearchIndex, tokenize

MAX_HISTORY_TURNS = 6
MAX_HISTORY_CHARS = 4000
MAX_TURNS_PER_CONVERSATION = 50
MAX_CONVERSATIONS = 200
RETRIEVAL_K = 6

_REFERENTIAL_RE = re.compile(
    r"\b(it|its|this|that|they|them|those|these|the one|same|above|previous|earlier|the function|the class|the module|the method)\b",
    re.IGNORECASE,
)
_REF_PHRASE_RE = re.compile(
    r"\b(?:that|this|the)\s+(?:function|class|module|method|file|service|component)\b",
    re.IGNORECASE,
)
_PRONOUN_RE = re.compile(r"\b(it|its|they|them|those|these|that|this)\b", re.IGNORECASE)


@dataclass
class Turn:
    question: str
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "local"
    model: str | None = None
    provider: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "mode": self.mode,
            "model": self.model,
            "provider": self.provider,
        }


@dataclass
class Conversation:
    id: str
    repo_id: str = "default"
    turns: list[Turn] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_turn(self, turn: Turn) -> None:
        with self._lock:
            self.turns.append(turn)
            if len(self.turns) > MAX_TURNS_PER_CONVERSATION:
                del self.turns[:-MAX_TURNS_PER_CONVERSATION]

    def reset(self) -> None:
        with self._lock:
            self.turns.clear()

    def last_turn(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    def recent(self, count: int) -> list[Turn]:
        return self.turns[-count:] if count > 0 else []

    def salient_entity(self) -> str | None:
        last = self.last_turn()
        if not last:
            return None
        for source in last.sources:
            label = source.get("label") or ""
            if label and not label.startswith(("http", "chunk-", "file-")):
                if "." in label:
                    return label.rsplit(".", 1)[0]
                return label
        if last.sources:
            f = last.sources[0].get("file") or ""
            if "." in f:
                return f.rsplit(".", 1)[0].split("/")[-1]
            return f or None
        return None

    def history_for_prompt(self, max_turns: int = MAX_HISTORY_TURNS) -> list[tuple[str, str]]:
        recent_turns = self.recent(max_turns)
        out: list[tuple[str, str]] = []
        total_chars = 0
        for t in reversed(recent_turns):
            q_clean = " ".join(t.question.split())
            a_clean = " ".join(t.answer.split())
            if len(a_clean) > 400:
                a_clean = a_clean[:400] + "..."
            turn_chars = len(q_clean) + len(a_clean)
            if total_chars + turn_chars > MAX_HISTORY_CHARS and out:
                break
            out.append((q_clean, a_clean))
            total_chars += turn_chars
        out.reverse()
        return out


class ConversationManager:
    """Thread-safe multi-turn conversations with optional SQLite persistence."""

    def __init__(self, db: Any = None) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.Lock()
        self.db = db
        self.dal = None
        if db is not None:
            try:
                from codecompass.storage.repositories import ConversationDAL
                self.dal = ConversationDAL(db)
            except Exception:
                self.dal = None

    def get_or_create(self, conversation_id: str | None = None, repo_id: str = "default") -> Conversation:
        with self._lock:
            cid = conversation_id.strip() if conversation_id else ""
            if not cid:
                cid = uuid.uuid4().hex
            if cid not in self._conversations:
                if len(self._conversations) >= MAX_CONVERSATIONS:
                    oldest_id = next(iter(self._conversations))
                    del self._conversations[oldest_id]
                conv = Conversation(id=cid, repo_id=repo_id)
                if self.dal is not None:
                    try:
                        import json
                        self.dal.get_or_create_conversation(cid, repo_id)
                        persisted_turns = self.dal.get_turns(cid)
                        for pt in persisted_turns:
                            srcs = json.loads(pt.sources_json or "[]")
                            conv.turns.append(
                                Turn(
                                    question=pt.question,
                                    answer=pt.answer,
                                    sources=srcs,
                                    mode=pt.mode or "local",
                                )
                            )
                    except Exception:
                        pass
                self._conversations[cid] = conv
            return self._conversations[cid]

    def record_turn(self, conversation: Conversation, turn: Turn) -> None:
        conversation.add_turn(turn)
        if self.dal is not None:
            try:
                import json
                from codecompass.storage.models import ConversationTurnRecord
                self.dal.add_turn(
                    ConversationTurnRecord(
                        conversation_id=conversation.id,
                        turn_index=len(conversation.turns),
                        question=turn.question,
                        answer=turn.answer,
                        mode=turn.mode,
                        sources_json=json.dumps(turn.sources),
                    )
                )
            except Exception:
                pass

    def reset(self, conversation_id: str) -> bool:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                conv.reset()
            if self.dal is not None:
                try:
                    self.dal.reset_conversation(conversation_id)
                except Exception:
                    pass
            return bool(conv)


def resolve_query(question: str, conversation: Conversation) -> dict[str, Any]:
    text = question.strip()
    is_referential = bool(_REFERENTIAL_RE.search(text))
    entity = conversation.salient_entity() if is_referential else None

    resolved_text = text
    if entity and is_referential:
        if _REF_PHRASE_RE.search(resolved_text):
            resolved_text = _REF_PHRASE_RE.sub(entity, resolved_text, count=1)
        elif _PRONOUN_RE.search(resolved_text):
            resolved_text = _PRONOUN_RE.sub(entity, resolved_text, count=1)

    augmented = f"{resolved_text} {entity}" if entity else resolved_text
    return {
        "text": resolved_text,
        "augmented": augmented,
        "referential": is_referential,
        "entity": entity,
    }


def chat_answer(
    analysis: dict[str, Any],
    index: SearchIndex | None,
    conversation: Conversation,
    question: str,
    assistant: LLMProvider | None = None,
    manager: ConversationManager | None = None,
) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {
            "conversation_id": conversation.id,
            "answer": "Ask a question about this repository.",
            "sources": [],
            "mode": "empty",
            "turn": len(conversation.turns),
        }

    resolved = resolve_query(question, conversation)
    results = index.search(resolved["augmented"], k=RETRIEVAL_K) if index else []
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
    model: str | None = None
    provider_name: str | None = None

    if provider and provider.configured:
        history_tuples = conversation.history_for_prompt()
        context = _build_context(analysis, results, history=history_tuples)
        # Format turns for LLM chat
        prior_turns = [{"question": q, "answer": a} for q, a in history_tuples]
        try:
            try:
                resp = provider.answer(question, context, prior_turns=prior_turns)
            except TypeError:
                resp = provider.answer(question, context)

            if isinstance(resp, str):
                answer = resp
                mode = "llm"
                model = getattr(provider, "model", getattr(provider, "model_name", "llm"))
                provider_name = getattr(provider, "provider_name", "llm")
            else:
                answer = resp.answer
                mode = "llm"
                model = resp.model
                provider_name = resp.provider
        except Exception as exc:
            local = _local_answer(analysis, results, resolved["text"])
            answer = f"(Cloud LLM unavailable: {exc})\n\n{local['answer']}"
            mode = "local-fallback"
    else:
        local = _local_answer(analysis, results, resolved["text"])
        answer = local["answer"]
        mode = "local"
        if resolved["referential"] and resolved["entity"]:
            answer = f"(Continuing on {resolved['entity']})\n{answer}"

    turn = Turn(
        question=question,
        answer=answer,
        sources=sources,
        mode=mode,
        model=model,
        provider=provider_name,
    )
    if manager is not None:
        manager.record_turn(conversation, turn)
    else:
        conversation.add_turn(turn)

    return {
        "conversation_id": conversation.id,
        "answer": answer,
        "sources": sources,
        "mode": mode,
        "model": model,
        "provider": provider_name,
        "resolved_question": resolved["text"],
        "turn": len(conversation.turns),
    }
