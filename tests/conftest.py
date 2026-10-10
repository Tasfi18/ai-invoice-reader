from pathlib import Path
from types import SimpleNamespace

import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

# What Claude returns for each sample: numbers copied exactly as printed.
PADMA = {
    "supplier_name": "Padma Packaging Ltd.",
    "supplier_address": "Plot 7, BSCIC Industrial Area, Khulna",
    "supplier_tax_id": "000123456-0101",
    "customer_name": "Corner Store",
    "invoice_number": "PP-2026-0418",
    "invoice_date": "2026-10-02",
    "due_date": "2026-10-17",
    "currency": "BDT",
    "line_items": [
        {"description": "Corrugated carton 12x10x8 in", "quantity": 200, "unit_price": 38.5, "amount": 7700},
        {"description": "Brown packing tape 2 in x 100 m", "quantity": 24, "unit_price": 145, "amount": 3480},
        {"description": "Bubble wrap roll 1 m x 50 m", "quantity": 6, "unit_price": 890, "amount": 5340},
        {"description": "Printed carry bag, medium", "quantity": 500, "unit_price": 6.2, "amount": 3100},
        {"description": "Thermal receipt roll 80 mm", "quantity": 40, "unit_price": 72, "amount": 2880},
    ],
    "subtotal": 22500,
    "discount": None,
    "tax_rate_percent": 15,
    "tax_amount": 3375,
    "shipping": 350,
    "total": 26225,
    "notes": "Payment within 15 days by bank transfer.",
}

RUPSHA = {
    **{k: None for k in PADMA},
    "supplier_name": "Rupsha Wholesale Traders",
    "supplier_address": "45 KDA Avenue, Khulna",
    "supplier_tax_id": "000987654-0202",
    "customer_name": "Corner Store",
    "notes": "Payment within 15 days by bank transfer.",
    "invoice_number": "RWT/26/1093",
    "invoice_date": "2026-10-05",
    "due_date": "2026-10-20",
    "currency": "BDT",
    "line_items": [
        {"description": "Basmati rice 5 kg, bag", "quantity": 20, "unit_price": 910, "amount": 18200},
        {"description": "Red lentils 1 kg", "quantity": 12, "unit_price": 145, "amount": 1470},  # printed wrong: should be 1,740
        {"description": "Sunflower oil 1 L, carton of 12", "quantity": 3, "unit_price": 2880, "amount": 8640},
        {"description": "Black tea 400 g", "quantity": 24, "unit_price": 295, "amount": 7080},
    ],
    "subtotal": 35390,
    "discount": 500,
    "tax_rate_percent": 5,
    "tax_amount": 1744.5,
    "total": 36634.5,
}


class FakeClient:
    """Stands in for anthropic.Anthropic(): records the request, returns a tool call."""

    def __init__(self, tool_input: dict):
        self.tool_input = tool_input
        self.requests: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name="record_invoice", input=self.tool_input)])


@pytest.fixture
def sample_bytes():
    return lambda name: (SAMPLES / f"{name}.pdf").read_bytes()
