"""Курсы: raw_course → courses и карта шаг → курс."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import (
    _parse_step_positions,
    _to_int,
    get_course_status,
    parse_dt,
)

logger = logging.getLogger(__name__)

# Дочерние таблицы курса. В миграциях FK созданы без ON DELETE CASCADE
# (в модели submissions cascade есть, но в БД — нет), поэтому удаление курса,
# исчезнувшего на Stepik, падало на FK. Чистим явно и в порядке зависимостей.
_COURSE_CHILD_TABLES = (
    "mart_steps",
    "mart_comments",
    "mart_certificates",
    "mart_reviews",
    "mart_lessons",
    "mart_modules",
    "student_enrollments",
    "submissions",
)


async def _delete_course(session: AsyncSession, course_id: str) -> None:
    for table in _COURSE_CHILD_TABLES:
        await session.execute(text(f"DELETE FROM {table} WHERE course_id = :cid"), {"cid": course_id})
    await session.execute(text("DELETE FROM courses WHERE id = :cid"), {"cid": course_id})


async def transform_courses(session: AsyncSession, user_id: str | None = None):
    logger.info("=== Courses ===")
    r = await session.execute(
        text("""
        SELECT course_id, title, became_published_at, is_public
        FROM raw_course ORDER BY course_id
    """)
    )
    raw_courses = [dict(r._mapping) for r in r]
    uid_param = str(user_id) if user_id else None
    if uid_param:
        r = await session.execute(
            text("SELECT id, stepik_course_id FROM courses WHERE user_id = :uid"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(
            text("SELECT id, stepik_course_id FROM courses ORDER BY created_at, id")
        )
    existing = {row[1]: str(row[0]) for row in r}

    # stepik_course_id уникален глобально, поэтому нельзя вставлять курс,
    # который уже принадлежит другой локальной учётной записи: раньше это
    # падало с UniqueViolation и роняло всю синхронизацию.
    r = await session.execute(text("SELECT stepik_course_id FROM courses"))
    taken_ids = {row[0] for row in r}

    if uid_param:
        r = await session.execute(
            text("SELECT id FROM users WHERE id = :uid LIMIT 1"),
            {"uid": uid_param},
        )
    else:
        r = await session.execute(text("SELECT id FROM users ORDER BY created_at, id LIMIT 1"))
    user_row = r.fetchone()
    if not user_row:
        logger.warning("No user found")
        return
    user_id_db = str(user_row[0])

    seen_ids = set()
    upserted = 0
    skipped = 0
    for rc in raw_courses:
        sid = rc["course_id"]
        if sid is None:
            continue
        sid = int(sid)
        seen_ids.add(sid)
        is_pub_raw = rc.get("is_public")
        if is_pub_raw is not None:
            if isinstance(is_pub_raw, bool):
                is_pub = is_pub_raw
            elif isinstance(is_pub_raw, (int, float)):
                is_pub = bool(is_pub_raw)
            else:
                is_pub = str(is_pub_raw).lower() in ("true", "1")
        else:
            is_pub = None
        pub_dt = None
        if is_pub:
            pub_raw = rc.get("became_published_at")
            pub_dt = parse_dt(pub_raw) if pub_raw else None
        status = get_course_status(is_pub) if is_pub is not None else None
        title = (rc.get("title") or "Untitled")[:255]

        if sid in existing:
            await session.execute(
                text("""
                    UPDATE courses
                    SET title = :t,
                        status = COALESCE(:s, status),
                        published_at = COALESCE(:p, published_at)
                    WHERE stepik_course_id = :sid
                """),
                {"t": title, "s": status, "p": pub_dt, "sid": sid},
            )
            upserted += 1
        elif sid in taken_ids:
            skipped += 1
        else:
            await session.execute(
                text("""
                    INSERT INTO courses (id, user_id, stepik_course_id, title, status, published_at, created_at)
                    VALUES (:id, :uid, :sid, :t, :s, :p, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "uid": user_id_db,
                    "sid": sid,
                    "t": title,
                    "s": status or "Draft",
                    "p": pub_dt,
                    "now": datetime.now(UTC),
                },
            )
            taken_ids.add(sid)
            upserted += 1

    deleted = 0
    for sid, cid_str in existing.items():
        if sid not in seen_ids:
            await _delete_course(session, cid_str)
            deleted += 1

    logger.info("  %d upserted, %d deleted, %d skipped (owned by another user)", upserted, deleted, skipped)


