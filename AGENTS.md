# AGENTS.md

## Проект

Stepik Control Panel — CRM/BI-панель для авторов курсов на Stepik. Приложение **только для чтения**: все данные берутся из Stepik API, прямая модификация данных на платформе исключена.

## Zero-Write Policy (КРИТИЧЕСКИЙ ПРИОРИТЕТ)

- **Только HTTP GET** к Stepik API. POST, PUT, PATCH, DELETE категорически запрещены.
- OAuth2 токены запрашивать строго с правами `read`. Права `write` запрашивать запрещено.
- Все интерактивные действия (баны, ответы, редактирование дедлайнов, промокоды) — через **Deep Links** на оригинальный интерфейс Stepik (`target="_blank"`).
- Приложение диагностирует проблему, но отправляет пользователя решать её на stepik.org.

## Технологии

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic, APScheduler
- **Frontend:** React 18+, Vite, Tailwind CSS v3, Recharts
- **БД:** PostgreSQL 16, Redis 7
- **Шрифты:** Inter (текст), JetBrains Mono (строго для числовых показателей, ID, финансов)

## Запуск

```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

Требуется `.env` из `.env.example` (OAuth2 Client ID/Secret, `ENCRYPTION_KEY`, данные БД).

Порты настраиваются в `.env`:
```
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

## Stepik API

- Базовый URL: `https://stepik.org/api/`
- Плоская схема: нет вложенных путей, фильтрация через query-параметры
- Пакетная загрузка: `?ids[]=1&ids[]=2` (side-loading)
- Используемые эндпоинты:
  - `GET /courses?teacher=` — курсы автора (`is_public` = опубликован, `is_published` не отдаётся)
  - `GET /course-grades?course=` — оценки студентов
  - `GET /certificates?course=` — сертификаты
  - `GET /submissions?step=` — отправки решений (по шагам, все студенты; поле `user` всегда None — норма API)
  - `GET /course-benefit-by-months` — финансовые данные
  - `GET /course-benefits` — детали по курсам
  - `GET /course-review-summaries?ids[]=` — рейтинги и отзывы (side-loading по ID из `courses.review_summary`)
  - `GET /comments?course=` — комментарии студентов (поле даты: `time`, не `update_date`)
  - `GET /course-reviews?course=` — тексты отзывов (score, text, reply_text, translations)

### Важные нюансы API

- `courses.review_summary` — это **int ID**, а не dict. Для получения `average`/`count` нужен отдельный запрос к `/course-review-summaries`
- `courses.is_published` всегда `None` — используй `courses.is_public` для определения статуса публикации
- Stepik API возвращает максимум 20 комментариев на страницу (игнорирует `page_size > 20`)
- **`page_size` игнорируется** на всех list-эндпоинтах — API всегда возвращает **20 записей** на страницу. `page_size` > 20 молча обрезается до 20. Не рассчитывай на 500/1000 записей в страницу
- Исключение: `course-benefit-by-months` — плоский ответ, **без пагинации**, page_size=0
- Значение `page_size` хранится в `meta_endpoint.page_size` (0 = нет пагинации)
- `GET /submissions?course=X` возвращает **только submissions текущего пользователя**. Для получения submissions всех студентов нужно использовать `GET /submissions?step=STEP_ID`
- `GET /submissions?step=` не поддерживает параметр `order` — всегда возвращает oldest first
- Мета-данные submissions (`meta.has_next`) не содержат `total` — нужно страница за страницей пока `has_next=true`
- `has_next` может возвращать `true` даже на страницах за пределами данных — **обязательно ставить `max_pages` лимит**

## OAuth2 (только read)

При обмене кода на токен **обязательно** передавать `scope=read`:

```bash
curl -X POST \
  -d "grant_type=client_credentials&scope=read" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  https://stepik.org/oauth2/token/
```

В коде это реализовано в `backend/app/services/stepik_api.py` → `exchange_code_for_token()`.

## Обработка Rate Limit

- Redis Token Bucket для rate limiting
- При 429: извлечь `Retry-After`, `await asyncio.sleep(retry_after)`, вернуть фронтенду `202 Accepted`
- Не прерывать сессию пользователя

## База данных (6 таблиц)

| Таблица | Назначение |
|---|---|
| `users` | Авторы/владельцы, зашифрованные токены (Fernet) |
| `courses` | Курсы, health_score |
| `student_enrollments` | Прогресс студентов, когортный статус |
| `submissions` | Отправки решений по шагам (correct/wrong), `is_author` |
| `financial_snapshots` | Снапшоты финансовой сводки + community (отзывы, рейтинг, комментарии по месяцам, `last_comment_time` для инкрементального sync) |
| `step_sync_state` | Состояние инкрементальной загрузки submissions (`step_id` → `last_page`) |

