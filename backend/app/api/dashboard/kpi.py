"""KPI cards data: revenue, purchases, refunds, courses, rating, certificates, etc."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user, in_clause, votes_weighted_grade
from app.api.dashboard.course_filter import (
    filter_community,
    filter_financials,
    filter_steps_average_grade,
    parse_course_ids,
)
from app.database import get_db
from app.models import FinancialSnapshot, StudentEnrollment, Submission, User

router = APIRouter()


_MART_MONTH_TABLES = {"mart_certificates", "mart_reviews", "mart_comments"}


async def _count_mart_month(db, table, year, month, course_ids=None, is_solution=None) -> int:
    """Count mart view rows in the given month.

    table: mart_certificates / mart_reviews / mart_comments (year/month are
    denormalized by the transforms). With course_ids (stepik course ids)
    restricts to those; is_solution optionally splits comments/solutions.
    """
    if table not in _MART_MONTH_TABLES:
        raise ValueError(f"unexpected mart table: {table!r}")
    where = ["year = :year", "month = :month"]
    params: dict = {"year": year, "month": month}
    if course_ids is not None:
        placeholders, cid_params = in_clause(course_ids, "cid")
        where.append(f"stepik_course_id IN ({placeholders})")
        params.update(cid_params)
    if is_solution is not None and table == "mart_comments":
        where.append("is_solution = :sol")
        params["sol"] = is_solution
    rows = await db.execute(
        text(f"SELECT count(*) FROM {table} WHERE {' AND '.join(where)}"), params
    )
    return rows.scalar() or 0


async def _count_mart_total(db, table, course_ids=None, is_solution=None) -> int:
    """Total rows in a mart view (same filters as _count_mart_month)."""
    if table not in _MART_MONTH_TABLES:
        raise ValueError(f"unexpected mart table: {table!r}")
    where = []
    params: dict = {}
    if course_ids is not None:
        placeholders, cid_params = in_clause(course_ids, "cid")
        where.append(f"stepik_course_id IN ({placeholders})")
        params.update(cid_params)
    if is_solution is not None and table == "mart_comments":
        where.append("is_solution = :sol")
        params["sol"] = is_solution
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    rows = await db.execute(text(f"SELECT count(*) FROM {table}{clause}"), params)
    return rows.scalar() or 0


async def _steps_average_grade(db) -> float:
    rows = await db.execute(text("SELECT grade, grade_votes FROM mart_steps"))
    return votes_weighted_grade(rows.all())


def _pct(cur, prev):
    if prev:
        return round((cur - prev) / abs(prev) * 100)
    return 0 if cur == 0 else None


def _trend(cur, prev) -> tuple[int | None, dict | None]:
    """KPI trend: percent plus the numbers behind it (None when percent is None)."""
    pct = _pct(cur, prev)
    detail = {"current": cur, "previous": prev} if pct is not None else None
    return pct, detail


# Пустое состояние должно иметь РОВНО тот же набор полей, что и заполненное:
# раньше часть ключей (current_month_*, total_refunds_count, *_change_*) в
# пустом ответе отсутствовала, и фронтенд получал undefined вместо нуля.
_EMPTY_KPI = {
    "total_revenue": 0,
    "revenue_change_pct": None,
    "revenue_change_detail": None,
    "current_month_payments": 0,
    "payments_change_pct": None,
    "payments_change_detail": None,
    "current_month_refunds_amount": 0,
    "refunds_amount_change_pct": None,
    "refunds_amount_change_detail": None,
    "current_month_refunds_count": 0,
    "refunds_count_change_pct": None,
    "refunds_count_change_detail": None,
    "current_month_submissions": 0,
    "submissions_change_pct": None,
    "current_month_students": 0,
    "students_change_pct": None,
    "students_change_detail": None,
    "current_month_comments": 0,
    "comments_change_pct": None,
    "comments_change_detail": None,
    "total_students": 0,
    "students_prev_months": 0,
    "certificates_issued": 0,
    "certificates_prev_months": 0,
    "certificates_current_month": 0,
    "certificates_change_pct": None,
    "certificates_change_detail": None,
    "courses_count": 0,
    "courses_published": 0,
    "courses_unpublished": 0,
    "total_income": 0,
    "total_turnover": 0,
    "total_refunds": 0,
    "total_refunds_count": 0,
    "total_payments": 0,
    "current_month_turnover": 0,
    "total_comments": 0,
    "comments_prev_months": 0,
    "total_reviews": 0,
    "reviews_prev_months": 0,
    "reviews_current_month": 0,
    "reviews_change_pct": None,
    "reviews_change_detail": None,
    "published_solutions_prev_months": 0,
    "published_solutions_current_month": 0,
    "published_solutions_change_pct": None,
    "published_solutions_change_detail": None,
    "average_rating": 0,
    "steps_average_grade": 0,
}


def _month_stat(months, year, month, key):
    """Статистика конкретного КАЛЕНДАРНОГО месяца из months-серии (0 если месяца нет).

    Regression: раньше «текущий месяц» брали позиционно (months[-1]) — в начале
    месяца до первой продажи это показывало цифры прошлого месяца, а «прошлый»
    (months[-2]) при пропуске месяцев перескакивал через них.
    """
    for m in months:
        if not isinstance(m, dict):
            continue
        if m.get("year") == year and m.get("month_num") == month:
            return m.get(key, 0)
    return 0


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
        return dict(_EMPTY_KPI)

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
    snapshot_data = snapshot.data if snapshot is not None and isinstance(snapshot.data, dict) else {}
    if snapshot:
        if is_filtered:
            fin = filter_financials(snapshot_data, selected_stepik_ids)
            summary = fin["summary"]
            months = fin["months"]
            community = await filter_community(db, snapshot_data, selected_stepik_ids)
        else:
            summary = snapshot_data.get("summary", {})
            community = snapshot_data.get("community", {})
            months = snapshot_data.get("months", [])
        if not isinstance(summary, dict):
            summary = {}
        if not isinstance(community, dict):
            community = {}
        if not isinstance(months, list):
            months = []

    revenue_change_pct = None
    payments_change_pct = None
    refunds_amount_change_pct = None
    refunds_count_change_pct = None
    current_month_income = 0
    current_month_payments = 0
    current_month_refunds_amount = 0
    current_month_refunds_count = 0
    revenue_change_detail = None
    payments_change_detail = None
    refunds_amount_change_detail = None
    refunds_count_change_detail = None
    now = datetime.now(UTC)
    cur_year, cur_month = now.year, now.month
    if cur_month == 1:
        prev_year, prev_month = cur_year - 1, 12
    else:
        prev_year, prev_month = cur_year, cur_month - 1
    if snapshot:
        # «Доход /месяц» — календарный текущий месяц из серии months, а не
        # поле summary: то фиксируется в момент синка и после смены месяца
        # показывает прошлый месяц. При пустой серии (старый снапшот/фикстура)
        # остаётся значение summary.
        current_month_income = _month_stat(months, cur_year, cur_month, "income")
        current_month_payments = _month_stat(months, cur_year, cur_month, "payments_count")
        if not months:
            current_month_income = summary.get("current_month_income", 0)
            current_month_payments = summary.get("current_month_payments", 0)
        # refunds — сумма в рублях, refunds_count — количество возвратов.
        # Раньше поля были перепутаны по смыслу (refunds_count содержал рубли).
        current_month_refunds_amount = _month_stat(months, cur_year, cur_month, "refunds")
        current_month_refunds_count = _month_stat(months, cur_year, cur_month, "refunds_count")
        prev_income = _month_stat(months, prev_year, prev_month, "income")
        revenue_change_pct, revenue_change_detail = _trend(current_month_income, prev_income)
        prev_payments = _month_stat(months, prev_year, prev_month, "payments_count")
        payments_change_pct, payments_change_detail = _trend(current_month_payments, prev_payments)
        prev_refunds = _month_stat(months, prev_year, prev_month, "refunds")
        refunds_amount_change_pct, refunds_amount_change_detail = _trend(
            current_month_refunds_amount, prev_refunds
        )
        prev_refunds_count = _month_stat(months, prev_year, prev_month, "refunds_count")
        refunds_count_change_pct, refunds_count_change_detail = _trend(
            current_month_refunds_count, prev_refunds_count
        )

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
    enroll_by_month = {
        (int(r.y), int(r.m)): r.cnt
        for r in enroll_result.all()
        if r.y is not None and r.m is not None
    }

    cur_subs = sub_by_month.get((cur_year, cur_month), 0)
    prev_subs = sub_by_month.get((prev_year, prev_month), 0)
    cur_enroll = enroll_by_month.get((cur_year, cur_month), 0)
    prev_enroll = enroll_by_month.get((prev_year, prev_month), 0)

    # Витрины — единый источник для KPI: те же строки, что на страницах
    # Комментарии/Отзывы/Сертификаты. Пока витрина не пересобрана (пустая),
    # остаётся fallback на снапшот/зачисления, чтобы карточки не обнулялись
    # на старой базе.
    mart_course_ids = selected_stepik_ids if is_filtered else None
    mart_certificates_total = await _count_mart_total(db, "mart_certificates", mart_course_ids)
    mart_reviews_total = await _count_mart_total(db, "mart_reviews", mart_course_ids)
    mart_comments_total = await _count_mart_total(
        db, "mart_comments", mart_course_ids, is_solution=False
    )
    mart_solutions_total = await _count_mart_total(
        db, "mart_comments", mart_course_ids, is_solution=True
    )
    has_comment_mart = (mart_comments_total + mart_solutions_total) > 0

    cur_certificates = await _count_mart_month(
        db, "mart_certificates", cur_year, cur_month, mart_course_ids
    )
    prev_certificates = await _count_mart_month(
        db, "mart_certificates", prev_year, prev_month, mart_course_ids
    )
    cur_reviews = await _count_mart_month(db, "mart_reviews", cur_year, cur_month, mart_course_ids)
    prev_reviews = await _count_mart_month(db, "mart_reviews", prev_year, prev_month, mart_course_ids)

    if has_comment_mart:
        cur_comments = await _count_mart_month(
            db, "mart_comments", cur_year, cur_month, mart_course_ids, is_solution=False
        )
        prev_comments = await _count_mart_month(
            db, "mart_comments", prev_year, prev_month, mart_course_ids, is_solution=False
        )
        cur_solutions = await _count_mart_month(
            db, "mart_comments", cur_year, cur_month, mart_course_ids, is_solution=True
        )
        prev_solutions = await _count_mart_month(
            db, "mart_comments", prev_year, prev_month, mart_course_ids, is_solution=True
        )
    else:
        comments_monthly = community.get("comments_monthly", {})
        if not isinstance(comments_monthly, dict):
            comments_monthly = {}
        cur_comments_key = f"{cur_year}-{cur_month:02d}"
        prev_comments_key = f"{prev_year}-{prev_month:02d}"
        cur_comments = comments_monthly.get(cur_comments_key, 0)
        prev_comments = comments_monthly.get(prev_comments_key, 0)

        solutions_monthly = community.get("solutions_monthly", {})
        if not isinstance(solutions_monthly, dict):
            solutions_monthly = {}
        cur_solutions = solutions_monthly.get(cur_comments_key, 0)
        prev_solutions = solutions_monthly.get(prev_comments_key, 0)

    total_certificates = mart_certificates_total or certificates_issued
    total_reviews = mart_reviews_total or int(community.get("total_reviews", 0) or 0)
    total_comments = mart_comments_total or int(community.get("total_comments", 0) or 0)
    total_solutions = mart_solutions_total or int(community.get("total_solutions", 0) or 0)

    if is_filtered:
        steps_average_grade = await filter_steps_average_grade(db, selected_stepik_ids)
    else:
        steps_average_grade = await _steps_average_grade(db)

    students_change_pct, students_change_detail = _trend(cur_enroll, prev_enroll)
    comments_change_pct, comments_change_detail = _trend(cur_comments, prev_comments)
    certificates_change_pct, certificates_change_detail = _trend(cur_certificates, prev_certificates)
    reviews_change_pct, reviews_change_detail = _trend(cur_reviews, prev_reviews)
    solutions_change_pct, solutions_change_detail = _trend(cur_solutions, prev_solutions)

    return {
        "total_revenue": current_month_income,
        "revenue_change_pct": revenue_change_pct,
        "revenue_change_detail": revenue_change_detail,
        "current_month_payments": current_month_payments,
        "payments_change_pct": payments_change_pct,
        "payments_change_detail": payments_change_detail,
        "current_month_refunds_amount": current_month_refunds_amount,
        "refunds_amount_change_pct": refunds_amount_change_pct,
        "refunds_amount_change_detail": refunds_amount_change_detail,
        "current_month_refunds_count": current_month_refunds_count,
        "refunds_count_change_pct": refunds_count_change_pct,
        "refunds_count_change_detail": refunds_count_change_detail,
        "current_month_submissions": cur_subs,
        "submissions_change_pct": _pct(cur_subs, prev_subs),
        "current_month_students": cur_enroll,
        "students_change_pct": students_change_pct,
        "students_change_detail": students_change_detail,
        "current_month_comments": cur_comments,
        "comments_change_pct": comments_change_pct,
        "comments_change_detail": comments_change_detail,
        "total_students": total_students,
        "students_prev_months": max(0, total_students - cur_enroll),
        "certificates_issued": total_certificates,
        "certificates_prev_months": max(0, total_certificates - cur_certificates),
        "certificates_current_month": cur_certificates,
        "certificates_change_pct": certificates_change_pct,
        "certificates_change_detail": certificates_change_detail,
        "courses_count": len(courses),
        "courses_published": sum(1 for c in courses if (c.status or "").lower() == "published"),
        "courses_unpublished": sum(1 for c in courses if (c.status or "").lower() != "published"),
        "total_income": summary.get("total_income", 0),
        "total_turnover": summary.get("total_turnover", 0),
        "total_refunds": summary.get("total_refunds", 0),
        "total_refunds_count": summary.get("total_refunds_count", 0),
        "total_payments": summary.get("total_payments", 0),
        "current_month_turnover": summary.get("current_month_turnover", 0),
        "total_comments": total_comments,
        "comments_prev_months": max(0, total_comments - cur_comments),
        "total_reviews": total_reviews,
        "reviews_prev_months": max(0, total_reviews - cur_reviews),
        "reviews_current_month": cur_reviews,
        "reviews_change_pct": reviews_change_pct,
        "reviews_change_detail": reviews_change_detail,
        "published_solutions_prev_months": max(0, total_solutions - cur_solutions),
        "published_solutions_current_month": cur_solutions,
        "published_solutions_change_pct": solutions_change_pct,
        "published_solutions_change_detail": solutions_change_detail,
        "average_rating": community.get("average_rating", 0),
        "steps_average_grade": steps_average_grade,
    }
