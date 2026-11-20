from app import COMPOSER_PLACEHOLDER, prefill_message, reset_session, respond
from core.engine import answer_message, create_session


def test_chat_without_attachments(session, clients):
    result = respond({"text": "Hello", "files": []}, [], session)
    assert "Hello!" in result[0]
    assert result[1] is session
    assert clients[1].document_calls == 0


def test_empty_composer_keeps_its_hint_after_a_reply_and_new_chat(session):
    updates = respond({"text": "Hello", "files": []}, [], session)
    assert updates[-1]["placeholder"] == COMPOSER_PLACEHOLDER
    reset = reset_session(session)
    assert reset[4]["value"] is None
    assert reset[4]["placeholder"] == COMPOSER_PLACEHOLDER


def test_model_failure_is_shown_and_next_message_can_complete(session, clients):
    clients[0].fail = True
    updates = respond({"text": "Hello", "files": []}, [], session)
    failed = updates
    assert "Gemini could not finish this answer" in failed[0]
    assert failed[2]["interactive"] is True
    assert failed[4]["placeholder"] == COMPOSER_PLACEHOLDER
    clients[0].fail = False
    recovered = respond({"text": "Hello", "files": []}, [], session)
    assert "Hello!" in recovered[0]
    assert recovered[2]["interactive"] is True


def test_message_indexes_files_before_answering_and_preserves_memory(session, text_file):
    respond({"text": "Hello", "files": []}, [], session)
    result = respond({"text": "Refund terms?", "files": [text_file]}, [], session)
    assert "14 days" in result[0]
    assert result[1] is session
    assert len(session.documents) == 1
    previous = answer_message(session, "What was my previous question?")
    assert "Question: Refund terms?" in previous["text"]


def test_files_only_message_does_not_call_chat_model(session, text_file, clients):
    clients[0].fail = True
    result = respond({"text": "", "files": [text_file]}, [], session)
    assert "Added 1 document" in result[0]
    assert session.turns == 0
    assert clients[1].document_calls == 1


def test_each_submission_indexes_only_its_new_files(session, text_file, tmp_path, clients):
    respond({"text": "", "files": [text_file]}, [], session)
    other = tmp_path / "shipping.txt"
    other.write_text("Shipping takes 3 days.")
    respond({"text": "", "files": [str(other)]}, [], session)
    respond({"text": "Hello", "files": []}, [], session)
    assert len(session.documents) == 2
    assert clients[1].document_calls == 2


def test_invalid_attachment_preserves_chat_and_indexed_documents(session, text_file, tmp_path):
    respond({"text": "Hello", "files": [text_file]}, [], session)
    path = tmp_path / "bad.txt"
    path.write_text("")
    result = respond({"text": "Read this", "files": [str(path)]}, [], session)
    assert "No readable text" in result[0]
    assert len(session.documents) == 1
    assert session.turns == 1
    assert "Hello" in answer_message(session, "What was my previous question?")["text"]


def test_suggestion_preserves_pending_attachments_without_rewriting_the_original_draft(text_file):
    draft = {"text": "Draft", "files": [text_file]}
    message = prefill_message("Summarize this document", draft)
    assert message["text"] == "Summarize this document"
    assert message["files"] == [text_file]
    assert draft["text"] == "Draft"


def test_new_chat_clears_documents_and_memory(session, text_file, clients):
    respond({"text": "Refund terms?", "files": [text_file]}, [], session)
    reset_session(session)
    assert session.closed
    assert session.index is None
    assert not session.documents
    other = create_session(*clients)
    result = answer_message(other, "What was my previous question?")
    assert result["text"] == "No previous question"
