"""row and batch item operation

Revision ID: 0012_row_and_batch_item_operation
Revises: 0011_store_and_submission_operation
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_row_and_batch_item_operation"
down_revision: Union[str, None] = "0011_store_and_submission_operation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submission_rows", sa.Column("operation", sa.String(length=32), nullable=False, server_default="add"))
    op.add_column("submission_batch_items", sa.Column("operation", sa.String(length=32), nullable=False, server_default="add"))


def downgrade() -> None:
    op.drop_column("submission_batch_items", "operation")
    op.drop_column("submission_rows", "operation")
