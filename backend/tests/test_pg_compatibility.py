"""Tests: Postgres compatibility — no SQLite-isms in transform/raw_sync."""

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from app.services.transform import _ensure_json, _serialize_data, parse_dt

# ─── _ensure_json ──────────────────────────────────────────────────────────


class TestEnsureJson:
    def test_dict_passthrough(self):
        d = {"foo": 1}
        assert _ensure_json(d) is d

    def test_str_parses(self):
        assert _ensure_json('{"foo": 1}') == {"foo": 1}

    def test_str_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _ensure_json("not json")

    def test_list_dict(self):
        d = [{"a": 1}, {"b": 2}]
        assert _ensure_json(d) is d

    def test_list_str(self):
        assert _ensure_json('[{"a": 1}]') == [{"a": 1}]

    def test_none_passthrough(self):
        assert _ensure_json(None) is None

    def test_number_str(self):
        assert _ensure_json("42") == 42

    def test_bool_str(self):
        assert _ensure_json("true") is True
        assert _ensure_json("false") is False


# ─── _serialize_data ──────────────────────────────────────────────────────


class TestSerializeData:
    def test_returns_str(self):
        result = _serialize_data({"a": 1}, MagicMock())
        assert isinstance(result, str)

    def test_roundtrip(self):
        data = {"a": [1, 2], "b": "тест"}
        s = _serialize_data(data, MagicMock())
        assert json.loads(s) == data

    def test_empty_dict(self):
        assert _serialize_data({}, MagicMock()) == "{}"

    def test_ensure_ascii_false(self):
        result = _serialize_data({"x": "привет"}, MagicMock())
        assert "привет" in result


# ─── parse_dt ─────────────────────────────────────────────────────────────


