from __future__ import annotations

from pathlib import Path
import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal, get_db
from app.models import Submission, SubmissionRow, SubmissionSelection, TorobMatch
from app.services.excel import ExcelParseError, build_template_xlsx, parse_products_excel
from app.services.torob import TorobClient, TorobClientError
from app.settings import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request) -> Response:
    return templates.TemplateResponse(request, "index.html")


@router.get("/template.xlsx")
def template_xlsx() -> Response:
    return Response(
        build_template_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="torobjan-template.xlsx"'},
    )


@router.post("/uploads")
async def upload_products(
    request: Request,
    background_tasks: BackgroundTasks,
    store_name: str = Form(...),
    seller_phone: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Response:
    store_name = store_name.strip()
    if not store_name:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "نام فروشگاه الزامی است."},
            status_code=400,
        )
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "فقط فایل xls یا xlsx قابل قبول است."},
            status_code=400,
        )

    content = await file.read()
    try:
        parsed_rows = parse_products_excel(content, file.filename)
    except ExcelParseError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": str(exc)},
            status_code=400,
        )
    submission = Submission(
        store_name=store_name,
        seller_phone=(seller_phone or "").strip() or None,
        original_filename=file.filename,
        status="processing",
    )
    try:
        db.add(submission)
        db.commit()
        db.refresh(submission)
    except OperationalError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "دیتابیس محلی موقتا قفل است. اگر سرور قبلی باز مانده، آن را ببند و دوباره تلاش کن."},
            status_code=503,
        )

    submission.stored_file_path = _store_upload_file(submission.id, file.filename, content)
    submission.total_rows = len([row for row in parsed_rows if row.product_name])
    for parsed in parsed_rows:
        db.add(_row_from_parsed(submission.id, parsed))
    if submission.total_rows == 0:
        submission.status = "ready"
    db.commit()

    if submission.total_rows > 0:
        background_tasks.add_task(process_submission_matches, submission.id)

    return templates.TemplateResponse(request, "processing.html", {"submission": submission})


async def process_submission_matches(submission_id: int) -> None:
    db = SessionLocal()
    client = TorobClient()
    consecutive_torob_failures = 0
    successful_torob_searches = 0
    try:
        submission = _get_submission(db, submission_id)
        rows = [row for row in submission.rows if row.input_product_name and not row.error_message]
        for row in rows:
            try:
                results = await client.search_base_products(row.input_product_name or "", size=5)
            except TorobClientError as exc:
                if successful_torob_searches == 0:
                    submission.status = "failed"
                    submission.error_message = _global_torob_error_message(exc)
                    db.commit()
                    return
                row.error_message = _row_torob_error_message(exc)
                db.commit()
                consecutive_torob_failures += 1
                if _should_pause_batch(exc, consecutive_torob_failures):
                    _mark_remaining_rows_as_waiting(db, rows, row)
                    submission.status = "ready"
                    db.commit()
                    return
                continue
            consecutive_torob_failures = 0
            successful_torob_searches += 1
            if not results:
                row.error_message = "نتیجه‌ای در ترب پیدا نشد."
                db.commit()
                continue
            for result in results:
                db.add(
                    TorobMatch(
                        row_id=row.id,
                        rank=result.rank,
                        base_prk=result.base_prk,
                        name=result.name,
                        price=result.price,
                        price_text=result.price_text,
                        image_url=result.image_url,
                        product_url=result.product_url,
                        is_already_added=result.is_already_added,
                    )
                )
            db.commit()
        submission.status = "ready"
        db.commit()
    except Exception as exc:
        db.rollback()
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if submission is not None:
            submission.status = "failed"
            submission.error_message = f"پردازش با خطا متوقف شد: {exc}"
            db.commit()
    finally:
        await client.close()
        db.close()


def _row_from_parsed(submission_id: int, parsed) -> SubmissionRow:
    return SubmissionRow(
        submission_id=submission_id,
        input_row=parsed.input_row,
        input_product_name=parsed.product_name,
        input_price=parsed.price,
        barcode=parsed.barcode,
        brand=parsed.brand,
        description=parsed.description,
        error_message=parsed.error_message,
    )


