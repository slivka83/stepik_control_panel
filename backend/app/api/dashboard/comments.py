"""Comments analytics: monthly/yearly/per-course aggregates + totals.

Reads the mart_comments view (rebuilt by transform_comments from raw_comment):
course attribution, year/month, likes/dislikes/replies, user name and step
path are denormalized at transform time — the API never touches raw_*.
Comments whose step is not attributable to a course are dropped by the
transform, so the invariant «filter = all courses» == «no filter» holds.

Like/dislike semantics: Stepik does not expose separate like/dislike counters
(/votes?ids[]= returns only the caller's own vote). The only vote aggregate on
a comment is vote_delta (net score), which is already synced. Likes = sum of
positive vote_delta, dislikes = module of the sum of negative vote_delta.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import (
    PeriodAggregator,
    course_label,
    format_month_label,
    get_courses_for_user,
    in_clause,
)
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import User

router = APIRouter()

LIST_TYPES = ("unanswered", "disliked")

# SQL ordering expressions for server-side sorting. Only whitelisted keys are
# interpolated into the query, so this is safe from SQL injection.
LIST_SORT_SQL = {
    "time": "time",
    "student": "user_name",
    # Сортируем по названию, которое видит пользователь, а не по числовому id.
    "course": "(SELECT COALESCE(c.title, '') FROM courses c "
    "WHERE c.stepik_course_id = mart_comments.stepik_course_id)",
    "text": "text",
    "likes": "likes",
    "dislikes": "dislikes",
    "replies": "replies",
    "step": "COALESCE(module_number, 0) * 100000 + COALESCE(lesson_number, 0) * 1000 + COALESCE(step_number, 0)",
}


def _empty() -> dict:
    return {
        "months": [],
        "years": [],
        "by_course": [],
        "totals": {"comments": 0, "students": 0, "likes": 0, "dislikes": 0, "replies": 0},
    }


@router.get("/comments")
async def get_comments(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    courses, _ = await get_courses_for_user(db, user, parse_course_ids(course_ids))
    selected_stepik = {c.stepik_course_id for c in courses}
    if not selected_stepik:
        return _empty()

    placeholders, params = in_clause(selected_stepik, "cid")
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, year, month, user_id, likes, dislikes, replies "
            f"FROM mart_comments WHERE is_solution = FALSE "
            f"AND stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    agg = PeriodAggregator({"likes": 0, "dislikes": 0, "replies": 0})
    for cid, year, month, user_id, likes, dislikes, replies in rows:
        agg.add(
            year=year,
            month=month,
            course_id=cid,
            student_id=user_id,
            likes=likes,
            dislikes=dislikes,
            replies=replies,
        )

    months = [
        {
            "month": format_month_label(m["month"], m["year"]),
            "year": m["year"],
            "month_num": m["month"],
            "students": m["students"],
            "total": m["total"],
            "likes": m["likes"],
            "dislikes": m["dislikes"],
            "replies": m["replies"],
        }
        for m in agg.months()
    ]

    years = agg.years()

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    by_course = []
    for c in agg.courses():
        course_uuid, title = course_label(course_by_stepik, c["stepik_course_id"])
        by_course.append(
            {
                "course_id": course_uuid,
                "stepik_course_id": c["stepik_course_id"],
                "title": title,
                "students": c["students"],
                "total": c["total"],
                "likes": c["likes"],
                "dislikes": c["dislikes"],
                "replies": c["replies"],
            }
        )

    t = agg.totals()
    totals = {
        "comments": t["total"],
        "students": t["students"],
        "likes": t["likes"],
        "dislikes": t["dislikes"],
        "replies": t["replies"],
    }

    return {"months": months, "years": years, "by_course": by_course, "totals": totals}


@router.get("/comments/list")
async def get_comments_list(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    list_type: str = Query("unanswered", alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("time"),
    order: str = Query("desc"),
    course_ids: str = Query(None),
):
    """Отдельные комментарии для вкладок «Не отвеченные» и «Дизлайки».

    Серверная пагинация/сортировка (как /students). Читает mart_comments:
    is_unanswered/is_disliked пресчитаны трансформом; не-атрибутируемые шаги
    отсутствуют в витрине, поэтому «фильтр = все курсы» == «без фильтра».
    """
    if list_type not in LIST_TYPES:
        raise HTTPException(status_code=400, detail=f"invalid type: {list_type!r}")
    if sort not in LIST_SORT_SQL:
        raise HTTPException(status_code=400, detail=f"invalid sort field: {sort!r}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    courses, _ = await get_courses_for_user(db, user, parse_course_ids(course_ids))
    selected_stepik = {c.stepik_course_id for c in courses}
    if not selected_stepik:
        return {"comments": [], "total": 0}

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    placeholders, params = in_clause(selected_stepik, "cid")
    type_filter = "is_unanswered = TRUE" if list_type == "unanswered" else "is_disliked = TRUE"
    sort_expr = LIST_SORT_SQL[sort]
    # NULLS LAST expressed via a CASE so it works on both PostgreSQL and SQLite.
    # Unique tiebreaker: сортировка по likes/replies с одинаковыми значениями
    # без него даёт произвольный порядок и дубли/пропуски строк между страницами.
    order_clause = (
        f"CASE WHEN {sort_expr} IS NULL THEN 1 ELSE 0 END, {sort_expr} {order.upper()}, comment_id ASC"
    )

    count_result = await db.execute(
        text(
            "SELECT count(*) FROM mart_comments "
            f"WHERE is_deleted = FALSE AND {type_filter} "
            f"AND is_solution = FALSE AND stepik_course_id IN ({placeholders})"
        ),
        params,
    )
    total = count_result.scalar() or 0

    rows = await db.execute(
        text(
            "SELECT comment_id, time, user_id, user_name, stepik_course_id, text, "
            "likes, dislikes, replies, lesson_id, step_number, module_number, "
            "lesson_number, module_title, lesson_title "
            f"FROM mart_comments WHERE is_deleted = FALSE AND {type_filter} "
            f"AND is_solution = FALSE AND stepik_course_id IN ({placeholders}) "
            f"ORDER BY {order_clause} LIMIT :limit OFFSET :skip"
        ),
        {**params, "limit": limit, "skip": skip},
    )

    comments = []
    for (
        comment_id, time_raw, user_id, user_name, cid, ctext, likes, dislikes,
        replies, lesson_id, step_number, module_number, lesson_number,
        module_title, lesson_title,
    ) in rows:
        course_obj = course_by_stepik.get(cid)
        mn, ln, sn = module_number, lesson_number, step_number
        comments.append(
            {
                "comment_id": comment_id,
                "time": time_raw,
                "user_id": user_id,
                "user_name": user_name,
                "course_id": str(course_obj.id) if course_obj else "",
                "course_title": course_obj.title if course_obj else "Unknown",
                "stepik_course_id": cid,
                "text": ctext,
                "likes": likes,
                "dislikes": dislikes,
                "replies": replies,
                "lesson_id": lesson_id,
                "step_number": step_number,
                "module_number": module_number,
                "lesson_number": lesson_number,
                "module_title": module_title,
                "lesson_title": lesson_title,
                "step_sort": (mn or 0) * 100000 + (ln or 0) * 1000 + (sn or 0) if mn and ln and sn else None,
            }
        )

    return {"comments": comments, "total": total}
