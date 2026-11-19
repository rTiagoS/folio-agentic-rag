import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.documents import extract_file, split_documents


def test_txt_metadata_and_overlapping_chunks(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("\ufeff" + "Refund terms and conditions. " * 100, encoding="utf-8")
    documents = extract_file(str(path))
    chunks = split_documents(documents)
    assert len(chunks) > 1
    assert len({chunk.metadata["source_id"] for chunk in chunks}) == len(chunks)
    assert all(chunk.metadata["name"] == "notes.txt" for chunk in chunks)
    assert all(chunk.metadata["page"] is None for chunk in chunks)
    assert all(len(chunk.page_content) <= 1200 for chunk in chunks)
    assert chunks[0].page_content[-100:] in chunks[1].page_content


def test_pdf_extracts_page_numbers(tmp_path):
    writer = PdfWriter()
    for text in ["Refunds last 14 days.", "Warranty lasts 2 years."]:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "policy.pdf"
    writer.write(path)
    documents = extract_file(str(path))
    assert [document.metadata["page"] for document in documents] == [1, 2]
    assert "14 days" in documents[0].page_content
    assert "2 years" in documents[1].page_content


@pytest.mark.parametrize(
    "name,content",
    [
        ("empty.txt", b"  "),
        ("invalid.txt", b"\xff\xfe"),
        ("broken.pdf", b"not a PDF"),
        ("script.py", b"print('no')"),
    ],
)
def test_unreadable_or_unsupported_files_are_rejected(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(ValueError):
        extract_file(str(path))


def test_rejects_oversized_text_without_truncation(tmp_path):
    path = tmp_path / "large.txt"
    path.write_text("x" * 150_001)
    with pytest.raises(ValueError, match="too long"):
        extract_file(str(path))
