"""eitaa submission source metadata

Revision ID: 0010_eitaa_submission_source
Revises: 0009_torob_bulk_send_status
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_eitaa_submission_source"
down_revision: Union[str, None] = "0009_torob_bulk_send_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("source", sa.String(length=32), nullable=False, server_default="excel"))
    op.add_column("submissions", sa.Column("source_ref", sa.String(length=255), nullable=True))
    op.add_column("submission_rows", sa.Column("source_message_id", sa.String(length=120), nullable=True))
    op.add_column("submission_rows", sa.Column("source_image_path", sa.Text(), nullable=True))
    op.add_column("submission_rows", sa.Column("auto_match_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("submission_rows", "auto_match_score")
    op.drop_column("submission_rows", "source_image_path")
    op.drop_column("submission_rows", "source_message_id")
    op.drop_column("submissions", "source_ref")
    op.drop_column("submissions", "source")
