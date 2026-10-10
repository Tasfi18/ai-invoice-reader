"""CSV export: one row per line item, with the invoice header repeated, ready for a spreadsheet or accounting import."""

from __future__ import annotations

import csv
import io

from .models import Invoice

COLUMNS = [
    "supplier", "supplier_tax_id", "invoice_number", "invoice_date", "due_date", "currency",
    "line", "description", "quantity", "unit_price", "amount",
    "subtotal", "discount", "tax_rate_percent", "tax_amount", "shipping", "total",
]


def _s(v) -> str:
    return "" if v is None else str(v)


def to_csv(inv: Invoice) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(COLUMNS)
    header = [inv.supplier_name, inv.supplier_tax_id, inv.invoice_number, inv.invoice_date, inv.due_date, inv.currency]
    totals = [inv.subtotal, inv.discount, inv.tax_rate_percent, inv.tax_amount, inv.shipping, inv.total]
    lines = inv.line_items or [None]
    for i, li in enumerate(lines, start=1):
        row = [li.description, li.quantity, li.unit_price, li.amount] if li else ["", "", "", ""]
        w.writerow([_s(v) for v in [*header, i if li else "", *row, *totals]])
    return out.getvalue()
