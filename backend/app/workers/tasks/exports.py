"""Async export tasks — generate PDF/Excel reports in the background."""

from __future__ import annotations

from backend.app.workers.celery_app import celery


@celery.task(name="backend.app.workers.tasks.exports.generate_report_pdf")
def generate_report_pdf(report_type: str, params: dict) -> dict:
    """Generate a PDF report and store it via FileStorageService.

    Returns a dict with ``{"file_path": "...", "status": "done"}``.
    """
    from backend.app.core.database import SessionLocal
    from backend.app.services.file_service import FileStorageService

    db = SessionLocal()
    try:
        # Delegate to the existing synchronous PDF export functions
        from backend.app.services import export_pdf

        generator = getattr(export_pdf, f"export_{report_type}_pdf", None)
        if generator is None:
            return {"status": "error", "detail": f"Unknown report: {report_type}"}

        buf = generator(db, **params)
        fs = FileStorageService()
        path = fs.save(f"reports/{report_type}.pdf", buf.getvalue())
        return {"status": "done", "file_path": path}
    finally:
        db.close()


@celery.task(name="backend.app.workers.tasks.exports.generate_report_excel")
def generate_report_excel(report_type: str, params: dict) -> dict:
    """Generate an Excel report and store it via FileStorageService."""
    from backend.app.core.database import SessionLocal
    from backend.app.services.file_service import FileStorageService

    db = SessionLocal()
    try:
        from backend.app.services import export_excel

        generator = getattr(export_excel, f"export_{report_type}_excel", None)
        if generator is None:
            return {"status": "error", "detail": f"Unknown report: {report_type}"}

        buf = generator(db, **params)
        fs = FileStorageService()
        path = fs.save(f"reports/{report_type}.xlsx", buf.getvalue())
        return {"status": "done", "file_path": path}
    finally:
        db.close()
