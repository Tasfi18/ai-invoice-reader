from conftest import PADMA, RUPSHA, FakeClient
from fastapi.testclient import TestClient
from invoice_reader.app import create_app
from invoice_reader.extract import extract_invoice


def client_for(tool_input):
    fake = FakeClient(tool_input)
    return TestClient(create_app(lambda data: extract_invoice(data, client=fake)))


def test_upload_returns_fields_and_checks(sample_bytes):
    api = client_for(RUPSHA)
    res = api.post("/api/extract", files={"file": ("inv.pdf", sample_bytes("rupsha-wholesale-line-error"), "application/pdf")})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["invoice"]["invoice_number"] == "RWT/26/1093"
    assert body["invoice"]["line_items"][1]["amount"] == "1470.00"  # exact decimals as strings
    assert {c["name"]: c["status"] for c in body["checks"]}["Line totals"] == "fail"


def test_correcting_a_field_reruns_the_checks():
    api = client_for(RUPSHA)
    fixed = {**RUPSHA, "line_items": [dict(li) for li in RUPSHA["line_items"]]}
    fixed["line_items"][1]["amount"] = 1740
    fixed["subtotal"] = 35660
    fixed["tax_amount"] = 1758
    fixed["total"] = 36918
    checks = api.post("/api/check", json=fixed).json()
    assert all(c["status"] != "fail" for c in checks)


def test_csv_download():
    res = client_for(PADMA).post("/api/export.csv", json=PADMA)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="PP-2026-0418.csv"' in res.headers["content-disposition"]


def test_non_pdf_upload_is_refused():
    res = client_for(PADMA).post("/api/extract", files={"file": ("a.txt", b"hello", "text/plain")})
    assert res.status_code == 422
    assert "isn't a PDF" in res.json()["detail"]


def test_serves_the_page():
    res = client_for(PADMA).get("/")
    assert res.status_code == 200
    assert "Invoice Reader" in res.text