async def build_lesson_course_map(session: AsyncSession) -> dict[int, int]:
    """lesson_id → stepik course id (first course by numeric id).

    Нужна для комментариев, прикреплённых к уроку, а не к шагу: Stepik
    возвращает `target` без типа, и id уроков/шагов могут совпадать.
    """
    r = await session.execute(
        text("""
        SELECT l.lesson_id, sec.course
        FROM raw_lesson l
        JOIN raw_unit u ON u.lesson_id = l.lesson_id
        JOIN raw_section sec ON sec.section_id = u.section_id
        WHERE l.lesson_id IS NOT NULL AND sec.course IS NOT NULL
    """)
    )
    rows = []
    for lesson_id, course in r:
        lesson_int = _to_int(lesson_id)
        course_int = _to_int(course)
        if lesson_int is not None and course_int is not None:
            rows.append((course_int, lesson_int))
    result: dict[int, int] = {}
    for course_int, lesson_int in sorted(rows):
        result.setdefault(lesson_int, course_int)
    return result


async def build_step_course_map(session: AsyncSession) -> dict[int, int]:
    """step_id → stepik course id (первый по возрастанию course id).

    Источник истины — структура (`raw_lesson.steps` → unit → section), как в
    `transform_steps`. `raw_step.lesson` используется только как fallback для
    шагов, которых нет в списках уроков: иначе структура, решения и
    комментарии могли приписать один и тот же шаг разным курсам.
    """
    result: dict[int, int] = {}

    # raw_section.course — TEXT, поэтому SQL ORDER BY по нему сортирует
    # лексикографически ("10" < "9"). Приводим в Python к int и только потом
    # выбираем «первый курс» — ровно та же нумерация, что в transform_steps.
    r = await session.execute(
        text("""
        SELECT l.lesson_id, l.steps, sec.course
        FROM raw_lesson l
        JOIN raw_unit u ON u.lesson_id = l.lesson_id
        JOIN raw_section sec ON sec.section_id = u.section_id
        WHERE l.lesson_id IS NOT NULL AND sec.course IS NOT NULL
    """)
    )
    structure_rows = []
    for lesson_id, steps, course in r:
        course_int = _to_int(course)
        lesson_int = _to_int(lesson_id)
        if course_int is None or lesson_int is None:
            continue
        structure_rows.append((course_int, lesson_int, steps))
    for _course, _lesson, steps in sorted(structure_rows, key=lambda row: (row[0], row[1])):
        for step_id in _parse_step_positions(steps):
            result.setdefault(step_id, _course)

    # Fallback: шаг знает свой урок, но урок не попал в списки steps/юниты.
    r = await session.execute(
        text("""
        SELECT DISTINCT s.step_id, sec.course
        FROM raw_step s
        JOIN raw_unit u ON u.lesson_id = s.lesson
        JOIN raw_section sec ON sec.section_id = u.section_id
        WHERE s.step_id IS NOT NULL AND sec.course IS NOT NULL
    """)
    )
    fallback_rows = []
    for step_id, course in r:
        step_int = _to_int(step_id)
        course_int = _to_int(course)
        if step_int is not None and course_int is not None:
            fallback_rows.append((step_int, course_int))
    for step_int, course_int in sorted(fallback_rows):
        result.setdefault(step_int, course_int)
    return result