def _global_torob_error_message(exc: TorobClientError) -> str:
    if exc.code == "torob_forbidden":
        return _forbidden_torob_error_message()
    if exc.code == "torob_gateway_not_found":
        return (
            "مسیر gateway ترب پیدا نشد و سرویس proxy پاسخ 404 برگرداند. "
            "این مشکل مربوط به فایل اکسل نیست؛ deploy یا route سرویس gateway باید بررسی شود."
        )
    if exc.code == "torob_bot_challenge":
        return (
            "ترب فعلا درخواست‌های جستجوی خودکار را تایید نمی‌کند و صفحه بررسی ربات برمی‌گرداند. "
            "این مشکل مربوط به فایل اکسل نیست. کمی بعد دوباره تست کن یا cookie/session مجاز ترب را در تنظیمات قرار بده."
        )
    if exc.code == "torob_timeout":
        return (
            "ارتباط با ترب timeout شد. اگر VPN روشن است خاموشش کن و دوباره تست بگیر. "
            "این مشکل مربوط به فایل اکسل نیست."
        )
    return (
        "ارتباط با ترب الان پایدار نیست و چند جستجو پشت سر هم ناموفق شد. "
        "این مشکل مربوط به فایل اکسل نیست. کمی بعد دوباره تست کن؛ اگر تکرار شد باید دسترسی/session مجاز ترب را برای سرویس تنظیم کنیم."
    )


def _should_pause_batch(exc: TorobClientError, consecutive_failures: int) -> bool:
    if exc.code in {
        "torob_forbidden",
        "torob_bot_challenge",
        "torob_gateway_not_found",
        "torob_rate_limited",
        "torob_gateway_error",
    }:
        return True
    return consecutive_failures >= 3


def _row_torob_error_message(exc: TorobClientError) -> str:
    if exc.code == "torob_gateway_not_found":
        return "مسیر gateway ترب پیدا نشد. کمی بعد تلاش مجدد بزن."
    if exc.code == "torob_rate_limited":
        return "gateway ترب فعلا شلوغ است. کمی بعد تلاش مجدد بزن."
    if exc.code == "torob_gateway_error":
        return "gateway ترب پاسخ پایدار نداد. کمی بعد تلاش مجدد بزن."
    if exc.code == "torob_bot_challenge":
        return "جستجو از gateway ترب کامل نشد. کمی بعد تلاش مجدد بزن."
    if exc.code == "torob_forbidden":
        return "دسترسی gateway ترب برای این جستجو تایید نشد."
    return exc.public_message


def _mark_remaining_rows_as_waiting(db: Session, rows: list[SubmissionRow], current_row: SubmissionRow) -> None:
    mark = False
    for row in rows:
        if row.id == current_row.id:
            mark = True
            continue
        if mark and not row.matches and not row.error_message:
            row.error_message = "جستجو هنوز کامل نشده. کمی بعد تلاش مجدد بزن."
    db.commit()


def _forbidden_torob_error_message() -> str:
    return (
        "اتصال به ترب مجاز نیست. جستجوی محصولات از ترب برای این درخواست تایید نشد. "
        "این مشکل مربوط به فایل اکسل نیست."
    )


@router.get("/submissions/{submission_id}/processing-status")
def processing_status(request: Request, submission_id: int, db: Session = Depends(get_db)) -> Response:
    submission = _get_submission(db, submission_id)
    if submission.status == "ready":
        return Response(status_code=204, headers={"HX-Redirect": f"/submissions/{submission.id}/match"})
    if submission.status == "failed":
        return templates.TemplateResponse(
            request,
            "partials/processing_failed.html",
            {"submission": submission},
            headers={"X-Processing-State": "failed"},
        )
    total_count = len([row for row in submission.rows if row.input_product_name])
    processed_count = len(
        [
            row
            for row in submission.rows
            if row.input_product_name and (row.error_message or row.matches)
        ]
    )
    progress_percent = int((processed_count / total_count) * 100) if total_count else 100
    return templates.TemplateResponse(
        request,
        "partials/processing_status.html",
        {
            "submission": submission,
            "total_count": total_count,
            "processed_count": processed_count,
            "progress_percent": progress_percent,
        },
    )


