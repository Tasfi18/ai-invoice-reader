"""Arithmetic and sanity checks on an extracted invoice.

The AI copies numbers as printed; it is told not to fix them. These checks then
catch mistakes on the invoice itself (a wrong line total, a subtotal that doesn't
add up) as well as any misread digit, so nothing wrong reaches the books unnoticed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .models import Check, Invoice

CENT = Decimal("0.01")


def _fmt(d: Decimal | None) -> str:
    return "—" if d is None else f"{d:,.2f}"


def _close(a: Decimal, b: Decimal, tolerance: Decimal = CENT) -> bool:
    return abs(a - b) <= tolerance


def _parse_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def run_checks(inv: Invoice) -> list[Check]:
    checks: list[Check] = []

    # 1. Required fields
    missing = [label for label, value in [
        ("supplier", inv.supplier_name),
        ("invoice number", inv.invoice_number),
        ("invoice date", inv.invoice_date),
        ("total", inv.total),
    ] if value in (None, "")]
    checks.append(
        Check(name="Required fields", status="fail", message=f"Missing: {', '.join(missing)}.")
        if missing
        else Check(name="Required fields", status="pass", message="Supplier, invoice number, date and total are present.")
    )

    # 2. Each line: quantity × unit price = amount
    bad_lines = []
    checked = 0
    for i, li in enumerate(inv.line_items, start=1):
        if li.quantity is None or li.unit_price is None or li.amount is None:
            continue
        checked += 1
        expected = (li.quantity * li.unit_price).quantize(CENT)
        if not _close(expected, li.amount):
            bad_lines.append(f"Line {i} ({li.description or 'no description'}): {li.quantity} × {_fmt(li.unit_price)} = {_fmt(expected)}, invoice says {_fmt(li.amount)}")
    if checked == 0:
        checks.append(Check(name="Line totals", status="skip", message="No line has quantity, unit price and amount together."))
    elif bad_lines:
        checks.append(Check(name="Line totals", status="fail", message="; ".join(bad_lines) + "."))
    else:
        checks.append(Check(name="Line totals", status="pass", message=f"All {checked} lines multiply out correctly."))

    # 3. Lines add up to the subtotal
    amounts = [li.amount for li in inv.line_items if li.amount is not None]
    if inv.subtotal is None or not amounts:
        checks.append(Check(name="Subtotal", status="skip", message="No subtotal or no line amounts to compare."))
    else:
        s = sum(amounts, Decimal("0"))
        checks.append(
            Check(name="Subtotal", status="pass", message=f"Lines add up to the subtotal ({_fmt(s)}).")
            if _close(s, inv.subtotal)
            else Check(name="Subtotal", status="fail", message=f"Lines add up to {_fmt(s)}, but the subtotal says {_fmt(inv.subtotal)} (difference {_fmt(inv.subtotal - s)}).")
        )

    # 4. Tax matches the stated rate (allowing for rounding to the nearest unit)
    if inv.tax_rate_percent is None or inv.tax_amount is None or inv.subtotal is None:
        checks.append(Check(name="Tax", status="skip", message="No tax rate, tax amount or subtotal to compare."))
    else:
        base = inv.subtotal - (inv.discount or 0)
        expected = (base * inv.tax_rate_percent / 100).quantize(CENT)
        checks.append(
            Check(name="Tax", status="pass", message=f"{inv.tax_rate_percent}% of {_fmt(base)} is {_fmt(expected)}, as stated.")
            if _close(expected, inv.tax_amount, Decimal("1.00"))
            else Check(name="Tax", status="fail", message=f"{inv.tax_rate_percent}% of {_fmt(base)} is {_fmt(expected)}, but the invoice says {_fmt(inv.tax_amount)}.")
        )

    # 5. Subtotal − discount + tax + shipping = total
    if inv.subtotal is None or inv.total is None:
        checks.append(Check(name="Grand total", status="skip", message="No subtotal or total to compare."))
    else:
        t = inv.subtotal - (inv.discount or 0) + (inv.tax_amount or 0) + (inv.shipping or 0)
        checks.append(
            Check(name="Grand total", status="pass", message=f"Subtotal, discount, tax and shipping give the total ({_fmt(t)}).")
            if _close(t, inv.total)
            else Check(name="Grand total", status="fail", message=f"Subtotal, discount, tax and shipping give {_fmt(t)}, but the total says {_fmt(inv.total)}.")
        )

    # 6. Dates make sense
    issued, due = _parse_date(inv.invoice_date), _parse_date(inv.due_date)
    if inv.invoice_date and not issued:
        checks.append(Check(name="Dates", status="fail", message=f'Invoice date "{inv.invoice_date}" is not a valid date.'))
    elif issued and due and due < issued:
        checks.append(Check(name="Dates", status="fail", message=f"Due date {due} is before the invoice date {issued}."))
    elif issued:
        checks.append(Check(name="Dates", status="pass", message="Dates are valid." + (f" Payment due {due}." if due else "")))
    else:
        checks.append(Check(name="Dates", status="skip", message="No invoice date."))

    return checks


def all_ok(checks: list[Check]) -> bool:
    return not any(c.status == "fail" for c in checks)
