"""Dashboard API package: /api/dashboard/* endpoints split by domain.

- alerts: pending certificates, zero-score students
- kpi: dashboard KPI card data
- cohorts: cohort segmentation
- charts: monthly series (revenue, submissions, active students, published solutions)
- students: paginated student list
- steps: hardest steps ranking
"""

from fastapi import APIRouter

from app.api.dashboard import alerts, charts, cohorts, kpi, steps, students

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
router.include_router(alerts.router)
router.include_router(kpi.router)
router.include_router(cohorts.router)
router.include_router(charts.router)
router.include_router(students.router)
router.include_router(steps.router)

__all__ = ["router"]
