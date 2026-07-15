import asyncio
import uuid
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.services.stepik_api import _request, get_course_grades
from app.services.crypto import decrypt_token
from app.database import engine, Base
from app.models.models import Course, StudentEnrollment, User
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

settings = get_settings()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

STEPIK_API_BASE = "https://stepik.org/api"


async def _paginated_get(path: str, token: str, params: dict | None = None, key: str = "courses") -> list[dict]:
    """Fetch all pages from a Stepik API endpoint."""
    all_items = []
    page = 1
    while True:
        p = {**(params or {}), "page": page, "page_size": 50}
        data = await _request("GET", path, token, p)
        items = data.get(key, [])
        all_items.extend(items)
        meta = data.get("meta", {})
        if not meta.get("has_next", False) or not items:
            break
        page += 1
    return all_items


async def sync_courses():
    # Get token from DB
    async with SessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user_db = result.scalar_one_or_none()
        if not user_db:
            print("No user token found.")
            return
        token = decrypt_token(user_db.access_token)
        user_id_db = user_db.id

    user_id = settings.stepik_user_id
    if not user_id:
        print("STEPIK_USER_ID not set")
        return

    print(f"Syncing for user {user_id}...")

    # 1. Fetch courses
    courses_data = await _paginated_get("/courses", token, {"teacher": user_id}, "courses")
    print(f"Courses: {len(courses_data)}")

    async with SessionLocal() as session:
        async with session.begin():
            # Clear old data
            await session.execute(text("DELETE FROM student_enrollments"))
            await session.execute(text("DELETE FROM courses"))

            course_map = {}
            for c in courses_data:
                course = Course(
                    id=uuid.uuid4(),
                    user_id=user_id_db,
                    stepik_course_id=c["id"],
                    title=c.get("title", "Untitled"),
                    status="Published" if c.get("is_published", True) else "Draft",
                    health_score=100.0,
                )
                session.add(course)
                await session.flush()
                course_map[c["id"]] = course

            # 2. For each course, fetch course-grades (paginated) + certificates
            total_enrollments = 0
            total_certs = 0
            for c in courses_data:
                sid = c["id"]
                local_course = course_map[sid]
                print(f"  [{sid}] {c.get('title', '?')[:50]}...", end="")

                # Fetch all course-grades
                try:
                    grades = await _paginated_get("/course-grades", token, {"course": sid}, "course-grades")
                except Exception as e:
                    print(f" grades_err={e}")
                    grades = []

                # Fetch certificates
                try:
                    certs = await _paginated_get("/certificates", token, {"course": sid}, "certificates")
                    cert_users = {cert["user"] for cert in certs}
                except Exception:
                    cert_users = set()

                # Build enrollment from grades
                for grade in grades:
                    student_id = grade.get("user")
                    if not student_id:
                        continue

                    score = grade.get("score", 0) or 0
                    is_passed = student_id in cert_users

                    enrollment = StudentEnrollment(
                        id=uuid.uuid4(),
                        course_id=local_course.id,
                        student_id=student_id,
                        cohort_status="Active" if score > 0 else "Passive",
                        points_earned=int(score),
                        certificate_issued=is_passed,
                        last_viewed_at=datetime.utcnow(),
                    )
                    session.add(enrollment)
                    total_enrollments += 1

                total_certs += len(cert_users)
                print(f" grades={len(grades)} certs={len(cert_users)}")

            print(f"\nSynced: {len(courses_data)} courses, {total_enrollments} enrollments, {total_certs} certificates")


if __name__ == "__main__":
    asyncio.run(sync_courses())
