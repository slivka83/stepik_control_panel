"""Глобальные schema-contract тесты.

Превентивная защита от класса ошибок "дрейфа схемы":
1. Каждая таблица.колонка, на которую ссылается SQL-код трансформаций
   (transform.py, raw_sync.py), обязана существовать в тестовой фикстуре
   raw-таблиц и в SQLAlchemy-моделях.
2. Все raw-колонки, которые читают трансформации, обязаны быть TEXT —
   реальная PostgreSQL хранит raw-слой как TEXT, и SQLite не должен
   маскировать ошибки типов.
3. (live PG) Схема raw_* в реальной PostgreSQL обязана совпадать с фикстурой.
4. (live PG) meta_field_mapping.db_column активных эндпоинтов обязан
   существовать в реальной PG-схеме.
5. (live PG) Полный пайплайн transform_* обязан отрабатывать на реальной PG.

Regression: transform.py падал на live PostgreSQL из-за дрейфа между
SQLite-фикстурой и реальной схемой: raw_certificate.course вместо course_id,
raw_attempt.user_id вместо "user", INTEGER/TEXT несоответствия, несуществующие
колонки в meta_field_mapping (steps.lesson -> lesson_id).
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, MetaEndpoint, MetaFieldMapping  # noqa: F401
from tests.conftest import RAW_TABLES

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent

SCANNED_FILES = [
    (APP_ROOT / "app/services/transform.py", "transform"),
    (APP_ROOT / "app/services/raw_sync.py", "raw_sync"),
]

KEYWORDS = {
    "select",
    "from",
    "where",
    "join",
    "on",
    "group",
    "by",
    "order",
    "having",
    "insert",
    "into",
    "values",
    "update",
    "set",
    "delete",
    "limit",
    "offset",
    "as",
    "distinct",
    "and",
    "or",
    "not",
    "in",
    "is",
    "null",
    "like",
    "between",
    "exists",
    "union",
    "all",
    "case",
    "when",
    "then",
    "else",
    "end",
    "asc",
    "desc",
    "true",
    "false",
    "do",
    "conflict",
    "returning",
    "nulls",
    "first",
    "last",
    "unique",
    "primary",
    "auto_increment",
    "default",
    "check",
    "references",
    "create",
    "table",
    "if",
    "collate",
    "cast",
    "extract",
    "interval",
    "restart",
    "identity",
    "cascade",
    "index",
    "serial",
}

FUNCTIONS = {
    "json_extract",
    "cast",
    "count",
    "sum",
    "min",
    "max",
    "avg",
    "coalesce",
    "pragma_table_info",
    "round",
    "lower",
    "upper",
    "length",
    "array_agg",
    "string_agg",
    "now",
    "abs",
}

VIRTUAL_TABLES = {
    "information_schema": {"column_name", "table_name", "column_default"},
    "pragma_table_info": {"name"},
}

DDL_COL_RE = re.compile(r'^\s+(?:"([a-zA-Z_]\w*)"|([a-zA-Z_]\w*))\s+([A-Z_]+)', re.M)
SQL_BLOCK_RE = re.compile(r'text\(\s*("""(.*?)"""|"(.*?)")', re.S)
TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+((?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*)(?:\s+([a-zA-Z_]\w*))?")
QUAL_RE = re.compile(r"(?<![\w.])" r"([a-zA-Z_]\w*)\." r"([a-zA-Z_]\w*)")
TOKEN_RE = re.compile(r'"([a-zA-Z_]\w*)"|([a-zA-Z_]\w*)|(\d+(?:\.\d+)?)|(:[a-zA-Z_]\w+|\?)')


def ddl_columns(ddl: str) -> dict[str, str]:
    cols = {}
    for m in DDL_COL_RE.finditer(ddl):
        name = m.group(1) or m.group(2)
        if name.lower() in KEYWORDS:
            continue
        cols[name] = m.group(3).upper()
    return cols


def build_schema() -> dict[str, set[str]]:
    schema = {}
    for t, ddl in RAW_TABLES.items():
        schema[t] = set(ddl_columns(ddl))
    for t, table in Base.metadata.tables.items():
        schema[t] = set(table.columns.keys())
    return schema


def extract_statements() -> list[tuple[str, str, str]]:
    """(file_label, kind, sql) для всех статических text(...) блоков."""
    stmts = []
    for path, label in SCANNED_FILES:
        src = path.read_text(encoding="utf-8")
        for m in SQL_BLOCK_RE.finditer(src):
            sql = m.group(2) or m.group(3)
            stmts.append((label, path.name, sql))
    return stmts


def clean_sql(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'[^']*'", " '' ", sql)


def statement_tables(sql: str) -> tuple[dict[str, list[str]], str | None]:
    """(prefix_to_table: prefix -> таблица, target) для UPDATE/INSERT стейтмента."""
    sql = clean_sql(sql)
    prefix_to_table: dict[str, str] = {}
    target: str | None = None
    for m in TABLE_REF_RE.finditer(sql):
        table = m.group(1)
        alias = m.group(2)
        lead = sql[m.start() :].lstrip()[:7].split()[0].upper()
        if "." in table:
            table = table.split(".", 1)[0]
        if table.lower() in KEYWORDS:
            continue
        if alias and (alias.lower() in KEYWORDS or alias.lower() in FUNCTIONS):
            alias = None
        if table in VIRTUAL_TABLES:
            prefix_to_table[table] = table
            continue
        prefix_to_table[table] = table
        if alias:
            prefix_to_table[alias] = table
        if lead in {"UPDATE", "INTO"}:
            target = table
    return prefix_to_table, target


def split_cols(raw: str) -> list[str]:
    out = []
    for item in raw.split(","):
        item = item.strip().strip('"')
        if re.fullmatch(r"[a-zA-Z_]\w*", item):
            out.append(item)
    return out


def referenced_columns(sql: str, known_names: set[str] | None = None) -> set[str]:
    """Все простые идентификаторы, похожие на колонки."""
    known_names = known_names or set()
    sql = clean_sql(sql)
    candidates = set()
    tokens = list(TOKEN_RE.finditer(sql))
    for i, m in enumerate(tokens):
        word = m.group(1) or m.group(2)
        if not word:
            continue
        low = word.lower()
        if low in KEYWORDS or low in FUNCTIONS:
            continue
        if word in VIRTUAL_TABLES or word in known_names:
            continue
        prev_tok = tokens[i - 1] if i else None
        next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
        before = sql[prev_tok.end() : m.start()] if prev_tok else sql[: m.start()]
        after = sql[m.end() : next_tok.start()] if next_tok else sql[m.end() :]
        prev_word = (prev_tok.group(1) or prev_tok.group(2)) if prev_tok else None
        if prev_word is not None and prev_word.lower() == "as":
            continue
        if after.lstrip().startswith("("):
            continue
        if before.rstrip().endswith(":") or before.rstrip().endswith("."):
            continue
        if after.lstrip().startswith("."):
            continue
        candidates.add(word)
    return candidates


def clause_columns(sql: str, target: str | None) -> set[str]:
    """Колонки из INSERT-списков, ON CONFLICT и SET lhs."""
    sql = clean_sql(sql)
    found: set[str] = set()
    for m in re.finditer(r"\bINTO\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)", sql):
        found.update(split_cols(m.group(2)))
    for m in re.finditer(r"\bON\s+CONFLICT\s*\(([^)]*)\)", sql):
        found.update(split_cols(m.group(1)))
    m = re.search(r"\bSET\s+(.*)$", sql)
    if m:
        for item in m.group(1).split(","):
            lhs = item.split("=")[0].strip().strip('"')
            if re.fullmatch(r"[a-zA-Z_]\w*", lhs):
                found.add(lhs)
    return found


def validate_statement(schema: dict[str, set[str]], label: str, sql: str) -> list[str]:
    errors: list[str] = []
    sql_clean = clean_sql(sql)
    prefix_to_table, target = statement_tables(sql)
    if not prefix_to_table:
        return errors

    tables = set(prefix_to_table.values())

    for prefix, table in prefix_to_table.items():
        if table not in schema and table not in VIRTUAL_TABLES:
            errors.append(f"[{label}] неизвестная таблица в SQL: '{table}'")

    for m in QUAL_RE.finditer(sql_clean):
        prefix, col = m.group(1), m.group(2)
        if prefix.lower() == "excluded" or prefix in VIRTUAL_TABLES:
            continue
        table = prefix_to_table.get(prefix)
        if table is None:
            errors.append(f"[{label}] неизвестный псевдоним таблицы: '{prefix}'")
            continue
        if table not in schema:
            continue
        if col not in schema[table]:
            errors.append(f"[{label}] колонка '{col}' отсутствует в '{table}'")

    if target:
        check_tables = {target}
    else:
        check_tables = set(t for t in tables if t in schema)
    if not check_tables:
        return errors

    virtual_cols = set()
    for t in tables:
        if t in VIRTUAL_TABLES:
            virtual_cols.update(VIRTUAL_TABLES[t])
    known_names = set(prefix_to_table)

    for cand in referenced_columns(sql, known_names) | clause_columns(sql, target):
        if cand in virtual_cols:
            continue
        if not any(cand in schema[t] for t in check_tables):
            ctx = "SET/INSERT/ON CONFLICT"
            errors.append(f"[{label}] колонка '{cand}' ({ctx}) отсутствует в таблицах: {sorted(check_tables)}")
    return errors


def referenced_raw_columns(schema: dict[str, set[str]]) -> dict[str, set[str]]:
    """(raw_table -> колонки), которые реально читает transform.py."""
    used: dict[str, set[str]] = {}
    for label, _, sql in extract_statements():
        if label != "transform":
            continue
        prefix_to_table, target = statement_tables(sql)
        known_names = set(prefix_to_table)
        for prefix, table in prefix_to_table.items():
            if not table.startswith("raw_"):
                continue
            for m in QUAL_RE.finditer(clean_sql(sql)):
                if m.group(1) == prefix:
                    used.setdefault(table, set()).add(m.group(2))
            for col in referenced_columns(sql, known_names) | clause_columns(sql, target):
                if col in schema.get(table, set()):
                    used.setdefault(table, set()).add(col)
    return used


# ---------------------------------------------------------------------------
# Статические тесты (без БД)
# ---------------------------------------------------------------------------


def test_static_sql_references_exist_in_schema():
    schema = build_schema()
    all_errors: list[str] = []
    for label, fname, sql in extract_statements():
        all_errors += validate_statement(schema, fname, sql)
    assert not all_errors, "Дрейф схемы: SQL ссылается на несуществующие колонки:\n" + "\n".join(all_errors)


def test_static_sql_found_in_scanned_files():
    stmts = extract_statements()
    assert len(stmts) >= 20, f"Не найдены text(...) блоки: {len(stmts)}"


def test_transform_reads_raw_columns_as_text():
    """Все raw-колонки, которые читает transform.py, обязаны быть TEXT.

    Реальная PG хранит raw-слой как TEXT; SQLite-фикстура должна совпадать,
    иначе баги INTEGER vs TEXT не воспроизводятся в тестах.
    """
    schema = {t: ddl_columns(ddl) for t, ddl in RAW_TABLES.items()}
    problems = []
    for table, cols in referenced_raw_columns(schema).items():
        for col in sorted(cols):
            if col in {"id", "_loaded_at"}:
                continue
            ctype = schema.get(table, {}).get(col)
            if ctype != "TEXT":
                problems.append(f"{table}.{col}: {ctype} (должно быть TEXT)")
    assert not problems, "Нетекстовые raw-колонки, читаемые трансформациями:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# Live-PostgreSQL тесты (пропускаются без .env DATABASE_URL)
# ---------------------------------------------------------------------------


def _pg_url() -> str | None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            if url.startswith("postgresql"):
                return url
    return None


PG_URL = _pg_url()
needs_pg = pytest.mark.skipif(PG_URL is None, reason="Нет PostgreSQL (DATABASE_URL в .env)")


async def _pg_columns(engine) -> dict[str, dict[str, str]]:
    async with engine.connect() as conn:
        r = await conn.execute(
            text(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns WHERE table_name LIKE :pat "
                "ORDER BY table_name, ordinal_position"
            ),
            {"pat": "raw_%"},
        )
    cols: dict[str, dict[str, str]] = {}
    for table, col, dtype in r:
        cols.setdefault(table, {})[col] = dtype
    return cols


async def _pg_engine():
    return create_async_engine(PG_URL)


@needs_pg
async def test_pg_raw_schema_contains_transform_columns():
    """PG-схема raw_* содержит все колонки, которые читает transform.py.

    PG-таблицы могут иметь больше колонок (rebuild_raw создаёт их из полного
    meta_field_mapping), но колонки, потребляемые трансформациями, обязаны
    существовать и быть TEXT/JSONB — иначе INTEGER/TEXT баги не воспроизводятся.
    """
    engine = await _pg_engine()
    try:
        pg_cols = await _pg_columns(engine)
    finally:
        await engine.dispose()

    fixture_cols = {t: ddl_columns(ddl) for t, ddl in RAW_TABLES.items() if t != "raw_sync_state"}
    missing_tables = [t for t in fixture_cols if t not in pg_cols]
    assert not missing_tables, f"Таблицы отсутствуют в PG: {missing_tables}"

    schema = build_schema()
    used = referenced_raw_columns(schema)
    for table, cols in used.items():
        if table not in pg_cols:
            continue
        for col in sorted(cols):
            if col in {"id", "_loaded_at"}:
                continue
            dtype = pg_cols[table].get(col)
            assert dtype is not None, (
                f"{table}.{col}: колонка есть в фикстуре, но отсутствует в PG — transform упадёт на живой БД"
            )
            assert dtype in {"text", "jsonb"}, (
                f"{table}.{col}: в PG тип {dtype}, но трансформации читают его как TEXT — риск INTEGER/TEXT бага"
            )


@needs_pg
async def test_pg_meta_field_mapping_columns_exist():
    """meta_field_mapping.db_column активных эндпоинтов обязан существовать в PG.

    Regression: mapping ссылался на несуществующие колонки
    (steps.lesson -> lesson_id, sections.course -> course_id) — трансформации
    падали с ProgrammerError на живой БД.
    """
    engine = await _pg_engine()
    try:
        pg_cols = await _pg_columns(engine)
        async with engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT e.raw_table, m.db_column, m.api_field, e.endpoint_name
                    FROM meta_field_mapping m
                    JOIN meta_endpoint e ON e.endpoint_name = m.endpoint_name
                    WHERE e.is_active = TRUE AND m.is_loaded = TRUE
                    ORDER BY e.endpoint_name, m.db_column
                """)
            )
            rows = list(r)
    finally:
        await engine.dispose()

    assert rows, "Нет активных записей в meta_field_mapping"
    problems = []
    for raw_table, db_column, api_field, ep in rows:
        if raw_table not in pg_cols:
            problems.append(f"[{ep}] таблица '{raw_table}' не существует в PG")
            continue
        if db_column not in pg_cols[raw_table]:
            problems.append(f"[{ep}] колонка '{raw_table}.{db_column}' (api_field='{api_field}') отсутствует в PG")
    assert not problems, "Дрейф meta_field_mapping:\n" + "\n".join(problems)


