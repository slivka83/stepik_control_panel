"""Сообщество: рейтинги и комментарии → financial_snapshots.community."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.transform.common import (
    _ensure_json,
    _month_tuple,
    _serialize_data,
    _to_bool,
    _to_int,
    is_published_solution,
    load_course_map,
)
from app.services.transform.courses import build_lesson_course_map, build_step_course_map

logger = logging.getLogger(__name__)


async def transform_community(session: AsyncSession):
    logger.info("=== Community ===")

    course_map = await load_course_map(session)

    # Пустой course_map — не повод оставлять старую community в снапшоте:
    # после удаления всех курсов KPI и страница «Активности» показывали бы
    # комментарии/рейтинги несуществующих курсов. Ниже строится пустая
    # community и записывается в снапшот (или создаёт его).
    if not course_map:
        logger.warning("  no courses — writing empty community")

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_course_review_summary
    """)
    )
    reviews = [rv for row in r if isinstance(rv := _ensure_json(row[0]), dict)]

    average_rating = 0.0
    total_reviews = 0
    per_course_rating = {}
    per_course_reviews_count = {}
    if reviews:
        for rv in reviews:
            # id сводки — не id курса; без course строку нельзя привязать к
            # курсу (course-review-summaries всегда отдаёт course).
            cid = _to_int(rv.get("course"))
            if cid not in course_map:
                # Сводка чужого/удалённого курса не должна попадать в
                # «Всего отзывов»: иначе KPI расходится со страницей Отзывов
                # (mart_reviews строится только по курсам из courses).
                continue
            avg = rv.get("average")
            cnt = _to_int(rv.get("count")) or 0
            total_reviews += cnt
            # Количество отзывов не зависит от наличия рейтинга: курс без
            # оценки обязан остаться в per_course, иначе фильтр «все курсы»
            # даёт меньший итог, чем отсутствие фильтра.
            per_course_reviews_count[str(cid)] = cnt
            if avg:
                try:
                    avg_f = float(avg)
                    if avg_f > 0:
                        per_course_rating[str(cid)] = round(avg_f, 2)
                except (ValueError, TypeError):
                    pass
        if per_course_rating:
            average_rating = round(sum(per_course_rating.values()) / len(per_course_rating), 2)

    r = await session.execute(
        text("""
        SELECT _raw_json FROM raw_comment
    """)
    )
    comments = [cm for row in r if isinstance(cm := _ensure_json(row[0]), dict)]

    total_comments = 0
    comments_monthly = {}
    total_solutions = 0
    solutions_monthly = {}
    per_course_comments = {}

    step_course = await build_step_course_map(session)
    lesson_course = await build_lesson_course_map(session)

    for cm in comments:
        if _to_bool(cm.get("is_deleted")) is True:
            continue
        ym = _month_tuple(cm.get("time"))
        if ym is None:
            continue
        key = f"{ym[0]}-{ym[1]:02d}"
        is_solution = is_published_solution(cm)

        # Only comments attributable to one of the user's courses count towards
        # the global/per-course totals. Prefer step→course mapping; fall back to
        # the course id reported by the comment itself. This keeps the snapshot
        # consistent with mart_comments and with the filtered (course selection)
        # community stats — otherwise "all courses" would not equal "no filter".
        target = cm.get("target")
        # Атрибуция — ровно та же, что у mart_comments: шаг → курс, а если шаг
        # не атрибутирован, то курс из самого комментария. Иначе один и тот же
        # комментарий попадал в KPI, но отсутствовал на странице Комментариев.
        step_cid = step_course.get(_to_int(target)) if (target and step_course) else None
        if not step_cid and target:
            # Комментарий к уроку: target — lesson_id, а не step_id.
            step_cid = lesson_course.get(_to_int(target))
        if not step_cid and target:
            # Комментарий к курсу целиком.
            target_cid = _to_int(target)
            if target_cid in course_map:
                step_cid = target_cid
        if not step_cid:
            step_cid = _to_int(cm.get("course"))
        if not step_cid or step_cid not in course_map:
            continue

        if is_solution:
            total_solutions += 1
            solutions_monthly[key] = solutions_monthly.get(key, 0) + 1
        else:
            # Published solutions are counted separately (total_solutions /
            # solutions_monthly); plain "comments" excludes them so the two
            # categories don't double-count.
            total_comments += 1
            comments_monthly[key] = comments_monthly.get(key, 0) + 1

            cid_str = str(step_cid)
            per_course_comments[cid_str] = per_course_comments.get(cid_str, 0) + 1

    per_course = {}
    for cid, _ in course_map.items():
        cid_str = str(cid)
        per_course[cid_str] = {
            "comments": per_course_comments.get(cid_str, 0),
            "reviews_count": per_course_reviews_count.get(cid_str, 0),
            "average_rating": per_course_rating.get(cid_str, 0),
        }

    community = {
        "average_rating": average_rating,
        "total_reviews": total_reviews,
        "total_comments": total_comments,
        "comments_monthly": comments_monthly,
        "total_solutions": total_solutions,
        "solutions_monthly": solutions_monthly,
        "per_course": per_course,
    }

    r = await session.execute(text("SELECT id, data FROM financial_snapshots LIMIT 1"))
    row = r.fetchone()
    if row:
        snap_id = row[0]
        data = _ensure_json(row[1])
        if not isinstance(data, dict):
            data = {}
        data["community"] = community
        await session.execute(
            text("UPDATE financial_snapshots SET data = :data, updated_at = :now WHERE id = :id"),
            {"data": _serialize_data(data), "now": datetime.now(UTC), "id": snap_id},
        )
    else:
        await session.execute(
            text("INSERT INTO financial_snapshots (id, data, updated_at) VALUES (:id, :data, :now)"),
            {
                "id": str(uuid.uuid4()),
                "data": _serialize_data({"community": community}),
                "now": datetime.now(UTC),
            },
        )

    logger.info(
        "  rating=%.2f reviews=%d comments=%d solutions=%d",
        average_rating,
        total_reviews,
        total_comments,
        total_solutions,
    )
