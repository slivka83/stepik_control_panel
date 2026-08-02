"""Hardest steps ranking by success rate."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.database import get_db
from app.models import Course, Submission, User

router = APIRouter()


def _parse_step_positions(raw) -> dict[int, int]:
    """step_id → позиция в уроке (1-based).

    raw_lesson.steps в реальной PG — jsonb: asyncpg возвращает уже
    разобранный list. В SQLite-фикстуре колонка TEXT: приходит JSON-строка.
    Оба варианта обязаны работать (регрессия: json.loads(list) → TypeError
    и молча пустой результат).
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


@router.get("/hardest-steps")
async def get_hardest_steps(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    min_submissions: int = Query(10, ge=1),
):
    course_ids_result = await db.execute(select(Course.id).where(Course.user_id == user.id))
    course_ids = [r[0] for r in course_ids_result.all()]

    if not course_ids:
        return {"steps": []}

    course_map_result = await db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids)))
    course_map = {row[0]: row[1] for row in course_map_result.all()}

    result = await db.execute(
        select(
            Submission.stepik_step_id,
            Submission.course_id,
            func.count(Submission.id).label("total"),
            func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author.is_(False),
        )
        .group_by(Submission.stepik_step_id, Submission.course_id)
        .having(func.count(Submission.id) >= min_submissions)
        .order_by(
            (func.count(case((Submission.status == "correct", 1), else_=None)) * 1.0 / func.count(Submission.id)).asc()
        )
        .limit(limit)
    )
    rows = result.all()

    steps = []
    for row in rows:
        total = row.total
        correct = row.correct
        steps.append(
            {
                "stepik_step_id": row.stepik_step_id,
                "course_id": str(row.course_id),
                "course_title": course_map.get(row.course_id, "Unknown"),
                "total": total,
                "correct": correct,
                "wrong": total - correct,
                "success_pct": round((correct / total) * 100, 1) if total > 0 else 0,
                "students": row.students,
            }
        )

    step_lesson = {}
    if steps:
        ids = [s["stepik_step_id"] for s in steps]
        params = {f"id{i}": str(sid) for i, sid in enumerate(ids)}
        placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
        res = await db.execute(
            text(f"SELECT DISTINCT step_id, lesson FROM raw_step WHERE step_id IN ({placeholders})"),
            params,
        )
        step_lesson = {
            int(r[0]): int(r[1])
            for r in res
            if r[0] is not None and r[1] is not None
        }

    step_number_map = {}
    lesson_ids = sorted({lid for lid in step_lesson.values() if lid is not None})
    if lesson_ids:
        params_l = {f"lid{i}": str(lid) for i, lid in enumerate(lesson_ids)}
        placeholders_l = ", ".join(f":lid{i}" for i in range(len(lesson_ids)))
        res_l = await db.execute(
            text(f"SELECT lesson_id, steps FROM raw_lesson WHERE lesson_id IN ({placeholders_l})"),
            params_l,
        )
        for r in res_l:
            if r[0] is None or not r[1]:
                continue
            step_number_map.update(_parse_step_positions(r[1]))

    for s in steps:
        s["lesson_id"] = step_lesson.get(s["stepik_step_id"])
        s["step_number"] = step_number_map.get(s["stepik_step_id"])

    return {"steps": steps}
