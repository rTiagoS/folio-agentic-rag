import logging

import pytest

from core.engine import answer_message, attach_documents, close_session, create_session


def test_agent_searches_uploaded_document_and_reuses_embeddings(session, text_file, clients):
    attach_documents(session, [text_file])
    first = answer_message(session, "What are the refund terms?")
    second = answer_message(session, "What is the warranty?")
    assert "14 days" in first["text"]
    assert first["sources"][0]["source_id"] in first["text"]
    assert "2 years" in second["text"]
    assert clients[1].document_calls == 1
    assert clients[1].query_calls == 2


def test_agent_selects_one_document(session, text_file, clients, tmp_path):
    other = tmp_path / "premium.txt"
    other.write_text("Premium refunds are available for 90 days.")
    catalog = attach_documents(session, [text_file, str(other)])
    clients[0].document_ids = [catalog[1]["id"]]
    result = answer_message(session, "What are the refund terms?")
    assert "90 days" in result["text"]
    assert {source["name"] for source in result["sources"]} == {"premium.txt"}


def test_session_memory_isolated_from_other_sessions(session, text_file, clients):
    other = create_session(*clients)
    attach_documents(session, [text_file])
    attach_documents(other, [text_file])
    answer_message(session, "Tell me about refunds")
    remembered = answer_message(session, "What was my previous question?")
    forgotten = answer_message(other, "What was my previous question?")
    assert "Tell me about refunds" in remembered["text"]
    assert forgotten["text"] == "No previous question"
    assert session.id != other.id
    assert session.index is not other.index
    assert session.checkpointer is not other.checkpointer


def test_empty_session_cannot_access_other_documents(session, text_file, clients):
    attach_documents(session, [text_file])
    other = create_session(*clients)
    with pytest.raises(ValueError, match="Attach"):
        answer_message(other, "Show the refund policy")


def test_tool_rejects_ids_outside_current_session(session, text_file, clients):
    attach_documents(session, [text_file])
    clients[0].document_ids = ["another-session-document"]
    result = answer_message(session, "Show the refund policy")
    assert not result["sources"]
    assert "14 days" not in result["text"]


@pytest.mark.parametrize("failure", ["provider", "incomplete_batch"])
def test_failed_batch_does_not_change_index_or_catalog(
    session, text_file, clients, monkeypatch, failure
):
    attach_documents(session, [text_file])
    if failure == "provider":
        clients[1].fail = True
    else:
        embed = clients[1].embed_documents
        monkeypatch.setattr(clients[1], "embed_documents", lambda texts: embed(texts)[:-1])
    with pytest.raises(RuntimeError, match="Indexing failed"):
        attach_documents(session, [text_file, text_file])
    assert len(session.documents) == 1
    assert len(session.index.store) == 1


def test_provider_failure_resets_partial_memory_without_logging_content(
    session,
    text_file,
    clients,
    caplog,
):
    attach_documents(session, [text_file])
    clients[0].fail = True
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="memory was reset"):
        answer_message(session, "private question")
    assert "answer_failed" in caplog.text
    assert session.id in caplog.text
    assert "private question" not in caplog.text
    assert "sensitive content" not in caplog.text
    assert session.checkpointer.get_tuple({"configurable": {"thread_id": session.id}}) is None
    clients[0].fail = False
    assert answer_message(session, "Refund terms?")["sources"]


def test_search_loop_is_bounded(session, text_file, clients):
    attach_documents(session, [text_file])
    clients[0].repeat_search = True
    with pytest.raises(RuntimeError, match="could not finish"):
        answer_message(session, "Keep searching")
    assert clients[1].query_calls <= 3


def test_closing_session_clears_documents_index_and_memory(session, text_file):
    attach_documents(session, [text_file])
    answer_message(session, "Refund terms?")
    close_session(session)
    assert session.index is None
    assert not session.documents
    assert session.agent is None
    with pytest.raises(ValueError, match="expired"):
        answer_message(session, "Refund terms?")


def test_missing_api_key_is_actionable(monkeypatch, text_file):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        attach_documents(create_session(), [text_file])


def test_question_and_turn_limits(session, text_file):
    attach_documents(session, [text_file])
    with pytest.raises(ValueError, match="4,000"):
        answer_message(session, "x" * 4001)
    session.turns = 20
    with pytest.raises(ValueError, match="20 turns"):
        answer_message(session, "Refund terms?")
