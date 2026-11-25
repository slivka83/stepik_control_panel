"""Paginated aggregated student list.

Reads the student_marts view layer only — one row per student, rebuilt
by transform_students at the end of each sync.

With ?course_ids= the list is restricted to students enrolled in at least
one of the selected courses (student_marts has no per-course breakdown, so
the membership is resolved via student_enrollments). The counters shown in
the rows are then recomputed for the same selected courses — otherwise the
table would show account-wide numbers next to a filtered cohort bar.
"""

from datetime import UTC
from functools import cmp_to_key

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.constants import COHORT_RANK
from app.database import get_db
from app.models import (
    Course,
    MartCertificate,
    MartComment,
    StudentEnrollment,
    StudentMart,
    Submission,
    User,
)

router = APIRouter()

COHORT_SORT_RANK = case(
    *[(StudentMart.cohort_status == status, rank) for status, rank in COHORT_RANK.items()],
    else_=99,
)

SORTABLE = {
    "name": StudentMart.name,
    # Не алфавит: порядок как в полосе когорт (Active → Passive → …).
    "cohort_status": COHORT_SORT_RANK,
    "courses_count": StudentMart.courses_count,
    "certificates": StudentMart.certificates,
    "submissions_count": StudentMart.submissions_count,
    "submissions_successful": StudentMart.submissions_successful,
    "comments_count": StudentMart.comments_count,
    "published_solutions": StudentMart.published_solutions,
    "last_activity": StudentMart.last_activity,
}


async def _filtered_stats(db: AsyncSession, courses: list[Course], student_ids: list[int]) -> dict[int, dict]:
    """Recompute row counters for the selected courses.

    student_marts stores account-wide aggregates. When the user filters the
    panel by courses, the row numbers must describe the same selection as the
    cohort bar and the other pages.
    """
    if not student_ids or not courses:
        return {}
    course_uuids = [c.id for c in courses]
    stepik_ids = [c.stepik_course_id for c in courses]
    stats: dict[int, dict] = {
        sid: {
            "courses_count": 0,
            "certificates": 0,
            "submissions_count": 0,
            "submissions_successful": 0,
            "comments_count": 0,
            "published_solutions": 0,
            "last_activity": None,
            "cohort_status": None,
            "_rank": 99,
        }
        for sid in student_ids
    }

    # SQLite/asyncpg ограничивают число bind-параметров; фильтрованный список
    # может содержать десятки тысяч студентов — агрегируем порциями.
    chunk_size = 500
    for start in range(0, len(student_ids), chunk_size):
        chunk = student_ids[start : start + chunk_size]
        enrollments = await db.execute(
            select(
                StudentEnrollment.student_id,
                StudentEnrollment.cohort_status,
                func.count(StudentEnrollment.id).label("cnt"),
                func.max(StudentEnrollment.last_viewed_at).label("last_viewed"),
            )
            .where(
                StudentEnrollment.course_id.in_(course_uuids),
                StudentEnrollment.student_id.in_(chunk),
            )
            .group_by(StudentEnrollment.student_id, StudentEnrollment.cohort_status)
        )
        for sid, status, cnt, last_viewed in enrollments:
            row = stats.get(sid)
            if row is None:
                continue
            row["courses_count"] += cnt
            if last_viewed is not None and (row["last_activity"] is None or last_viewed > row["last_activity"]):
                row["last_activity"] = last_viewed
            rank = COHORT_RANK.get(status, 99)
            if rank < row["_rank"]:
                row["_rank"] = rank
                row["cohort_status"] = status

        certificates = await db.execute(
            select(MartCertificate.user_id, func.count(MartCertificate.id))
            .where(
                MartCertificate.stepik_course_id.in_(stepik_ids),
                MartCertificate.user_id.in_(chunk),
            )
            .group_by(MartCertificate.user_id)
        )
        for sid, cnt in certificates:
            if sid in stats:
                stats[sid]["certificates"] = cnt

        submissions = await db.execute(
            select(
                Submission.user_id,
                func.count(Submission.id).label("cnt"),
                func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            )
            .where(
                Submission.course_id.in_(course_uuids),
                Submission.user_id.in_(chunk),
                Submission.is_author.is_(False),
            )
            .group_by(Submission.user_id)
        )
        for sid, cnt, correct in submissions:
            if sid in stats:
                stats[sid]["submissions_count"] = cnt
                stats[sid]["submissions_successful"] = correct

        comments = await db.execute(
            select(
                MartComment.user_id,
                func.count(case((MartComment.is_solution.is_(False), 1), else_=None)).label("comments"),
                func.count(case((MartComment.is_solution.is_(True), 1), else_=None)).label("solutions"),
            )
            .where(
                MartComment.stepik_course_id.in_(stepik_ids),
                MartComment.user_id.in_(chunk),
            )
            .group_by(MartComment.user_id)
        )
        for sid, comments_count, solutions_count in comments:
            if sid in stats:
                stats[sid]["comments_count"] = comments_count
                stats[sid]["published_solutions"] = solutions_count

    for row in stats.values():
        if row["cohort_status"] is None:
            row["cohort_status"] = "Sleeping"

    return stats


