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
from app.api.dashboard.common import format_month_label, get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.database import get_db
from app.models import User

router = APIRouter()

LIST_TYPES = ("unanswered", "disliked")

# sort key → функция извлечения значения из строки списка (для серверной сортировки)
LIST_SORTS = {
    "time": lambda c: c["time"],
    "student": lambda c: c["user_name"],
    "course": lambda c: c["course_title"],
    "text": lambda c: c["text"],
    "likes": lambda c: c["likes"],
    "dislikes": lambda c: c["dislikes"],
    "replies": lambda c: c["replies"],
    "step": lambda c: c["step_sort"],
}


def _empty() -> dict:
    return {
        "months": [],
        "years": [],
        "by_course": [],
        "totals": {"comments": 0, "students": 0, "likes": 0, "dislikes": 0, "replies": 0},
    }


def _in_clause(stepik_ids: set[int]) -> tuple[str, dict]:
    ids = sorted(stepik_ids)
    placeholders = ", ".join(f":cid{i}" for i in range(len(ids)))
    return placeholders, {f"cid{i}": cid for i, cid in enumerate(ids)}


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

    placeholders, params = _in_clause(selected_stepik)
    rows = await db.execute(
        text(
            "SELECT stepik_course_id, year, month, user_id, likes, dislikes, replies "
            f"FROM mart_comments WHERE stepik_course_id IN ({placeholders})"
        ),
        params,
    )

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for cid, year, month, user_id, likes, dislikes, replies in rows:
        if year is None or month is None:
            continue
        ym = (year, month)

        bucket = month_buckets.setdefault(ym, {"total": 0, "likes": 0, "dislikes": 0, "replies": 0})
        bucket["total"] += 1
        bucket["likes"] += likes
        bucket["dislikes"] += dislikes
        bucket["replies"] += replies

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(year, set()).add(user_id)
            course_students.setdefault(cid, set()).add(user_id)
            all_students.add(user_id)

        cstats = course_stats.setdefault(cid, {"stepik_course_id": cid, "total": 0, "likes": 0, "dislikes": 0, "replies": 0})  # noqa: E501
        cstats["total"] += 1
        cstats["likes"] += likes
        cstats["dislikes"] += dislikes
        cstats["replies"] += replies

    months = []
    for (y, m) in sorted(month_buckets):
        b = month_buckets[(y, m)]
        months.append(
            {
                "month": format_month_label(m, y),
                "students": len(month_students.get((y, m), ())),
                "total": b["total"],
                "likes": b["likes"],
                "dislikes": b["dislikes"],
                "replies": b["replies"],
            }
        )

    year_aggs: dict[int, dict] = {}
    for (y, _m), b in month_buckets.items():
        agg = year_aggs.setdefault(y, {"year": y, "total": 0, "likes": 0, "dislikes": 0, "replies": 0})
        agg["total"] += b["total"]
        agg["likes"] += b["likes"]
        agg["dislikes"] += b["dislikes"]
        agg["replies"] += b["replies"]
    years = []
    for y in sorted(year_aggs):
        agg = year_aggs[y]
        agg["students"] = len(year_students.get(y, ()))
        years.append(agg)

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    by_course = []
    for cid in sorted(course_stats):
        st = course_stats[cid]
        course_obj = course_by_stepik.get(cid)
        by_course.append(
            {
                "course_id": str(course_obj.id) if course_obj else "",
                "stepik_course_id": cid,
                "title": course_obj.title if course_obj else "Unknown",
                "students": len(course_students.get(cid, ())),
                "total": st["total"],
                "likes": st["likes"],
                "dislikes": st["dislikes"],
                "replies": st["replies"],
            }
        )

    totals = {
        "comments": sum(b["total"] for b in month_buckets.values()),
        "students": len(all_students),
        "likes": sum(b["likes"] for b in month_buckets.values()),
        "dislikes": sum(b["dislikes"] for b in month_buckets.values()),
        "replies": sum(b["replies"] for b in month_buckets.values()),
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
    if sort not in LIST_SORTS:
        raise HTTPException(status_code=400, detail=f"invalid sort field: {sort!r}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    courses, _ = await get_courses_for_user(db, user, parse_course_ids(course_ids))
    selected_stepik = {c.stepik_course_id for c in courses}
    if not selected_stepik:
        return {"comments": [], "total": 0}

    course_by_stepik = {c.stepik_course_id: c for c in courses}
    placeholders, params = _in_clause(selected_stepik)
    type_filter = "is_unanswered = TRUE" if list_type == "unanswered" else "is_disliked = TRUE"

    rows = await db.execute(
        text(
            "SELECT comment_id, time, user_id, user_name, stepik_course_id, text, "
            "likes, dislikes, replies, lesson_id, step_number, module_number, "
            "lesson_number, module_title, lesson_title "
            f"FROM mart_comments WHERE is_deleted = FALSE AND {type_filter} "
            f"AND stepik_course_id IN ({placeholders})"
        ),
        params,
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

    total = len(comments)
    key = LIST_SORTS[sort]
    comments.sort(key=lambda c: key(c) if key(c) is not None else "", reverse=(order == "desc"))
    comments.sort(key=lambda c: key(c) is None)
    return {"comments": comments[skip : skip + limit], "total": total}
