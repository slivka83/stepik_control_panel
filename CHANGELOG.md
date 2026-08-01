# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Features (Финансы — «Последние операции»)
- Вкладка «По UTM»: агрегация по метке источника (payments/turnover/income/refunds/last_used)
- Колонка UTM: метки источников вместо сырых значений (`UTM_SOURCE_LABELS` в `app/constants.py`: Я.Директ, E-mail, Telegram, VK, Уведомления)
- Колонка «Канал»: «А-ссылка» / «Stepik» / «По счету» (из `is_z_link_used` / `is_invoice_payment`)
- Колонка «Подарок» (`is_gift`) и «Студент» (имя покупателя из `raw_user` по `buyer`)
- Колонка «Дата» с временем (чч:мм), удалена колонка «Статус» — возвраты красным + зачёркнутые
- Лимит 30 убран: в `recent_payments` попадают все платежи (сортировка по времени)
- Возвраты в агрегациях (courses/promos/utms) хранятся положительными (`abs(amount)`) — раньше колонка «Возвраты» всегда показывала «—»
- Тултип в колонке UTM: только поля UTM-метки (`last_course_click_utm`)
- Тултип кнопки «Обновить»: Завершено % / Прошло / Осталось (расчётно по линейной экстраполяции)
- Скрипт `scripts/rebuild_marts.py`: пересборка всех витрин из raw-слоя без API-запросов (abort при пустом `raw_course`)

### Architecture / Refactoring
- Split `app/api/dashboard.py` (694 строк, 10 эндпоинтов) в пакет `app/api/dashboard/` (alerts, kpi, cohorts, charts, students, steps, common)
- Добавлен единый источник констант `app/constants.py` (MONTH_NAMES, когортные пороги); убраны дубли `MONTH_LABELS_RU`/`MONTH_NAMES`/`calculate_cohort_status`
- Удалена мёртвая модель `StepSyncState` (таблица никогда не использовалась — состояние живёт в `raw_sync_state`)
- Удалены orphan-скрипты: `transform.py`, `full_load.py`, `batch_explore.py`, `populate_meta.py`, `rebuild_raw_course.py`, `reload_courses.py`, `test_page_sizes.py`
- Исправлен форк alembic-миграций: `20fc60296db6` переподчинена на `012` — единственный head
- `STEPIK_OAUTH_TOKEN_URL` вынесена в константу `stepik_api.py` (была захардкожена в 3 местах)
- Дефолты конфига приведены к docker-compose (PG 5433, Redis 6380)
- Убраны неиспользуемые зависимости: `gunicorn`, `python-dotenv`
- Ruff: `app/` и `scripts/` — 0 ошибок; настроены per-file-ignores для идиом FastAPI/тестов; удалена мёртвая pytest-конфигурация из pyproject
- Добавлены архитектурные тесты `tests/test_architecture.py` (18): один alembic head, отсутствие dead-артефактов, единый источник констант, дефолты конфига, сплит dashboard-пакета

### Security
- Session token moved from URL query params to HttpOnly cookies
- Removed plaintext Stepik token endpoint (`GET /api/auth/token`)
- Replaced custom HMAC session signing with `itsdangerous.URLSafeTimedSerializer`
- Added CSRF protection (state parameter) in OAuth2 flow
- Added rate limiting on auth endpoints (5 req/min per IP)
- Added `SECRET_KEY` validation in production
- Added Redis blacklist for logout with server-side invalidation
- Added `SESSION_TTL_HOURS` and `ALLOWED_ORIGINS` config options
- Restricted CORS to GET/POST methods and Content-Type/Cookie headers

### Backend
- Fixed sync data loss: fetch-then-replace pattern (no DELETE before API fetch)
- Fixed N+1 query in `get_alerts` (single aggregated query)
- Fixed cohort boundaries (no overlaps/gaps: 0-7, 8-30, 31-90, >90)
- Fixed cohort status calculation (by days since activity, not score)
- Added auth (`Depends(get_user)`) and user-scoping on all data endpoints
- Added max retry (5) on 429 with exponential backoff
- Added retry on 5xx Stepik API errors
- Added `asyncio.Lock` for thread-safe finance token cache
- Isolated token refresh errors per-user (separate transactions)
- Added `user_id` parameter to `sync_all()` for multi-user support
- Moved `trigger_sync` to FastAPI BackgroundTasks
- Added `POST /api/auth/refresh` endpoint
- Replaced `== False`/`== True` with `.is_(False)`/`.is_(True)`
- Added `__repr__` to all models
- Atomic Redis token bucket via Lua script
- Fail-open behavior when Redis unavailable
- Health endpoint now checks Redis

### Database
- Added indexes on `course_id`, `student_id`, `last_viewed_at`, `user_id`, `step_id`
- Added `UniqueConstraint` on `(course_id, student_id)`
- All `DateTime` columns now timezone-aware
- Migration 002 downgrade fixed (`op.Column` → `sa.Column`)
- Split models into separate files (`user.py`, `course.py`, etc.)

### Frontend
- Fixed Provider order: `AuthProvider` > `SyncProvider` (was reversed)
- `SyncProvider` now skips fetch when unauthenticated
- Added production `baseURL` from `VITE_API_URL`
- Added 404 catch-all route with `NotFound` page
- Added code splitting / lazy loading for all pages
- Added `AbortController` in `SyncContext`
- Added polling backoff on error (30s → up to 5min)
- Improved 401 interceptor (redirect instead of reload)
- Added token refresh on 401 (retry original request)
- Added non-JSON response handling in `AuthContext`
- Added `ErrorBanner` component and error states on all pages
- Fixed `RevenueChart` current month highlight (handles Russian + ISO formats)
- Added `formatCurrency`/`formatNumber` utils with null-safety
- Added Russian pluralization util
- Added `STEPIK_URLS` constants (no more hardcoded URLs)
- Financials: active tab persists in URL, pagination for recent payments
- Case-insensitive course status comparison
- `CohortChart`: tooltip formatter, stable keys
- `KpiCard`: `colorClasses` moved outside, PropTypes, unified formatting
- ARIA landmarks and icon labels in Layout
- Chart alt-text via `<figure>`/`<figcaption>`
- Firefox scrollbar styles
- Optimized font loading (non-blocking)
- Removed dead Tailwind config (`darkMode`, `backdropBlur.xs`)
- Translated `ErrorBoundary` to Russian

### Infrastructure
- Frontend Dockerfile: multi-stage build with nginx (no dev server in prod)
- Backend Dockerfile: non-root user, multi-stage, healthcheck
- docker-compose: restart policies, resource limits, Redis auth, configurable ports
- `start.sh`: graceful shutdown, readiness checks, dependency checks, `set -eo pipefail`, PID files
- `start.bat`: PowerShell-based port kill (locale-independent)
- `.gitignore`: extended with certs, coverage, docker overrides
- `.env.example`: added `SESSION_TTL_HOURS`, `ALLOWED_ORIGINS`, `REDIS_PASSWORD`, port hints

### Code Quality
- Added ESLint (flat config) for frontend
- Added Ruff for backend
- Added Prettier for frontend
- Added pre-commit hooks
- Added `pyproject.toml` with Ruff + mypy config
- Added `pytest.ini` testpaths and filterwarnings
- Removed hardcoded `ENCRYPTION_KEY` from test fixtures
- `vitest.config.js`: removed `globals: true`
- Added `@testing-library/user-event` to devDependencies
- Added `prop-types` to dependencies
