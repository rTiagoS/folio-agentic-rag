import hashlib
import os
import re
from uuid import uuid4

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import pytest  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402

from core.engine import create_session  # noqa: E402


class LocalEmbeddings(Embeddings):
    """Stable word vectors for synthetic test documents; never used by the application."""

    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0
        self.fail = False

    def vector(self, text):
        vector = [0.0] * 64
        for word in re.findall(r"\w+", text.lower()):
            vector[hashlib.sha256(word.encode()).digest()[0] % 64] += 1
        return vector

    def embed_documents(self, texts):
        self.document_calls += 1
        if self.fail:
            raise RuntimeError("Synthetic embedding failure")
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        self.query_calls += 1
        return self.vector(text)


class ToolCallingModel(BaseChatModel):
    """Exercise LangChain's actual agent loop with deterministic tool decisions."""

    document_ids: list[str] | None = None
    fail: bool = False
    repeat_search: bool = False

    @property
    def _llm_type(self):
        return "local-tool-calling-test-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.fail:
            raise RuntimeError("Synthetic provider error: sensitive content must not be logged")
        humans = [message for message in messages if isinstance(message, HumanMessage)]
        question = humans[-1].content.split("Question: ")[-1]
        if question.lower() in {"hello", "hi"}:
            response = AIMessage(content="Hello! How can I help?")
        elif "previous question" in question.lower():
            response = AIMessage(
                content=humans[-2].content if len(humans) > 1 else "No previous question"
            )
        elif isinstance(messages[-1], ToolMessage) and not self.repeat_search:
            if "absent" in question:
                response = AIMessage(content="I could not find that information in the documents.")
            else:
                response = AIMessage(content=messages[-1].content)
        else:
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": uuid4().hex,
                        "name": "search_uploaded_documents",
                        "args": {"query": question, "document_ids": self.document_ids},
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=response)])


@pytest.fixture
def clients():
    return ToolCallingModel(), LocalEmbeddings()


@pytest.fixture
def session(clients):
    return create_session(*clients)


@pytest.fixture
def text_file(tmp_path):
    path = tmp_path / "refunds.txt"
    path.write_text("Refunds are available within 14 days. Warranty coverage lasts 2 years.")
    return str(path)
