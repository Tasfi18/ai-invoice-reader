"""Web app: upload an invoice PDF, review the fields and checks, export CSV or JSON."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from .checks import run_checks
from .export import to_csv
from .extract import MAX_PDF_BYTES, extract_invoice
from .models import Check, ExtractResult, Invoice

STATIC = Path(__file__).resolve().parent.parent / "static"


def _load_env() -> None:
    """Read KEY=value lines from .env, so the API key never has to be typed in a shell."""
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def create_app(extractor: Callable[[bytes], ExtractResult] = extract_invoice) -> FastAPI:
    _load_env()
    app = FastAPI(title="Invoice Reader", version="1.0.0")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.post("/api/extract", response_model=ExtractResult)
    async def extract(file: UploadFile = File(...)):
        data = await file.read(MAX_PDF_BYTES + 1)
        try:
            return extractor(data)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

    @app.post("/api/check", response_model=list[Check])
    def check(invoice: Invoice):
        """Re-run the checks after the user corrects a field."""
        return run_checks(invoice)

    @app.post("/api/export.csv", response_class=PlainTextResponse)
    def export_csv(invoice: Invoice):
        name = (invoice.invoice_number or "invoice").replace("/", "-")
        return PlainTextResponse(
            to_csv(invoice),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
        )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