@router.get("/students")
async def get_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("last_activity"),
    order: str = Query("desc"),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    courses: list[Course] | None = None
    course_uuids = None
    if parsed is not None:
        courses, course_uuids = await get_courses_for_user(db, user, parsed)

    col = SORTABLE.get(sort)
    if col is None:
        raise HTTPException(status_code=400, detail=f"invalid sort field: {sort!r}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    primary = col.asc().nullslast() if order == "asc" else col.desc().nullslast()
    order_by = [primary, StudentMart.student_id.asc()]

    base = select(StudentMart)
    if course_uuids is not None:
        in_selected = exists().where(
            StudentEnrollment.student_id == StudentMart.student_id,
            StudentEnrollment.course_id.in_(course_uuids),
        )
        base = base.where(in_selected)

    rows: list[StudentMart]
    filtered = None
    if course_uuids is None:
        count_result = await db.execute(select(func.count(StudentMart.id)))
        total = count_result.scalar() or 0
        result = await db.execute(base.order_by(*order_by).offset(skip).limit(limit))
        rows = list(result.scalars().all())
    else:
        # Сортировать по account-wide счётчикам, показывая отфильтрованные,
        # нельзя: порядок строк и страницы противоречили бы значениям в
        # ячейках. При активном фильтре берём всех подходящих студентов,
        # считаем их счётчики по выбранным курсам и сортируем уже их.
        result = await db.execute(base)
        all_rows = list(result.scalars().all())
        total = len(all_rows)
        filtered = await _filtered_stats(db, courses or [], [m.student_id for m in all_rows])

        def value_of(m: StudentMart):
            row = filtered.get(m.student_id) or {}
            if sort == "name":
                return m.name
            if sort == "cohort_status":
                return COHORT_RANK.get(row.get("cohort_status") or m.cohort_status, 99)
            if sort == "last_activity":
                # Не подставляем account-wide активность: она относится к
                # другому набору курсов.
                return row.get("last_activity")
            return row.get(sort, getattr(m, sort, None))

        def compare(a: StudentMart, b: StudentMart):
            va, vb = value_of(a), value_of(b)
            if va is None and vb is None:
                return (a.student_id > b.student_id) - (a.student_id < b.student_id)
            if va is None:
                return 1
            if vb is None:
                return -1
            if isinstance(va, str) and isinstance(vb, str):
                la, lb = va.casefold(), vb.casefold()
                diff = (la > lb) - (la < lb)
            else:
                diff = (va > vb) - (va < vb)
            if order == "desc":
                diff = -diff
            return diff or ((a.student_id > b.student_id) - (a.student_id < b.student_id))

        all_rows.sort(key=cmp_to_key(compare))
        rows = all_rows[skip : skip + limit]

    students = []
    for m in rows:
        last_activity = m.last_activity
        row = filtered.get(m.student_id) if filtered is not None else None
        if row is not None:
            last_activity = row["last_activity"]
        if last_activity is not None and last_activity.tzinfo is None:
            # SQLite теряет tz; фронтенд иначе трактует время как локальное.
            last_activity = last_activity.replace(tzinfo=UTC)
        students.append(
            {
                "student_id": m.student_id,
                "name": m.name,
                "profile_url": f"https://stepik.org/users/{m.student_id}",
                "cohort_status": row["cohort_status"] if row else m.cohort_status,
                "courses_count": row["courses_count"] if row else m.courses_count,
                "certificates": row["certificates"] if row else m.certificates,
                "submissions_count": row["submissions_count"] if row else m.submissions_count,
                "submissions_successful": (row["submissions_successful"] if row else m.submissions_successful),
                "comments_count": row["comments_count"] if row else m.comments_count,
                "published_solutions": (row["published_solutions"] if row else m.published_solutions),
                "last_activity": last_activity.isoformat() if last_activity else None,
            }
        )

    return {"students": students, "total": total}
