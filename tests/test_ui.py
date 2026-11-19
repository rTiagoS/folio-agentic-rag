from app import reset_session, respond
from core.engine import answer_message, create_session


def test_native_text_message_without_attachments(session, clients):
    result = list(respond({"text": "Hello", "files": []}, [], session))[-1]
    assert "Hello!" in result[0][-1]["content"]
    assert result[2] is session
    assert result[3] == ""
    assert clients[1].document_calls == 0


def test_native_message_indexes_files_before_answering(session, text_file):
    result = list(respond({"text": "Refund terms?", "files": [text_file]}, [], session))[-1]
    assert "14 days" in result[0][-1]["content"]
    assert "refunds.txt" in result[3]
    assert len(session.documents) == 1


def test_files_only_message_does_not_call_chat_model(session, text_file, clients):
    clients[0].fail = True
    result = list(respond({"text": "", "files": [text_file]}, [], session))[-1]
    assert "Added 1 document" in result[0][-1]["content"]
    assert session.turns == 0
    assert clients[1].document_calls == 1


def test_invalid_attachment_preserves_the_chat(session, tmp_path):
    answer_message(session, "Hello")
    path = tmp_path / "bad.txt"
    path.write_text("")
    result = list(respond({"text": "Read this", "files": [str(path)]}, [], session))[-1]
    assert "No readable text" in result[0][-1]["content"]
    assert session.turns == 1
    assert "Hello" in answer_message(session, "What was my previous question?")["text"]


def test_new_chat_clears_documents_and_memory(session, text_file, clients):
    list(respond({"text": "Refund terms?", "files": [text_file]}, [], session))
    assert reset_session(session) == ([], None, None, "")
    assert session.closed
    assert session.index is None
    assert not session.documents
    other = create_session(*clients)
    result = answer_message(other, "What was my previous question?")
    assert result["text"] == "No previous question"
