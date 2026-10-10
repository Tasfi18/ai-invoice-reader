"""Turn an invoice PDF into structured fields with Claude.

Claude is given one tool, `record_invoice`, and is required to call it. With
`strict: True` the tool input always matches the JSON schema below, so the app
gets clean, typed fields instead of free text it would have to parse.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Any

from pypdf import PdfReader

from .checks import all_ok, run_checks
from .models import ExtractResult, Invoice

MAX_PDF_BYTES = 10 * 1024 * 1024
# Fewer characters than this means the PDF is probably a scan with no text layer.
MIN_TEXT_CHARS = 80

_nullable_string = {"type": ["string", "null"]}
_nullable_number = {"type": ["number", "null"]}

INVOICE_TOOL = {
    "name": "record_invoice",
    "description": "Record the fields of one supplier invoice exactly as printed on it.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "supplier_name", "supplier_address", "supplier_tax_id", "customer_name",
            "invoice_number", "invoice_date", "due_date", "currency", "line_items",
            "subtotal", "discount", "tax_rate_percent", "tax_amount", "shipping", "total", "notes",
        ],
        "properties": {
            "supplier_name": _nullable_string,
            "supplier_address": _nullable_string,
            "supplier_tax_id": {**_nullable_string, "description": "VAT, BIN, GST or tax registration number"},
            "customer_name": _nullable_string,
            "invoice_number": _nullable_string,
            "invoice_date": {**_nullable_string, "description": "YYYY-MM-DD"},
            "due_date": {**_nullable_string, "description": "YYYY-MM-DD"},
            "currency": {**_nullable_string, "description": "ISO 4217 code such as BDT, USD, EUR"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description", "quantity", "unit_price", "amount"],
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": _nullable_number,
                        "unit_price": _nullable_number,
                        "amount": _nullable_number,
                    },
                },
            },
            "subtotal": _nullable_number,
            "discount": {**_nullable_number, "description": "Discount as a positive amount"},
            "tax_rate_percent": {**_nullable_number, "description": "For example 15 for 15% VAT"},
            "tax_amount": _nullable_number,
            "shipping": _nullable_number,
            "total": {**_nullable_number, "description": "The final amount due"},
            "notes": {**_nullable_string, "description": "Payment terms or bank details, briefly"},
        },
    },
}

SYSTEM_PROMPT = """You read supplier invoices and record their fields with the record_invoice tool.

Rules:
- Copy every number exactly as printed, even if the arithmetic on the invoice looks wrong. The app checks the arithmetic separately, so do not correct anything.
- Use null for anything that isn't on the invoice. Never calculate or guess a missing value.
- Amounts are plain numbers without currency symbols or thousands separators.
- Dates become YYYY-MM-DD. If a date is ambiguous (03/04/2026), read it the way the supplier's country writes dates.
- Record one line item per row of the invoice table."""


def pdf_text(data: bytes) -> str:
    """Text of every page, labelled, so Claude knows where pages break."""
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append(f"--- Page {i} ---\n{(page.extract_text() or '').strip()}")
    return "\n\n".join(pages)


def build_message(data: bytes) -> tuple[list[dict[str, Any]], str]:
    """Send the text when the PDF has a text layer (cheaper); otherwise send the PDF itself."""
    text = pdf_text(data)
    if len(text.replace("--- Page", "").strip()) >= MIN_TEXT_CHARS:
        return [{"type": "text", "text": f"Invoice text:\n\n{text}"}], "text"
    return [
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(data).decode()},
        },
        {"type": "text", "text": "This is a scanned invoice. Record its fields."},
    ], "pdf"


def _client():
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
    return anthropic.Anthropic()


def extract_invoice(data: bytes, client: Any = None, model: str | None = None) -> ExtractResult:
    if not data.startswith(b"%PDF"):
        raise ValueError("That file isn't a PDF.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDFs must be 10 MB or smaller.")

    content, source = build_message(data)
    client = client or _client()
    response = client.messages.create(
        model=model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "record_invoice"},
        messages=[{"role": "user", "content": content}],
    )
    call = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if call is None:
        raise RuntimeError("Claude did not return invoice fields. Try again.")

    invoice = Invoice.model_validate(call.input)
    checks = run_checks(invoice)
    return ExtractResult(invoice=invoice, checks=checks, ok=all_ok(checks), source=source)
