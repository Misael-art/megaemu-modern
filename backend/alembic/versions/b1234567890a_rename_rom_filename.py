"""rename rom_filename to filename

Revision ID: b1234567890a
Revises: a43c65902e0b
Create Date: 2023-10-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1234567890a'
down_revision = 'a43c65902e0b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename column if it exists
    op.execute("""
        ALTER TABLE roms RENAME COLUMN IF EXISTS rom_filename TO filename;
    """)


def downgrade() -> None:
    # Rename back
    op.execute("""
        ALTER TABLE roms RENAME COLUMN IF EXISTS filename TO rom_filename;
    """)