@router.get("/submissions/{submission_id}/match")
def match_submission(request: Request, submission_id: int, db: Session = Depends(get_db)) -> Response:
    return _render_match(request, db, submission_id)


@router.post("/rows/{row_id}/retry")
async def retry_row_search(request: Request, row_id: int, db: Session = Depends(get_db)) -> Response:
    row = _get_row(db, row_id)
    if not row.input_product_name:
        row.error_message = "نام محصول برای جستجو خالی است."
        db.commit()
        return _render_row_card(request, row)

    for match in list(row.matches):
        db.delete(match)
    for selection in list(row.selections):
        db.delete(selection)
    row.error_message = None
    row.selected_match_id = None
    row.final_price = None
    db.commit()
    db.refresh(row)

    client = TorobClient()
    try:
        results = await client.search_base_products(row.input_product_name, size=5)
    except TorobClientError as exc:
        row.error_message = exc.public_message
        db.commit()
        return _render_row_card(request, row)
    finally:
        await client.close()

    if not results:
        row.error_message = "نتیجه‌ای در ترب پیدا نشد."
        db.commit()
        return _render_row_card(request, row)

    for result in results:
        db.add(
            TorobMatch(
                row_id=row.id,
                rank=result.rank,
                base_prk=result.base_prk,
                name=result.name,
                price=result.price,
                price_text=result.price_text,
                image_url=result.image_url,
                product_url=result.product_url,
                is_already_added=result.is_already_added,
            )
        )
    db.commit()
    db.refresh(row)
    return _render_row_card(request, row)


def _store_upload_file(submission_id: int, filename: str, content: bytes) -> str:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(filename).name).strip("-") or "products.xlsx"
    path = upload_dir / f"{submission_id}-{safe_name}"
    path.write_bytes(content)
    return str(path)


@router.post("/submissions/{submission_id}/confirm")
async def confirm_submission(
    request: Request,
    submission_id: int,
    db: Session = Depends(get_db),
) -> Response:
    form = await request.form()
    submission = _get_submission(db, submission_id)
    selected_count = 0
    for row in submission.rows:
        if row.error_message:
            continue
        for selection in list(row.selections):
            db.delete(selection)
        selected_values = [str(value) for value in form.getlist(f"selected_{row.id}")]
        price_value = str(form.get(f"price_{row.id}") or "").strip()
        row.selected_match_id = None
        row.final_price = None
        if not selected_values or not price_value:
            continue
        valid_matches = [item for item in row.matches if str(item.id) in selected_values]
        if not valid_matches:
            continue
        row.selected_match_id = valid_matches[0].id
        row.final_price = price_value
        selected_count += len(valid_matches)
        for match in valid_matches:
            db.add(SubmissionSelection(row_id=row.id, match_id=match.id, final_price=price_value))
    submission.selected_rows = selected_count
    submission.status = "submitted"
    db.commit()
    return templates.TemplateResponse(request, "success.html", {"submission": submission})


def _render_match(request: Request, db: Session, submission_id: int) -> Response:
    submission = _get_submission(db, submission_id)
    parseable_rows = [row for row in submission.rows if row.input_product_name]
    valid_rows = [row for row in submission.rows if row.input_product_name and row.matches and not row.error_message]
    invalid_rows = [row for row in submission.rows if row.error_message]
    return templates.TemplateResponse(
        request,
        "match.html",
        {
            "submission": submission,
            "rows": submission.rows,
            "parseable_count": len(parseable_rows),
            "valid_count": len(valid_rows),
            "invalid_rows": invalid_rows,
        },
    )


def _render_row_card(request: Request, row: SubmissionRow) -> Response:
    return templates.TemplateResponse(request, "partials/row_card.html", {"row": row})


def _get_row(db: Session, row_id: int) -> SubmissionRow:
    row = (
        db.query(SubmissionRow)
        .options(selectinload(SubmissionRow.matches))
        .options(selectinload(SubmissionRow.selections))
        .filter(SubmissionRow.id == row_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return row


def _get_submission(db: Session, submission_id: int) -> Submission:
    submission = (
        db.query(Submission)
        .options(
            selectinload(Submission.rows).selectinload(SubmissionRow.matches),
            selectinload(Submission.rows).selectinload(SubmissionRow.selections),
        )
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission
