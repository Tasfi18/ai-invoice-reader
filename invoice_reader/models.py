"""The invoice fields the app extracts, and the result of each arithmetic check."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

TWO_PLACES = Decimal("0.01")


def to_decimal(v, places: bool = False):
    """Amounts are exact decimals, never floats. Money is rounded to two places."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    d = Decimal(str(v).replace(",", ""))
    return d.quantize(TWO_PLACES) if places else d


class LineItem(BaseModel):
    description: str = ""
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    amount: Optional[Decimal] = None

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v):
        return to_decimal(v)

    @field_validator("unit_price", "amount", mode="before")
    @classmethod
    def _money(cls, v):
        return to_decimal(v, places=True)


class Invoice(BaseModel):
    supplier_name: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    tax_rate_percent: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    shipping: Optional[Decimal] = None
    total: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("subtotal", "discount", "tax_amount", "shipping", "total", mode="before")
    @classmethod
    def _money(cls, v):
        return to_decimal(v, places=True)

    @field_validator("tax_rate_percent", mode="before")
    @classmethod
    def _rate(cls, v):
        return to_decimal(v)


class Check(BaseModel):
    name: str
    status: Literal["pass", "fail", "skip"]
    message: str


class ExtractResult(BaseModel):
    invoice: Invoice
    checks: list[Check]
    ok: bool
    # "text" when the PDF had a text layer; "pdf" when Claude read the pages
    # themselves (scanned invoices).
    source: Literal["text", "pdf"]
