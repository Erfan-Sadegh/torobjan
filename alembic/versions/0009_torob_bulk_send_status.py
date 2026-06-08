"""track torob bulk send status

Revision ID: 0009_torob_bulk_send_status
Revises: 0008_submission_batches
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_torob_bulk_send_status"
down_revision: Union[str, None] = "0008_submission_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submission_batches", sa.Column("torob_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "submission_batches",
        sa.Column("torob_sent_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "submission_batches",
        sa.Column("torob_skipped_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("submission_batches", sa.Column("torob_error_message", sa.Text(), nullable=True))
    op.add_column("submission_batches", sa.Column("torob_response_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submission_batches", "torob_response_text")
    op.drop_column("submission_batches", "torob_error_message")
    op.drop_column("submission_batches", "torob_skipped_count")
    op.drop_column("submission_batches", "torob_sent_count")
    op.drop_column("submission_batches", "torob_sent_at")
