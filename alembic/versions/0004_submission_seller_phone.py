"""submission seller phone

Revision ID: 0004_submission_seller_phone
Revises: 0003_submission_error_message
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_submission_seller_phone"
down_revision: Union[str, None] = "0003_submission_error_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("seller_phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "seller_phone")

