"""submission selections

Revision ID: 0005_submission_selections
Revises: 0004_submission_seller_phone
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_submission_selections"
down_revision: Union[str, None] = "0004_submission_seller_phone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submission_selections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("final_price", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["torob_matches.id"]),
        sa.ForeignKeyConstraint(["row_id"], ["submission_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_submission_selections_match_id"), "submission_selections", ["match_id"], unique=False)
    op.create_index(op.f("ix_submission_selections_row_id"), "submission_selections", ["row_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_submission_selections_row_id"), table_name="submission_selections")
    op.drop_index(op.f("ix_submission_selections_match_id"), table_name="submission_selections")
    op.drop_table("submission_selections")