PK — UUID. Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`.

## Синхронизация (пайплайн API → raw → app)

Все синхронизации идут через два слоя:

### Raw-слой (`app/services/raw_sync.py`)
- `sync_courses_structure()` — курсы + sections/units/lessons/steps
- `sync_course_grades_and_certs()` — оценки + сертификаты
- `sync_submissions()` — отправки + попытки (инкрементально)
- `sync_financials()` — финансы (course-benefit-by-months + course-benefits)
- `sync_community()` — рейтинги + комментарии
- Использует `_request()` из `stepik_api.py`, пишет в `raw_*` таблицы
- `_replace_raw_table()` (TRUNCATE + INSERT) для full_reload
- `_upsert_raw_table()` (INSERT ON CONFLICT) для incremental
- Работает с маппингом полей из `meta_field_mapping` (API → raw columns)

### Transform-слой (`app/services/transform.py`)
- `transform_courses()` — raw_course → courses (upsert + delete orphaned)
- `transform_enrollments()` — raw_course_grade + raw_certificate → student_enrollments
- `transform_submissions()` — raw_submission + raw_attempt → submissions (upsert)
- `transform_financials()` — raw_course_benefit_by_month + raw_course_benefit → financial_snapshots
- `transform_community()` — raw_course_review_summary + raw_comment → financial_snapshots community data
- Использует сырой SQL (`text()`), UUID-параметры конвертируются в `str()` для SQLite-совместимости
- Для SQLite-совместимости JSON-обращения используют `json_extract(_raw_json, '$.field')` вместо PG `->>`

### Оркестратор (`app/services/sync.py`)
- `sync_all_sync()` — вызывает raw_sync.* → transform.* последовательно, обновляя прогресс (0% → 100%)
- Этапы: courses/enrollments (40%), submissions (85%), financials (95%), community (100%)
- Хранит `SYNC_COOLDOWN_SECONDS=300`, `can_sync()` проверяет соoldown
- Сохраняет `calculate_cohort_status()`, `MONTH_NAMES` для обратной совместимости импортов

### Порядок этапов

```
sync_all:
  1. sync_courses_and_enrollments  (0→40%)
     - raw_sync.sync_courses_structure + sync_course_grades_and_certs
     - transform.transform_courses + transform_enrollments
  2. sync_submissions (40→85%)
     - raw_sync.sync_submissions
     - transform.transform_submissions
  3. sync_financials (85→95%)
     - raw_sync.sync_financials
     - transform.transform_financials
  4. sync_community_stats (95→100%)
     - raw_sync.sync_community
     - transform.transform_community
```

### Инкрементальная загрузка submissions

- Таблица `step_sync_state`: `step_id` (PK) → `last_page` (номер последней загруженной страницы)
- При первом sync: загрузка с страницы 1 до `has_next=false`
- При повторном sync: загрузка с `last_page` (перезаписывается), продолжение до `has_next=false`
- **Важно:** `DELETE FROM courses` каскадно удаляет submissions (`ON DELETE CASCADE` в FK)
- Поэтому courses **не удаляются**, а обновляются IN PLACE по `stepik_course_id`
- Если курс удалён на Stepik — удаляется через `session.delete()` (каскад удалит его submissions)

### Запись данных — принцип

**Все данные пишутся в БД по мере поступления**, без промежуточного кэширования в памяти:
- Курсы — upsert сразу
- Enrollments — per-course (после скачивания оценок каждого курса)
- Submissions — per-page (после каждой страницы API)
- Финансы — один снапшот целиком (потому что это один JSON-объект)
- Рейтинги — одна запись после скачивания
- Комментарии — per-page (после каждой страницы API)

### SQLAlchemy JSONB — КРИТИЧЕСКАЯ ОШИБКА (in-place mutation)

При обновлении JSONB-колонки **нельзя** мутировать dict in-place и переприсваивать `snapshot.data`. SQLAlchemy сравнивает committed state (который уже мутирован in-place) с новым значением и считает их идентичными — **UPDATE не выполняется**.

**Неправильно** (данные не пишутся):
```python
community = snapshot.data.get("community", {})
community["total_comments"] = total  # ← мутирует committed state
community["comments_monthly"] = monthly
snapshot.data = {**snapshot.data, "community": community}  # ← SQLAlchemy видит то же самое
```

**Правильно** (создаётся новый dict):
```python
prev = snapshot.data.get("community", {})
snapshot.data = {**snapshot.data, "community": {
    **prev,  # ← копия, не ссылка
    "total_comments": total,
    "comments_monthly": monthly,
}}
```

Паттерн `{**prev, key: value}` создаёт новый dict — SQLAlchemy фиксирует разницу и выполняет UPDATE.

## Когортные пороги

| Сегмент | Дни с последней активности |
|---|---|
| Active | ≤ 7 |
| Passive | 8–30 |
| Fading | 30–90 |
| Sleeping | > 90 |
| Zombie | Sleeping + last_viewed в пределах 3 дней от date_joined |

## UI-тема

«Spaceship Control Panel» — тёмный фон, неоновые акценты, glassmorphism-карточки.

Цвета Tailwind:
- `space-black` `#0b0f19` — фон
- `space-gray` `#162032` — панели
- `cyber-blue` `#38bdf8` — базовые элементы / яркий синий на диаграмме
- `neon-green` `#4ade80` — растущие метрики / яркий зелёный на диаграмме
- `amber-alert` `#f59e0b` — предупреждения
- `crimson-alert` `#f43f5e` — критические алерты

