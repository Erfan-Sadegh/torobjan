"""submission error message

Revision ID: 0003_submission_error_message
Revises: 0002_store_upload_file
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_submission_error_message"
down_revision: Union[str, None] = "0002_store_upload_file"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "error_message")

