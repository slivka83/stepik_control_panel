"""Monthly chart series: revenue, submissions, active students, published solutions."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import (
    format_month_label,
    get_courses_for_user,
    weighted_success_pct,
    wilson_success_pct,
)
from app.api.dashboard.course_filter import (
    filter_community,
    filter_financials,
    parse_course_ids,
)
from app.database import get_db
from app.models import FinancialSnapshot, StudentEnrollment, Submission, User

router = APIRouter()


@router.get("/revenue")
async def get_revenue(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    if not snapshot:
        return {"months": []}
    if not parsed:
        months = snapshot.data.get("months", [])
    else:
        courses, _ = await get_courses_for_user(db, user, parsed)
        selected_stepik_ids = {c.stepik_course_id for c in courses}
        months = filter_financials(snapshot.data, selected_stepik_ids)["months"]
    return {"months": months}


@router.get("/submissions")
async def get_submissions(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    courses, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    if not course_ids:
        return {"months": [], "by_course": [], "years": []}

    month_result = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            extract("month", Submission.submission_time).label("month"),
            func.count(Submission.id).label("total"),
            func.count(Submission.id).filter(Submission.status == "correct").label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(Submission.course_id.in_(course_ids), Submission.is_author.is_(False))
        .group_by("year", "month")
        .order_by("year", "month")
    )
    month_rows = month_result.all()

    # Средний успех по строкам (не по попыткам): unweighted mean, иначе
    # один доминирующий месяц/курс сдвигает global в свою сторону.
    rates = [row.correct / row.total for row in month_rows if row.total > 0]
    global_pct = (sum(rates) / len(rates) * 100) if rates else 0.0

    months = []
    for row in month_rows:
        y, m = int(row.year), int(row.month)
        months.append(
            {
                "month": format_month_label(m, y),
                "total": row.total,
                "correct": row.correct,
                "students": row.students,
                "success_pct": round(wilson_success_pct(row.correct, row.total), 1),
                "weighted_success_pct": round(weighted_success_pct(row.correct, row.total, global_pct), 1),
            }
        )

    year_stats: dict[int, dict[str, int]] = {}
    for row in month_rows:
        y = int(row.year)
        agg = year_stats.setdefault(y, {"year": y, "total": 0, "correct": 0})
        agg["total"] += row.total
        agg["correct"] += row.correct

    year_students_result = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(Submission.course_id.in_(course_ids), Submission.is_author.is_(False))
        .group_by("year")
    )
    for row in year_students_result.all():
        y = int(row.year)
        if y in year_stats:
            year_stats[y]["students"] = row.students
    years = []
    for y in sorted(year_stats):
        agg = year_stats[y]
        years.append(
            {
                **agg,
                "success_pct": round(wilson_success_pct(agg["correct"], agg["total"]), 1),
                "weighted_success_pct": round(weighted_success_pct(agg["correct"], agg["total"], global_pct), 1),
            }
        )

    course_result = await db.execute(
        select(
            Submission.course_id,
            func.count(Submission.id).label("total"),
            func.count(Submission.id).filter(Submission.status == "correct").label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(Submission.course_id.in_(course_ids), Submission.is_author.is_(False))
        .group_by(Submission.course_id)
    )
    course_rows = course_result.all()

    course_by_id = {c.id: c for c in courses}

    by_course = []
    for course_row in course_rows:
        course_obj = course_by_id.get(course_row.course_id)
        by_course.append(
            {
                "course_id": course_row.course_id,
                "stepik_course_id": course_obj.stepik_course_id if course_obj else 0,
                "title": course_obj.title if course_obj else "Unknown",
                "total": course_row.total,
                "correct": course_row.correct,
                "students": course_row.students,
                "success_pct": round(wilson_success_pct(course_row.correct, course_row.total), 1),
                "weighted_success_pct": round(
                    weighted_success_pct(course_row.correct, course_row.total, global_pct), 1
                ),
            }
        )

    return {"months": months, "by_course": by_course, "years": years}


@router.get("/active-students")
async def get_active_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    _, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    if not course_ids:
        return {"months": []}

    per_course = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            extract("month", Submission.submission_time).label("month"),
            Submission.course_id,
            func.count(func.distinct(Submission.user_id)).label("cnt"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author.is_(False),
            Submission.user_id.isnot(None),
        )
        .group_by("year", "month", Submission.course_id)
        .order_by("year", "month")
    )
    per_course_rows = per_course.all()

    monthly: dict[tuple[int, int], int] = {}
    for row in per_course_rows:
        y, m = int(row.year), int(row.month)
        key = (y, m)
        monthly[key] = monthly.get(key, 0) + row.cnt

    all_unique = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            extract("month", Submission.submission_time).label("month"),
            func.count(func.distinct(Submission.user_id)).label("cnt"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author.is_(False),
            Submission.user_id.isnot(None),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    all_unique_rows = all_unique.all()
    unique_map = {(int(r.year), int(r.month)): r.cnt for r in all_unique_rows}

    months = []
    for y, m in sorted(monthly.keys()):
        months.append(
            {
                "month": format_month_label(m, y),
                "dark": monthly[(y, m)],
                "light": unique_map.get((y, m), 0),
            }
        )

    return {"months": months}


@router.get("/active-enrolled-students")
async def get_active_enrolled_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    _, course_ids = await get_courses_for_user(db, user, parse_course_ids(course_ids))

    if not course_ids:
        return {"months": []}

    per_course = await db.execute(
        select(
            extract("year", StudentEnrollment.last_viewed_at).label("year"),
            extract("month", StudentEnrollment.last_viewed_at).label("month"),
            StudentEnrollment.course_id,
            func.count(func.distinct(StudentEnrollment.student_id)).label("cnt"),
        )
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at.isnot(None),
        )
        .group_by("year", "month", StudentEnrollment.course_id)
        .order_by("year", "month")
    )
    per_course_rows = per_course.all()

    monthly: dict[tuple[int, int], int] = {}
    for row in per_course_rows:
        y, m = int(row.year), int(row.month)
        key = (y, m)
        monthly[key] = monthly.get(key, 0) + row.cnt

    all_unique = await db.execute(
        select(
            extract("year", StudentEnrollment.last_viewed_at).label("year"),
            extract("month", StudentEnrollment.last_viewed_at).label("month"),
            func.count(func.distinct(StudentEnrollment.student_id)).label("cnt"),
        )
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at.isnot(None),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    all_unique_rows = all_unique.all()
    unique_map = {(int(r.year), int(r.month)): r.cnt for r in all_unique_rows}

    months = []
    for y, m in sorted(monthly.keys()):
        months.append(
            {
                "month": format_month_label(m, y),
                "dark": monthly[(y, m)],
                "light": unique_map.get((y, m), 0),
            }
        )

    return {"months": months}


@router.get("/published-solutions")
async def get_published_solutions(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {"months": []}
    if parsed:
        courses, _ = await get_courses_for_user(db, user, parsed)
        community = await filter_community(db, snapshot.data, {c.stepik_course_id for c in courses})
    else:
        community = snapshot.data.get("community", {})

    monthly = community.get("solutions_monthly", {})
    months_res = []
    for key in sorted(monthly.keys()):
        y_str, m_str = key.split("-")
        y, m = int(y_str), int(m_str)
        val = monthly[key]
        months_res.append(
            {
                "month": format_month_label(m, y),
                "dark": val,
                "light": val,
            }
        )
    return {"months": months_res}
