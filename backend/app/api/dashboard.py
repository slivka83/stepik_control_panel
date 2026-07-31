from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract, case, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
import json

from app.database import get_db
from app.models import Course, StudentEnrollment, FinancialSnapshot, User, Submission
from app.api.auth import get_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/alerts")
async def get_alerts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    certs_pending_query = (
        select(
            Course.id,
            Course.title,
            Course.stepik_course_id,
            func.count(StudentEnrollment.id).label("count"),
        )
        .join(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(
            Course.user_id == user.id,
            StudentEnrollment.points_earned >= 100,
            StudentEnrollment.certificate_issued.is_(False),
        )
        .group_by(Course.id, Course.title, Course.stepik_course_id)
    )
    certs_result = await db.execute(certs_pending_query)
    certs_rows = certs_result.all()

    low_score_query = (
        select(
            Course.id,
            Course.title,
            Course.stepik_course_id,
            func.count(StudentEnrollment.id).label("count"),
        )
        .join(StudentEnrollment, Course.id == StudentEnrollment.course_id)
        .where(
            Course.user_id == user.id,
            StudentEnrollment.points_earned == 0,
        )
        .group_by(Course.id, Course.title, Course.stepik_course_id)
        .having(func.count(StudentEnrollment.id) > 10)
    )
    low_score_result = await db.execute(low_score_query)
    low_score_rows = low_score_result.all()

    alerts = []
    for row in certs_rows:
        alerts.append({
            "type": "warning",
            "message": f"{row.count} студентов набрали проходной балл, но не получили сертификат",
            "link": f"https://stepik.org/course/{row.stepik_course_id}/certificates",
            "link_text": "Открыть на Stepik",
        })
    for row in low_score_rows:
        alerts.append({
            "type": "error",
            "message": f"{row.count} студентов на курсе «{row.title}» не набрали ни одного балла",
            "link": f"https://stepik.org/course/{row.stepik_course_id}/students",
            "link_text": "Посмотреть на Stepik →",
        })

    return {"alerts": alerts}


@router.get("/kpi")
async def get_kpi(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {
            "total_revenue": 0, "total_students": 0, "certificates_issued": 0,
            "courses_count": 0, "courses_published": 0, "courses_unpublished": 0,
            "total_income": 0, "net_income": 0,
            "total_turnover": 0, "total_refunds": 0, "total_payments": 0,
            "current_month_turnover": 0,
            "total_comments": 0, "total_reviews": 0, "average_rating": 0,
            "students_prev_months": 0, "certificates_prev_months": 0,
            "certificates_current_month": 0, "comments_prev_months": 0,
            "reviews_prev_months": 0, "reviews_current_month": 0,
            "certificates_change_pct": None, "reviews_change_pct": None,
            "published_solutions_prev_months": 0, "published_solutions_current_month": 0,
            "published_solutions_change_pct": None,
            "steps_average_grade": 0,
        }

    students_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(StudentEnrollment.course_id.in_(course_ids))
    )
    total_students = students_result.scalar() or 0

    certs_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificates_issued = certs_result.scalar() or 0

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    summary = snapshot.data.get("summary", {}) if snapshot else {}
    community = snapshot.data.get("community", {}) if snapshot else {}

    revenue_change_pct = None
    payments_change_pct = None
    refunds_change_pct = None
    current_month_payments = 0
    current_month_refunds_count = 0
    if snapshot:
        months = snapshot.data.get("months", [])
        current = summary.get("current_month_income", 0)
        if months:
            last = months[-1] if months else {}
            current_month_payments = last.get("payments_count", 0)
            current_month_refunds_count = last.get("refunds", 0)
        if months:
            prev = months[-2].get("income", 0) if len(months) >= 2 else 0
            if prev:
                revenue_change_pct = round((current - prev) / abs(prev) * 100)
            else:
                revenue_change_pct = 0 if current == 0 else None
        if len(months) >= 2:
            prev_payments = months[-2].get("payments_count", 0)
            if prev_payments:
                payments_change_pct = round((current_month_payments - prev_payments) / abs(prev_payments) * 100)
            else:
                payments_change_pct = 0 if current_month_payments == 0 else None
            prev_refunds = months[-2].get("refunds", 0)
            if prev_refunds:
                refunds_change_pct = round((current_month_refunds_count - prev_refunds) / abs(prev_refunds) * 100)
            else:
                refunds_change_pct = 0 if current_month_refunds_count == 0 else None

    now = datetime.now(timezone.utc)
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
        .where(Submission.course_id.in_(course_ids), Submission.is_author == False)
        .group_by("y", "m")
    )
    sub_by_month = {(int(r.y), int(r.m)): r.cnt for r in sub_result.all()}

    enroll_result = await db.execute(
        select(
            extract("year", StudentEnrollment.date_joined).label("y"),
            extract("month", StudentEnrollment.date_joined).label("m"),
            func.count(StudentEnrollment.id).label("cnt"),
        )
        .where(StudentEnrollment.course_id.in_(course_ids))
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

    def _json_field(val, field):
        if isinstance(val, (dict, list)):
            return val.get(field) if isinstance(val, dict) else None
        if isinstance(val, (str, bytes, bytearray)):
            try:
                return json.loads(val).get(field)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    async def _count_raw_month(table, field, prefix):
        rows = await db.execute(text(f"SELECT _raw_json FROM {table}"))
        return sum(
            1 for row in rows.all()
            if str(_json_field(row[0], field) or "").startswith(prefix)
        )

    cur_prefix = f"{cur_year}-{cur_month:02d}"
    prev_prefix = f"{prev_year}-{prev_month:02d}"
    cur_certificates = await _count_raw_month("raw_certificate", "issue_date", cur_prefix)
    prev_certificates = await _count_raw_month("raw_certificate", "issue_date", prev_prefix)
    cur_reviews = await _count_raw_month("raw_course_review", "create_date", cur_prefix)
    prev_reviews = await _count_raw_month("raw_course_review", "create_date", prev_prefix)

    async def _steps_average_grade():
        rows = await db.execute(text("SELECT _raw_json FROM raw_step"))
        votes_total = 0
        votes_count = 0
        for row in rows.all():
            ng = _json_field(row[0], "num_grades")
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

    def pct(cur, prev):
        if prev:
            return round((cur - prev) / abs(prev) * 100)
        return 0 if cur == 0 else None

    return {
        "total_revenue": summary.get("current_month_income", 0),
        "revenue_change_pct": revenue_change_pct,
        "current_month_payments": current_month_payments,
        "payments_change_pct": payments_change_pct,
        "current_month_refunds_count": current_month_refunds_count,
        "refunds_change_pct": refunds_change_pct,
        "current_month_submissions": cur_subs,
        "submissions_change_pct": pct(cur_subs, prev_subs),
        "current_month_students": cur_enroll,
        "students_change_pct": pct(cur_enroll, prev_enroll),
        "current_month_comments": cur_comments,
        "comments_change_pct": pct(cur_comments, prev_comments),
        "total_students": total_students,
        "students_prev_months": max(0, total_students - cur_enroll),
        "certificates_issued": certificates_issued,
        "certificates_prev_months": max(0, certificates_issued - cur_certificates),
        "certificates_current_month": cur_certificates,
        "certificates_change_pct": pct(cur_certificates, prev_certificates),
        "courses_count": len(courses),
        "courses_published": sum(1 for c in courses if c.status == "Published"),
        "courses_unpublished": sum(1 for c in courses if c.status != "Published"),
        "total_income": summary.get("total_income", 0),
        "net_income": summary.get("net_income", 0),
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
        "reviews_change_pct": pct(cur_reviews, prev_reviews),
        "published_solutions_prev_months": max(0, community.get("total_solutions", 0) - cur_solutions),
        "published_solutions_current_month": cur_solutions,
        "published_solutions_change_pct": pct(cur_solutions, prev_solutions),
        "average_rating": community.get("average_rating", 0),
        "steps_average_grade": await _steps_average_grade(),
    }


@router.get("/cohorts")
async def get_cohorts(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"active": 0, "passive": 0, "fading": 0, "sleeping": 0}

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    cohorts = {}

    for label, days_min, days_max in [
        ("active", 0, 7),
        ("passive", 7, 30),
        ("fading", 30, 90),
    ]:
        result = await db.execute(
            select(func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.cohort_status != "Zombie",
                StudentEnrollment.last_viewed_at >= now - timedelta(days=days_max),
                StudentEnrollment.last_viewed_at < now - timedelta(days=days_min),
            )
        )
        cohorts[label] = result.scalar() or 0

    sleeping_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.last_viewed_at < now - timedelta(days=90),
            StudentEnrollment.cohort_status != "Zombie",
        )
    )
    cohorts["sleeping"] = sleeping_result.scalar() or 0

    zombie_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(
            StudentEnrollment.course_id.in_(course_ids),
            StudentEnrollment.cohort_status == "Zombie",
        )
    )
    cohorts["zombie"] = zombie_result.scalar() or 0

    return cohorts


