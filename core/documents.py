"""Extract, index, and retrieve document passages without generating answers."""

from pathlib import Path
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 150_000
MAX_PAGES = 200
MAX_CHUNKS = 500


def extract_file(path: str) -> list[Document]:
    """Read PDF pages or UTF-8 text and preserve source metadata."""
    source = Path(path)
    if source.suffix.lower() not in {".pdf", ".txt"}:
        raise ValueError("Please attach a PDF or TXT file.")
    if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Each file must exist and be no larger than 10 MB.")

    document_id = uuid4().hex
    try:
        if source.suffix.lower() == ".pdf":
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported.")
            if len(reader.pages) > MAX_PAGES:
                raise ValueError("Please use a PDF with at most 200 pages.")
            pages = []
            size = 0
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                size += len(text)
                if size > MAX_TEXT_CHARS:
                    raise ValueError("This document is too long; use up to 150,000 characters.")
                pages.append((number, text))
        else:
            text = source.read_text(encoding="utf-8-sig")
            if len(text) > MAX_TEXT_CHARS:
                raise ValueError("This document is too long; use up to 150,000 characters.")
            pages = [(None, text)]
    except (PyPdfError, UnicodeError, OSError) as exc:
        raise ValueError("Could not read this file. Use a readable PDF or UTF-8 TXT.") from exc

    documents = [
        Document(
            page_content=text.strip(),
            metadata={"document_id": document_id, "name": source.name, "page": number},
        )
        for number, text in pages
        if text.strip()
    ]
    if not documents:
        raise ValueError(
            "No readable text found. Scanned PDFs need OCR, which is not included yet."
        )
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """Use a modest character budget and overlap; keep page boundaries intact."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=180)
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.id = uuid4().hex
        chunk.metadata["source_id"] = chunk.id[:12]
    return chunks


def search_documents(
    index: InMemoryVectorStore,
    query: str,
    document_ids: list[str] | None = None,
) -> list[Document]:
    """Search a session-owned index, optionally restricting the source documents."""
    return index.similarity_search(
        query,
        k=4,
        filter=(lambda doc: doc.metadata["document_id"] in document_ids) if document_ids else None,
    )