@needs_pg
async def test_pg_mapping_covers_transform_read_columns():
    """Каждая raw-колонка, читаемая трансформациями, обязана писаться loader'ом.

    Loader (_replace_raw_table/_upsert_raw_table) пишет ТОЛЬКО колонки из
    meta_field_mapping — если маппинга нет, колонка молча остаётся NULL.
    Regression: courses.published_at пустел («Опубликован» = «—»), потому что
    в mapping не было became_published_at, хотя колонка существовала.
    """
    engine = await _pg_engine()
    try:
        async with engine.connect() as conn:
            r = await conn.execute(
                text("""
                    SELECT e.raw_table, e.endpoint_name, m.db_column
                    FROM meta_field_mapping m
                    JOIN meta_endpoint e ON e.endpoint_name = m.endpoint_name
                    WHERE e.is_active = TRUE AND m.is_loaded = TRUE
                """)
            )
            mapping_rows = list(r)
    finally:
        await engine.dispose()

    assert mapping_rows, "Нет записей в meta_field_mapping"
    mapped_cols: dict[str, set[str]] = {}
    for raw_table, ep, db_column in mapping_rows:
        mapped_cols.setdefault(raw_table, set()).add(db_column)

    schema = build_schema()
    used = referenced_raw_columns(schema)
    problems = []
    for table, cols in sorted(used.items()):
        for col in sorted(cols):
            if col in {"id", "_loaded_at", "_raw_json"}:
                continue
            if col not in mapped_cols.get(table, set()):
                problems.append(
                    f"{table}.{col}: колонка существует, но loader не пишет её — "
                    f"нет is_loaded строки в meta_field_mapping, трансформации "
                    f"всегда получают NULL"
                )
    assert not problems, "Raw-колонки без mapping-покрытия:\n" + "\n".join(problems)