@router.get("/revenue")
async def get_revenue(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    months = snapshot.data.get("months", []) if snapshot else []
    return {"months": months}


MONTH_LABELS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
    7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
}


@router.get("/submissions")
async def get_submissions(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return {"months": [], "by_course": [], "years": []}

    month_result = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            extract("month", Submission.submission_time).label("month"),
            func.count(Submission.id).label("total"),
            func.count(Submission.id).filter(Submission.status == "correct").label("correct"),
        )
        .where(Submission.course_id.in_(course_ids), Submission.is_author == False)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    month_rows = month_result.all()

    months = []
    for row in month_rows:
        y, m = int(row.year), int(row.month)
        months.append({
            "month": f"{MONTH_LABELS_RU.get(m, str(m))} {y}",
            "total": row.total,
            "correct": row.correct,
        })

    year_stats = {}
    for row in month_rows:
        y = int(row.year)
        agg = year_stats.setdefault(y, {"year": y, "total": 0, "correct": 0})
        agg["total"] += row.total
        agg["correct"] += row.correct
    years = [year_stats[y] for y in sorted(year_stats)]

    course_result = await db.execute(
        select(
            Submission.course_id,
            func.count(Submission.id).label("total"),
            func.count(Submission.id).filter(Submission.status == "correct").label("correct"),
        )
        .where(Submission.course_id.in_(course_ids), Submission.is_author == False)
        .group_by(Submission.course_id)
    )
    course_rows = course_result.all()

    course_id_to_title = {c.id: c.stepik_course_id for c in courses}

    by_course = []
    for row in course_rows:
        course_obj = None
        for c in courses:
            if c.id == row.course_id:
                course_obj = c
                break
        by_course.append({
            "course_id": row.course_id,
            "stepik_course_id": course_obj.stepik_course_id if course_obj else 0,
            "title": course_obj.title if course_obj else "Unknown",
            "total": row.total,
            "correct": row.correct,
        })

    return {"months": months, "by_course": by_course, "years": years}


