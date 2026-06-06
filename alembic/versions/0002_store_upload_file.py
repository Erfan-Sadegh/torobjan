"""store upload file metadata

Revision ID: 0002_store_upload_file
Revises: 0001_initial
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_store_upload_file"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("submissions", sa.Column("stored_file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "stored_file_path")
    op.drop_column("submissions", "original_filename")

