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
- **`page_size` игнорируется** на многих эндпоинтах (`course-grades`, и др.) — API всегда возвращает **20 записей** на страницу вне зависимости от `page_size`. Не рассчитывай на 500/1000 записей в страницу
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

## Синхронизация

**Синхронизация выполняется только пользователем — по кнопке в UI. Агент НЕ имеет возможности запускать синхронизацию самостоятельно.**

### Порядок этапов

```
sync_all:
  1. sync_courses_and_enrollments  (0→40%)
     - GET /courses — список курсов автора
     - Курсы пишутся в БД сразу (upsert по stepik_course_id, IN PLACE)
     - Для каждого курса:
       - GET /course-grades?course=X — студенты (20 записей/страница)
       - GET /certificates?course=X — сертификаты
       - DELETE старых enrollments + INSERT новых для этого курса
  2. sync_submissions (40→85%)
     - GET /steps — все шаги всех курсов
     - Фильтрация: только code/choice/external-grader шаги (~57% от всех)
     - GET /submissions?step=STEP_ID — все submissions по шагу
     - Инкрементальная загрузка через step_sync_state (last_page)
     - Upsert по stepik_submission_id (ON CONFLICT DO UPDATE)
     - Пометка is_author=True для submission IDs из GET /submissions?course=X
  3. sync_financials (85→95%)
     - GET /course-benefit-by-months — сводка по месяцам
     - GET /course-benefits — все платежи (содержат promo_code)
     - Агрегация промокодов из всех платежей
     - Создание/пересоздание FinancialSnapshot (DELETE + INSERT)
  4. sync_community_stats (95→100%)
     - GET /course-review-summaries — рейтинги → запись в snapshot
     - Комментарии — **инкрементально**: читает `last_comment_time` из snapshot, считает только новые, прибавляет к totals
     - Для каждого курса: GET /comments?course=X → страница за страницей (API отдаёт oldest first)
     - Запись в snapshot после подсчёта всех курсов
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

## Документация

- `docs/brd.md` — бизнес-требования, модули, бизнес-правила
- `docs/api.md` — справочник по Stepik API
