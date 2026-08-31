"""fix: convert naive timestamp columns to timezone-aware

All app tables use DateTime(timezone=True) in SQLAlchemy models, but
several PG columns were created as 'timestamp without time zone' by
migration 001. Migration 005 tried to ALTER them but silently failed
(try/except: pass). asyncpg now rejects tz-aware datetimes into naive
columns, crashing transform_enrollments at INSERT time.

Data is already UTC, so AT TIME ZONE 'UTC' conversion is lossless.

Revision ID: 020
Revises: 019
"""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


COLUMNS_TO_FIX = [
    ("student_enrollments", ["last_viewed_at", "created_at"]),
    ("courses", ["created_at"]),
    ("financial_snapshots", ["updated_at"]),
    ("users", ["token_expires_at", "created_at"]),
]


def upgrade() -> None:
    for table, columns in COLUMNS_TO_FIX:
        for col in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE TIMESTAMP WITH TIME ZONE "
                f"USING {col} AT TIME ZONE 'UTC'"
            )


def downgrade() -> None:
    for table, columns in COLUMNS_TO_FIX:
        for col in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                f"USING {col} AT TIME ZONE 'UTC'"
            )
