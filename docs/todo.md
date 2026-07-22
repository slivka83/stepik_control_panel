# План полного рефакторинга — Stepik Control Panel

> Дата создания: 2026-07-19
> Статус: Ожидает выполнения
> Приоритеты: CRITICAL > HIGH > MEDIUM > LOW

---

## Оглавление

- [1. Backend: Безопасность](#1-backend-безопасность)
- [2. Backend: Архитектура](#2-backend-архитектура)
- [3. Backend: Модели данных и БД](#3-backend-модели-данных-и-бд)
- [4. Backend: API Endpoints](#4-backend-api-endpoints)
- [5. Backend: Сервисы](#5-backend-сервисы)
- [6. Backend: Тесты](#6-backend-тесты)
- [7. Frontend: Архитектура](#7-frontend-архитектура)
- [8. Frontend: Контексты и состояния](#8-frontend-контексты-и-состояния)
- [9. Frontend: Страницы](#9-frontend-страницы)
- [10. Frontend: Компоненты](#10-frontend-компоненты)
- [11. Frontend: Стили и UI](#11-frontend-стили-и-ui)
- [12. Frontend: Доступность (a11y)](#12-frontend-доступность-a11y)
- [13. Frontend: Тесты](#13-frontend-тесты)
- [14. Инфраструктура: Docker и CI](#14-инфраструктура-docker-и-ci)
- [15. Скрипты запуска](#15-скрипты-запуска)
- [16. Конфигурация проекта](#16-конфигурация-проекта)
- [17. Документация](#17-документация)
- [18. Стандарты кода и линтинг](#18-стандарты-кода-и-линтинг)

---

## 1. Backend: Безопасность

### 1.1 [CRITICAL] Убрать session token из URL query-параметров

**Файл:** `backend/app/api/auth.py:121`
**Проблема:** Session token передаётся как `?session_token=...` в URL редиректа. Токен попадает в:
- Историю браузера
- Логи веб-сервера (nginx/access.log)
- Referrer-заголовки при переходах
- Аналитические системы

**Решение:**
- После OAuth2 callback генерировать кратковременный `exchange_code` (одноразовый, TTL 30 сек)
- Передавать в URL только `exchange_code`
- Frontend обменивает `exchange_code` на session token через отдельный POST-endpoint `/api/auth/exchange`
- Session token устанавливать через `Set-Cookie` с флагами: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`
- Убрать `localStorage` для хранения токена — использовать cookie

**Критерии приёмки:**
- Токен никогда не появляется в URL
- Cookie имеет все защитные флаги
- В `localStorage` не хранится никаких токенов

---

### 1.2 [CRITICAL] Убрать endpoint, возвращающий plaintext Stepik-токен

**Файл:** `backend/app/api/auth.py:142-143`
**Проблема:** `GET /api/auth/token` вызывает `decrypt_token(user.access_token)` и возвращает расшифрованный токен Stepik API на фронтенд. Фронтенд не должен никогда иметь доступ к raw Stepik API-токену.

**Решение:**
- Полностью удалить endpoint `GET /api/auth/token`
- Если фронтенду нужно знать, авторизован ли пользователь — использовать `GET /api/auth/me` (возвращает `{ authenticated: true, user_id, stepik_user_id, display_name }`)
- Все запросы к Stepik API идут только через backend-прокси

**Критерии приёмки:**
- Endpoint `/api/auth/token` удалён
- Ни один endpoint не возвращает plaintext-токены

---

### 1.3 [CRITICAL] Убрать кастомную схему подписи сессий

**Файл:** `backend/app/api/auth.py:22-27`
**Проблема:** Собственная реализация HMAC-подписи session token (`hmac.new(secret_key.encode(), ...)`) хрупкая и уязвимая при `SECRET_KEY=dev-secret-key`.

**Решение:**
- Использовать `itsdangerous.URLSafeTimedSerializer` или `python-jose` (JWT)
- Токен содержит: `user_id`, `issued_at`, `expires_at`
- Подпись использует `SECRET_KEY`
- Валидация проверяет подпись И срок действия
- Срок жизни: 24 часа (конфигурируемый через `SESSION_TTL_HOURS`)

**Критерии приёмки:**
- Используется стандартная библиотека для подписи токенов
- Токены имеют TTL и проверяются на истечение

---

### 1.4 [HIGH] Добавить аутентификацию на все data-endpoints

**Файлы:** `backend/app/api/courses.py`, `backend/app/api/dashboard.py`, `backend/app/api/financials.py`
**Проблема:** Все endpoints с данными (курсы, дашборд, финансы) доступны без авторизации. Любой может получить полный доступ ко всем данным.

**Решение:**
- Добавить `Depends(get_user)` в каждый endpoint:
  - `list_courses`, `get_course` в `courses.py`
  - `get_kpis`, `get_alerts`, `get_cohort_stats` в `dashboard.py`
  - `get_financials` в `financials.py`
- Добавить user-scoping: фильтрация данных по `user.id` из токена
- `/api/auth/me` и `/api/auth/login` — единственные public endpoints

**Критерии приёмки:**
- Все data-endpoints возвращают 401 без валидного токена
- Данные фильтруются по `user_id` текущего пользователя

---

### 1.5 [HIGH] Добавить CSRF-защиту в OAuth2 flow

**Файл:** `backend/app/api/auth.py:81`
**Проблема:** OAuth2 callback не верифицирует `state`-параметр. Злоумышленник может подставить свой код авторизации.

**Решение:**
- При генерации login URL — создавать криптографически случайный `state`
- Сохранять `state` в `Set-Cookie` (HttpOnly, SameSite=Lax, short TTL)
- В callback — сравнивать `state` из query params и из cookie
- При несовпадении — возвращать 403

**Критерии приёмки:**
- `state` генерируется и проверяется в каждом OAuth2 flow
- Несовпадение `state` блокирует авторизацию

---

### 1.6 [HIGH] Добавить rate limiting на auth endpoints

**Файл:** `backend/app/api/auth.py`
**Проблема:** Endpoints `/login`, `/callback` не защищены от brute-force.

**Решение:**
- Применить Redis-based rate limiter на auth endpoints: 5 запросов/минуту с одного IP
- При превышении — 429 с `Retry-After`
- Логировать подозрительные попытки

---

### 1.7 [HIGH] Добавить валидацию `SECRET_KEY` в production

**Файл:** `backend/app/config.py:21`
**Проблема:** При `APP_ENV=production` и `SECRET_KEY=dev-secret-key` приложение молча работает с известным секретом.

**Решение:**
- При `APP_ENV=production`:
  - Если `SECRET_KEY` пустой или равен `dev-secret-key` — выбрасывать `RuntimeError`
  - Проверять минимальную длину (32 символа)
- При `APP_ENV=development` — warning в лог

---

### 1.8 [MEDIUM] Валидация `ENCRYPTION_KEY` при старте

**Файл:** `backend/app/config.py`, `backend/app/services/crypto.py`
**Проблема:** При невалидном `ENCRYPTION_KEY` ошибка возникает только при первом encrypt/decrypt, что затрудняет диагностику.

**Решение:**
- В `config.py` → `Settings.__post_init__` или валидатор Pydantic: проверить, что `encryption_key` — валидный 32-byte URL-safe base64
- В `crypto.py`: кэшировать Fernet instance (не создавать заново при каждом вызове)
- Добавить `decrypt_token` с обработкой `InvalidToken` и понятным сообщением

---

### 1.9 [MEDIUM] Добавить logout с server-side invalidation

**Файл:** `backend/app/api/auth.py:137-138`
**Проблема:** `POST /api/auth/logout` возвращает `{"ok": True}` без реальных действий — токен остаётся валидным.

**Решение:**
- Добавить Redis blacklist: при logout — добавлять `jti` токена в blacklist с TTL = оставшееся время жизни токена
- При валидации токена — проверять blacklist
- Очищать session cookie (`Set-Cookie: ...; Max-Age=0`)

---

### 1.10 [LOW] Ограничить CORS-политику

**Файл:** `backend/app/main.py:78-79`
**Проблема:** `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_origins=[settings.frontend_url]` — избыточно широкие права.

**Решение:**
- `allow_methods=["GET", "POST"]` (только необходимые методы)
- `allow_headers=["Content-Type", "Cookie"]`
- `allow_credentials=True` (для cookie-based auth)
- В production: `allow_origins` из `.env` `ALLOWED_ORIGINS` (список через запятую)

---

## 2. Backend: Архитектура

### 2.1 [HIGH] Убрать `Base.metadata.create_all` из lifespan

**Файл:** `backend/app/main.py:25-26`
**Проблема:** `create_all` создаёт таблицы напрямую, минуя Alembic. Если модели и миграции разошлись — схема будет несогласованной. В production это может привести к потере данных.

**Решение:**
- Убрать `async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)`
- При старте проверять, что миграции применены (или применять автоматически через `alembic upgrade head`)
- В dev-режиме: логировать предупреждение, если `create_all` вызывается

---

### 2.2 [HIGH] Убрать race condition на startup sync

**Файл:** `backend/app/main.py:49`
**Проблема:** `asyncio.create_task(_startup_sync())` запускает фоновый sync без обработки ошибок. `_last_sync_completed_at` мутируется из другого модуля (`sync_mod._last_sync_completed_at = updated_ts`), что хрупко и непрозрачно.

**Решение:**
- Использовать APScheduler (уже в зависимостях) для startup sync: `scheduler.add_job(sync_all, trigger='date', run_date=...)`
- Инкапсулировать состояние синхронизации в сервис `SyncState` (класс), а не в глобальные переменные
- Обрабатывать и логировать ошибки startup sync
- Не мутировать переменные другого модуля — использовать setter-метод или event bus

---

### 2.3 [MEDIUM] Убрать глобальные переменные в sync.py

**Файл:** `backend/app/services/sync.py:18-19`
**Проблема:** `_sync_in_progress` и `_last_sync_completed_at` — глобальные переменные, мутирующие из разных async-контекстов. В multi-worker deployment (gunicorn) эти переменные не разделяются между воркерами.

**Решение:**
- Создать класс `SyncState` с Redis-backed хранилищем:
  ```python
  class SyncState:
      async def is_in_progress(self) -> bool: ...
      async def set_in_progress(self, value: bool): ...
      async def get_last_completed(self) -> datetime | None: ...
      async def set_last_completed(self, ts: datetime): ...
  ```
- Redis key: `sync:in_progress`, `sync:last_completed`
- Это обеспечит консистентность между воркерами

---

### 2.4 [MEDIUM] Ввести dependency injection для httpx.AsyncClient

**Файл:** `backend/app/services/stepik_api.py`
**Проблема:** Новый `httpx.AsyncClient` создаётся при каждом запросе. Нет connection pooling, нет reuse.

**Решение:**
- Создать singleton `StepikClient` (или `AsyncClient` через FastAPI lifespan):
  ```python
  # main.py lifespan
  app.state.stepik_client = httpx.AsyncClient(
      base_url="https://stepik.org/api/",
      timeout=30.0,
      limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
  )
  yield
  await app.state.stepik_client.aclose()
  ```
- Передавать client через FastAPI Depends: `client: httpx.AsyncClient = Depends(get_stepik_client)`

---

### 2.5 [MEDIUM] Убрать `Base.metadata.create_all` из тестов

**Файл:** `backend/tests/conftest.py`
**Проблема:** Тесты создают таблицы через `create_all`, но миграции могут содержать индексы/констрейнты, которых нет в моделях. Тесты не проверяют согласованность с миграциями.

**Решение:**
- В тестовом `conftest.py` использовать Alembic `upgrade head` для test-БД
- Или: использовать `Base.metadata.create_all` но добавить тест-проверку согласованности schema vs migrations

---

### 2.6 [LOW] Структурировать импорты

**Файл:** `backend/app/main.py:37`
**Проблема:** `import app.services.sync as sync_mod` — late import внутри async-функции. Нестандартно, затрудняет чтение.

**Решение:**
- Все импорты — в начале файла, по PEP 8 (stdlib → third-party → local)
- Использовать isort для автоматической сортировки

---

## 3. Backend: Модели данных и БД

### 3.1 [HIGH] Добавить индексы на часто запрашиваемые колонки

**Файл:** `backend/app/models/models.py`
**Проблема:** Отсутствуют индексы на:
- `student_enrollments.course_id` — фильтрация по курсу на Dashboard и Cohorts
- `student_enrollments.student_id` — JOIN с submissions
- `student_enrollments.last_viewed_at` — когортная сегментация
- `courses.user_id` — user-scoping
- `submissions.step_id` — bottleneck analysis

**Решение:**
- Добавить `Index` в модельные `__table_args__`:
  ```python
  __table_args__ = (
      Index('ix_student_enrollments_course_id', 'course_id'),
      Index('ix_student_enrollments_last_viewed', 'last_viewed_at'),
      Index('ix_student_enrollments_course_student', 'course_id', 'student_id'),
      UniqueConstraint('course_id', 'student_id', name='uq_enrollment'),
  )
  ```
- Создать Alembic-миграцию `005_add_indexes.py`
- Добавить `EXPLAIN ANALYZE`-тесты для критических запросов

---

### 3.2 [HIGH] Добавить UniqueConstraint на (course_id, student_id)

**Файл:** `backend/app/models/models.py` → `StudentEnrollment`
**Проблема:** Нет ограничения уникальности, возможны дублирующие записи.

**Решение:**
- Добавить `UniqueConstraint('course_id', 'student_id')` в `__table_args__`
- Миграция: `ALTER TABLE student_enrollments ADD CONSTRAINT uq_course_student UNIQUE (course_id, student_id)`
- Предварительно удалить дубликаты (если есть) через `DELETE ... WHERE ctid NOT IN (...)`

---

### 3.3 [HIGH] Исправить timezone-naive datetimes

**Файл:** `backend/app/models/models.py` (все `created_at`, `updated_at`, `last_viewed_at`)
**Проблема:** `datetime.now(timezone.utc).replace(tzinfo=None)` — создаёт naive datetime. Это антипаттерн: сравнения с aware datetime вызовут `TypeError`, а в БД нет информации о timezone.

**Решение:**
- Изменить все `DateTime` колонки на `DateTime(timezone=True)`
- Убрать `.replace(tzinfo=None)` из `default` lambda
- Использовать `datetime.now(timezone.utc)` напрямую
- Создать миграцию `006_fix_timezone_columns.py`:
  ```python
  op.alter_column('courses', 'created_at', type_=sa.DateTime(timezone=True))
  # ... для всех таблиц
  ```
- Обновить все запросы/сравнения в sync.py, dashboard.py, чтобы работать с aware datetimes

---

### 3.4 [MEDIUM] Исправить когортный статус

**Файл:** `backend/app/services/sync.py:151`
**Проблема:** `"Active" if score > 0 else "Passive"` — не соответствует BRD. Когорта определяется днями с последней активности, а не score.

**Решение:**
```python
def calculate_cohort_status(last_viewed_at: datetime) -> str:
    days = (datetime.now(timezone.utc) - last_viewed_at).days
    if days <= 7: return "Active"
    if days <= 30: return "Passive"
    if days <= 90: return "Fading"
    return "Sleeping"
```
- Применить при upsert в `sync_courses_and_enrollments`
- Покрыть unit-тестами (boundary: день 7, 8, 30, 31, 90, 91)

---

### 3.5 [MEDIUM] Перенести модели в отдельные файлы

**Файл:** `backend/app/models/models.py`
**Проблема:** Все 5 моделей в одном файле. При росте проекта станет неуправляемым.

**Решение:**
- Создать:
  ```
  models/
  ├── __init__.py     # re-export: from .user import User; from .course import Course; ...
  ├── base.py         # Base = DeclarativeBase
  ├── user.py         # User
  ├── course.py       # Course
  ├── enrollment.py   # StudentEnrollment
  ├── submission.py   # Submission
  └── financial.py    # FinancialSnapshot
  ```
- Обновить импорты в `alembic/env.py` и `main.py`

---

### 3.6 [MEDIUM] Исправить миграцию 002 (broken downgrade)

**Файл:** `backend/alembic/versions/002_drop_unused_tables.py:25`
**Проблема:** `downgrade()` использует `op.Column` вместо `sa.Column`. Откат миграции сломан.

**Решение:**
- Заменить `op.Column` на `sa.Column` в функции `downgrade()`
- Протестировать: `alembic downgrade 001 && alembic upgrade head`

---

### 3.7 [LOW] Добавить `__repr__` и `__str__` в модели

**Проблема:** Модели не имеют человекочитаемого представления. При логировании и отладке видно только `<Course object at 0x...>`.

**Решение:**
```python
def __repr__(self) -> str:
    return f"<Course id={self.id} title={self.title!r}>"
```

---

### 3.8 [LOW] Re-export моделей из `__init__.py`

**Файл:** `backend/app/models/__init__.py`
**Проблема:** Пустой файл. Каждый раз нужно писать `from app.models.models import Course`.

**Решение:**
```python
from .models import User, Course, StudentEnrollment, Submission, FinancialSnapshot
```

---

## 4. Backend: API Endpoints

### 4.1 [CRITICAL] Исправить sync: устранить окно потери данных

**Файл:** `backend/app/services/sync.py:101-102, 185, 334`
**Проблема:** `text("DELETE FROM student_enrollments")` и аналогичные — удаляют все данные ДО получения новых из API. Если API-запрос вернул частичные данные или упал — старые данные уже потеряны.

**Решение:**
- Паттерн **fetch-then-replace**:
  1. Получить ВСЕ данные из API (в память)
  2. Открыть транзакцию
  3. Удалить старые данные (`DELETE FROM ... WHERE user_id = :uid`)
  4. Вставить новые данные (bulk insert)
  5. Commit
- Если шаг 1 fails — данные НЕ удаляются
- Если шаг 4 fails — транзакция откатывается, старые данные сохраняются

**Альтернатива (upsert):**
- Использовать `INSERT ... ON CONFLICT (course_id, student_id) DO UPDATE`
- Добавить `synced_at` колонку
- После sync — удалять записи, у которых `synced_at < текущий sync timestamp`
- Это безопаснее и не требует полной перезаписи

**Критерии приёмки:**
- При падении API mid-sync — старые данные остаются в БД
- Нет `DELETE FROM` до получения новых данных

---

### 4.2 [HIGH] Исправить N+1 в `get_alerts`

**Файл:** `backend/app/api/dashboard.py:18-50`
**Проблема:** Для каждого курса выполняется 2 отдельных SQL-запроса. При 100 курсах = 200 запросов.

**Решение:**
- Переписать одним агрегированным запросом:
  ```python
  alerts_query = (
      select(
          Course.id,
          Course.title,
          func.count(StudentEnrollment.id).label("count")
      )
      .join(StudentEnrollment)
      .where(
          Course.user_id == user.id,
          StudentEnrollment.certificate_issued == False,
          StudentEnrollment.points_earned >= 100
      )
      .group_by(Course.id)
  )
  ```
- Для submission-алертов — аналогичная агрегация
- Один запрос вместо N+1

---

### 4.3 [HIGH] Добавить пагинацию

**Файлы:** `courses.py`, `financials.py`
**Проблема:** `list_courses` возвращает все курсы без лимита. `recent_payments` рендерится без пагинации на фронтенде.

**Решение:**
- Создать generic пагинатор:
  ```python
  async def paginate(query, db, page=1, page_size=20, max_page_size=100):
      total = await db.scalar(select(func.count()).select_from(query.subquery()))
      items = (await db.execute(
          query.offset((page - 1) * page_size).limit(page_size)
      )).scalars().all()
      return {"items": items, "total": total, "page": page, "page_size": page_size}
  ```
- Добавить query-параметры `?page=1&page_size=20` в endpoints
- Response schema: `{ items: [...], total: int, page: int, page_size: int, pages: int }`

---

### 4.4 [MEDIUM] Исправить когортные границы

**Файл:** `backend/app/api/dashboard.py:105-110`
**Проблема:** Границы когорт имеют зазоры: day 7.5 не попадает ни в одну когорту (active = `days_max=7`, passive = `days_min=8`). Float-значения дней остаются неклассифицированными.

**Решение:**
```python
if days <= 7:
    cohort = "active"
elif days <= 30:
    cohort = "passive"
elif days <= 90:
    cohort = "fading"
else:
    cohort = "sleeping"
```
- Использовать `<=` для верхней границы каждой когорты
- Это соответствует определению в AGENTS.md: Active ≤ 7, Passive 8–30, Fading 30–90, Sleeping > 90

---

### 4.5 [MEDIUM] Вынести trigger_sync в background task

**Файл:** `backend/app/api/sync.py:35`
**Проблема:** `trigger_sync` вызывает `sync_all()` напрямую, блокируя HTTP-request. Для больших наборов данных request может упасть по таймауту.

**Решение:**
- Использовать FastAPI `BackgroundTasks`:
  ```python
  @router.post("")
  async def trigger_sync(
      background_tasks: BackgroundTasks,
      user=Depends(get_user)
  ):
      background_tasks.add_task(sync_all)
      return {"status": "sync_started"}
  ```
- Frontend опрашивает `/api/sync/status` для отслеживания прогресса

---

### 4.6 [MEDIUM] Заменить `== False` / `== True` на `is_(False)` / `is_(True)`

**Файлы:** `dashboard.py:25, 72`
**Проблема:** `StudentEnrollment.certificate_issued == False` — PEP8-noncompliant и может вызвать предупреждения линтера.

**Решение:**
- Использовать SQLAlchemy `.is_(False)` и `.is_(True)`:
  ```python
  .where(StudentEnrollment.certificate_issued.is_(False))
  ```

---

### 4.7 [LOW] Добавить типизацию response models (Pydantic schemas)

**Файлы:** все API endpoints
**Проблема:** Endpoints возвращают `dict` без валидации. Нет автодокументации в Swagger, нет гарантии структуры ответа.

**Решение:**
- Создать `backend/app/schemas/`:
  ```
  schemas/
  ├── __init__.py
  ├── course.py       # CourseResponse, CourseListResponse
  ├── dashboard.py    # KpiResponse, AlertResponse, CohortStatsResponse
  ├── financials.py   # FinancialsResponse, PaymentResponse
  ├── sync.py         # SyncStatusResponse
  └── auth.py         # UserResponse, LoginResponse
  ```
- Использовать `response_model=` в декораторах:
  ```python
  @router.get("/", response_model=list[CourseResponse])
  ```

---

### 4.8 [LOW] Добавить type hints на все параметры endpoints

**Проблема:** Многие параметры не имеют type annotations: `user=Depends(get_user)`, `page: int = 1`.

**Решение:**
- Добавить полные type hints:
  ```python
  async def list_courses(
      page: int = Query(1, ge=1),
      page_size: int = Query(20, ge=1, le=100),
      user: User = Depends(get_user),
      db: AsyncSession = Depends(get_db),
  ) -> CourseListResponse:
  ```

---

## 5. Backend: Сервисы

### 5.1 [HIGH] Добавить max retry на 429 Rate Limit

**Файл:** `backend/app/services/stepik_api.py:37-40`
**Проблема:** При получении 429 `_request` рекурсивно вызывает себя без лимита. Если Stepik вернёт 429 подряд 100 раз — бесконечный цикл.

**Решение:**
```python
MAX_RETRIES = 5
async def _request(self, endpoint, params=None, token=None, retries=0):
    if retries >= MAX_RETRIES:
        raise RateLimitExceeded(f"Exceeded {MAX_RETRIES} retries for {endpoint}")
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 2 ** retries))
        await asyncio.sleep(retry_after)
        return await self._request(endpoint, params, token, retries + 1)
```
- Добавить exponential backoff: `min(retry_after, 2 ** retries)`
- После MAX_RETRIES — выбрасывать кастомное исключение `StepikRateLimitError`
- Логировать каждый retry с уровнем WARNING

---

### 5.2 [HIGH] Сделать rate limiter атомарным (Redis Lua)

**Файл:** `backend/app/services/rate_limiter.py:17-40`
**Проблема:** GET-then-SET pipeline в Redis не атомарен. Два параллельных запроса могут прочитать одинаковое значение и оба декрементировать, превышая лимит.

**Решение:**
- Заменить на Lua-скрипт:
  ```python
  LUA_TOKEN_BUCKET = """
  local key = KEYS[1]
  local max_tokens = tonumber(ARGV[1])
  local refill_rate = tonumber(ARGV[2])
  local now = tonumber(ARGV[3])

  local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
  local tokens = tonumber(bucket[1]) or max_tokens
  local last_refill = tonumber(bucket[2]) or now

  local elapsed = now - last_refill
  tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

  if tokens >= 1 then
      tokens = tokens - 1
      redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
      redis.call('EXPIRE', key, 60)
      return 1
  else
      redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
      redis.call('EXPIRE', key, 60)
      return 0
  end
  """
  ```
- Зарегистрировать скрипт при инициализации: `redis.register_script(LUA_TOKEN_BUCKET)`
- Вызывать атомарно: `script(keys=[key], args=[max_tokens, refill_rate, now])`

---

### 5.3 [HIGH] Добавить обработку Redis unavailability

**Файл:** `backend/app/services/rate_limiter.py`
**Проблема:** Если Redis недоступен, `acquire_token()` выбрасывает необработанное исключение, краша API-запрос.

**Решение:**
```python
async def acquire_token(...) -> bool:
    try:
        result = await script(...)
        return bool(result)
    except (RedisError, ConnectionError):
        logger.warning("Redis unavailable, allowing request (open circuit)")
        return True  # fail-open: если Redis down — пропускаем запрос
```
- Добавить healthcheck endpoint для Redis: `GET /api/health` проверяет Redis и возвращает статус

---

### 5.4 [MEDIUM] Добавить retry на 5xx ошибки Stepik API

**Файл:** `backend/app/services/stepik_api.py`
**Проблема:** Только 429 обрабатывается. 500, 502, 503 — падают сразу.

**Решение:**
- Добавить exponential backoff на 5xx:
  ```python
  if response.status_code >= 500:
      if retries < MAX_RETRIES:
          await asyncio.sleep(2 ** retries)
          return await self._request(endpoint, params, token, retries + 1)
  ```

---

### 5.5 [MEDIUM] Сделать `_finance_token_cache` потокобезопасным

**Файл:** `backend/app/services/stepik_api.py:95`
**Проблема:** Модульный `dict` мутируется из async-контекстов. При concurrent-запросах возможны race conditions.

**Решение:**
- Использовать `asyncio.Lock`:
  ```python
  _cache_lock = asyncio.Lock()
  _finance_token_cache = {}

  async def get_finance_token(user_id):
      async with _cache_lock:
          if user_id in _finance_token_cache:
              return _finance_token_cache[user_id]
      token = await _fetch_finance_token(user_id)
      async with _cache_lock:
          _finance_token_cache[user_id] = token
      return token
  ```
- Или использовать Redis с TTL для кэширования

---

### 5.6 [MEDIUM] Изолировать ошибки token refresh per-user

**Файл:** `backend/app/services/token_refresh.py:21-54`
**Проблема:** Все пользователи обновляются в одной транзакции. Ошибка для одного пользователя откатывает все успешные обновления.

**Решение:**
- Каждый пользователь — отдельная транзакция:
  ```python
  for user in users:
      try:
          async with async_session() as session:
              await refresh_single_user(session, user)
              await session.commit()
      except Exception as e:
          logger.error(f"Token refresh failed for user {user.id}: {e}")
  ```

---

### 5.7 [MEDIUM] Добавить user-scoping в sync

**Файл:** `backend/app/services/sync.py:57`
**Проблема:** `select(User).limit(1)` — берёт первого попавшегося пользователя. В multi-user сценарии синхронизируются данные только одного пользователя.

**Решение:**
- Добавить параметр `user_id: UUID` в `sync_all()`:
  ```python
  async def sync_all(user_id: UUID | None = None):
      async with async_session() as session:
          if user_id:
              users = (await session.execute(select(User).where(User.id == user_id))).scalars().all()
          else:
              users = (await session.execute(select(User))).scalars().all()
      for user in users:
          await sync_user_data(user)
  ```
- В `trigger_sync` — передавать `user.id` из токена
- В `startup_sync` — синхронизировать всех пользователей

---

### 5.8 [LOW] Возвращать 202 Accepted при rate limit (per AGENTS.md)

**Файл:** `backend/app/services/rate_limiter.py` → `handle_rate_limit`
**Проблема:** AGENTS.md предписывает: при 429 вернуть фронтенду `202 Accepted`. Текущая реализация просто спит и ретраит.

**Решение:**
- При получении 429:
  1. Извлечь `Retry-After`
  2. Поставить фоновую задачу на retry
  3. Вернуть `202 Accepted` с заголовком `Retry-After` и телом `{"status": "rate_limited", "retry_after": N}`
- Frontend показывает индикатор "Ожидание синхронизации"

---

## 6. Backend: Тесты

### 6.1 [HIGH] Переписать тесты моделей

**Файл:** `backend/tests/test_models.py`
**Проблема:** Тесты используют `MagicMock` вместо реальных SQLAlchemy-моделей. Тестируются мок-объекты, что не имеет ценности.

**Решение:**
- Тестировать реальные модели с SQLite in-memory:
  ```python
  async def test_course_creation(db_session):
      course = Course(id=uuid4(), title="Test", user_id=uuid4())
      db_session.add(course)
      await db_session.commit()
      result = await db_session.get(Course, course.id)
      assert result.title == "Test"
  ```
- Тестировать constraints (unique, not null)
- Тестировать default-значения
- Тестировать отношения (relationship loading)

---

### 6.2 [HIGH] Убрать `inspect.getsource` из тестов

**Файл:** `backend/tests/test_edge_cases.py`
**Проблема:** Тесты проверяют текст исходного кода (`assert "GET" in source`), а не поведение. Любое реформатирование ломает тесты.

**Решение:**
- Заменить на behavioral tests:
  - Вместо проверки `"GET" in source` — мокнуть httpx и проверять, что вызывается только GET
  - Вместо проверки `"DELETE" not in source` — мокнуть HTTP и проверять, что POST/PUT/DELETE не вызываются

---

### 6.3 [HIGH] Добавить интеграционные тесты sync

**Проблема:** Все sync-тесты — unit-level. Нет end-to-end теста полного sync flow.

**Решение:**
- Создать `backend/tests/test_sync_integration.py`:
  ```python
  async def test_full_sync_flow(db_session, mock_stepik_api):
      # 1. Setup: mock Stepik API responses
      # 2. Call sync_all(user_id)
      # 3. Verify: courses, enrollments, submissions, financials created in DB
      # 4. Call sync_all again with updated data
      # 5. Verify: data updated correctly, no duplicates
  ```
- Тестировать partial failure: один API-запрос fails, остальные succeed
- Тестировать пустой ответ API (новый пользователь без курсов)

---

### 6.4 [MEDIUM] Заменить `asyncio.get_event_loop().run_until_complete()` на `asyncio.run()`

**Файл:** `backend/tests/test_sync_api.py:62`
**Проблема:** `asyncio.get_event_loop()` deprecated в Python 3.10+.

**Решение:**
- Использовать `@pytest.mark.asyncio` для всех async-тестов
- Убрать все `run_until_complete` вызовы
- Настроить `asyncio_mode = auto` в `pytest.ini` (уже настроено, но не все тесты используют)

---

### 6.5 [MEDIUM] Добавить тесты `acquire_token` (rate limiter)

**Файл:** `backend/tests/test_rate_limiter.py`
**Проблема:** Тестируется только `handle_rate_limit`. `acquire_token` (основная логика bucket) не покрыта.

**Решение:**
- Тесты:
  - Token available → returns True, tokens decremented
  - No tokens → returns False
  - Token refill after time → tokens available again
  - Concurrent requests → only N succeed (атомарность)
  - Redis down → fail-open behavior

---

### 6.6 [MEDIUM] Убрать hardcoded `ENCRYPTION_KEY` из тестовых фикстур

**Файл:** `backend/tests/conftest.py:3`
**Проблема:** Реальный Fernet-ключ захардкожен в тестовых фикстурах.

**Решение:**
- Генерировать ключ динамически:
  ```python
  from cryptography.fernet import Fernet
  TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()
  ```
- Или использовать env var `TEST_ENCRYPTION_KEY` с fallback на generated

---

### 6.7 [LOW] Добавить `testpaths` и `filterwarnings` в pytest.ini

**Файл:** `backend/pytest.ini`

**Решение:**
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

---

### 6.8 [LOW] Добавить coverage thresholds

**Проблема:** Нет минимального порога покрытия. Тесты могут деградировать без уведомления.

**Решение:**
- Добавить `pytest-cov` в `requirements-test.txt`
- Настроить: `pytest --cov=app --cov-report=html --cov-fail-under=80`
- Добавить coverage-отчёт в CI pipeline

---

## 7. Frontend: Архитектура

### 7.1 [CRITICAL] Исправить порядок Provider-ов

**Файл:** `frontend/src/main.jsx`
**Проблема:** `SyncProvider` оборачивает `AuthProvider` (через `App`). Это означает, что `SyncContext` делает API-вызовы ДО того, как auth-токен доступен. Для неавторизованных пользователей: 6 API-запросов → 401 → interceptor reloads page → reload → снова 401 → infinite loop.

**Решение:**
```jsx
// main.jsx
<AuthProvider>
  <SyncProvider>
    <App />
  </SyncProvider>
</AuthProvider>
```
- `SyncProvider` должен проверять `isAuthenticated` перед fetch:
  ```jsx
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchAll();
  }, [isAuthenticated]);
  ```
- Вынести `AuthProvider` в `main.jsx`, а не в `App.jsx`

---

### 7.2 [HIGH] Добавить production base URL для API

**Файл:** `frontend/src/api.js`
**Проблема:** Axios instance не имеет `baseURL`. В dev работает через Vite proxy, в production — API-запросы пойдут на frontend-origin (404).

**Решение:**
```javascript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
});
```
- В `vite.config.js` proxy работает для dev (префикс `/api`)
- В production: nginx reverse proxy или `VITE_API_URL=http://backend:8000/api`

---

### 7.3 [HIGH] Добавить 404/catch-all route

**Файл:** `frontend/src/App.jsx`
**Проблема:** При переходе на несуществующий путь — пустая страница.

**Решение:**
```jsx
<Route path="*" element={<NotFound />} />
```
- Создать `src/pages/NotFound.jsx` с кнопкой "Вернуться на дашборд"
- Стилизация в общей теме «Spaceship Control Panel»

---

### 7.4 [HIGH] Добавить code splitting / lazy loading

**Файл:** `frontend/src/App.jsx`
**Проблема:** Все страницы импортируются eagerly. Initial bundle включает все страницы, Recharts (тяжёлая библиотека), и все компоненты.

**Решение:**
```jsx
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Courses = lazy(() => import('./pages/Courses'));
const Financials = lazy(() => import('./pages/Financials'));
const Cohorts = lazy(() => import('./pages/Cohorts'));

<Suspense fallback={<PageSkeleton />}>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    ...
  </Routes>
</Suspense>
```
- Recharts загружается только при навигации на страницу с графиками

---

### 7.5 [MEDIUM] Добавить обработку ошибок API на уровне контекста

**Файл:** `frontend/src/contexts/SyncContext.jsx`
**Проблема:** `catch {}` (пустой catch) и `console.error` — ошибки API невидимы для пользователя.

**Решение:**
- Добавить `error` state в SyncContext:
  ```jsx
  const [errors, setErrors] = useState({});
  // В fetchAll:
  results.forEach((result, i) => {
    if (result.status === 'rejected') {
      setErrors(prev => ({ ...prev, [keys[i]]: result.reason?.message }));
    }
  });
  ```
- Экспортировать `errors` из контекста
- Страницы отображают `ErrorBanner` при наличии errors

---

### 7.6 [MEDIUM] Добавить backoff при ошибке polling

**Файл:** `frontend/src/contexts/SyncContext.jsx:74`
**Проблема:** Polling каждые 30 секунд без backoff. Если backend down — hammering каждые 30 сек.

**Решение:**
```jsx
const [pollInterval, setPollInterval] = useState(30_000);
// При ошибке:
setPollInterval(prev => Math.min(prev * 2, 300_000)); // до 5 минут
// При успехе:
setPollInterval(30_000);
```

---

### 7.7 [MEDIUM] Вынести localStorage key в константу

**Файлы:** `frontend/src/api.js:20`, `frontend/src/contexts/AuthContext.jsx:4`
**Проблема:** `"stepik_session_token"` дублируется в двух файлах.

**Решение:**
- В `constants.js`:
  ```javascript
  export const STORAGE_KEYS = {
    SESSION_TOKEN: 'stepik_session_token',
  };
  ```
- Импортировать в `api.js` и `AuthContext.jsx`
- В дальнейшем (после перехода на cookie) — удалить

---

### 7.8 [MEDIUM] Добавить AbortController в SyncContext fetchAll

**Файл:** `frontend/src/contexts/SyncContext.jsx`
**Проблема:** При unmount компонента API-запросы продолжают выполняться и пытаются обновить state unmounted компонента.

**Решение:**
```jsx
useEffect(() => {
  const controller = new AbortController();
  fetchAll(controller.signal);
  return () => controller.abort();
}, []);
```

---

### 7.9 [LOW] Убрать unused `import React` из main.jsx

**Файл:** `frontend/src/main.jsx:1`
**Проблема:** С React 18 JSX transform — `import React` не нужен.

**Решение:**
- Удалить строку `import React from 'react'`

---

## 8. Frontend: Контексты и состояния

### 8.1 [HIGH] Добавить обработку не-JSON ответов в AuthContext

**Файл:** `frontend/src/contexts/AuthContext.jsx:60`
**Проблема:** `login()` вызывает `res.json()`. Если сервер вернёт HTML (nginx error) — неинформативный `SyntaxError`.

**Решение:**
```javascript
const contentType = res.headers.get('content-type');
if (!contentType?.includes('application/json')) {
  throw new Error(`Server returned non-JSON response (${res.status})`);
}
const data = await res.json();
```

---

### 8.2 [HIGH] Улучшить 401 interceptor

**Файл:** `frontend/src/api.js:23`
**Проблема:** `window.location.reload()` — агрессивный reload. Пользователь теряет контекст. Проверка `pathname.startsWith('/api/auth')` бессмысленна (фронтенд не имеет `/api/auth` путей).

**Решение:**
```javascript
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      window.location.href = '/';  // редирект на login, не reload
    }
    return Promise.reject(error);
  }
);
```

---

### 8.3 [MEDIUM] Добавить token refresh на фронтенде

**Файл:** `frontend/src/contexts/AuthContext.jsx`
**Проблема:** Нет механизма refresh. При истечении session token пользователь просто получает 401 и reload.

**Решение:**
- При 401: попытаться refresh token через `POST /api/auth/refresh`
- Если refresh успешен — повторить исходный запрос
- Если refresh fails — logout + redirect на login

---

## 9. Frontend: Страницы

### 9.1 [HIGH] Добавить error states на все страницы

**Файлы:** `Dashboard.jsx`, `Courses.jsx`, `Financials.jsx`, `Cohorts.jsx`
**Проблема:** Ни одна страница не отображает ошибки API. Если backend вернул ошибку — пользователь видит пустую страницу или loading-спиннер навсегда.

**Решение:**
- На каждой странице:
  ```jsx
  if (errors?.dashboard) {
    return <ErrorBanner message={errors.dashboard} onRetry={refetch} />;
  }
  ```
- Создать универсальный компонент `ErrorBanner`
- Показывать inline-ошибки для отдельных виджетов (не блокируя всю страницу)

---

### 9.2 [HIGH] Исправить RevenueChart: сломанная подсветка текущего месяца

**Файл:** `frontend/src/components/RevenueChart.jsx:22`
**Проблема:** `currentMonth = new Date().toISOString().slice(0, 7)` → `"2026-07"`. Сравнение `entry.month?.startsWith(currentMonth)` не работает, если month — русское название (`"Июль 2026"`) или полная дата (`"2026-07-01T00:00:00"`).

**Решение:**
- Нормализовать формат месяца на backend (ISO: `2026-07`)
- Или на frontend — парсить оба формата:
  ```javascript
  const isCurrentMonth = (monthStr) => {
    const current = new Date().toISOString().slice(0, 7); // "2026-07"
    if (!monthStr) return false;
    if (monthStr.startsWith(current)) return true;
    // Парсинг "Июль 2026"
    const months_ru = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                        'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
    const parts = monthStr.split(' ');
    const idx = months_ru.indexOf(parts[0]);
    if (idx >= 0 && parts[1]) {
      const isoMonth = String(idx + 1).padStart(2, '0');
      return `${parts[1]}-${isoMonth}` === current;
    }
    return false;
  };
  ```

---

### 9.3 [MEDIUM] Разбить Financials на подкомпоненты

**Файл:** `frontend/src/pages/Financials.jsx` (228 строк)
**Проблема:** Три tab-view (months, courses, recent) в одном компоненте. Слишком длинный, трудно читать.

**Решение:**
```
Financials/
├── index.jsx            # Tab navigation + layout
├── MonthlyRevenue.jsx   # Tab: месяцы
├── CourseBreakdown.jsx  # Tab: курсы
└── RecentPayments.jsx   # Tab: платежи
```
- Каждый подкомпонент — 50-80 строк
- Общая логика фильтрации — в custom hook `useFinancials`

---

### 9.4 [MEDIUM] Добавить null-safety на `.toLocaleString()` вызовы

**Файл:** `frontend/src/pages/Financials.jsx:127-133`
**Проблема:** `m.turnover.toLocaleString('ru-RU')` — если `m.turnover` undefined/null → TypeError.

**Решение:**
- Создать helper:
  ```javascript
  const formatCurrency = (value) =>
    (value ?? 0).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });
  ```
- Или использовать optional chaining: `(m.turnover ?? 0).toLocaleString('ru-RU')`

---

### 9.5 [MEDIUM] Добавить пагинацию на frontend для recent_payments

**Файл:** `frontend/src/pages/Financials.jsx`
**Проблема:** Все платежи рендерятся без лимита. При тысячах записей — тормоза рендера.

**Решение:**
- Использовать server-side пагинацию (если добавлена на backend, см. 4.3)
- Или client-side: показывать 20 записей + кнопка "Показать ещё" / номера страниц
- Создать универсальный `Pagination` компонент

---

### 9.6 [MEDIUM] Исправить русскую плюрализацию

**Файл:** `frontend/src/pages/Courses.jsx:28`
**Проблема:** `"1 курсов"` — грамматически некорректно.

**Решение:**
```javascript
const pluralize = (n, forms) => {
  // forms: ['курс', 'курса', 'курсов']
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
};
// Usage: `${count} ${pluralize(count, ['курс', 'курса', 'курсов'])}`
```
- Вынести в `utils/pluralize.js`
- Применить везде, где используется счётная форма

---

### 9.7 [MEDIUM] Вынести hardcoded URL в константы

**Файл:** `frontend/src/pages/Courses.jsx:65`
**Проблема:** `https://stepik.org/course/` захардкожено в компоненте.

**Решение:**
- В `constants.js`:
  ```javascript
  export const STEPIK_URLS = {
    course: (id) => `https://stepik.org/course/${id}`,
    courseEdit: (id) => `https://stepik.org/course/${id}/edit`,
    lessonEdit: (courseId, lessonId) => `https://stepik.org/lesson/${lessonId}/edit`,
    announcements: (courseId) => `https://stepik.org/course/${courseId}/announcements`,
  };
  ```
- Импортировать во все компоненты

---

### 9.8 [MEDIUM] Сохранять активный таб в URL

**Файл:** `frontend/src/pages/Financials.jsx`
**Проблема:** Активный таб хранится в `useState`. При refresh страницы — сбрасывается на первый.

**Решение:**
- Использовать `useSearchParams`:
  ```jsx
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };
  ```

---

### 9.9 [LOW] Нормализовать сравнение статуса курса

**Файл:** `frontend/src/pages/Courses.jsx:53`
**Проблема:** `course.status === 'Published'` — зависит от регистра. API может вернуть `'published'`.

**Решение:**
```javascript
const isPublished = course.status?.toLowerCase() === 'published';
```

---

## 10. Frontend: Компоненты

### 10.1 [MEDIUM] Добавить PropTypes на все компоненты

**Файлы:** все компоненты в `src/components/`
**Проблема:** Нет валидации props. При передаче неправильных типов — silent failure.

**Решение:**
- Добавить PropTypes:
  ```jsx
  import PropTypes from 'prop-types';
  KpiCard.propTypes = {
    title: PropTypes.string.isRequired,
    value: PropTypes.number.isRequired,
    icon: PropTypes.string.isRequired,
    color: PropTypes.oneOf(['cyber-blue', 'neon-green', 'amber-alert', 'crimson-alert']),
    trend: PropTypes.number,
  };
  ```
- Или: рассмотреть миграцию на TypeScript (долгосрочная задача)

---

### 10.2 [MEDIUM] Вынести `colorClasses` map из компонента KpiCard

**Файл:** `frontend/src/components/KpiCard.jsx`
**Проблема:** Объект `colorClasses` пересоздаётся при каждом рендере.

**Решение:**
- Вынести за пределы компонента:
  ```jsx
  const COLOR_CLASSES = {
    'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
    'neon-green': 'text-neon-green border-neon-green/20',
    // ...
  };
  ```

---

### 10.3 [MEDIUM] Добавить tooltip formatter в CohortChart

**Файл:** `frontend/src/components/CohortChart.jsx`
**Проблема:** Tooltip показывает raw numbers без форматирования. Нет locale.

**Решение:**
```jsx
<Tooltip formatter={(value) => value.toLocaleString('ru-RU')} />
```

---

### 10.4 [LOW] Заменить index-based keys на stable IDs

**Файлы:** `RevenueChart.jsx:61`, `CohortChart.jsx:41`, `Financials.jsx:123, 159, 198`, `Dashboard.jsx:89`
**Проблема:** `key={i}` (индекс массива) — при переупорядочивании React некорректно обновляет DOM.

**Решение:**
- Использовать stable ID: `key={item.id}`, `key={item.month}`, `key={`${course.id}-${i}`}`
- Для alerts: `key={`alert-${course.id}-${alert.type}`}`

---

### 10.5 [LOW] Унифицировать форматирование чисел

**Файлы:** `KpiCard.jsx` (CountUp с `separator=" "`), `Financials.jsx` (`toLocaleString('ru-RU')`)
**Проблема:** CountUp использует обычный пробел, `toLocaleString` — non-breaking space. Разное форматирование на одном экране.

**Решение:**
- Создать `utils/formatNumber.js`:
  ```javascript
  export const formatNumber = (value, options = {}) =>
    value.toLocaleString('ru-RU', { maximumFractionDigits: 0, ...options });
  ```
- CountUp: использовать `formattingFn` для консистентности
- Использовать единый форматтер во всех компонентах

---

## 11. Frontend: Стили и UI

### 11.1 [MEDIUM] Добавить Firefox scrollbar стили

**Файл:** `frontend/src/index.css`
**Проблема:** Кастомные скроллбары только для WebKit-браузеров. Firefox показывает стандартные.

**Решение:**
```css
* {
  scrollbar-width: thin;
  scrollbar-color: #38bdf8 #162032;
}
```

---

### 11.2 [MEDIUM] Оптимизировать загрузку шрифтов

**Файл:** `frontend/index.html:9`
**Проблема:** Google Fonts загружается синхронно (render-blocking).

**Решение:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
      rel="stylesheet" media="print" onload="this.onload=null;this.removeAttribute('media');">
<noscript><link rel="stylesheet" href="..."></noscript>
```
- Или: self-host шрифты (скачать .woff2 и положить в `public/fonts/`)

---

### 11.3 [LOW] Убрать dead config в tailwind

**Файл:** `frontend/tailwind.config.js`
**Проблема:** `darkMode: 'class'` — класс `dark` hardcoded в `index.html`, переключение невозможно. `backdropBlur.xs` — определён, но нигде не используется.

**Решение:**
- Если dark mode единственный режим — убрать `darkMode: 'class'` и `dark:` prefix из всех классов
- Или: оставить для будущего light mode (задокументировать решение)
- Убрать `backdropBlur.xs` если не используется, или начать использовать

---

### 11.4 [LOW] Унифицировать переводы / язык интерфейса

**Файл:** `frontend/src/components/ErrorBoundary.jsx`
**Проблема:** ErrorBoundary на английском ("Application Error", "Stack trace", "Reload"), остальной интерфейс — на русском.

**Решение:**
- Перевести ErrorBoundary на русский
- Создать `src/i18n/ru.js` с константами переводов (для будущего i18n)
- Все тексты вынести из компонентов в файл переводов

---

## 12. Frontend: Доступность (a11y)

### 12.1 [MEDIUM] Добавить ARIA landmarks

**Файл:** `frontend/src/components/Layout.jsx`
**Проблема:** Нет семантических ARIA-атрибутов. Screen readers не могут определить навигацию.

**Решение:**
```jsx
<nav role="navigation" aria-label="Основная навигация">
  {/* sidebar */}
</nav>
<main role="main" aria-label="Основной контент">
  {/* page content */}
</main>
```

---

### 12.2 [MEDIUM] Добавить text alternatives для иконок

**Файл:** `frontend/src/components/Layout.jsx`
**Проблема:** Unicode-символы (◈, ◆, ◉, ◎) используются как иконки. Screen readers читают их как "White diamond", "Black diamond" и т.д.

**Решение:**
- Добавить `aria-label` на каждую иконку-кнопку:
  ```jsx
  <button aria-label="Дашборд">◈</button>
  ```
- Или: заменить Unicode на SVG-иконки с `<title>` (lucide-react, heroicons)
- Рекомендуется SVG — более гибко стилизуется

---

### 12.3 [LOW] Добавить alt-text для графиков

**Файлы:** `RevenueChart.jsx`, `CohortChart.jsx`
**Проблема:** Графики Recharts — чисто визуальные. Нет текстового описания данных.

**Решение:**
- Обернуть графики в `<figure>` с `<figcaption>`:
  ```jsx
  <figure role="img" aria-label="Диаграмма доходов по месяцам">
    <BarChart ...>
    <figcaption>Доходы за последние 12 месяцев: ...</figcaption>
  </figure>
  ```

---

## 13. Frontend: Тесты

### 13.1 [HIGH] Убрать SyncProvider из TestRouter

**Файл:** `frontend/src/test/TestRouter.jsx`
**Проблема:** `TestRouter` оборачивает в `AuthProvider` + `SyncProvider`. Каждый тест запускает 6 API-запросов из SyncContext. Тесты медленные, требуют моков всех 6 endpoints.

**Решение:**
- Убрать `SyncProvider` из `TestRouter`
- Создавать отдельный `renderWithSync` helper для integration tests
- Unit tests компонентов — рендерить без SyncProvider, передавать данные через props

---

### 13.2 [MEDIUM] Добавить тесты tab-switching в Financials

**Файл:** `frontend/src/test/Financials.test.jsx`
**Проблема:** Тестируется только default tab "months". Табы "courses" и "recent" не покрыты.

**Решение:**
- Тесты:
  - Click "По курсам" → renders course breakdown table
  - Click "Платежи" → renders recent payments list
  - Tab state persists in URL (интеграционный тест)

---

### 13.3 [MEDIUM] Добавить тест подсветки текущего месяца в RevenueChart

**Файл:** `frontend/src/test/RevenueChart.test.jsx`
**Проблема:** Ключевая визуальная фича (подсветка текущего месяца) не протестирована.

**Решение:**
```jsx
test('highlights current month bar', () => {
  render(<RevenueChart data={mockData} />);
  const currentMonthBar = screen.getByTestId('bar-current-month');
  expect(currentMonthBar).toHaveClass('current-month-highlight');
});
```

---

### 13.4 [MEDIUM] Заменить `global.fetch = vi.fn()` на `vi.spyOn`

**Файл:** `frontend/src/test/Layout.test.jsx:53`
**Проблема:** Прямая перезапись `global.fetch` — хрупко, может протечь между тестами.

**Решение:**
```jsx
const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(...);
// afterEach:
fetchSpy.mockRestore();
```

---

### 13.5 [MEDIUM] Добавить `user-event` для тестирования взаимодействий

**Файл:** `frontend/package.json`
**Проблема:** Отсутствует `@testing-library/user-event`. Тесты используют `fireEvent`, что не имитирует реальные пользовательские события.

**Решение:**
- Установить: `npm install -D @testing-library/user-event`
- Заменить `fireEvent.click` на `await userEvent.click` в тестах

---

### 13.6 [LOW] Добавить тесты color variants в KpiCard

**Файл:** `frontend/src/test/KpiCard.test.jsx`
**Проблема:** Тестируется только `cyber-blue`. Остальные варианты цветов не покрыты.

**Решение:**
- Параметризованный тест:
  ```jsx
  test.each(['cyber-blue', 'neon-green', 'amber-alert', 'crimson-alert'])(
    'renders with color %s', (color) => {
      render(<KpiCard title="Test" value={100} icon="◈" color={color} />);
      expect(screen.getByText('Test')).toHaveClass(`text-${color}`);
    }
  );
  ```

---

### 13.7 [LOW] Убрать `globals: true` из vitest config

**Файл:** `frontend/vitest.config.js`
**Проблема:** `globals: true` засоряет глобальную область видимости тестов.

**Решение:**
- Убрать `globals: true`
- Добавить явные импорты: `import { describe, it, expect, vi } from 'vitest'`

---

## 14. Инфраструктура: Docker и CI

### 14.1 [HIGH] Исправить frontend Dockerfile: dev server в production

**Файл:** `frontend/Dockerfile:12`
**Проблема:** `CMD ["npm", "run", "dev"]` — Vite dev server в production. Нет minification, tree-shaking, chunk splitting. Dev server медленный и небезопасный.

**Решение:**
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```
- Создать `frontend/nginx.conf` для SPA routing (fallback на `index.html`)

---

### 14.2 [HIGH] Добавить non-root user в backend Dockerfile

**Файл:** `backend/Dockerfile`
**Проблема:** Контейнер запускается от root. При компрометации контейнера — root-доступ к хосту.

**Решение:**
```dockerfile
RUN addgroup --system app && adduser --system --ingroup app app
USER app
```

---

### 14.3 [MEDIUM] Использовать multi-stage build для backend

**Файл:** `backend/Dockerfile`
**Проблема:** `build-essential` (gcc, make) устанавливается, но не нужен в runtime. Образ раздут.

**Решение:**
```dockerfile
# Build stage
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY app/ /app/app/
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 14.4 [MEDIUM] Добавить healthcheck в backend Dockerfile

**Решение:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1
```

---

### 14.5 [MEDIUM] Добавить restart policy в docker-compose

**Файл:** `docker-compose.yml`
**Проблема:** Контейнеры не перезапускаются при crash.

**Решение:**
```yaml
restart: unless-stopped
```
- Добавить для всех сервисов

---

### 14.6 [LOW] Использовать `npm ci` вместо `npm install`

**Файл:** `frontend/Dockerfile`
**Проблема:** `npm install` может изменить `package-lock.json`. Билд не воспроизводим.

**Решение:**
- Заменить на `npm ci` (устанавливает точные версии из lockfile)

---

### 14.7 [LOW] Добавить resource limits в docker-compose

**Файл:** `docker-compose.yml`
**Решение:**
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '1.0'
```

---

### 14.8 [LOW] Добавить Redis authentication

**Файл:** `docker-compose.yml`
**Решение:**
```yaml
redis:
  command: redis-server --requirepass ${REDIS_PASSWORD:-stepik_redis}
```
- Добавить `REDIS_PASSWORD` в `.env.example`
- Обновить backend `rate_limiter.py` для передачи пароля

---

## 15. Скрипты запуска

### 15.1 [HIGH] Заменить `kill -9` на graceful shutdown

**Файл:** `start.sh:20-24`
**Проблема:** `kill -9` (SIGKILL) — не даёт процессам время на cleanup. Риск повреждения данных (незавершённые DB-транзакции, open connections).

**Решение:**
```bash
cleanup() {
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill -TERM "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill -TERM "$FRONTEND_PID" 2>/dev/null
    # Wait up to 10 seconds for graceful shutdown
    for i in $(seq 1 10); do
        if ! kill -0 "$BACKEND_PID" 2>/dev/null && ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    # Force kill if still running
    [ -n "$BACKEND_PID" ] && kill -9 "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill -9 "$FRONTEND_PID" 2>/dev/null
    docker compose down 2>/dev/null
}
```

---

### 15.2 [HIGH] Добавить readiness checks вместо sleep

**Файл:** `start.sh:39, 61`
**Проблема:** `sleep 3` — ненадёжно. На медленных машинах PostgreSQL/Redis могут не подняться за 3 секунды.

**Решение:**
```bash
wait_for_service() {
    local cmd="$1"
    local timeout=30
    local elapsed=0
    while ! eval "$cmd" > /dev/null 2>&1; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ $elapsed -ge $timeout ]; then
            echo "Timeout waiting for service: $cmd"
            exit 1
        fi
    done
}

wait_for_service "docker compose exec -T postgres pg_isready"
wait_for_service "docker compose exec -T redis redis-cli ping"
```

---

### 15.3 [MEDIUM] Добавить проверку зависимостей

**Файлы:** `start.sh`, `start.bat`
**Проблема:** Скрипты предполагают наличие `docker`, `uv`, `node`, `npm` без проверки.

**Решение:**
```bash
check_deps() {
    local missing=()
    for cmd in docker node npm uv; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing dependencies: ${missing[*]}"
        echo "Please install them and try again."
        exit 1
    fi
}
check_deps
```

---

### 15.4 [MEDIUM] Добавить `set -o pipefail` в start.sh

**Файл:** `start.sh:2`
**Проблема:** `set -e` без `pipefail` — pipe-ошибки не прерывают скрипт.

**Решение:**
```bash
set -eo pipefail
```

---

### 15.5 [MEDIUM] Исправить `taskkill` для не-английских Windows

**Файл:** `start.bat:79-80`
**Проблема:** `netstat` + `findstr "LISTENING"` зависит от локали. На русской Windows — `"ПРОСЛУШИВАНИЕ"`.

**Решение:**
- Использовать PowerShell:
  ```batch
  powershell -Command "Get-NetTCPConnection -LocalPort %BACKEND_PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
  ```

---

### 15.6 [LOW] Проверять существование `.env` перед запуском

**Решение:**
```bash
if [ ! -f .env ]; then
    echo ".env file not found. Copy from .env.example and fill in values."
    exit 1
fi
```

---

### 15.7 [LOW] Сделать `pkill` более специфичным

**Файл:** `start.sh:21-24`
**Проблема:** `pkill -f "uvicorn app.main"` может убить другие uvicorn-процессы на машине.

**Решение:**
- Использовать PID-файлы:
  ```bash
  echo $! > /tmp/stepik_backend.pid
  # cleanup:
  kill $(cat /tmp/stepik_backend.pid) 2>/dev/null
  rm -f /tmp/stepik_backend.pid
  ```

---

## 16. Конфигурация проекта

### 16.1 [MEDIUM] Расширить .gitignore

**Файл:** `.gitignore`
**Проблема:** Отсутствуют: `.env.*` (wildcard), `*.pem`, `*.key`, `docker-compose.override.yml`, `.coverage`, `htmlcov/`.

**Решение:**
```gitignore
# Environment files
.env
.env.*
!.env.example

# Certificates
*.pem
*.key
*.crt

# Coverage
.coverage
htmlcov/
coverage/

# Docker overrides
docker-compose.override.yml
```

---

### 16.2 [MEDIUM] Сделать порты БД/Redis конфигурируемыми

**Файл:** `docker-compose.yml`
**Проблема:** Порты PostgreSQL (5433) и Redis (6380) захардкожены, а порты backend/frontend — из `.env`.

**Решение:**
```yaml
ports:
  - "${POSTGRES_PORT:-5433}:5432"
ports:
  - "${REDIS_PORT:-6380}:6379"
```
- Добавить `POSTGRES_PORT` и `REDIS_PORT` в `.env.example`

---

### 16.3 [LOW] Добавить hint для генерации SECRET_KEY в .env.example

**Файл:** `.env.example`
**Решение:**
```bash
# Generate with: openssl rand -hex 32
SECRET_KEY=your_secret_key_here
```

---

### 16.4 [LOW] Добавить `gunicorn` в requirements.txt

**Файл:** `backend/requirements.txt`
**Проблема:** Только `uvicorn` — не подходит для production (single worker).

**Решение:**
```
gunicorn==22.0.0
```
- В `start.sh` для production: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`

---

## 17. Документация

### 17.1 [MEDIUM] Обновить README.md

**Проблема:** README не описывает:
- Переменные окружения (что каждая делает)
- API endpoints backend-а
- Архитектурные решения (почему read-only, как работает sync)
- Troubleshooting

**Решение:**
- Добавить раздел "API Endpoints" с таблицей
- Добавить раздел "Environment Variables"
- Добавить раздел "Troubleshooting"
- Добавить badges (tests, coverage, build status)

---

### 17.2 [MEDIUM] Добавить inline документацию в сложные сервисы

**Файлы:** `sync.py`, `stepik_api.py`, `rate_limiter.py`
**Проблема:** Сложная бизнес-логика без комментариев. Новый разработчик не поймет flow sync или rate limiting.

**Решение:**
- Добавить docstrings на все public-функции
- Добавить inline-комментарии для нетривиальной логики
- Добавить sequence diagram в комментариях к `sync_all()`:
  ```
  # Flow:
  # 1. Fetch user token from DB
  # 2. GET /api/courses?teacher={user_id}
  # 3. For each course: GET /api/course-grades, GET /api/submissions
  # 4. Fetch-then-replace in DB (transaction)
  # 5. Update sync timestamp
  ```

---

### 17.3 [LOW] Добавить CHANGELOG.md

**Решение:**
- Создать `CHANGELOG.md` с форматом Keep a Changelog
- Обновлять при каждом значимом изменении

---

## 18. Стандарты кода и линтинг

### 18.1 [HIGH] Добавить ESLint для frontend

**Файл:** `frontend/package.json`
**Проблема:** Нет линтера. Ошибки стиля и потенциальные баги не обнаруживаются.

**Решение:**
- Установить и настроить ESLint:
  ```bash
  npm install -D eslint @eslint/js eslint-plugin-react eslint-plugin-react-hooks
  ```
- Создать `frontend/eslint.config.js` (flat config)
- Добавить script: `"lint": "eslint src/"`
- Включить правила:
  - `react/prop-types: warn`
  - `react-hooks/rules-of-hooks: error`
  - `react-hooks/exhaustive-deps: warn`
  - `no-unused-vars: warn`
  - `no-console: warn`

---

### 18.2 [HIGH] Добавить Ruff для backend

**Файл:** `backend/requirements-test.txt`
**Проблема:** Нет Python-линтера. Код не проверяется на PEP 8, unused imports, и т.д.

**Решение:**
- Установить Ruff:
  ```
  ruff>=0.5.0
  ```
- Создать `backend/pyproject.toml`:
  ```toml
  [tool.ruff]
  line-length = 120
  target-version = "py312"
  select = ["E", "F", "I", "N", "W", "UP", "B", "A", "SIM"]

  [tool.ruff.isort]
  known-first-party = ["app"]
  ```
- Добавить script в CI: `ruff check app/ tests/`

---

### 18.3 [MEDIUM] Добавить Prettier для frontend

**Решение:**
```bash
npm install -D prettier eslint-config-prettier
```
- Создать `.prettierrc`:
  ```json
  {
    "semi": true,
    "singleQuote": true,
    "tabWidth": 2,
    "trailingComma": "all",
    "printWidth": 120
  }
  ```
- `"format": "prettier --write src/"` в `package.json`

---

### 18.4 [MEDIUM] Добавить pre-commit hooks

**Решение:**
- Backend: `pre-commit` (Python):
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      hooks: [ruff, ruff-format]
    - repo: https://github.com/pre-commit/pre-commit-hooks
      hooks: [trailing-whitespace, end-of-file-fixer, check-yaml]
  ```
- Frontend: `husky` + `lint-staged`:
  ```json
  "lint-staged": {
    "src/**/*.{js,jsx}": ["eslint --fix", "prettier --write"]
  }
  ```

---

### 18.5 [LOW] Добавить type hints на backend (mypy)

**Решение:**
- Установить `mypy` в `requirements-test.txt`
- Настроить в `pyproject.toml`:
  ```toml
  [tool.mypy]
  python_version = "3.12"
  strict = false
  warn_unused_configs = true
  ```
- Постепенно довести coverage type hints до 100%

---

## Сводная таблица приоритетов

| Приоритет | Кол-во задач | Ключевые области |
|-----------|-------------|------------------|
| **CRITICAL** | 4 | Session token в URL, data loss при sync, plaintext token exposure, порядок Providers |
| **HIGH** | 18 | Auth на endpoints, CSRF, индексы БД, N+1 queries, rate limiter, Docker production, ESLint/Ruff |
| **MEDIUM** | 30 | Timezones, когорты, пагинация, error states, ARIA, pre-commit, Redis atomic, token refresh |
| **LOW** | 20 | Type hints, PropTypes, code splitting, scrollbar, gitignore, changelog, format |
| **ВСЕГО** | **72** | |

---

## Рекомендуемый порядок выполнения

### Фаза 1: Критическая безопасность (CRITICAL)
1. §1.1 — Session token → cookie
2. §1.2 — Убрать plaintext token endpoint
3. §1.3 — Стандартная подпись сессий
4. §4.1 — Fix sync data loss
5. §7.1 — Fix Provider order

### Фаза 2: Базовая безопасность (HIGH security)
6. §1.4 — Auth на все endpoints
7. §1.5 — CSRF protection
8. §1.6 — Rate limit auth endpoints
9. §1.7 — SECRET_KEY validation

### Фаза 3: Backend архитектура (HIGH)
10. §2.1 — Убрать create_all
11. §3.1 — Индексы БД
12. §3.2 — UniqueConstraint
13. §3.3 — Timezone fix
14. §4.2 — N+1 fix
15. §5.1 — Max retry 429
16. §5.2 — Atomic rate limiter

### Фаза 4: Frontend архитектура (HIGH)
17. §7.2 — Production API URL
18. §7.3 — 404 route
19. §8.1–8.2 — Error handling
20. §9.1 — Error states
21. §9.2 — RevenueChart fix

### Фаза 5: Качество кода (HIGH)
22. §18.1 — ESLint
23. §18.2 — Ruff
24. §6.1–6.3 — Backend tests
25. §13.1 — Frontend tests
26. §14.1 — Docker production

### Фаза 6: Улучшения (MEDIUM)
27. Все MEDIUM задачи

### Фаза 7: Полировка (LOW)
28. Все LOW задачи
