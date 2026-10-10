from decimal import Decimal

from conftest import PADMA, RUPSHA
from invoice_reader.checks import all_ok, run_checks
from invoice_reader.models import Invoice


def by_name(checks):
    return {c.name: c for c in checks}


def test_a_correct_invoice_passes_every_check():
    checks = run_checks(Invoice.model_validate(PADMA))
    assert all_ok(checks)
    assert [c.status for c in checks] == ["pass"] * 6


def test_catches_a_wrong_line_total_printed_on_the_invoice():
    checks = by_name(run_checks(Invoice.model_validate(RUPSHA)))
    assert checks["Line totals"].status == "fail"
    assert "Line 2 (Red lentils 1 kg): 12 × 145.00 = 1,740.00, invoice says 1,470.00" in checks["Line totals"].message
    # The rest of the invoice is consistent with the printed figures.
    assert checks["Subtotal"].status == "pass"
    assert checks["Tax"].status == "pass"
    assert checks["Grand total"].status == "pass"


def test_catches_a_subtotal_that_does_not_add_up():
    inv = Invoice.model_validate({**PADMA, "subtotal": 22050})
    c = by_name(run_checks(inv))["Subtotal"]
    assert c.status == "fail"
    assert "Lines add up to 22,500.00, but the subtotal says 22,050.00" in c.message


def test_catches_a_total_that_does_not_match():
    c = by_name(run_checks(Invoice.model_validate({**PADMA, "total": 26525})))["Grand total"]
    assert c.status == "fail"
    assert "give 26,225.00" in c.message


def test_tax_allows_rounding_to_the_nearest_taka_but_not_more():
    assert by_name(run_checks(Invoice.model_validate({**PADMA, "tax_amount": 3375.6, "total": 26225.6})))["Tax"].status == "pass"
    assert by_name(run_checks(Invoice.model_validate({**PADMA, "tax_amount": 3400, "total": 26250})))["Tax"].status == "fail"


def test_tax_is_worked_out_after_the_discount():
    c = by_name(run_checks(Invoice.model_validate(RUPSHA)))["Tax"]
    assert c.message == "5% of 34,890.00 is 1,744.50, as stated."


def test_missing_fields_and_bad_dates():
    inv = Invoice.model_validate({**PADMA, "invoice_number": None, "due_date": "2026-09-01"})
    checks = by_name(run_checks(inv))
    assert checks["Required fields"].message == "Missing: invoice number."
    assert checks["Dates"].status == "fail"
    assert by_name(run_checks(Invoice.model_validate({**PADMA, "invoice_date": "05/10/2026"})))["Dates"].status == "fail"


def test_checks_are_skipped_not_failed_when_data_is_absent():
    checks = by_name(run_checks(Invoice(supplier_name="X", invoice_number="1", invoice_date="2026-10-01", total=Decimal("10"))))
    assert checks["Line totals"].status == "skip"
    assert checks["Subtotal"].status == "skip"
    assert checks["Tax"].status == "skip"
    assert all_ok(list(checks.values()))


def test_money_is_exact_decimal_not_float():
    inv = Invoice.model_validate({"line_items": [{"description": "x", "quantity": 3, "unit_price": 0.1, "amount": 0.3}], "subtotal": "1,234.5"})
    assert inv.line_items[0].unit_price == Decimal("0.10")
    assert inv.subtotal == Decimal("1234.50")
    assert by_name(run_checks(inv))["Line totals"].status == "pass"  # 3 × 0.10 = 0.30 exactly
