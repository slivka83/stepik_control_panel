"""Transform-слой: пересборка витрин из raw-слоя.

Пакет разбит по предметным областям. Публичный вход остался прежним:
`from app.services import transform` и
`from app.services.transform import transform_courses` работают как раньше.
"""

from app.services.transform.certificates import transform_certificates
from app.services.transform.comments import transform_comments
from app.services.transform.common import (
    _ensure_json,
    _insert_rows,
    _month_tuple,
    _parse_raw,
    _parse_step_positions,
    _serialize_data,
    _step_grade,
    _to_float,
    _to_int,
    calculate_cohort_status,
    get_course_status,
    load_course_map,
    parse_dt,
)
from app.services.transform.community import transform_community
from app.services.transform.courses import build_step_course_map, transform_courses
from app.services.transform.enrollments import transform_enrollments
from app.services.transform.financials import transform_financials
from app.services.transform.reviews import transform_reviews
from app.services.transform.steps import transform_steps
from app.services.transform.students import STATUS_RANK, transform_students
from app.services.transform.submissions import transform_submissions

__all__ = [
    "STATUS_RANK",
    "_ensure_json",
    "_insert_rows",
    "_month_tuple",
    "_parse_raw",
    "_parse_step_positions",
    "_serialize_data",
    "_step_grade",
    "_to_float",
    "_to_int",
    "build_step_course_map",
    "calculate_cohort_status",
    "get_course_status",
    "load_course_map",
    "parse_dt",
    "transform_certificates",
    "transform_comments",
    "transform_community",
    "transform_courses",
    "transform_enrollments",
    "transform_financials",
    "transform_reviews",
    "transform_steps",
    "transform_students",
    "transform_submissions",
]
