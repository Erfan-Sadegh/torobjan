from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Submission, SubmissionRow, TorobMatch
from app.services.eitaa import score_product_match
from app.settings import settings


def find_known_store_match(db: Session, store_id: int | None, product_name: str) -> TorobMatch | None:
    if store_id is None or not product_name:
        return None
    rows = (
        db.query(SubmissionRow)
        .join(Submission, SubmissionRow.submission_id == Submission.id)
        .filter(Submission.store_id == store_id)
        .filter(Submission.operation == "add")
        .filter(SubmissionRow.input_product_name.isnot(None))
        .order_by(SubmissionRow.id.desc())
        .all()
    )
    best_row: SubmissionRow | None = None
    best_score = 0.0
    for row in rows:
        match = _selected_match(row)
        if match is None:
            continue
        score = max(
            score_product_match(product_name, row.input_product_name or ""),
            score_product_match(product_name, match.name),
        )
        if score > best_score:
            best_score = score
            best_row = row
    if best_row is None or best_score < settings.eitaa_auto_match_threshold:
        return None
    return _selected_match(best_row)


def copy_match_for_row(row_id: int, match: TorobMatch) -> TorobMatch:
    return TorobMatch(
        row_id=row_id,
        source=match.source,
        rank=0,
        base_prk=match.base_prk,
        name=match.name,
        price=match.price,
        price_text=match.price_text,
        image_url=match.image_url,
        product_url=match.product_url,
        is_already_added=match.is_already_added,
    )


def search_result_match_for_row(row_id: int, result, rank: int) -> TorobMatch:
    return TorobMatch(
        row_id=row_id,
        source=getattr(result, "source", "torob") or "torob",
        rank=rank,
        base_prk=result.base_prk,
        name=result.name,
        price=result.price,
        price_text=result.price_text,
        image_url=result.image_url,
        product_url=result.product_url,
        is_already_added=getattr(result, "is_already_added", False),
    )


def _selected_match(row: SubmissionRow) -> TorobMatch | None:
    if row.selected_match is not None:
        return row.selected_match
    if row.selections:
        return row.selections[-1].match
    return None
