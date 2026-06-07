"""mark submitted input rows

Revision ID: 0007_submission_row_submitted_at
Revises: 0006_match_source_and_more
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_submission_row_submitted_at"
down_revision: Union[str, None] = "0006_match_source_and_more"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submission_rows", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("submission_rows", "submitted_at")
