"""Raw-layer sync: Stepik API → `raw_*` tables.

Разбит по предметным областям:

- ``common``      — общие помощники (пагинация, upsert/replace, sync-state);
- ``structure``   — курсы, секции, юниты, уроки, шаги, оценки, сертификаты;
- ``submissions`` — отправки решений и попытки (инкрементально);
- ``financials``  — финансы (client_credentials);
- ``community``   — сводки/отзывы и комментарии;
- ``users``       — анкеты студентов.

`app.services.raw_sync` остаётся публичной точкой входа: здесь реэкспортированы
функции синка и помощники, которые подменяют тесты (``_request``,
``_paginated_fetch``, ``_upsert_raw_table``, ``get_finance_token``).
"""

from app.services.stepik_api import _request, get_finance_token

from .common import (
    _get_fields_mapping,
    _is_text_step,
    _paginated_fetch,
    _replace_raw_table,
    _upsert_raw_table,
)
from .community import sync_community
from .financials import sync_financials
from .structure import sync_course_grades_and_certs, sync_courses_structure
from .submissions import sync_submissions
from .users import sync_users

__all__ = [
    "_get_fields_mapping",
    "_is_text_step",
    "_paginated_fetch",
    "_replace_raw_table",
    "_request",
    "_upsert_raw_table",
    "get_finance_token",
    "sync_community",
    "sync_course_grades_and_certs",
    "sync_courses_structure",
    "sync_financials",
    "sync_submissions",
    "sync_users",
]
