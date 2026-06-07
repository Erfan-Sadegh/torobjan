"""real submission batches

Revision ID: 0008_submission_batches
Revises: 0007_submission_row_submitted_at
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_submission_batches"
down_revision: Union[str, None] = "0007_submission_row_submitted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submission_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_submission_batches_submission_id", "submission_batches", ["submission_id"])
    op.create_table(
        "submission_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("submission_batches.id"), nullable=False),
        sa.Column("row_id", sa.Integer(), sa.ForeignKey("submission_rows.id"), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("torob_matches.id"), nullable=False),
        sa.Column("final_price", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_submission_batch_items_batch_id", "submission_batch_items", ["batch_id"])
    op.create_index("ix_submission_batch_items_row_id", "submission_batch_items", ["row_id"])
    op.create_index("ix_submission_batch_items_match_id", "submission_batch_items", ["match_id"])
    _backfill_batches()


def downgrade() -> None:
    op.drop_index("ix_submission_batch_items_match_id", table_name="submission_batch_items")
    op.drop_index("ix_submission_batch_items_row_id", table_name="submission_batch_items")
    op.drop_index("ix_submission_batch_items_batch_id", table_name="submission_batch_items")
    op.drop_table("submission_batch_items")
    op.drop_index("ix_submission_batches_submission_id", table_name="submission_batches")
    op.drop_table("submission_batches")


def _backfill_batches() -> None:
    connection = op.get_bind()
    submission_rows = sa.table(
        "submission_rows",
        sa.column("id", sa.Integer()),
        sa.column("submission_id", sa.Integer()),
        sa.column("submitted_at", sa.DateTime(timezone=True)),
    )
    submission_selections = sa.table(
        "submission_selections",
        sa.column("id", sa.Integer()),
        sa.column("row_id", sa.Integer()),
        sa.column("match_id", sa.Integer()),
        sa.column("final_price", sa.String(length=80)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    submission_batches = sa.table(
        "submission_batches",
        sa.column("id", sa.Integer()),
        sa.column("submission_id", sa.Integer()),
        sa.column("status", sa.String(length=40)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    submission_batch_items = sa.table(
        "submission_batch_items",
        sa.column("batch_id", sa.Integer()),
        sa.column("row_id", sa.Integer()),
        sa.column("match_id", sa.Integer()),
        sa.column("final_price", sa.String(length=80)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    existing_batches = connection.execute(
        sa.select(submission_rows.c.submission_id, submission_rows.c.submitted_at)
        .where(submission_rows.c.submitted_at.is_not(None))
        .distinct()
    ).all()

    for existing_batch in existing_batches:
        batch_result = connection.execute(
            submission_batches.insert().values(
                submission_id=existing_batch.submission_id,
                status="pending",
                created_at=existing_batch.submitted_at,
                updated_at=existing_batch.submitted_at,
            )
        )
        batch_id = batch_result.inserted_primary_key[0]
        existing_items = connection.execute(
            sa.select(
                submission_selections.c.row_id,
                submission_selections.c.match_id,
                submission_selections.c.final_price,
                submission_selections.c.created_at,
            )
            .select_from(
                submission_selections.join(
                    submission_rows,
                    submission_selections.c.row_id == submission_rows.c.id,
                )
            )
            .where(submission_rows.c.submission_id == existing_batch.submission_id)
            .where(submission_rows.c.submitted_at == existing_batch.submitted_at)
        ).all()
        for item in existing_items:
            connection.execute(
                submission_batch_items.insert().values(
                    batch_id=batch_id,
                    row_id=item.row_id,
                    match_id=item.match_id,
                    final_price=item.final_price,
                    created_at=item.created_at or existing_batch.submitted_at,
                )
            )