class TestParseDt:
    def test_none_returns_none(self):
        assert parse_dt(None) is None

    def test_tz_aware_iso(self):
        dt = parse_dt("2026-07-30T12:00:00+00:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_z_suffix(self):
        dt = parse_dt("2026-07-30T12:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_iso_stays_naive(self):
        dt = parse_dt("2026-07-30T12:00:00")
        assert dt is not None
        assert dt.tzinfo is None

    def test_timestamp_int(self):
        dt = parse_dt(1722345600)
        assert dt is not None
        assert dt.tzinfo is not None

    def test_timestamp_float(self):
        dt = parse_dt(1722345600.5)
        assert dt is not None

    def test_invalid_returns_none(self):
        assert parse_dt("not a date") is None

    def test_empty_string_returns_none(self):
        assert parse_dt("") is None


# ─── SQL has no SQLite-only functions ────────────────────────────────────


SQLITE_ONLY_RE = re.compile(
    r"\b(json_extract|json_type|json_each|json_set|json_group"
    r"|strftime|julianday|datetime\(|iif\(|unicode|substr"
    r"|instr|ltrim|rtrim|zeroblob|typeof|total_changes|changes"
    r"|last_insert_rowid|sqlite_version)\s*\(",
    re.IGNORECASE,
)


def _extract_sql_strings(source: str) -> list[str]:
    """Extract multi-line SQL strings (triple-quoted or parenthesized .text(...))."""
    sqls = []
    lines = source.split("\n")

    in_triple = False
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()

        if in_triple:
            buf.append(line)
            if '"""' in stripped:
                in_triple = False
                block = "\n".join(buf)
                # Extract content between triple quotes
                m = re.search(r'"""\s*(.*?)\s*"""', block, re.DOTALL)
                if m:
                    sqls.append(m.group(1))
                buf = []
            continue

        if stripped.startswith('text("""') or stripped.startswith('text("""'):
            in_triple = True
            buf = [line]
            if '"""' in stripped[9:]:
                in_triple = False
                block = "\n".join(buf)
                m = re.search(r'"""\s*(.*?)\s*"""', block, re.DOTALL)
                if m:
                    sqls.append(m.group(1))
                buf = []
            continue

        m = re.search(r'text\(["\'](.*?)["\']\s*\)', stripped)
        if m:
            sqls.append(m.group(1))

    return sqls


SQLITE_ONLY_EXCEPTIONS = {
    # These are intentional uses through SQLAlchemy, not raw SQL
    "pragma_table_info",
}


def _check_file_for_sqlite_functions(filepath: str) -> list[dict]:
    """Return list of {line, func, sql} for every SQLite-only function found."""
    with open(filepath) as f:
        lines = f.readlines()

    hits = []
    for i, line in enumerate(lines, 1):
        for m in SQLITE_ONLY_RE.finditer(line):
            func = m.group(1)
            if func in SQLITE_ONLY_EXCEPTIONS:
                continue
            hits.append({"line": i, "func": func, "sql": line.strip()})
    return hits


TRANSFORM_PATH = __import__("app.services.transform", fromlist=[""]).__file__ or "app/services/transform.py"
RAW_SYNC_PATH = __import__("app.services.raw_sync", fromlist=[""]).__file__ or "app/services/raw_sync.py"


class TestNoSqliteInTransform:
    def test_no_json_extract_in_transform(self):
        hits = _check_file_for_sqlite_functions(TRANSFORM_PATH)
        msg = "\n".join(f"  L{h['line']}: {h['func']} in `{h['sql']}`" for h in hits)
        assert not hits, f"SQLite-only function(s) found in transform.py:\n{msg}"

    def test_no_json_extract_in_raw_sync(self):
        hits = _check_file_for_sqlite_functions(RAW_SYNC_PATH)
        msg = "\n".join(f"  L{h['line']}: {h['func']} in `{h['sql']}`" for h in hits)
        assert not hits, f"SQLite-only function(s) found in raw_sync.py:\n{msg}"


# ─── transform helpers work with both str and dict _raw_json ──────────────


@pytest.mark.asyncio
async def test_transform_financials_with_dict_raw_json(db_session):
    """Regression: transform_financials must handle dict _raw_json (PG jsonb)."""
    from app.services.transform import transform_financials

    user = _make_user(db_session)
    await _make_course(db_session, user.id, stepik_course_id=100)
    await db_session.commit()

    # Insert raw data with _raw_json as dict (PG) not str (SQLite)
    raw_json = {
        "id": "2026-01-RUB-12345-ALL",
        "date": "2026-01-01T00:00:00+03:00",
        "user": 12345,
        "year": 2026,
        "month": 1,
        "count_refunds": 0,
        "currency_code": "RUB",
        "total_refunds": 0,
        "count_payments": 5,
        "total_turnover": "5000.00",
        "count_z_payments": 0,
        "total_user_income": "4000.00",
        "count_non_z_payments": 5,
        "count_course_payments": 5,
        "count_invoice_payments": 0,
    }
    await db_session.execute(
        text("""
        DELETE FROM raw_course_benefit_by_month
    """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_course_benefit_by_month (_raw_json)
        VALUES (:j)
    """),
        {"j": json.dumps(raw_json)},
    )

    benefit_json = {
        "id": 999,
        "course": 100,
        "time": "2026-01-15T10:00:00Z",
        "amount": "4000.00",
        "payment_amount": "5000.00",
        "status": "paid",
        "promo_code": None,
        "buyer": 999999,
    }
    await db_session.execute(text("DELETE FROM raw_course_benefit"))
    await db_session.execute(
        text("""
        INSERT INTO raw_course_benefit (_raw_json)
        VALUES (:j)
    """),
        {"j": json.dumps(benefit_json)},
    )
    await db_session.commit()

    await transform_financials(db_session)
    await db_session.commit()

    r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    assert row is not None
    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    assert data["summary"]["total_turnover"] == 5000


# ─── datetime naivety in INSERT/UPDATE params ────────────────────────────


DT_AWARE = datetime.now(UTC)
DT_NAIVE = DT_AWARE.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_financial_snapshot_insert_with_naive_dt(db_session):
    """Regression: timestamptz column must accept naive UTC datetime (asyncpg compat)."""
    from app.services.transform import transform_financials

    user = _make_user(db_session)
    await _make_course(db_session, user.id, stepik_course_id=100)

    raw_json = {
        "id": "2026-01-RUB-12345-ALL",
        "date": "2026-01-01T00:00:00+03:00",
        "user": 12345,
        "year": 2026,
        "month": 1,
        "count_refunds": 0,
        "currency_code": "RUB",
        "total_refunds": 0,
        "count_payments": 3,
        "total_turnover": "3000.00",
        "count_z_payments": 0,
        "total_user_income": "2500.00",
        "count_non_z_payments": 3,
        "count_course_payments": 3,
        "count_invoice_payments": 0,
    }
    await db_session.execute(text("DELETE FROM raw_course_benefit_by_month"))
    await db_session.execute(
        text("""
        INSERT INTO raw_course_benefit_by_month (_raw_json)
        VALUES (:j)
    """),
        {"j": json.dumps(raw_json)},
    )

    benefit_json = {
        "id": 888,
        "course": 100,
        "time": "2026-01-15T10:00:00Z",
        "amount": "2500.00",
        "payment_amount": "3000.00",
        "status": "paid",
        "promo_code": None,
        "buyer": 888888,
    }
    await db_session.execute(text("DELETE FROM raw_course_benefit"))
    await db_session.execute(
        text("""
        INSERT INTO raw_course_benefit (_raw_json)
        VALUES (:j)
    """),
        {"j": json.dumps(benefit_json)},
    )
    await db_session.commit()

    await transform_financials(db_session)
    await db_session.commit()

    r = await db_session.execute(
        text("""
        SELECT updated_at FROM financial_snapshots LIMIT 1
    """)
    )
    row = r.fetchone()
    assert row is not None
    # SQLite returns str, PG returns datetime — either is fine
    assert row[0] is not None


# ─── All transforms with dict _raw_json (PG jsonb compat) ────────────────
# Only functions that read _raw_json directly are affected:
#   transform_financials, transform_community, transform_submissions


@pytest.mark.asyncio
async def test_transform_submissions_with_dict_raw_json(db_session):
    """Regression: transform_submissions must handle dict _raw_json."""
    from app.services.transform import transform_submissions

    user = _make_user(db_session)
    cid = await _make_course(db_session, user.id, stepik_course_id=400)

    # Need a step-course mapping: raw_step.lesson → raw_unit.lesson_id → raw_section.course
    await db_session.execute(text("DELETE FROM raw_step"))
    await db_session.execute(
        text("""
        INSERT INTO raw_step (step_id, lesson, _raw_json)
        VALUES (:sid, :lid, :j)
    """),
        {"sid": 10, "lid": 20, "j": json.dumps({"id": 10, "lesson": 20})},
    )
    await db_session.execute(text("DELETE FROM raw_unit"))
    await db_session.execute(
        text("""
        INSERT INTO raw_unit (unit_id, lesson_id, section_id, _raw_json)
        VALUES (1, 20, 1, :j)
    """),
        {"j": json.dumps({"id": 30, "lesson": 20, "section": 1})},
    )
    await db_session.execute(text("DELETE FROM raw_section"))
    await db_session.execute(
        text("""
        INSERT INTO raw_section (section_id, course, units, _raw_json)
        VALUES (1, 400, '[1]', :j)
    """),
        {"j": json.dumps({"id": 1, "course": 400})},
    )

    raw_sub = {
        "id": 1000,
        "step": 10,
        "user": 99999,
        "time": "2026-07-15T12:00:00Z",
        "status": "correct",
        "attempt": 555,
    }
    await db_session.execute(text("DELETE FROM raw_submission"))
    await db_session.execute(
        text("""
        INSERT INTO raw_submission (_raw_json)
        VALUES (:j)
    """),
        {"j": json.dumps(raw_sub)},
    )

    raw_attempt = {"id": 555, "user": 99999}
    await db_session.execute(text("DELETE FROM raw_attempt"))
    await db_session.execute(
        text("""
        INSERT INTO raw_attempt (attempt_id, _raw_json)
        VALUES (:aid, :j)
    """),
        {"aid": 555, "j": json.dumps(raw_attempt)},
    )
    await db_session.commit()

    await transform_submissions(db_session)
    await db_session.commit()

    r = await db_session.execute(
        text("""
        SELECT status FROM submissions WHERE stepik_step_id = 10
    """)
    )
    row = r.fetchone()
    assert row is not None
    assert row[0] == "correct"


@pytest.mark.asyncio
async def test_transform_community_with_dict_raw_json(db_session):
    """Regression: transform_community must handle dict _raw_json."""
    from app.services.transform import transform_community

    user = _make_user(db_session)
    await _make_course(db_session, user.id, stepik_course_id=500)
    await db_session.commit()

    # Pre-create a financial snapshot
    snap_id = str(uuid.uuid4())
    await db_session.execute(
        text("""
        INSERT INTO financial_snapshots (id, data, updated_at)
        VALUES (:id, :data, :now)
    """),
        {
            "id": snap_id,
            "data": json.dumps({"summary": {"total_turnover": 10000}}),
            "now": datetime.now(UTC).replace(tzinfo=None),
        },
    )

    # Insert raw course review summary
    await db_session.execute(text("DELETE FROM raw_course_review_summary"))
    await db_session.execute(
        text("""
        INSERT INTO raw_course_review_summary (_raw_json)
        VALUES (:j)
    """),
        {
            "j": json.dumps(
                {
                    "id": 500,
                    "course": 500,
                    "average": "4.5",
                    "count": 10,
                }
            )
        },
    )

    # Insert raw comment
    await db_session.execute(text("DELETE FROM raw_comment"))
    await db_session.execute(
        text("""
        INSERT INTO raw_comment (_raw_json)
        VALUES (:j)
    """),
        {
            "j": json.dumps(
                {
                    "id": 1,
                    "course": 500,
                    "time": "2026-07-20T10:00:00Z",
                    "thread": "step-10",
                }
            )
        },
    )
    await db_session.commit()

    await transform_community(db_session)
    await db_session.commit()

    r = await db_session.execute(text("SELECT data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    assert row is not None
    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    assert data["community"]["average_rating"] == 4.5
    assert data["community"]["total_comments"] == 1


# ─── Helpers (duplicated from test_transform to avoid import coupling) ─────


def _make_user(session, stepik_id=12345):
    from app.models import User
    from app.services.crypto import encrypt_token

    user = User(
        id=uuid.uuid4(),
        stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(user)
    return user


async def _make_course(session, user_id, stepik_course_id=100, title="Test"):
    cid = str(uuid.uuid4())
    await session.execute(
        text("""
        INSERT INTO courses (id, user_id, stepik_course_id, title, status, created_at)
        VALUES (:id, :uid, :sid, :t, :s, :now)
    """),
        {
            "id": cid,
            "uid": str(user_id),
            "sid": stepik_course_id,
            "t": title,
            "s": "Published",
            "now": datetime.now(UTC),
        },
    )
    return cid
