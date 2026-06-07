from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    seller_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="matching", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    rows: Mapped[list[SubmissionRow]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionRow.input_row",
    )


class SubmissionRow(Base):
    __tablename__ = "submission_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False, index=True)
    input_row: Mapped[int] = mapped_column(Integer, nullable=False)
    input_product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(120), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    selected_match_id: Mapped[int | None] = mapped_column(ForeignKey("torob_matches.id"), nullable=True)
    has_more_matches: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_search_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="rows")
    matches: Mapped[list[TorobMatch]] = relationship(
        back_populates="row",
        cascade="all, delete-orphan",
        foreign_keys="TorobMatch.row_id",
        order_by="TorobMatch.rank",
    )
    selected_match: Mapped[TorobMatch | None] = relationship(
        foreign_keys=[selected_match_id],
        post_update=True,
    )
    selections: Mapped[list[SubmissionSelection]] = relationship(
        back_populates="row",
        cascade="all, delete-orphan",
        order_by="SubmissionSelection.id",
    )


class TorobMatch(Base):
    __tablename__ = "torob_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("submission_rows.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="torob", nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    base_prk: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_already_added: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    row: Mapped[SubmissionRow] = relationship(back_populates="matches", foreign_keys=[row_id])
    selections: Mapped[list[SubmissionSelection]] = relationship(back_populates="match")


class SubmissionSelection(Base):
    __tablename__ = "submission_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("submission_rows.id"), nullable=False, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("torob_matches.id"), nullable=False, index=True)
    final_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    row: Mapped[SubmissionRow] = relationship(back_populates="selections")
    match: Mapped[TorobMatch] = relationship(back_populates="selections")
