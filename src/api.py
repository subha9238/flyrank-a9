from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .pdf import generate_pdf


app = FastAPI(title="A8 PDF Report Generator")


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "report.db"
REPORTS_DIR = BASE_DIR / "reports"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=201)
def create_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.execute(
        """
        INSERT INTO reports (path, created_at)
        VALUES (?, ?)
        """,
        ("", datetime.now(timezone.utc).isoformat()),
    )

    report_id = cursor.lastrowid

    pdf_path = REPORTS_DIR / f"{report_id}.pdf"

    generate_pdf(pdf_path)

    connection.execute(
        """
        UPDATE reports
        SET path = ?
        WHERE id = ?
        """,
        (str(pdf_path), report_id),
    )

    connection.commit()
    connection.close()

    return {
        "id": report_id,
        "file": f"/reports/{report_id}/file",
    }


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    connection = sqlite3.connect(DB_PATH)

    row = connection.execute(
        """
        SELECT id, path, created_at
        FROM reports
        WHERE id = ?
        """,
        (report_id,),
    ).fetchone()

    connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    return {
        "id": row[0],
        "path": row[1],
        "created_at": row[2],
        "file": f"/reports/{row[0]}/file",
    }


@app.get("/reports/{report_id}/file")
def download_report(report_id: int):
    connection = sqlite3.connect(DB_PATH)

    row = connection.execute(
        """
        SELECT path
        FROM reports
        WHERE id = ?
        """,
        (report_id,),
    ).fetchone()

    connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    pdf_path = Path(row[0])

    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report file not found",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )