from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Submission, SubmissionBatch, SubmissionBatchItem, SubmissionRow, SubmissionSelection, utc_now
from app.services.excel import build_batch_export_xlsx, build_export_xlsx
from app.services.torob_bulk import TorobBulkAddClient, TorobBulkAddError, TorobBulkAddItem
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
    batches = _visible_batches(submission)
    return templates.TemplateResponse(
        request,
        "admin_detail.html",
        {
            "submission": submission,
            "rows": submission.rows,
            "batches": batches,
            "bulk_add_configured": bool(settings.torob_bulk_add_key),
            "admin_send_summary": _admin_send_summary(submission, batches),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
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


@router.post("/submissions/{submission_id}/rebuild-batch")
def rebuild_submission_batch(
    request: Request,
    submission_id: int,
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(request)
    submission = _get_submission(db, submission_id)
    created_count = _create_batch_from_unbatched_selections(db, submission)
    if created_count <= 0:
        return _admin_detail_redirect(submission.id, error="انتخاب قابل بازیابی برای ساخت ثبت ارسال پیدا نشد.")
    db.commit()
    return _admin_detail_redirect(submission.id, message=f"ثبت ارسال برای {created_count} کالا از انتخاب‌های قبلی ساخته شد.")


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


@router.get("/rows/{row_id}/source-image")
def row_source_image(request: Request, row_id: int, db: Session = Depends(get_db)) -> Response:
    _require_admin(request)
    row = db.query(SubmissionRow).filter(SubmissionRow.id == row_id).first()
    if row is None or not row.source_image_path:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(row.source_image_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@router.post("/submissions/{submission_id}/batches/{batch_id}/send-torob")
async def send_batch_to_torob(
    request: Request,
    submission_id: int,
    batch_id: int,
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(request)
    submission = _get_submission(db, submission_id)
    batch = _get_batch(submission, batch_id)
    if batch.status == "sent":
        return _admin_detail_redirect(submission.id, error="این ثبت قبلا به ترب ارسال شده است.")

    shop_id = _parse_shop_id(submission.shop_id)
    if shop_id is None:
        return _admin_detail_redirect(submission.id, error="اول Shop ID عددی فروشگاه را ذخیره کن.")

    torob_items, skipped_count = _torob_bulk_items(batch)
    if not torob_items:
        batch.status = "failed"
        batch.torob_skipped_count = skipped_count
        batch.torob_error_message = "این ثبت کالای انتخاب‌شده از ترب ندارد و مستقیم قابل ارسال نیست."
        db.commit()
        return _admin_detail_redirect(submission.id, error=batch.torob_error_message)

    batch.status = "sending"
    batch.torob_error_message = None
    batch.torob_response_text = None
    batch.torob_skipped_count = skipped_count
    db.commit()

    client = TorobBulkAddClient()
    try:
        result = await client.bulk_add(shop_id=shop_id, items=torob_items)
    except TorobBulkAddError as exc:
        batch.status = "failed"
        batch.torob_error_message = _bulk_add_error_text(exc)
        batch.torob_response_text = exc.response_text
        db.commit()
        return _admin_detail_redirect(submission.id, error=batch.torob_error_message)
    finally:
        await client.close()

    batch.status = "sent"
    batch.torob_sent_at = utc_now()
    batch.torob_sent_count = result.sent_count
    batch.torob_skipped_count = skipped_count
    batch.torob_response_text = result.response_text
    db.commit()
    message = f"{result.sent_count} کالا به ترب ارسال شد."
    if skipped_count:
        message += f" {skipped_count} کالای غیرتربی ارسال نشد."
    return _admin_detail_redirect(submission.id, message=message)


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


@router.get("/torob-bulk-health")
async def torob_bulk_health(request: Request) -> Response:
    _require_admin(request)
    client = TorobBulkAddClient()
    try:
        result = await client.health_check()
    finally:
        await client.close()

    bulk_key_state = "set" if settings.torob_bulk_add_key else "empty"
    iw1_state = "set" if settings.torob_iw1_header else "empty"
    lines = [
        "OK" if result.outcome in {"reachable", "auth_rejected"} else f"FAILED: {result.outcome}",
        f"TOROB_BULK_ADD_URL={settings.torob_bulk_add_url}",
        f"TOROB_BULK_ADD_KEY={bulk_key_state}",
        f"TOROB_IW1_HEADER={iw1_state}",
        f"status_code={result.status_code}",
        f"detail={result.detail}",
    ]
    status_code = 200 if result.outcome in {"reachable", "auth_rejected"} else 503
    return Response("\n".join(lines), status_code=status_code, media_type="text/plain; charset=utf-8")


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


def _admin_send_summary(submission: Submission, batches: list[SubmissionBatch]) -> dict[str, int]:
    unbatched_selection_count = _unbatched_selection_count(submission)
    return {
        "batch_count": len(batches),
        "pending_batch_count": len([batch for batch in batches if batch.status != "sent"]),
        "selection_count": sum(len(row.selections) for row in submission.rows),
        "unbatched_selection_count": unbatched_selection_count,
    }


def _unbatched_selection_count(submission: Submission) -> int:
    batched_selection_keys = {
        (item.row_id, item.match_id, str(item.final_price or ""))
        for batch in submission.batches
        for item in batch.items
    }
    count = 0
    for row in submission.rows:
        for selection in row.selections:
            key = (selection.row_id, selection.match_id, str(selection.final_price or ""))
            if key not in batched_selection_keys:
                count += 1
    return count


def _create_batch_from_unbatched_selections(db: Session, submission: Submission) -> int:
    batched_selection_keys = {
        (item.row_id, item.match_id, str(item.final_price or ""))
        for batch in submission.batches
        for item in batch.items
    }
    batch_items = []
    for row in submission.rows:
        for selection in row.selections:
            key = (selection.row_id, selection.match_id, str(selection.final_price or ""))
            if key in batched_selection_keys:
                continue
            if not selection.final_price:
                continue
            batch_items.append((row, selection))
    if not batch_items:
        return 0

    now = utc_now()
    batch = SubmissionBatch(
        submission_id=submission.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(batch)
    db.flush()
    for row, selection in batch_items:
        if row.submitted_at is None:
            row.submitted_at = selection.created_at or now
        db.add(
            SubmissionBatchItem(
                batch_id=batch.id,
                row_id=row.id,
                match_id=selection.match_id,
                final_price=selection.final_price,
                created_at=selection.created_at or now,
            )
        )
    submission.selected_rows = sum(len(row.selections) for row in submission.rows)
    if submission.status != "submitted":
        submission.status = "submitted"
    return len(batch_items)


def _get_batch(submission: Submission, batch_id: int) -> SubmissionBatch:
    for batch in submission.batches:
        if batch.id == batch_id:
            return batch
    raise HTTPException(status_code=404, detail="Batch not found")


def _parse_shop_id(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if not text.isdigit():
        return None
    return int(text)


def _torob_bulk_items(batch: SubmissionBatch) -> tuple[list[TorobBulkAddItem], int]:
    items: list[TorobBulkAddItem] = []
    skipped_count = 0
    sendable_sources = {"torob", "torob_image"}
    for item in batch.items:
        if (item.match.source or "torob") not in sendable_sources:
            skipped_count += 1
            continue
        price = _parse_positive_int(item.final_price)
        if price is None:
            skipped_count += 1
            continue
        items.append(TorobBulkAddItem(base_product_rk=item.match.base_prk, price=price))
    return items, skipped_count


def _parse_positive_int(value: object) -> int | None:
    try:
        amount = int(str(value or "").strip())
    except ValueError:
        return None
    return amount if amount > 0 else None


def _bulk_add_error_text(exc: TorobBulkAddError) -> str:
    if exc.code == "bot_challenge":
        return exc.public_message
    if exc.status_code:
        return f"{exc.public_message} ({exc.status_code})"
    return exc.public_message


def _admin_detail_redirect(submission_id: int, message: str | None = None, error: str | None = None) -> Response:
    params = []
    if message:
        params.append(("message", message))
    if error:
        params.append(("error", error))
    query = ""
    if params:
        from urllib.parse import urlencode

        query = "?" + urlencode(params)
    return RedirectResponse(f"/admin/submissions/{submission_id}{query}", status_code=303)


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
