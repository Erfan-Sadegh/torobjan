"""store and submission operation

Revision ID: 0011_store_and_submission_operation
Revises: 0010_eitaa_submission_source
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_store_and_submission_operation"
down_revision: Union[str, None] = "0010_eitaa_submission_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("seller_phone", sa.String(length=32), nullable=True),
        sa.Column("shop_id", sa.String(length=64), nullable=True),
        sa.Column("eitaa_channel_id", sa.String(length=255), nullable=True),
        sa.Column("eitaa_last_update_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eitaa_channel_id"),
    )
    op.add_column("submissions", sa.Column("store_id", sa.Integer(), nullable=True))
    op.add_column("submissions", sa.Column("operation", sa.String(length=32), nullable=False, server_default="add"))
    op.create_index(op.f("ix_submissions_store_id"), "submissions", ["store_id"], unique=False)
    op.create_foreign_key("fk_submissions_store_id_stores", "submissions", "stores", ["store_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_submissions_store_id_stores", "submissions", type_="foreignkey")
    op.drop_index(op.f("ix_submissions_store_id"), table_name="submissions")
    op.drop_column("submissions", "operation")
    op.drop_column("submissions", "store_id")
    op.drop_table("stores")
