"""bootstrap raw layer for fresh installs

Revision ID: 021
Revises: 020
Create Date: 2026-11-09

Свежая база не могла синхронизироваться: таблицы raw_* создавались только
вручную через scripts/explore_endpoint.py, а мета-маппинг был пуст. В итоге
первый же sync падал на `relation "raw_course" does not exist`.

Миграция создаёт минимальный raw-слой, который нужен пайплайну sync_all
(courses → structure → grades/certs → submissions/attempts → financials →
community → users), и заполняет meta_endpoint/meta_field_mapping. Операции
идемпотентны (IF NOT EXISTS / ON CONFLICT DO NOTHING), поэтому безопасны на
базе, где raw-схема уже есть.
"""

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


RAW_TABLES = {
    "raw_course": """
        CREATE TABLE IF NOT EXISTS raw_course (
            id SERIAL PRIMARY KEY,
            course_id text,
            title text,
            became_published_at text,
            begin_date text,
            updated_at text,
            is_public text,
            is_published text,
            review_summary text,
            review_summary_json text,
            section_ids text,
            owner_user_id text,
            cover_url text,
            instructor_ids text,
            intro_text text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_section": """
        CREATE TABLE IF NOT EXISTS raw_section (
            id SERIAL PRIMARY KEY,
            section_id text,
            course text,
            position text,
            units text,
            title text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_unit": """
        CREATE TABLE IF NOT EXISTS raw_unit (
            id SERIAL PRIMARY KEY,
            unit_id text,
            lesson_id text,
            section_id text,
            position text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_lesson": """
        CREATE TABLE IF NOT EXISTS raw_lesson (
            id SERIAL PRIMARY KEY,
            lesson_id text,
            steps text,
            title text,
            cover_url text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_step": """
        CREATE TABLE IF NOT EXISTS raw_step (
            id SERIAL PRIMARY KEY,
            step_id text,
            lesson text,
            progress text,
            block text,
            block_video_json text,
            block_is_deprecated text,
            block_type text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_course_grade": """
        CREATE TABLE IF NOT EXISTS raw_course_grade (
            id SERIAL PRIMARY KEY,
            course_id text,
            user_id text,
            score text,
            last_viewed text,
            date_joined text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_certificate": """
        CREATE TABLE IF NOT EXISTS raw_certificate (
            id SERIAL PRIMARY KEY,
            certificate_id text,
            user_id text,
            course_id text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_submission": """
        CREATE TABLE IF NOT EXISTS raw_submission (
            id SERIAL PRIMARY KEY,
            submission_id text,
            step text,
            "user" text,
            status text,
            "time" text,
            score text,
            attempt text,
            eta text,
            reply text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_attempt": """
        CREATE TABLE IF NOT EXISTS raw_attempt (
            id SERIAL PRIMARY KEY,
            attempt_id text,
            "user" text,
            step text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_course_benefit_by_month": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit_by_month (
            id SERIAL PRIMARY KEY,
            year text,
            month text,
            total_turnover text,
            total_user_income text,
            total_refunds text,
            count_payments text,
            count_refunds text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_course_benefit": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit (
            id SERIAL PRIMARY KEY,
            benefit_id text,
            course text,
            amount text,
            payment_amount text,
            status text,
            "time" text,
            buyer text,
            promo_code text,
            currency_code text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_course_review": """
        CREATE TABLE IF NOT EXISTS raw_course_review (
            id SERIAL PRIMARY KEY,
            review_id text,
            course text,
            "user" text,
            score text,
            create_date text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_course_review_summary": """
        CREATE TABLE IF NOT EXISTS raw_course_review_summary (
            id SERIAL PRIMARY KEY,
            review_summary_id text,
            average text,
            count text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_comment": """
        CREATE TABLE IF NOT EXISTS raw_comment (
            id SERIAL PRIMARY KEY,
            comment_id text,
            "user" text,
            target text,
            "time" text,
            thread text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_user": """
        CREATE TABLE IF NOT EXISTS raw_user (
            id SERIAL PRIMARY KEY,
            user_id text,
            first_name text,
            last_name text,
            full_name text,
            _raw_json jsonb,
            _loaded_at timestamptz DEFAULT now()
        )
    """,
    "raw_sync_state": """
        CREATE TABLE IF NOT EXISTS raw_sync_state (
            endpoint_name text NOT NULL,
            key text NOT NULL,
            value text NOT NULL,
            PRIMARY KEY (endpoint_name, key)
        )
    """,
}


ENDPOINTS = [
    # name, api_path, api_object, raw_table, auth_method, incremental, pk_field, sync_order
    ("courses", "/courses", "courses", "raw_course", "user_token", "full_reload", "id", 1),
    ("sections", "/sections", "sections", "raw_section", "user_token", "full_reload", "id", 2),
    ("units", "/units", "units", "raw_unit", "user_token", "full_reload", "id", 3),
    ("lessons", "/lessons", "lessons", "raw_lesson", "user_token", "full_reload", "id", 4),
    ("steps", "/steps", "steps", "raw_step", "user_token", "full_reload", "id", 5),
    ("course_grades", "/course-grades", "course-grades", "raw_course_grade", "user_token", "full_reload", "id", 6),
    ("certificates", "/certificates", "certificates", "raw_certificate", "user_token", "full_reload", "id", 7),
    (
        "submissions",
        "/submissions",
        "submissions",
        "raw_submission",
        "user_token",
        "incremental_page",
        "id",
        8,
    ),
    ("attempts", "/attempts", "attempts", "raw_attempt", "user_token", "incremental_page", "id", 9),
    (
        "course_benefit_by_months",
        "/course-benefit-by-months",
        "course-benefit-by-months",
        "raw_course_benefit_by_month",
        "client_credentials",
        "full_reload",
        "id",
        10,
    ),
    (
        "course_benefits",
        "/course-benefits",
        "course-benefits",
        "raw_course_benefit",
        "client_credentials",
        "full_reload",
        "id",
        11,
    ),
    (
        "course_review_summaries",
        "/course-review-summaries",
        "course-review-summaries",
        "raw_course_review_summary",
        "user_token",
        "full_reload",
        "id",
        12,
    ),
    (
        "course_reviews",
        "/course-reviews",
        "course-reviews",
        "raw_course_review",
        "user_token",
        "full_reload",
        "id",
        13,
    ),
    ("comments", "/comments", "comments", "raw_comment", "user_token", "incremental_time", "id", 14),
    ("users", "/users", "users", "raw_user", "user_token", "full_reload", "id", 15),
]


MAPPINGS = {
    "courses": [
        ("id", "course_id", "text"),
        ("title", "title", "text"),
        ("became_published_at", "became_published_at", "text"),
        ("begin_date", "begin_date", "text"),
        ("update_date", "updated_at", "text"),
        ("is_public", "is_public", "text"),
        ("review_summary", "review_summary_json", "text"),
        ("sections", "section_ids", "jsonb"),
        ("owner", "owner_user_id", "text"),
    ],
    "sections": [
        ("id", "section_id", "text"),
        ("course", "course", "text"),
        ("position", "position", "text"),
        ("units", "units", "jsonb"),
        ("title", "title", "text"),
    ],
    "units": [
        ("id", "unit_id", "text"),
        ("lesson", "lesson_id", "text"),
        ("section", "section_id", "text"),
        ("position", "position", "text"),
    ],
    "lessons": [
        ("id", "lesson_id", "text"),
        ("steps", "steps", "jsonb"),
        ("title", "title", "text"),
    ],
    "steps": [
        ("id", "step_id", "text"),
        ("lesson", "lesson", "text"),
        ("progress", "progress", "text"),
        ("block", "block", "jsonb"),
    ],
    "course_grades": [
        ("course", "course_id", "text"),
        ("user", "user_id", "text"),
        ("score", "score", "text"),
        ("last_viewed", "last_viewed", "text"),
        ("date_joined", "date_joined", "text"),
    ],
    "certificates": [
        ("id", "certificate_id", "text"),
        ("user", "user_id", "text"),
        ("course", "course_id", "text"),
    ],
    "submissions": [
        ("id", "submission_id", "text"),
        ("user", "user", "text"),
        ("status", "status", "text"),
        ("time", "time", "text"),
        ("score", "score", "text"),
        ("attempt", "attempt", "text"),
        ("eta", "eta", "text"),
        ("reply", "reply", "text"),
    ],
    "attempts": [
        ("id", "attempt_id", "text"),
        ("user", "user", "text"),
        ("step", "step", "text"),
    ],
    "course_benefit_by_months": [
        ("year", "year", "text"),
        ("month", "month", "text"),
        ("total_turnover", "total_turnover", "text"),
        ("total_user_income", "total_user_income", "text"),
        ("total_refunds", "total_refunds", "text"),
        ("count_payments", "count_payments", "text"),
        ("count_refunds", "count_refunds", "text"),
    ],
    "course_benefits": [
        ("id", "benefit_id", "text"),
        ("course", "course", "text"),
        ("amount", "amount", "text"),
        ("payment_amount", "payment_amount", "text"),
        ("status", "status", "text"),
        ("time", "time", "text"),
        ("buyer", "buyer", "text"),
        ("promo_code", "promo_code", "text"),
        ("currency_code", "currency_code", "text"),
    ],
    "course_review_summaries": [
        ("id", "review_summary_id", "text"),
        ("average", "average", "text"),
        ("count", "count", "text"),
    ],
    "course_reviews": [
        ("id", "review_id", "text"),
        ("course", "course", "text"),
        ("user", "user", "text"),
        ("score", "score", "text"),
        ("create_date", "create_date", "text"),
    ],
    "comments": [
        ("id", "comment_id", "text"),
        ("user", "user", "text"),
        ("target", "target", "text"),
        ("time", "time", "text"),
        ("thread", "thread", "text"),
    ],
    "users": [
        ("id", "user_id", "text"),
        ("first_name", "first_name", "text"),
        ("last_name", "last_name", "text"),
        ("full_name", "full_name", "text"),
    ],
}


UNIQUE_KEYS = {
    "raw_submission": "submission_id",
    "raw_attempt": "attempt_id",
    "raw_comment": "comment_id",
    "raw_user": "user_id",
}


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    for ddl in RAW_TABLES.values():
        op.execute(ddl)

    for table, column in UNIQUE_KEYS.items():
        op.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_{table}_{column}" ON "{table}" ("{column}")')

    for name, path, obj, raw_table, auth, incremental, pk, order in ENDPOINTS:
        op.execute(
            "INSERT INTO meta_endpoint "
            "(endpoint_name, api_path, api_object, auth_method, raw_table, pk_field, incremental, is_active, sync_order) "
            f"VALUES ({_sql_literal(name)}, {_sql_literal(path)}, {_sql_literal(obj)}, "
            f"{_sql_literal(auth)}, {_sql_literal(raw_table)}, {_sql_literal(pk)}, "
            f"{_sql_literal(incremental)}, TRUE, {order}) "
            "ON CONFLICT (endpoint_name) DO NOTHING"
        )

    for endpoint, fields in MAPPINGS.items():
        values = ", ".join(
            f"({_sql_literal(endpoint)}, {_sql_literal(api)}, {_sql_literal(db)}, {_sql_literal(db_type)}, TRUE)"
            for api, db, db_type in fields
        )
        op.execute(
            "INSERT INTO meta_field_mapping (endpoint_name, api_field, db_column, db_type, is_loaded) "
            f"VALUES {values} ON CONFLICT (endpoint_name, api_field) DO NOTHING"
        )


def downgrade() -> None:
    endpoints = ", ".join(_sql_literal(name) for name, *_ in ENDPOINTS)
    op.execute(f"DELETE FROM meta_field_mapping WHERE endpoint_name IN ({endpoints})")
    op.execute(f"DELETE FROM meta_endpoint WHERE endpoint_name IN ({endpoints})")
    for table in RAW_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
