"""raw promo codes for commission attribution

Revision ID: 022
Revises: 021
Create Date: 2026-11-13

Авторские (не Stepik) промокоды важны для проверки комиссии: если покупка
пришла по промокоду автора, ставка 7% ожидаема, а 40% — повод проверить.
Список промокодов курса отдаёт `/api/promo-codes?course=...`, поле
`is_stepik_side` отделяет промокоды Stepik от авторских. Складываем ответ в
raw-слой, чтобы трансформация финансов не ходила в API.
"""

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


RAW_TABLE = """
    CREATE TABLE IF NOT EXISTS raw_promo_code (
        id SERIAL PRIMARY KEY,
        promo_code_id text,
        course text,
        name text,
        is_stepik_side text,
        "user" text,
        discount text,
        _raw_json jsonb,
        _loaded_at timestamptz DEFAULT now()
    )
"""

FIELDS = [
    ("id", "promo_code_id", "text"),
    ("course", "course", "text"),
    ("name", "name", "text"),
    ("is_stepik_side", "is_stepik_side", "text"),
    ("user", "user", "text"),
    ("discount", "discount", "text"),
]


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(RAW_TABLE)
    op.execute(
        "INSERT INTO meta_endpoint "
        "(endpoint_name, api_path, api_object, auth_method, raw_table, pk_field, incremental, is_active, sync_order) "
        f"VALUES ({_sql_literal('promo_codes')}, {_sql_literal('/promo-codes')}, "
        f"{_sql_literal('promo-codes')}, {_sql_literal('client_credentials')}, "
        f"{_sql_literal('raw_promo_code')}, {_sql_literal('id')}, "
        f"{_sql_literal('full_reload')}, TRUE, 16) "
        "ON CONFLICT (endpoint_name) DO NOTHING"
    )
    values = ", ".join(
        f"({_sql_literal('promo_codes')}, {_sql_literal(api)}, {_sql_literal(db)}, "
        f"{_sql_literal(db_type)}, TRUE)"
        for api, db, db_type in FIELDS
    )
    op.execute(
        "INSERT INTO meta_field_mapping (endpoint_name, api_field, db_column, db_type, is_loaded) "
        f"VALUES {values} ON CONFLICT (endpoint_name, api_field) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM meta_field_mapping WHERE endpoint_name = 'promo_codes'")
    op.execute("DELETE FROM meta_endpoint WHERE endpoint_name = 'promo_codes'")
    op.execute("DROP TABLE IF EXISTS raw_promo_code")