Дополнительные цвета KPI-карточек:
- `dim-green` `#22763d` — тёмный зелёный
- `dim-blue` `#1a6a9e` — тёмный синий
- `dim-crimson` `#8b2040` — тёмный красный
- `white` / `text-gray-300` — приглушённый белый

Градиент рейтинга (средний рейтинг):
| Диапазон | RGB |
|----------|-----|
| 1.0 | `rgb(239,68,68)` |
| 2.0 | `rgb(249,115,22)` |
| 3.0 | `rgb(234,179,8)` |
| 4.0 | `rgb(132,204,22)` |
| 4.5 | `rgb(100,214,81)` |
| 4.9+ | `rgb(74,222,128)` |

Дашборд — 2 ряда по 6 KPI-карточек:
- **Ряд 1:** Доход /месяц (trend), Покупки /месяц (trend), Возвраты /месяц (trend), Курсы, Средний рейтинг (градиент), Сертификаты
- **Ряд 2:** Решения /месяц (trend), Студенты /месяц (trend), Комментарии /месяц (trend), Комментарии (всего), Отзывы, Комментарии

KPI-карточки с трендом показывают `↑ N%` или `↓ N%` справа от заголовка (зелёный/красный).

Y-ось графиков:
- SubmissionsChart: `0, 0.5k, 1.0k, 1.5k, 2.0k` — `toFixed(1)` + `k`
- RevenueChart: `0, 2k, 4k, 6k` — `value/1000` + `.0` cleanup

Графики используют `CHART_COLORS` из `frontend/src/constants.js`.

## Критерии приёмки

1. Нет ни одного POST/PUT/PATCH/DELETE к `stepik.org` в кодовой базе
2. Рендер дашборда < 2 сек на курсах до 100k студентов
3. Graceful обработка 429 (Retry-After → sleep → 202)
4. Нет захардкоженных секретов — всё из `.env`
5. Нет глобальных кэшей в памяти — данные пишутся в БД по мере поступления

## Правило: баг → тест

При обнаружении бага **сразу пиши регрессивный тест**, reproducing баг. Не откладывай. Тест должен:

1. Быть в `tests/` с префиксом `test_` в имени файла
2. Падать **до** фикса и проходить **после** фикса
3. Покрывать конкретный сценарий бага (не общий)

Формулировка в docstring/комментарии: `"Regression: <описание бага>"`.

## Raw Layer — Состояние

Всего 24 raw-таблицы. Эндпоинты без данных деактивированы (is_active=False).
`page_size`: 20 для list-эндпоинтов, 0 для `course_benefit_by_months` (без пагинации).

### Стратегии обновления (meta_endpoint.incremental)

| Стратегия | Описание | Эндпоинты |
|---|---|---|
| `full_reload` | TRUNCATE + перезагрузка всех страниц | 21 эндпоинт (courses, sections, users, ...) |
| `incremental_page` | Догрузка по `last_page` (step_sync_state) | submissions, attempts |
| `incremental_time` | Догрузка по дате (фильтр на клиенте) | comments |

Скрипт: `backend/scripts/sync_raw.py`:
```
python scripts/sync_raw.py              # все активные
python scripts/sync_raw.py submissions  # конкретный
```

