"""Comments analytics: monthly/yearly/per-course aggregates + totals.

Reads raw_comment._raw_json (same approach as transform_community and
filter_community — the raw layer is TEXT/jsonb, ~1.5k rows). Each comment is
attributed to a course via the step→course map (raw_step JOIN raw_unit JOIN
raw_section); comments whose step is not in the structure are skipped in BOTH
filtered and unfiltered cases, so the invariant «filter = all courses» ==
«no filter» holds.

Like/dislike semantics: Stepik does not expose separate like/dislike counters
(/votes?ids[]= returns only the caller's own vote). The only vote aggregate on
a comment is vote_delta (net score), which is already synced. Likes = sum of
positive vote_delta, dislikes = module of the sum of negative vote_delta.
"""

import html
import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import build_step_path_maps, format_month_label, get_courses_for_user
from app.api.dashboard.course_filter import build_step_course_map, parse_course_ids
from app.database import get_db
from app.models import User

router = APIRouter()

_TAG_RE = re.compile(r"<[^>]+>")

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


def _parse_json(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _month_tuple(time_raw) -> tuple[int, int] | None:
    try:
        dt = datetime.fromisoformat(str(time_raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.year, dt.month


def _strip_html(raw) -> str:
    """Текст комментария без HTML-разметки (Stepik хранит text как HTML)."""
    if not raw:
        return ""
    plain = _TAG_RE.sub(" ", str(raw))
    plain = html.unescape(plain)
    return re.sub(r"\s+", " ", plain).strip()


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

    step_course = await build_step_course_map(db)

    rows = await db.execute(text("SELECT _raw_json FROM raw_comment"))

    month_buckets: dict[tuple[int, int], dict] = {}
    month_students: dict[tuple[int, int], set] = {}
    year_students: dict[int, set] = {}
    course_stats: dict[int, dict] = {}
    course_students: dict[int, set] = {}
    all_students: set[int] = set()

    for (raw_json,) in rows:
        cm = _parse_json(raw_json)
        if not cm:
            continue
        ym = _month_tuple(cm.get("time"))
        if not ym:
            continue
        target = _int_or_none(cm.get("target"))
        if target is None:
            continue
        cid = step_course.get(target)
        if cid is None or cid not in selected_stepik:
            continue

        user_id = _int_or_none(cm.get("user"))
        vote_delta = _int_or_none(cm.get("vote_delta")) or 0
        reply_count = _int_or_none(cm.get("reply_count")) or 0

        likes = vote_delta if vote_delta > 0 else 0
        dislikes = -vote_delta if vote_delta < 0 else 0

        bucket = month_buckets.setdefault(ym, {"total": 0, "likes": 0, "dislikes": 0, "replies": 0})
        bucket["total"] += 1
        bucket["likes"] += likes
        bucket["dislikes"] += dislikes
        bucket["replies"] += reply_count

        if user_id is not None:
            month_students.setdefault(ym, set()).add(user_id)
            year_students.setdefault(ym[0], set()).add(user_id)
            course_students.setdefault(cid, set()).add(user_id)
            all_students.add(user_id)

        cstats = course_stats.setdefault(cid, {"stepik_course_id": cid, "total": 0, "likes": 0, "dislikes": 0, "replies": 0})
        cstats["total"] += 1
        cstats["likes"] += likes
        cstats["dislikes"] += dislikes
        cstats["replies"] += reply_count

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
    for (y, m), b in month_buckets.items():
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
    type: str = Query("unanswered"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("time"),
    order: str = Query("desc"),
    course_ids: str = Query(None),
):
    """Отдельные комментарии для вкладок «Не отвеченные» и «Дизлайки».

    Серверная пагинация/сортировка (как /students). Читает только _raw_json;
    атрибуция через step→course map, не-атрибутируемые шаги пропускаются и
    с фильтром, и без (инвариант «фильтр = все курсы» == «без фильтра»).
    """
    if type not in LIST_TYPES:
        raise HTTPException(status_code=400, detail=f"invalid type: {type!r}")
    if sort not in LIST_SORTS:
        raise HTTPException(status_code=400, detail=f"invalid sort field: {sort!r}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    courses, _ = await get_courses_for_user(db, user, parse_course_ids(course_ids))
    selected_stepik = {c.stepik_course_id for c in courses}
    if not selected_stepik:
        return {"comments": [], "total": 0}

    step_course = await build_step_course_map(db)
    course_by_stepik = {c.stepik_course_id: c for c in courses}

    rows = await db.execute(text("SELECT _raw_json FROM raw_comment"))

    user_ids: set[int] = set()
    step_ids: set[int] = set()
    comments = []
    for (raw_json,) in rows:
        cm = _parse_json(raw_json)
        if not cm:
            continue
        if cm.get("is_deleted"):
            continue
        if type == "unanswered":
            if cm.get("is_staff_replied") is True or cm.get("user_role") == "teacher":
                continue
        else:
            vote = _int_or_none(cm.get("vote_delta"))
            if vote is None or vote >= 0:
                continue

        target = _int_or_none(cm.get("target"))
        if target is None:
            continue
        cid = step_course.get(target)
        if cid is None or cid not in selected_stepik:
            continue
        ym = _month_tuple(cm.get("time"))
        if not ym:
            continue

        user_id = _int_or_none(cm.get("user"))
        if user_id is not None:
            user_ids.add(user_id)
        step_ids.add(target)
        course_obj = course_by_stepik.get(cid)
        vote_delta = _int_or_none(cm.get("vote_delta")) or 0
        comments.append(
            {
                "comment_id": _int_or_none(cm.get("id")) or _int_or_none(cm.get("comment_id")),
                "target": target,
                "time": cm.get("time"),
                "user_id": user_id,
                "course_id": str(course_obj.id) if course_obj else "",
                "course_title": course_obj.title if course_obj else "Unknown",
                "stepik_course_id": cid,
                "text": _strip_html(cm.get("text")),
                "likes": vote_delta if vote_delta > 0 else 0,
                "dislikes": -vote_delta if vote_delta < 0 else 0,
                "replies": _int_or_none(cm.get("reply_count")) or 0,
            }
        )

    if comments:
        user_names = await _get_comment_user_names(db, user_ids)
        path_maps = await build_step_path_maps(db, sorted(step_ids))
        for c in comments:
            c["user_name"] = user_names.get(c["user_id"])
            pm = path_maps.get(c["target"], {})
            c["lesson_id"] = pm.get("lesson_id")
            c["step_number"] = pm.get("step_number")
            c["module_number"] = pm.get("module_number")
            c["lesson_number"] = pm.get("lesson_number")
            c["module_title"] = pm.get("module_title")
            c["lesson_title"] = pm.get("lesson_title")
            mn, ln, sn = c["module_number"], c["lesson_number"], c["step_number"]
            c["step_sort"] = (mn or 0) * 100000 + (ln or 0) * 1000 + (sn or 0) if mn and ln and sn else None

    total = len(comments)
    key = LIST_SORTS[sort]
    comments.sort(key=lambda c: key(c) if key(c) is not None else "", reverse=(order == "desc"))
    comments.sort(key=lambda c: key(c) is None)
    for c in comments:
        c.pop("target", None)
    return {"comments": comments[skip : skip + limit], "total": total}


async def _get_comment_user_names(db: AsyncSession, user_ids: set[int]) -> dict[int, str | None]:
    """user_id → «Имя Фамилия» из raw_user (как в student marts)."""
    if not user_ids:
        return {}
    ids = sorted(user_ids)
    params = {f"id{i}": str(uid) for i, uid in enumerate(ids)}
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    res = await db.execute(
        text(f"SELECT user_id, first_name, last_name FROM raw_user WHERE user_id IN ({placeholders})"),
        params,
    )
    names: dict[int, str | None] = {}
    for row in res:
        if row[0] is None:
            continue
        first = (row[1] or "").strip()
        last = (row[2] or "").strip()
        names[int(row[0])] = f"{first} {last}".strip() or None
    return names