@router.get("/active-students")
async def get_active_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

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
            Submission.is_author == False,
            Submission.user_id.isnot(None),
        )
        .group_by("year", "month", Submission.course_id)
        .order_by("year", "month")
    )
    per_course_rows = per_course.all()

    course_map = {c.id: c.title for c in courses}

    monthly: dict[tuple[int, int], dict] = {}
    for row in per_course_rows:
        y, m = int(row.year), int(row.month)
        key = (y, m)
        if key not in monthly:
            monthly[key] = {"per_course_sum": 0, "user_ids": set()}
        monthly[key]["per_course_sum"] += row.cnt
        monthly[key]["user_ids"].add(row.course_id)

    all_unique = await db.execute(
        select(
            extract("year", Submission.submission_time).label("year"),
            extract("month", Submission.submission_time).label("month"),
            func.count(func.distinct(Submission.user_id)).label("cnt"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author == False,
            Submission.user_id.isnot(None),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    all_unique_rows = all_unique.all()
    unique_map = {(int(r.year), int(r.month)): r.cnt for r in all_unique_rows}

    months = []
    for (y, m) in sorted(monthly.keys()):
        months.append({
            "month": f"{MONTH_LABELS_RU.get(m, str(m))} {y}",
            "dark": monthly[(y, m)]["per_course_sum"],
            "light": unique_map.get((y, m), 0),
        })

    return {"months": months}


@router.get("/active-enrolled-students")
async def get_active_enrolled_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

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

    monthly: dict[tuple[int, int], dict] = {}
    for row in per_course_rows:
        y, m = int(row.year), int(row.month)
        key = (y, m)
        if key not in monthly:
            monthly[key] = {"per_course_sum": 0, "student_ids": set()}
        monthly[key]["per_course_sum"] += row.cnt

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
    for (y, m) in sorted(monthly.keys()):
        months.append({
            "month": f"{MONTH_LABELS_RU.get(m, str(m))} {y}",
            "dark": monthly[(y, m)]["per_course_sum"],
            "light": unique_map.get((y, m), 0),
        })

    return {"months": months}


@router.get("/published-solutions")
async def get_published_solutions(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {"months": []}
    community = snapshot.data.get("community", {})

    monthly = community.get("solutions_monthly", {})
    months_res = []
    for key in sorted(monthly.keys()):
        y_str, m_str = key.split("-")
        y, m = int(y_str), int(m_str)
        val = monthly[key]
        months_res.append({
            "month": f"{MONTH_LABELS_RU.get(m, str(m))} {y}",
            "dark": val,
            "light": val,
        })
    return {"months": months_res}


@router.get("/students")
async def get_students(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    courses_result = await db.execute(
        select(Course).where(Course.user_id == user.id)
    )
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]
    course_map = {c.id: c.title for c in courses}

    if not course_ids:
        return {"students": [], "total": 0}

    total_result = await db.execute(
        select(func.count(StudentEnrollment.id))
        .where(StudentEnrollment.course_id.in_(course_ids))
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(StudentEnrollment)
        .where(StudentEnrollment.course_id.in_(course_ids))
        .order_by(StudentEnrollment.last_viewed_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
    )
    enrollments = result.scalars().all()

    students = []
    for e in enrollments:
        students.append({
            "student_id": e.student_id,
            "course_id": str(e.course_id),
            "course_title": course_map.get(e.course_id, "Unknown"),
            "cohort_status": e.cohort_status,
            "points_earned": e.points_earned,
            "certificate_issued": e.certificate_issued,
            "last_viewed_at": e.last_viewed_at.isoformat() if e.last_viewed_at else None,
            "date_joined": e.date_joined.isoformat() if e.date_joined else None,
        })

    return {"students": students, "total": total}


@router.get("/hardest-steps")
async def get_hardest_steps(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    min_submissions: int = Query(10, ge=1),
):
    course_ids_result = await db.execute(
        select(Course.id).where(Course.user_id == user.id)
    )
    course_ids = [r[0] for r in course_ids_result.all()]

    if not course_ids:
        return {"steps": []}

    course_map_result = await db.execute(
        select(Course.id, Course.title).where(Course.id.in_(course_ids))
    )
    course_map = dict(course_map_result.all())

    result = await db.execute(
        select(
            Submission.stepik_step_id,
            Submission.course_id,
            func.count(Submission.id).label("total"),
            func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
        )
        .where(
            Submission.course_id.in_(course_ids),
            Submission.is_author == False,
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
        steps.append({
            "stepik_step_id": row.stepik_step_id,
            "course_id": str(row.course_id),
            "course_title": course_map.get(row.course_id, "Unknown"),
            "total": total,
            "correct": correct,
            "wrong": total - correct,
            "success_pct": round((correct / total) * 100, 1) if total > 0 else 0,
        })

    return {"steps": steps}
