import json
import uuid as uuid_module

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user
from app.api.dashboard.common import _parse_step_positions
from app.database import get_db
from app.models import Course, FinancialSnapshot, StudentEnrollment, Submission, User

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("")
async def list_courses(
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    courses_result = await db.execute(select(Course).where(Course.user_id == user.id))
    courses = courses_result.scalars().all()
    course_ids = [c.id for c in courses]

    enroll_counts = {}
    cert_counts = {}
    if course_ids:
        enroll_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(StudentEnrollment.course_id.in_(course_ids))
            .group_by(StudentEnrollment.course_id)
        )
        enroll_counts = {row[0]: row[1] for row in enroll_result.all()}

        cert_result = await db.execute(
            select(
                StudentEnrollment.course_id,
                func.count(StudentEnrollment.id),
            )
            .where(
                StudentEnrollment.course_id.in_(course_ids),
                StudentEnrollment.certificate_issued.is_(True),
            )
            .group_by(StudentEnrollment.course_id)
        )
        cert_counts = {row[0]: row[1] for row in cert_result.all()}

    snapshot_result = await db.execute(select(FinancialSnapshot).limit(1))
    snapshot = snapshot_result.scalar_one_or_none()
    per_course_community = snapshot.data.get("community", {}).get("per_course", {}) if snapshot else {}
    finance_courses = {c["course_id"]: c for c in (snapshot.data.get("courses", []) if snapshot else [])}

    courses_list = []
    for course in courses:
        sid = str(course.stepik_course_id)
        fc = finance_courses.get(course.stepik_course_id, {})
        pc = per_course_community.get(sid, {})
        courses_list.append(
            {
                "id": str(course.id),
                "stepik_course_id": course.stepik_course_id,
                "title": course.title,
                "status": course.status,
                "price": fc.get("price"),
                "income": fc.get("income"),
                "published_at": course.published_at.isoformat() if course.published_at else None,
                "enrollment_count": enroll_counts.get(course.id, 0),
                "certificates_count": cert_counts.get(course.id, 0),
                "comments_count": pc.get("comments", 0),
                "reviews_count": pc.get("reviews_count", 0),
                "average_rating": pc.get("average_rating", 0),
            }
        )
    courses_list.sort(key=lambda c: (c["published_at"] is not None, c["published_at"] or ""), reverse=True)
    return {"courses": courses_list}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {
        "course": {
            "id": str(course.id),
            "stepik_course_id": course.stepik_course_id,
            "title": course.title,
            "status": course.status,
        }
    }


