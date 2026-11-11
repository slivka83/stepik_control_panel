"""Общие помощники transform-слоя: разбор `_raw_json`, даты, когорты, вставка строк."""

import html
import json
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    COHORT_ACTIVE_DAYS,
    COHORT_FADING_DAYS,
    COHORT_PASSIVE_DAYS,
    ZOMBIE_DAYS_AFTER_JOIN,
)

logger = logging.getLogger(__name__)


def _ensure_json(val):
    """Handle _raw_json which is a dict (PG jsonb) or str (SQLite)."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (str, bytes, bytearray)):
        return json.loads(val)
    return val


def _serialize_data(val, session):
    """Serialize to JSON string. PG asyncpg expects string for jsonb codec."""
    return json.dumps(val, ensure_ascii=False)


def _parse_step_positions(raw) -> dict[int, int]:
    """step_id → позиция в уроке (1-based).

    raw_lesson.steps в реальной PG — jsonb (list); в SQLite-фикстуре — TEXT
    (JSON-строка). Оба варианта обязаны работать.
    """
    try:
        arr = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {}
    positions: dict[int, int] = {}
    if isinstance(arr, list):
        for i, sid in enumerate(arr):
            try:
                positions[int(sid)] = i + 1
            except (TypeError, ValueError):
                continue
    return positions


def _parse_raw(raw) -> dict:
    """Разобрать `_raw_json`: dict (PG jsonb) или JSON-строка (SQLite TEXT)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _step_grade(raw) -> tuple:
    """Средняя оценка шага пользователями из `_raw_json.num_grades`.

    `num_grades` = [g1, g2, g3, g4, g5] — распределение оценок 1..5
    (пять смайликов на странице шага). Среднее = Σ(cnt[i]·(i+1)) / Σ(cnt).
    Возвращает (grade, votes); без голосов — (None, 0).
    """
    ng = raw.get("num_grades") if isinstance(raw, dict) else None
    if not isinstance(ng, list):
        return None, 0
    votes_total = 0
    votes_count = 0
    for i, cnt in enumerate(ng):
        try:
            c = int(cnt)
        except (TypeError, ValueError):
            continue
        votes_total += c * (i + 1)
        votes_count += c
    if not votes_count:
        return None, 0
    return round(votes_total / votes_count, 2), votes_count


def _to_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _month_tuple(time_raw) -> tuple[int, int] | None:
    dt = parse_dt(time_raw)
    if dt is None:
        return None
    return dt.year, dt.month


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw) -> str:
    """Текст без HTML-разметки (Stepik хранит текст комментария как HTML)."""
    if not raw:
        return ""
    plain = _TAG_RE.sub(" ", str(raw))
    plain = html.unescape(plain)
    return re.sub(r"\s+", " ", plain).strip()


def parse_dt(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(int(raw), tz=UTC)
    s = str(raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def calculate_cohort_status(last_viewed_at, date_joined=None):
    if last_viewed_at is None:
        return "Zombie"
    if last_viewed_at.tzinfo is None:
        last_viewed_at = last_viewed_at.replace(tzinfo=UTC)
    days = (datetime.now(UTC) - last_viewed_at).days
    if days <= COHORT_ACTIVE_DAYS:
        return "Active"
    if days <= COHORT_PASSIVE_DAYS:
        return "Passive"
    if days <= COHORT_FADING_DAYS:
        return "Fading"
    if date_joined is not None:
        if date_joined.tzinfo is None:
            date_joined = date_joined.replace(tzinfo=UTC)
        days_after_join = (last_viewed_at.date() - date_joined.date()).days
        if 0 <= days_after_join <= ZOMBIE_DAYS_AFTER_JOIN:
            return "Zombie"
    return "Sleeping"


def get_course_status(is_public):
    return "Published" if is_public else "Draft"


async def load_course_map(session: AsyncSession) -> dict[int, str]:
    """stepik_course_id → id курса в приложении (UUID строкой)."""
    r = await session.execute(text("SELECT id, stepik_course_id FROM courses"))
    return {int(row[1]): str(row[0]) for row in r}


async def _get_buyer_names(session: AsyncSession) -> dict[int, str]:
    """Map buyer user_id → "First Last" from raw_user (same composition as student marts)."""
    rows = await session.execute(text("SELECT user_id, first_name, last_name FROM raw_user"))
    names: dict[int, str] = {}
    for row in rows:
        if row[0] is None:
            continue
        first = (row[1] or "").strip()
        last = (row[2] or "").strip()
        if first or last:
            names[int(row[0])] = f"{first} {last}".strip()
    return names


async def _insert_rows(session: AsyncSession, table: str, rows: list[dict]):
    if not rows:
        return
    col_names = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)
    await session.execute(
        text(f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"),
        rows,
    )
