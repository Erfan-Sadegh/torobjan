"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_name", sa.String(length=200), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("selected_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "submission_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("input_row", sa.Integer(), nullable=False),
        sa.Column("input_product_name", sa.String(length=500), nullable=True),
        sa.Column("input_price", sa.String(length=80), nullable=True),
        sa.Column("barcode", sa.String(length=120), nullable=True),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("final_price", sa.String(length=80), nullable=True),
        sa.Column("selected_match_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "torob_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("base_prk", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("price_text", sa.String(length=120), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("is_already_added", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["row_id"], ["submission_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "fk_submission_rows_selected_match_id_torob_matches",
        "submission_rows",
        "torob_matches",
        ["selected_match_id"],
        ["id"],
    )
    op.create_index(op.f("ix_submission_rows_submission_id"), "submission_rows", ["submission_id"], unique=False)
    op.create_index(op.f("ix_torob_matches_row_id"), "torob_matches", ["row_id"], unique=False)


def downgrade() -> None:
    op.drop_constraint(
        "fk_submission_rows_selected_match_id_torob_matches",
        "submission_rows",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_torob_matches_row_id"), table_name="torob_matches")
    op.drop_index(op.f("ix_submission_rows_submission_id"), table_name="submission_rows")
    op.drop_table("torob_matches")
    op.drop_table("submission_rows")
    op.drop_table("submissions")
