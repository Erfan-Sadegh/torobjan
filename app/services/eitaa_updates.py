from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Store, Submission, SubmissionRow, SubmissionSelection, TorobMatch
from app.services.eitaa import EitaaProductDraft, extract_eitaa_products
from app.services.torob import TorobSearchResult
from app.services.update_matching import copy_match_for_row, find_known_store_match, search_result_match_for_row


@dataclass(frozen=True)
class EitaaUpdatePreviewResult:
    preview_submission_id: int | None
    processed_update_count: int
    latest_update_id: int | None


@dataclass(frozen=True)
class _PreviewDraft:
    product: EitaaProductDraft
    operation: str
    known_match: TorobMatch | None
    torob_results: list[TorobSearchResult]
    error_message: str | None = None


def create_eitaa_update_preview(
    db: Session,
    store: Store,
    updates: list[dict],
    torob_results_by_name: dict[str, list[TorobSearchResult]] | None = None,
) -> EitaaUpdatePreviewResult:
    torob_results_by_name = torob_results_by_name or {}
    last_seen = int(store.eitaa_last_update_id or 0)
    accepted_updates: list[tuple[int, dict]] = []
    preview_drafts: list[_PreviewDraft] = []

    for update in updates:
        update_id = _to_int(update.get("update_id"))
        if update_id <= last_seen:
            continue
        message = _update_message(update)
        if message is None:
            continue
        accepted_updates.append((update_id, message))
        for product in extract_eitaa_products([message], max_products=20):
            if not product.price_toman:
                continue
            known_match = _latest_known_match_for_message(db, store.id, product.message_id)
            if known_match is None:
                known_match = find_known_store_match(db, store.id, product.product_name)
            torob_results = [] if known_match is not None else torob_results_by_name.get(product.product_name, [])
            if known_match is not None:
                operation = "price_update"
                error_message = None
            elif torob_results:
                operation = "add"
                error_message = None
            else:
                operation = "needs_review"
                error_message = "این محصول هنوز به محصول قبلی فروشگاه یا گزینه قابل انتخاب ترب وصل نشده است."
            preview_drafts.append(
                _PreviewDraft(
                    product=product,
                    operation=operation,
                    known_match=known_match,
                    torob_results=torob_results,
                    error_message=error_message,
                )
            )

    if not accepted_updates:
        return EitaaUpdatePreviewResult(
            preview_submission_id=None,
            processed_update_count=0,
            latest_update_id=None,
        )

    preview_submission_id: int | None = None
    if preview_drafts:
        preview_submission = Submission(
            store_id=store.id,
            store_name=store.name,
            seller_phone=store.seller_phone,
            shop_id=store.shop_id,
            source="eitaa_update",
            source_ref=store.eitaa_channel_id,
            operation="price_update",
            status="ready",
            price_unit="toman",
            total_rows=len(preview_drafts),
            selected_rows=0,
        )
        db.add(preview_submission)
        db.flush()
        selected_count = 0
        for input_row, draft in enumerate(preview_drafts, start=1):
            row = SubmissionRow(
                submission_id=preview_submission.id,
                input_row=input_row,
                input_product_name=draft.product.product_name,
                input_price=draft.product.price_toman,
                description=draft.product.description,
                source_message_id=draft.product.message_id,
                operation=draft.operation,
                final_price=draft.product.price_toman,
                error_message=draft.error_message,
            )
            db.add(row)
            db.flush()
            if draft.known_match is not None:
                match = copy_match_for_row(row.id, draft.known_match)
                db.add(match)
                db.flush()
                row.selected_match_id = match.id
                db.add(
                    SubmissionSelection(
                        row_id=row.id,
                        match_id=match.id,
                        final_price=draft.product.price_toman,
                    )
                )
                selected_count += 1
                continue
            for rank, result in enumerate(draft.torob_results):
                db.add(search_result_match_for_row(row.id, result, rank=rank))
                db.flush()
        preview_submission.selected_rows = selected_count
        preview_submission_id = preview_submission.id

    latest_update_id = max(update_id for update_id, _message in accepted_updates)
    store.eitaa_last_update_id = max(last_seen, latest_update_id)
    db.flush()
    return EitaaUpdatePreviewResult(
        preview_submission_id=preview_submission_id,
        processed_update_count=len(accepted_updates),
        latest_update_id=latest_update_id,
    )


def _update_message(update: dict) -> dict | None:
    for key in ("channel_post", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    return None


def _latest_known_match_for_message(db: Session, store_id: int | None, source_message_id: str) -> TorobMatch | None:
    if store_id is None or not source_message_id:
        return None
    rows = (
        db.query(SubmissionRow)
        .join(Submission, SubmissionRow.submission_id == Submission.id)
        .filter(Submission.store_id == store_id)
        .filter(Submission.operation == "add")
        .filter(SubmissionRow.source_message_id == source_message_id)
        .order_by(SubmissionRow.id.desc())
        .all()
    )
    for row in rows:
        if row.selected_match is not None:
            return row.selected_match
        if row.selections:
            return row.selections[-1].match
    return None


def _to_int(value: object) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0