Особенности:
- `full_reload` с `?ids[]=` — батчи по 100 ID, без ID пробует bare endpoint
- `full_reload` с `?course=X` — итерирует по всем курсам, страницы
- `full_reload` bare — до 20 страниц (макс ~400 записей)
- `client_credentials` — финансовые эндпоинты (course_benefits, course_benefit_by_months)

| Таблица | Строки | Колонки | Sync | Стратегия |
|---|---|---|---|---|
| raw_course | 7 | 90 | ✓ | full_reload |
| raw_section | 38 | 19 | ✓ | full_reload |
| raw_unit | 114 | 12 | ✓ | full_reload |
| raw_lesson | 114 | 26 | ✓ | full_reload |
| raw_step | 659 | 23 | ✓ | full_reload |
| raw_submission | 24272 | 6 | ✓ | incremental_page |
| raw_attempt | 38223 | 6 | ✓ | incremental_page |
| raw_comment | 1560 | 22 | ✓ | incremental_time |
| raw_course_grade | 814 | 14 | ✓ | full_reload |
| raw_certificate | 187 | 20 | ✓ | full_reload |
| raw_course_benefit_by_month | 18 | 15 | ✓ | full_reload |
| raw_course_benefit | 733 | 18 | ✓ | full_reload |
| raw_course_review_summary | 7 | 5 | ✓ | full_reload |
| raw_course_review | 20 | 16 | ✓ | full_reload |
| raw_enrollment | — | — | пусто | — |
| raw_progress | 659 | 9 | ✓ | full_reload |
| raw_user | 742 | 25 | ✓ | full_reload |
| raw_achievement | 62 | 5 | ✓ | full_reload |
| raw_achievement_progress | 100 | 10 | ✓ | full_reload |
| raw_author_list | 1 | 7 | ✓ | full_reload |
| raw_course_list | 100 | 12 | ✓ | full_reload |
| raw_course_rank | 2 | 8 | ✓ | full_reload |
| raw_course_recommendation | 1 | 3 | ✓ | full_reload |
| raw_social_profile | 88 | 5 | ✓ | full_reload |
| raw_user_review_summary | 100 | 5 | ✓ | full_reload |

**ID resolution (`IDS_SOURCE_MAP`):**
- sections ← raw_course.section_ids
- units ← raw_section.units
- lessons ← raw_unit.lesson_id
- steps ← raw_lesson.steps
- course_review_summaries ← raw_course.review_summary_json
- progresses ← raw_step.progress
- users ← __multi__ (4 raw-таблицы)
- profiles ← raw_user.profile

**COURSE_ENDPOINTS:** course_grades, certificates, comments, course_reviews, enrollments, course_period_statistics, course_total_statistics, course_ranks

**Работа с эндпоинтами (порядок):**
1. Показать пользователю поля (`docs/fields_*.md`), получить отметку Sync
2. `explore_endpoint.py --create-table --load` — создаёт таблицу, грузит данные
3. `rebuild_raw.py` — применяет sync-отметки, убирает неотмеченные колонки
4. Для `?ids[]=` эндпоинтов — сначала добавить источник в `IDS_SOURCE_MAP`

## Документация

- `docs/brd.md` — бизнес-требования, модули, бизнес-правила
- `docs/api.md` — справочник по Stepik API

## Тесты

250 тестов, 0 skipped, 0 failures (`pytest -v`).

| Файл | Тестов | Что тестирует |
|---|---|---|
| `tests/test_stepik_api.py` | 19 | `_request`, `exchange_code`, `refresh_token`, `get_user_profile` |
| `tests/test_stepik_api_comprehensive.py` | 15 | `get_finance_token`, 5xx retries, constants |
| `tests/test_raw_sync.py` | 7 | `sync_courses_structure`, `sync_grades_and_certs`, `sync_submissions`, `sync_financials`, `sync_community` |
| `tests/test_raw_sync_edge_cases.py` | 12 | `_paginated_fetch`, пустые/ошибочные данные transform и raw_sync |
| `tests/test_transform.py` | 11 | `transform_courses/enrollments/submissions/financials/community` |
| `tests/test_sync_integration.py` | 54 | `sync_all`, cohort status, интеграция raw_sync → transform |
| `tests/test_sync_comprehensive.py` | 21 | `sync_all`, `sync_community_stats`, `sync_financials` |
| `tests/test_sync_edge_cases.py` | 18 | Разрешение конфликтов, отсутствие данных, ошибки API |
| Остальные | 93 | API endpoints, dashboard, financials, crypto, rate limiter, ... |
