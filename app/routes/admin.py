from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Submission, SubmissionBatch, SubmissionBatchItem, SubmissionRow, SubmissionSelection
from app.services.excel import build_batch_export_xlsx, build_export_xlsx
from app.services.torob import TorobClient, TorobClientError
from app.settings import settings
from app.template_utils import create_templates

router = APIRouter(prefix="/admin")
templates = create_templates()
ADMIN_COOKIE = "torobjan_admin"


@router.get("/login")
def login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "admin_login.html")


@router.post("/login")
def login(request: Request, password: str = Form(...)) -> Response:
    if not hmac.compare_digest(password, settings.admin_password):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "رمز اشتباه است."},
            status_code=401,
    )
    response = RedirectResponse("/admin/submissions", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE,
        settings.session_secret,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout() -> Response:
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE)
    return response


@router.get("/submissions")
def submissions(request: Request, db: Session = Depends(get_db)) -> Response:
    _require_admin(request)
    items = db.query(Submission).order_by(Submission.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin_submissions.html",
        {"submissions": items},
    )


@router.get("/submissions/{submission_id}")
def submission_detail(request: Request, submission_id: int, db: Session = Depends(get_db)) -> Response:
    _require_admin(request)
    submission = _get_submission(db, submission_id)
    return templates.TemplateResponse(
        request,
        "admin_detail.html",
        {"submission": submission, "rows": submission.rows, "batches": _visible_batches(submission)},
    )


@router.post("/submissions/{submission_id}/shop-id")
def update_shop_id(
    request: Request,
    submission_id: int,
    shop_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(request)
    submission = _get_submission(db, submission_id)
    submission.shop_id = (shop_id or "").strip() or None
    db.commit()
    return RedirectResponse(f"/admin/submissions/{submission_id}", status_code=303)


@router.get("/submissions/{submission_id}/export.xlsx")
def export_submission(
    request: Request,
    submission_id: int,
    batch: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(request)
    submission = _get_submission(db, submission_id)
    filename = f"submission-{submission.id}"
    if batch:
        selected_batch = _get_batch(submission, batch)
        content = build_batch_export_xlsx(submission, selected_batch)
        filename += f"-batch-{batch}"
    else:
        content = build_export_xlsx(submission, submission.rows)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


@router.get("/torob-health")
async def torob_health(request: Request) -> Response:
    _require_admin(request)
    client = TorobClient()
    try:
        results = await client.search_base_products("رب گوجه", size=1)
    except TorobClientError as exc:
        return Response(
            _torob_health_error_text(exc),
            status_code=503,
            media_type="text/plain; charset=utf-8",
        )
    finally:
        await client.close()

    first_result = results[0].name if results else "بدون نتیجه"
    base_url = settings.torob_base_url
    proxy_token_state = "set" if settings.torob_proxy_token else "empty"
    iw1_state = "set" if settings.torob_iw1_header else "empty"
    cookie_state = "set" if settings.torob_cookie else "empty"
    return Response(
        f"OK\nTOROB_BASE_URL={base_url}\nTOROB_PROXY_TOKEN={proxy_token_state}\nTOROB_IW1_HEADER={iw1_state}\nTOROB_COOKIE={cookie_state}\nfirst_result={first_result}",
        media_type="text/plain; charset=utf-8",
    )


def _require_admin(request: Request) -> None:
    cookie = request.cookies.get(ADMIN_COOKIE)
    if not cookie or not hmac.compare_digest(cookie, settings.session_secret):
        raise HTTPException(status_code=401, detail="Admin login required")


def _torob_health_error_text(exc: TorobClientError) -> str:
    if exc.code == "torob_timeout":
        return "FAILED: torob_timeout\nاگر VPN روشن است خاموشش کن و دوباره /admin/torob-health را بزن."
    if exc.code == "torob_bot_challenge":
        return (
            "FAILED: torob_bot_challenge\n"
            "ترب صفحه بررسی ربات برگردانده. TOROB_IW1_HEADER و whitelist بودن IP production را چک کن."
        )
    if exc.code == "torob_forbidden":
        return "FAILED: torob_forbidden\nدسترسی/session ترب برای این درخواست تایید نشده."
    return f"FAILED: {exc.code}\n{exc.public_message}"


def _visible_batches(submission: Submission) -> list[SubmissionBatch]:
    return sorted([batch for batch in submission.batches if batch.items], key=lambda item: item.created_at, reverse=True)


def _get_batch(submission: Submission, batch_id: int) -> SubmissionBatch:
    for batch in submission.batches:
        if batch.id == batch_id:
            return batch
    raise HTTPException(status_code=404, detail="Batch not found")


def _get_submission(db: Session, submission_id: int) -> Submission:
    submission = (
        db.query(Submission)
        .options(
            selectinload(Submission.rows).selectinload(SubmissionRow.matches),
            selectinload(Submission.rows).selectinload(SubmissionRow.selected_match),
            selectinload(Submission.rows).selectinload(SubmissionRow.selections).selectinload(SubmissionSelection.match),
            selectinload(Submission.batches).selectinload(SubmissionBatch.items).selectinload(SubmissionBatchItem.row),
            selectinload(Submission.batches).selectinload(SubmissionBatch.items).selectinload(SubmissionBatchItem.match),
        )
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission
