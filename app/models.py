from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    seller_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eitaa_channel_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    eitaa_last_update_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    submissions: Mapped[list[Submission]] = relationship(back_populates="store")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True, index=True)
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    seller_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="excel", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    operation: Mapped[str] = mapped_column(String(32), default="add", nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="matching", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store: Mapped[Store | None] = relationship(back_populates="submissions")
    rows: Mapped[list[SubmissionRow]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionRow.input_row",
    )
    batches: Mapped[list[SubmissionBatch]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionBatch.created_at",
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
    source_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation: Mapped[str] = mapped_column(String(32), default="add", nullable=False)
    auto_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    selected_match_id: Mapped[int | None] = mapped_column(ForeignKey("torob_matches.id"), nullable=True)
    has_more_matches: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_search_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    batch_items: Mapped[list[SubmissionBatchItem]] = relationship(back_populates="row")


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
    batch_items: Mapped[list[SubmissionBatchItem]] = relationship(back_populates="match")


class SubmissionSelection(Base):
    __tablename__ = "submission_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("submission_rows.id"), nullable=False, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("torob_matches.id"), nullable=False, index=True)
    final_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    row: Mapped[SubmissionRow] = relationship(back_populates="selections")
    match: Mapped[TorobMatch] = relationship(back_populates="selections")


class SubmissionBatch(Base):
    __tablename__ = "submission_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    torob_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    torob_sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    torob_skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    torob_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    torob_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="batches")
    items: Mapped[list[SubmissionBatchItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="SubmissionBatchItem.id",
    )

    @property
    def row_count(self) -> int:
        return len({item.row_id for item in self.items})

    @property
    def selected_count(self) -> int:
        return len(self.items)


class SubmissionBatchItem(Base):
    __tablename__ = "submission_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("submission_batches.id"), nullable=False, index=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("submission_rows.id"), nullable=False, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("torob_matches.id"), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), default="add", nullable=False)
    final_price: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    batch: Mapped[SubmissionBatch] = relationship(back_populates="items")
    row: Mapped[SubmissionRow] = relationship(back_populates="batch_items")
    match: Mapped[TorobMatch] = relationship(back_populates="batch_items")