def _parse_raw(raw) -> dict:
    """Разобрать `_raw_json`: dict (PG jsonb) или JSON-строка (SQLite TEXT)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _to_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@router.get("/{course_id}/structure")
async def get_course_structure(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    """Структура одного курса: модули → уроки → шаги со статистикой.

    Читается из raw-слоя (raw_section/raw_unit/raw_lesson/raw_step) + таблицы
    submissions. Метрики шага: viewed_by/passed_by/correct_ratio из
    `raw_step._raw_json` (агрегаты Stepik API), total/correct/students из
    submissions (is_author=False).
    """
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_payload = {
        "id": str(course.id),
        "stepik_course_id": course.stepik_course_id,
        "title": course.title,
    }

    sections_result = await db.execute(
        text("SELECT section_id, position, title FROM raw_section WHERE course = :cid ORDER BY position"),
        {"cid": str(course.stepik_course_id)},
    )
    sections = [
        {
            "section_id": int(r[0]) if r[0] is not None else None,
            "position": int(r[1]) if r[1] is not None else None,
            "title": r[2],
        }
        for r in sections_result
    ]

    if not sections:
        return {"course": course_payload, "modules": []}

    section_ids = [s["section_id"] for s in sections if s["section_id"] is not None]
    units_by_section: dict[int, list[tuple[int, int]]] = {}
    if section_ids:
        params = {f"sid{i}": str(sid) for i, sid in enumerate(section_ids)}
        placeholders = ", ".join(f":sid{i}" for i in range(len(section_ids)))
        units_result = await db.execute(
            text(f"SELECT lesson_id, section_id, position FROM raw_unit WHERE section_id IN ({placeholders})"),
            params,
        )
        for r in units_result:
            if r[0] is None or r[1] is None:
                continue
            units_by_section.setdefault(int(r[1]), []).append(
                (int(r[2]) if r[2] is not None else 0, int(r[0]))
            )

    lesson_ids = sorted({lid for lst in units_by_section.values() for _, lid in lst})
    lesson_info: dict[int, dict] = {}
    if lesson_ids:
        params_l = {f"lid{i}": str(lid) for i, lid in enumerate(lesson_ids)}
        placeholders_l = ", ".join(f":lid{i}" for i in range(len(lesson_ids)))
        lessons_result = await db.execute(
            text(f"SELECT lesson_id, title, steps FROM raw_lesson WHERE lesson_id IN ({placeholders_l})"),
            params_l,
        )
        for r in lessons_result:
            if r[0] is None:
                continue
            lesson_info[int(r[0])] = {
                "title": r[1],
                "step_positions": _parse_step_positions(r[2]),
            }

    step_ids = sorted({sid for info in lesson_info.values() for sid in info["step_positions"]})
    step_meta: dict[int, dict] = {}
    if step_ids:
        params_s = {f"st{i}": str(sid) for i, sid in enumerate(step_ids)}
        placeholders_s = ", ".join(f":st{i}" for i in range(len(step_ids)))
        steps_result = await db.execute(
            text(f"SELECT step_id, _raw_json FROM raw_step WHERE step_id IN ({placeholders_s})"),
            params_s,
        )
        for r in steps_result:
            if r[0] is None:
                continue
            raw = _parse_raw(r[1])
            block = raw.get("block") if isinstance(raw.get("block"), dict) else None
            step_meta[int(r[0])] = {
                "block": block.get("name") if isinstance(block, dict) else None,
                "viewed_by": raw.get("viewed_by"),
                "passed_by": raw.get("passed_by"),
                "correct_ratio": raw.get("correct_ratio"),
            }

    stats: dict[int, dict] = {}
    sub_result = await db.execute(
        select(
            Submission.stepik_step_id,
            func.count(Submission.id).label("total"),
            func.count(case((Submission.status == "correct", 1), else_=None)).label("correct"),
            func.count(func.distinct(Submission.user_id)).label("students"),
        )
        .where(Submission.course_id == course_uuid, Submission.is_author.is_(False))
        .group_by(Submission.stepik_step_id)
    )
    for r in sub_result:
        if r[0] is None:
            continue
        stats[int(r[0])] = {"total": r[1], "correct": r[2], "students": r[3]}

    modules = []
    lesson_offset = 0
    for section in sections:
        sid = section["section_id"]
        if sid is None:
            continue
        units = sorted(units_by_section.get(sid, []))
        lessons = []
        for unit_pos, lid in units:
            info = lesson_info.get(lid)
            if not info:
                continue
            steps = []
            for step_id, step_number in sorted(info["step_positions"].items(), key=lambda kv: kv[1]):
                meta = step_meta.get(step_id, {})
                st = stats.get(step_id, {})
                steps.append(
                    {
                        "step_id": step_id,
                        "lesson_id": lid,
                        "step_number": step_number,
                        "block": meta.get("block"),
                        "viewed_by": _to_int(meta.get("viewed_by")),
                        "passed_by": _to_int(meta.get("passed_by")),
                        "correct_ratio": _to_float(meta.get("correct_ratio")),
                        "total": st.get("total", 0),
                        "correct": st.get("correct", 0),
                        "students": st.get("students", 0),
                    }
                )
            lessons.append(
                {
                    "lesson_id": lid,
                    "lesson_number": lesson_offset + unit_pos,
                    "title": info["title"],
                    "steps": steps,
                }
            )
        lesson_offset += len(units)
        modules.append(
            {
                "position": section["position"],
                "title": section["title"],
                "lessons": lessons,
            }
        )

    return {"course": course_payload, "modules": modules}


@router.get("/{course_id}/funnel")
async def get_course_funnel(
    course_id: str,
    user: User = Depends(get_user),
    db: AsyncSession = Depends(get_db),
):
    """Воронка прохождения одного курса.

    Этапы: «Записались» → «Модуль N» → «Получили сертификат». Значение этапа
    модуля — distinct-студенты, отправившие хотя бы одно решение в этом модуле
    или позже (cumulative suffix: воронка монотонно убывает). «Модуль 1»
    фактически = «начали курс» (сделали хотя бы одно решение). Шаги, не
    атрибутированные в структуру (не синканы), пропускаются. Авторские решения
    (is_author=True) исключены.
    """
    try:
        course_uuid = uuid_module.UUID(course_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    result = await db.execute(select(Course).where(Course.id == course_uuid, Course.user_id == user.id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_payload = {
        "id": str(course.id),
        "stepik_course_id": course.stepik_course_id,
        "title": course.title,
    }

    sections_result = await db.execute(
        text("SELECT section_id, position, title FROM raw_section WHERE course = :cid ORDER BY position"),
        {"cid": str(course.stepik_course_id)},
    )
    sections = [
        {
            "section_id": int(r[0]) if r[0] is not None else None,
            "position": int(r[1]) if r[1] is not None else None,
            "title": r[2],
        }
        for r in sections_result
    ]

    module_titles: list[tuple[int, str]] = []
    step_to_module: dict[int, int] = {}
    if sections:
        section_ids = [s["section_id"] for s in sections if s["section_id"] is not None]
        units_by_section: dict[int, list[tuple[int, int]]] = {}
        if section_ids:
            params = {f"sid{i}": str(sid) for i, sid in enumerate(section_ids)}
            placeholders = ", ".join(f":sid{i}" for i in range(len(section_ids)))
            units_result = await db.execute(
                text(f"SELECT lesson_id, section_id FROM raw_unit WHERE section_id IN ({placeholders})"),
                params,
            )
            for r in units_result:
                if r[0] is None or r[1] is None:
                    continue
                units_by_section.setdefault(int(r[1]), []).append(int(r[0]))

        lesson_ids = sorted({lid for lst in units_by_section.values() for lid in lst})
        lesson_steps: dict[int, dict[int, int]] = {}
        if lesson_ids:
            params_l = {f"lid{i}": str(lid) for i, lid in enumerate(lesson_ids)}
            placeholders_l = ", ".join(f":lid{i}" for i in range(len(lesson_ids)))
            lessons_result = await db.execute(
                text(f"SELECT lesson_id, steps FROM raw_lesson WHERE lesson_id IN ({placeholders_l})"),
                params_l,
            )
            for r in lessons_result:
                if r[0] is None:
                    continue
                lesson_steps[int(r[0])] = _parse_step_positions(r[1])

        for section in sections:
            sid = section["section_id"]
            if sid is None:
                continue
            idx = len(module_titles)
            module_titles.append((section["position"], section["title"] or ""))
            for lid in units_by_section.get(sid, []):
                for step_id in lesson_steps.get(lid, {}):
                    step_to_module[step_id] = idx

    module_users: list[set] = [set() for _ in module_titles]
    sub_result = await db.execute(
        select(Submission.stepik_step_id, Submission.user_id)
        .where(
            Submission.course_id == course_uuid,
            Submission.is_author.is_(False),
            Submission.user_id.is_not(None),
        )
        .distinct()
    )
    for step_id, user_id in sub_result:
        idx = step_to_module.get(int(step_id))
        if idx is not None:
            module_users[idx].add(user_id)

    enroll_result = await db.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(StudentEnrollment.course_id == course_uuid)
    )
    enrolled = enroll_result.scalar_one()

    cert_result = await db.execute(
        select(func.count())
        .select_from(StudentEnrollment)
        .where(
            StudentEnrollment.course_id == course_uuid,
            StudentEnrollment.certificate_issued.is_(True),
        )
    )
    certificate_count = cert_result.scalar_one()

    suffix_values = [0] * len(module_users)
    suffix: set = set()
    for i in range(len(module_users) - 1, -1, -1):
        suffix |= module_users[i]
        suffix_values[i] = len(suffix)

    stages = [{"key": "enrolled", "label": "Записались", "value": enrolled}]
    for i, (position, title) in enumerate(module_titles):
        stages.append(
            {
                "key": "module",
                "module_number": position,
                "label": f"Модуль {position}. {title}" if title else f"Модуль {position}",
                "value": suffix_values[i],
            }
        )
    stages.append({"key": "certificate", "label": "Получили сертификат", "value": certificate_count})

    return {"course": course_payload, "stages": stages}
