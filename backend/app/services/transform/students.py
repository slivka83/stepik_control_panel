"""Витрина студентов: student_enrollments + submissions + комментарии → student_marts."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import COHORT_RANK
from app.services.transform.common import (
    _ensure_json,
    _month_tuple,
    _to_bool,
    _to_int,
    calculate_cohort_status,
    is_published_solution,
    load_course_map,
    parse_dt,
)
from app.services.transform.courses import build_lesson_course_map, build_step_course_map

logger = logging.getLogger(__name__)


async def transform_students(session: AsyncSession):
    """Rebuild the student marts view layer — one row per student.

    Reads enrollments, submissions (app layer), comments and user profiles
    (raw layer), then replaces student_marts entirely.
    """
    logger.info("=== Student marts ===")

    agg = await session.execute(
        text("""
        SELECT student_id,
               count(*) AS courses_count,
               count(*) FILTER (WHERE certificate_issued) AS certificates,
               max(last_viewed_at) AS last_activity
        FROM student_enrollments
        GROUP BY student_id
    """)
    )
    agg_rows = list(agg)

    status_rows = await session.execute(
        text("""
        SELECT student_id, cohort_status, last_viewed_at, date_joined
        FROM student_enrollments
    """)
    )
    best_status: dict[int, str] = {}
    for sid, stored_status, last_viewed, joined in status_rows:
        # Legacy rows may have no stored status: derive it so the student card
        # and the /cohorts bar use the same segmentation.
        status = stored_status or calculate_cohort_status(parse_dt(last_viewed), parse_dt(joined))
        if sid not in best_status or COHORT_RANK.get(status, 99) < COHORT_RANK.get(best_status[sid], 99):
            best_status[sid] = status

    sub_rows = await session.execute(
        text("""
        SELECT user_id,
               count(*) AS cnt,
               count(*) FILTER (WHERE status = 'correct') AS correct_cnt
        FROM submissions
        WHERE user_id IS NOT NULL AND is_author = FALSE
        GROUP BY user_id
    """)
    )
    subs_by_user = {int(r.user_id): (r.cnt, r.correct_cnt) for r in sub_rows}

    # Comments live in the raw layer; the real author is in _raw_json because
    # the mapped `user` column may hold a stale OAuth client name. Course
    # attribution is the same as transform_comments/transform_community:
    # step→course first, the comment's own course as fallback. Comments from
    # deleted/foreign courses must not inflate the student's counters.
    course_map = await load_course_map(session)
    if not course_map:
        logger.warning("  no courses — clearing student_marts")
        await session.execute(text("DELETE FROM student_marts"))
        return
    step_course = await build_step_course_map(session)
    lesson_course = await build_lesson_course_map(session)
    comment_rows = await session.execute(text("SELECT _raw_json FROM raw_comment"))
    comments_by_user: dict[int, int] = {}
    solutions_by_user: dict[int, int] = {}
    for (raw_json,) in comment_rows:
        obj = _ensure_json(raw_json)
        if not isinstance(obj, dict) or _to_bool(obj.get("is_deleted")) is True:
            continue
        uid = _to_int(obj.get("user"))
        if uid is None:
            continue
        # transform_comments/mart_comments пропускают комментарий без
        # разбираемой даты — счётчик студента должен считать те же строки.
        if _month_tuple(obj.get("time")) is None:
            continue
        target = _to_int(obj.get("target"))
        course_id = step_course.get(target) if target is not None else None
        if course_id is None and target is not None:
            course_id = lesson_course.get(target)
        if course_id is None and target is not None and target in course_map:
            course_id = target
        if course_id is None:
            course_id = _to_int(obj.get("course"))
        if course_id not in course_map:
            continue
        if is_published_solution(obj):
            # Опубликованное решение — отдельная колонка «Опубликованные»;
            # в «Комментарии» оно не входит, как и на странице Комментариев.
            solutions_by_user[uid] = solutions_by_user.get(uid, 0) + 1
        else:
            comments_by_user[uid] = comments_by_user.get(uid, 0) + 1

    name_rows = await session.execute(text("SELECT user_id, first_name, last_name FROM raw_user"))
    names: dict[int, str] = {}
    for row in name_rows:
        uid = _to_int(row[0])
        if uid is None:
            continue
        first = (row[1] or "").strip()
        last = (row[2] or "").strip()
        if first or last:
            names[uid] = f"{first} {last}".strip()

    rows = []
    for r in agg_rows:
        sid = int(r.student_id)
        subs_cnt, subs_correct = subs_by_user.get(sid, (0, 0))
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "name": names.get(sid),
                "cohort_status": best_status.get(sid, "Sleeping"),
                "courses_count": r.courses_count,
                "certificates": r.certificates,
                "submissions_count": subs_cnt,
                "submissions_successful": subs_correct,
                "comments_count": comments_by_user.get(sid, 0),
                "published_solutions": solutions_by_user.get(sid, 0),
                "last_activity": r.last_activity,
                "updated_at": datetime.now(UTC),
            }
        )

    await session.execute(text("DELETE FROM student_marts"))
    if rows:
        col_names = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_str = ", ".join(f'"{c}"' for c in col_names)
        await session.execute(
            text(f"INSERT INTO student_marts ({cols_str}) VALUES ({placeholders})"),
            rows,
        )

    logger.info("  student_marts: %d rows", len(rows))
