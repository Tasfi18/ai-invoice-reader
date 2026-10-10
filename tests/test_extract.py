import base64

import pytest
from conftest import PADMA, RUPSHA, FakeClient
from invoice_reader.export import to_csv
from invoice_reader.extract import INVOICE_TOOL, build_message, extract_invoice, pdf_text
from invoice_reader.models import Invoice


def test_reads_the_text_layer_of_a_normal_pdf(sample_bytes):
    text = pdf_text(sample_bytes("rupsha-wholesale-line-error"))
    assert "Red lentils 1 kg 12 145.00 1,470.00" in text
    content, source = build_message(sample_bytes("rupsha-wholesale-line-error"))
    assert source == "text"
    assert content[0]["type"] == "text"


def test_sends_a_scanned_pdf_as_a_document(sample_bytes):
    data = sample_bytes("bhairab-fittings-scanned")
    content, source = build_message(data)
    assert source == "pdf"
    assert content[0]["type"] == "document"
    assert base64.b64decode(content[0]["source"]["data"]) == data


def test_forces_the_record_invoice_tool_with_a_strict_schema(sample_bytes):
    client = FakeClient(PADMA)
    extract_invoice(sample_bytes("padma-packaging-correct"), client=client, model="test-model")
    req = client.requests[0]
    assert req["tool_choice"] == {"type": "tool", "name": "record_invoice"}
    assert req["tools"] == [INVOICE_TOOL]
    assert INVOICE_TOOL["strict"] is True
    schema = INVOICE_TOOL["input_schema"]
    assert set(schema["required"]) == set(schema["properties"])  # every field always present
    assert "Copy every number exactly as printed" in req["system"]


def test_a_correct_invoice_comes_back_ok(sample_bytes):
    result = extract_invoice(sample_bytes("padma-packaging-correct"), client=FakeClient(PADMA))
    assert result.ok
    assert result.source == "text"
    assert str(result.invoice.total) == "26225.00"


def test_an_invoice_with_a_printed_mistake_is_flagged(sample_bytes):
    result = extract_invoice(sample_bytes("rupsha-wholesale-line-error"), client=FakeClient(RUPSHA))
    assert not result.ok
    assert [c.name for c in result.checks if c.status == "fail"] == ["Line totals"]


def test_rejects_files_that_are_not_pdfs():
    with pytest.raises(ValueError, match="isn't a PDF"):
        extract_invoice(b"hello", client=FakeClient(PADMA))


def test_reports_when_claude_returns_no_fields(sample_bytes):
    class Empty(FakeClient):
        def create(self, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="Sorry")])

    with pytest.raises(RuntimeError, match="did not return invoice fields"):
        extract_invoice(sample_bytes("padma-packaging-correct"), client=Empty(PADMA))


def test_csv_has_one_row_per_line_with_the_header_repeated():
    rows = to_csv(Invoice.model_validate(PADMA)).strip().split("\n")
    assert len(rows) == 1 + 5
    assert rows[0].startswith("supplier,supplier_tax_id,invoice_number")
    assert rows[1].startswith('Padma Packaging Ltd.,000123456-0101,PP-2026-0418,2026-10-02,2026-10-17,BDT,1,Corrugated carton 12x10x8 in,200,38.50,7700.00')
    assert rows[4].split(",")[7:9] == ['"Printed carry bag', ' medium"']  # comma in a description is quoted
