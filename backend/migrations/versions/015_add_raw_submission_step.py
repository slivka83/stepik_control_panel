"""add raw_submission.step (шаг известен только из контекста запроса)

Revision ID: 015
Revises: 014
Create Date: 2026-08-01

Stepik API не возвращает `step` в объекте submission — шаг известен только
из query-параметра `?step=` (см. api_propose.md: «Пользователь и шаг
определяются через attempt»). Раньше шаг ходил через магический ключ
`_raw_json['step']`, который schema-гарды не проверяли, и transform
молча пропускал все строки. Колонка делает контекст загрузки явным и
покрытым schema-contract тестами (TEXT-типизация, PG-парити, маппинг).
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("raw_submission"):
        return
    op.add_column("raw_submission", sa.Column("step", sa.Text(), nullable=True))
    op.execute("UPDATE raw_submission SET step = _raw_json->>'step' WHERE _raw_json ? 'step'")


def downgrade() -> None:
    if _has_table("raw_submission"):
        op.drop_column("raw_submission", "step")