@needs_pg
async def test_full_transform_pipeline_on_pg():
    """Полный пайплайн transform_* отрабатывает на реальной PG без ошибок.

    Regression: transform_enrollments/transform_courses/transform_submissions
    падали на live PG (типы/колонки). Всё выполняется в транзакции с rollback —
    данные не изменяются.
    """
    from app.services import transform as tr

    engine = create_async_engine(PG_URL)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            trans = await session.begin()
            try:
                await tr.transform_courses(session)
                await tr.transform_enrollments(session)
                await tr.transform_submissions(session)
                await tr.transform_financials(session)
                await tr.transform_community(session)
                await tr.transform_students(session)
            finally:
                # begin()-контекст коммитит на выходе — только явный rollback
                await trans.rollback()
    finally:
        await engine.dispose()


@needs_pg
async def test_pg_snapshot_schema_after_pipeline():
    """Снапшот финансов на реальной PG имеет полную структуру (summary/community).

    Regression: на live PG отсутствовали price в summary.courses и
    community.per_course — фронтенд показывал «—» вместо значений.
    """
    from app.services import transform as tr

    engine = create_async_engine(PG_URL)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            trans = await session.begin()
            try:
                await tr.transform_financials(session)
                await tr.transform_community(session)
                r = await session.execute(text("SELECT data FROM financial_snapshots ORDER BY updated_at DESC LIMIT 1"))
                row = r.fetchone()
            finally:
                # begin()-контекст коммитит на выходе — только явный rollback
                await trans.rollback()

        assert row is not None, "Нет financial_snapshots на PG"
        data = row[0]
        assert "summary" in data, "Нет summary в снапшоте"
        assert data["summary"].get("total_income", 0) > 0
        assert data.get("courses"), "Нет top-level courses в снапшоте"
        assert any("price" in c for c in data["courses"]), "Нет price в course entries — фронтенд покажет «—»"
        community = data.get("community", {})
        assert "per_course" in community, "Нет community.per_course в снапшоте"
        assert community.get("total_comments", 0) > 0
    finally:
        await engine.dispose()
