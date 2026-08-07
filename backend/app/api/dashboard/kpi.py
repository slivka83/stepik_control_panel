"""KPI cards data: revenue, purchases, refunds, courses, rating, certificates, etc."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user, json_field
from app.api.dashboard.course_filter import (
    filter_community,
    filter_financials,
    filter_steps_average_grade,
    parse_course_ids,
)
from app.database import get_db
from app.models import FinancialSnapshot, StudentEnrollment, Submission, User

router = APIRouter()


async def _count_raw_month(db, table, field, prefix, course_field=None, course_ids=None) -> int:
    """Count raw rows whose `field` value starts with `prefix`.

    With course_field/course_ids restricts to the given stepik course ids
    (the raw layer is TEXT, so ids are compared as strings).
    """
    if course_field and course_ids is not None:
        ids = sorted(course_ids)
        placeholders = ", ".join(f":cid{i}" for i in range(len(ids)))
        params = {f"cid{i}": str(cid) for i, cid in enumerate(ids)}
        rows = await db.execute(text(f"SELECT _raw_json FROM {table} WHERE {course_field} IN ({placeholders})"), params)
    else:
        rows = await db.execute(text(f"SELECT _raw_json FROM {table}"))
    return sum(1 for row in rows.all() if str(json_field(row[0], field) or "").startswith(prefix))


async def _steps_average_grade(db) -> float:
    rows = await db.execute(text("SELECT _raw_json FROM raw_step"))
    votes_total = 0
    votes_count = 0
    for row in rows.all():
        ng = json_field(row[0], "num_grades")
        if not isinstance(ng, list):
            continue
        for i, cnt in enumerate(ng):
            try:
                c = int(cnt)
            except (TypeError, ValueError):
                continue
            votes_total += c * (i + 1)
            votes_count += c
    return round(votes_total / votes_count, 2) if votes_count else 0


def _pct(cur, prev):
    if prev:
        return round((cur - prev) / abs(prev) * 100)
    return 0 if cur == 0 else None


@router.get("/kpi")
async def get_kpi(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    course_ids: str = Query(None),
):
    parsed = parse_course_ids(course_ids)
    is_filtered = parsed is not None
    courses, selected_course_ids = await get_courses_for_user(db, user, parsed)
    selected_stepik_ids = {c.stepik_course_id for c in courses}

    if not selected_course_ids:
        return {
            "total_revenue": 0,
            "total_students": 0,
            "certificates_issued": 0,
            "courses_count": 0,
            "courses_published": 0,
            "courses_unpublished": 0,
            "total_income": 0,
            "total_turnover": 0,
            "total_refunds": 0,
            "total_payments": 0,
            "current_month_turnover": 0,
            "total_comments": 0,
            "total_reviews": 0,
            "average_rating": 0,
            "students_prev_months": 0,
            "certificates_prev_months": 0,
            "certificates_current_month": 0,
            "comments_prev_months": 0,
            "reviews_prev_months": 0,
            "reviews_current_month": 0,
            "certificates_change_pct": None,
            "reviews_change_pct": None,
            "published_solutions_prev_months": 0,
            "published_solutions_current_month": 0,
            "published_solutions_change_pct": None,
            "steps_average_grade": 0,
            "revenue_change_detail": None,
            "payments_change_detail": None,
            "refunds_change_detail": None,
            "refunds_pcs_change_detail": None,
            "students_change_detail": None,
            "certificates_change_detail": None,
            "published_solutions_change_detail": None,
            "comments_change_detail": None,
            "reviews_change_detail": None,
        }

    students_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(StudentEnrollment.course_id.in_(selected_course_ids))
    )
    total_students = students_result.scalar() or 0

    certs_result = await db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.course_id.in_(selected_course_ids),
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificates_issued = certs_result.scalar() or 0

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    summary = {}
    community = {}
    months = []
    if snapshot:
        if is_filtered:
            fin = filter_financials(snapshot.data, selected_stepik_ids)
            summary = fin["summary"]
            months = fin["months"]
            community = await filter_community(db, snapshot.data, selected_stepik_ids)
        else:
            summary = snapshot.data.get("summary", {})
            community = snapshot.data.get("community", {})
            months = snapshot.data.get("months", [])

    revenue_change_pct = None
    payments_change_pct = None
    refunds_change_pct = None
    refunds_pcs_change_pct = None
    current_month_payments = 0
    current_month_refunds_count = 0
    current_month_refunds_pcs = 0
    revenue_change_detail = None
    payments_change_detail = None
    refunds_change_detail = None
    refunds_pcs_change_detail = None
    if snapshot:
        current = summary.get("current_month_income", 0)
        if months:
            last = months[-1]
            current_month_payments = last.get("payments_count", 0)
            current_month_refunds_count = last.get("refunds", 0)
            current_month_refunds_pcs = last.get("refunds_count", 0)
            prev_income = months[-2].get("income", 0) if len(months) >= 2 else 0
            revenue_change_pct = _pct(current, prev_income)
            if revenue_change_pct is not None:
                revenue_change_detail = {"current": current, "previous": prev_income}
        if len(months) >= 2:
            prev_payments = months[-2].get("payments_count", 0)
            payments_change_pct = _pct(current_month_payments, prev_payments)
            if payments_change_pct is not None:
                payments_change_detail = {"current": current_month_payments, "previous": prev_payments}
            prev_refunds = months[-2].get("refunds", 0)
            refunds_change_pct = _pct(current_month_refunds_count, prev_refunds)
            if refunds_change_pct is not None:
                refunds_change_detail = {"current": current_month_refunds_count, "previous": prev_refunds}
            prev_refunds_pcs = months[-2].get("refunds_count", 0)
            refunds_pcs_change_pct = _pct(current_month_refunds_pcs, prev_refunds_pcs)
            if refunds_pcs_change_pct is not None:
                refunds_pcs_change_detail = {"current": current_month_refunds_pcs, "previous": prev_refunds_pcs}

    now = datetime.now(UTC)
    cur_year, cur_month = now.year, now.month
    if cur_month == 1:
        prev_year, prev_month = cur_year - 1, 12
    else:
        prev_year, prev_month = cur_year, cur_month - 1

    sub_result = await db.execute(
        select(
            extract("year", Submission.submission_time).label("y"),
            extract("month", Submission.submission_time).label("m"),
            func.count(Submission.id).label("cnt"),
        )
        .where(Submission.course_id.in_(selected_course_ids), Submission.is_author.is_(False))
        .group_by("y", "m")
    )
    sub_by_month = {(int(r.y), int(r.m)): r.cnt for r in sub_result.all()}

    enroll_result = await db.execute(
        select(
            extract("year", StudentEnrollment.date_joined).label("y"),
            extract("month", StudentEnrollment.date_joined).label("m"),
            func.count(StudentEnrollment.id).label("cnt"),
        )
        .where(StudentEnrollment.course_id.in_(selected_course_ids))
        .group_by("y", "m")
    )
    enroll_by_month = {(int(r.y), int(r.m)): r.cnt for r in enroll_result.all()}

    cur_subs = sub_by_month.get((cur_year, cur_month), 0)
    prev_subs = sub_by_month.get((prev_year, prev_month), 0)
    cur_enroll = enroll_by_month.get((cur_year, cur_month), 0)
    prev_enroll = enroll_by_month.get((prev_year, prev_month), 0)

    comments_monthly = community.get("comments_monthly", {})
    cur_comments_key = f"{cur_year}-{cur_month:02d}"
    prev_comments_key = f"{prev_year}-{prev_month:02d}"
    cur_comments = comments_monthly.get(cur_comments_key, 0)
    prev_comments = comments_monthly.get(prev_comments_key, 0)

    solutions_monthly = community.get("solutions_monthly", {})
    cur_solutions = solutions_monthly.get(cur_comments_key, 0)
    prev_solutions = solutions_monthly.get(prev_comments_key, 0)

    cur_prefix = f"{cur_year}-{cur_month:02d}"
    prev_prefix = f"{prev_year}-{prev_month:02d}"
    if is_filtered:
        cur_certificates = await _count_raw_month(
            db, "raw_certificate", "issue_date", cur_prefix, "course_id", selected_stepik_ids
        )
        prev_certificates = await _count_raw_month(
            db, "raw_certificate", "issue_date", prev_prefix, "course_id", selected_stepik_ids
        )
        cur_reviews = await _count_raw_month(
            db, "raw_course_review", "create_date", cur_prefix, "course", selected_stepik_ids
        )
        prev_reviews = await _count_raw_month(
            db, "raw_course_review", "create_date", prev_prefix, "course", selected_stepik_ids
        )
    else:
        cur_certificates = await _count_raw_month(db, "raw_certificate", "issue_date", cur_prefix)
        prev_certificates = await _count_raw_month(db, "raw_certificate", "issue_date", prev_prefix)
        cur_reviews = await _count_raw_month(db, "raw_course_review", "create_date", cur_prefix)
        prev_reviews = await _count_raw_month(db, "raw_course_review", "create_date", prev_prefix)

    if is_filtered:
        steps_average_grade = await filter_steps_average_grade(db, selected_stepik_ids)
    else:
        steps_average_grade = await _steps_average_grade(db)

    return {
        "total_revenue": summary.get("current_month_income", 0),
        "revenue_change_pct": revenue_change_pct,
        "revenue_change_detail": revenue_change_detail,
        "current_month_payments": current_month_payments,
        "payments_change_pct": payments_change_pct,
        "payments_change_detail": payments_change_detail,
        "current_month_refunds_count": current_month_refunds_count,
        "refunds_change_pct": refunds_change_pct,
        "refunds_change_detail": refunds_change_detail,
        "current_month_refunds_pcs": current_month_refunds_pcs,
        "refunds_pcs_change_pct": refunds_pcs_change_pct,
        "refunds_pcs_change_detail": refunds_pcs_change_detail,
        "current_month_submissions": cur_subs,
        "submissions_change_pct": _pct(cur_subs, prev_subs),
        "current_month_students": cur_enroll,
        "students_change_pct": _pct(cur_enroll, prev_enroll),
        "students_change_detail": (
            {"current": cur_enroll, "previous": prev_enroll} if _pct(cur_enroll, prev_enroll) is not None else None
        ),
        "current_month_comments": cur_comments,
        "comments_change_pct": _pct(cur_comments, prev_comments),
        "comments_change_detail": (
            {"current": cur_comments, "previous": prev_comments}
            if _pct(cur_comments, prev_comments) is not None
            else None
        ),
        "total_students": total_students,
        "students_prev_months": max(0, total_students - cur_enroll),
        "certificates_issued": certificates_issued,
        "certificates_prev_months": max(0, certificates_issued - cur_certificates),
        "certificates_current_month": cur_certificates,
        "certificates_change_pct": _pct(cur_certificates, prev_certificates),
        "certificates_change_detail": (
            {"current": cur_certificates, "previous": prev_certificates}
            if _pct(cur_certificates, prev_certificates) is not None
            else None
        ),
        "courses_count": len(courses),
        "courses_published": sum(1 for c in courses if c.status == "Published"),
        "courses_unpublished": sum(1 for c in courses if c.status != "Published"),
        "total_income": summary.get("total_income", 0),
        "total_turnover": summary.get("total_turnover", 0),
        "total_refunds": summary.get("total_refunds", 0),
        "total_refunds_count": summary.get("total_refunds_count", 0),
        "total_payments": summary.get("total_payments", 0),
        "current_month_turnover": summary.get("current_month_turnover", 0),
        "total_comments": community.get("total_comments", 0),
        "comments_prev_months": max(0, community.get("total_comments", 0) - cur_comments),
        "total_reviews": community.get("total_reviews", 0),
        "reviews_prev_months": max(0, community.get("total_reviews", 0) - cur_reviews),
        "reviews_current_month": cur_reviews,
        "reviews_change_pct": _pct(cur_reviews, prev_reviews),
        "reviews_change_detail": (
            {"current": cur_reviews, "previous": prev_reviews} if _pct(cur_reviews, prev_reviews) is not None else None
        ),
        "published_solutions_prev_months": max(0, community.get("total_solutions", 0) - cur_solutions),
        "published_solutions_current_month": cur_solutions,
        "published_solutions_change_pct": _pct(cur_solutions, prev_solutions),
        "published_solutions_change_detail": (
            {"current": cur_solutions, "previous": prev_solutions}
            if _pct(cur_solutions, prev_solutions) is not None
            else None
        ),
        "average_rating": community.get("average_rating", 0),
        "steps_average_grade": steps_average_grade,
    }
