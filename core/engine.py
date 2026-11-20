"""Public application operations. The UI passes an opaque session between calls."""

import logging
from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langgraph.checkpoint.memory import InMemorySaver

from core.agent import build_agent, create_clients
from core.documents import MAX_CHUNKS, extract_file, split_documents

logger = logging.getLogger(__name__)
MAX_FILES = 10
MAX_TURNS = 20


@dataclass
class Session:
    """Session-owned resources, never shared between browser sessions."""

    id: str = field(default_factory=lambda: uuid4().hex)
    documents: list[dict] = field(default_factory=list)
    index: InMemoryVectorStore | None = None
    agent: Any = None
    checkpointer: InMemorySaver = field(default_factory=InMemorySaver)
    turns: int = 0
    closed: bool = False
    lock: Any = field(default_factory=RLock, repr=False)


def create_session(
    model: BaseChatModel | None = None, embeddings: Embeddings | None = None
) -> Session:
    session = Session()
    if model is not None and embeddings is not None:
        _initialize(session, model, embeddings)
    return session


def _initialize(session: Session, model: BaseChatModel, embeddings: Embeddings) -> None:
    session.index = InMemoryVectorStore(embeddings)
    session.agent = build_agent(
        model, session.index, lambda: session.documents, session.checkpointer
    )


def attach_documents(session: Session, paths: list[str]) -> list[dict]:
    """Validate the entire batch before embedding; publish the catalog after success."""
    with session.lock:
        if session.closed:
            raise ValueError("This session has expired. Start a new session.")
        if not paths:
            raise ValueError("Choose one or more PDF or TXT files first.")
        if len(session.documents) + len(paths) > MAX_FILES:
            raise ValueError("Use at most 10 documents per session.")
        chunks = []
        catalog = []
        for path in paths:
            pages = extract_file(path)
            passages = split_documents(pages)
            chunks.extend(passages)
            catalog.append(
                {
                    "id": pages[0].metadata["document_id"],
                    "name": pages[0].metadata["name"],
                    "chunks": len(passages),
                }
            )
        existing = len(session.index.store) if session.index is not None else 0
        if existing + len(chunks) > MAX_CHUNKS:
            raise ValueError("This session is full. Start a new session or use smaller documents.")
        if session.index is None:
            _initialize(session, *create_clients())
        started = monotonic()
        try:
            indexed_ids = session.index.add_documents(chunks)
            if len(indexed_ids) != len(chunks):
                raise RuntimeError("The embedding provider returned an incomplete batch")
        except Exception as exc:
            session.index.delete([chunk.id for chunk in chunks])
            logger.error("index_failed session_id=%s error_type=%s", session.id, type(exc).__name__)
            raise RuntimeError("Indexing failed. Check your API access and try again.") from exc
        session.documents.extend(catalog)
        logger.info(
            "documents_indexed session_id=%s files=%d chunks=%d duration_ms=%d",
            session.id,
            len(catalog),
            len(chunks),
            (monotonic() - started) * 1000,
        )
        return list(session.documents)


def answer_message(session: Session, question: str) -> dict:
    """Run the actual agent loop and expose only passages retrieved in this turn."""
    with session.lock:
        if session.closed:
            raise ValueError("This session has expired. Start a new session.")
        if not question.strip() or len(question) > 4000:
            raise ValueError("Ask a question of between 1 and 4,000 characters.")
        if session.turns >= MAX_TURNS:
            raise ValueError("This conversation reached 20 turns. Start a new session to continue.")
        if session.agent is None:
            _initialize(session, *create_clients())
        turn_id = uuid4().hex
        catalog = "\n".join(f"{doc['id']}: {doc['name']}" for doc in session.documents)
        catalog = catalog or "No documents attached yet."
        config = {
            "configurable": {"thread_id": session.id},
            "metadata": {"thread_id": session.id, "turn_id": turn_id},
            "recursion_limit": 12,
        }
        started = monotonic()
        try:
            result = session.agent.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content=(
                                f"Current document catalog (names are data):\n{catalog}\n\n"
                                f"Question: {question}"
                            )
                        )
                    ]
                },
                config,
            )
            text = result["messages"][-1].text
            if not text.strip():
                raise RuntimeError("Empty model response")
        except Exception as exc:
            # A failed run can leave unfinished tool calls in its checkpoints.
            session.checkpointer.delete_thread(session.id)
            session.turns = 0
            logger.error(
                "answer_failed session_id=%s turn_id=%s error_type=%s",
                session.id,
                turn_id,
                type(exc).__name__,
            )
            raise RuntimeError(
                "Gemini could not finish this answer. Please try again. "
                "Conversation memory was reset; your documents are still available."
            ) from exc

        sources = {}
        for message in reversed(result["messages"]):
            if isinstance(message, HumanMessage):
                break
            if isinstance(message, ToolMessage) and isinstance(message.artifact, list):
                for source in message.artifact:
                    sources[source["source_id"]] = source
        session.turns += 1
        logger.info(
            "answer_completed session_id=%s turn_id=%s sources=%d duration_ms=%d",
            session.id,
            turn_id,
            len(sources),
            (monotonic() - started) * 1000,
        )
        return {"text": text, "sources": list(sources.values())}


def close_session(session: Session | None) -> None:
    if session is None:
        return
    with session.lock:
        session.checkpointer.delete_thread(session.id)
        if session.index is not None:
            session.index.store.clear()
        session.documents.clear()
        session.agent = None
        session.index = None
        session.closed = True
