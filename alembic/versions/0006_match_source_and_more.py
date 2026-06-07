"""match source and load more state

Revision ID: 0006_match_source_and_more
Revises: 0005_submission_selections
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_match_source_and_more"
down_revision: Union[str, None] = "0005_submission_selections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("price_unit", sa.String(length=16), nullable=True))
    op.add_column(
        "submission_rows",
        sa.Column("has_more_matches", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "submission_rows",
        sa.Column("next_search_page", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "torob_matches",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="torob"),
    )


def downgrade() -> None:
    op.drop_column("torob_matches", "source")
    op.drop_column("submission_rows", "next_search_page")
    op.drop_column("submission_rows", "has_more_matches")
    op.drop_column("submissions", "price_unit")
