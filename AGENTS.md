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

## База данных (7 таблиц)

| Таблица | Назначение |
|---|---|
| `users` | Авторы/владельцы, зашифрованные токены (Fernet) |
| `courses` | Курсы автора (без health_score — удалён миграцией 010) |
| `student_enrollments` | Прогресс студентов, когортный статус |
| `submissions` | Отправки решений по шагам (correct/wrong), `is_author` |
| `financial_snapshots` | Снапшоты финансовой сводки + community (отзывы, рейтинг, комментарии по месяцам) |
| `student_marts` | Витрина студентов: одна строка на студента (имя, статус, курсы, сертификаты, решения, комментарии, активность). Пересобирается в конце синка |
| `raw_sync_state` | Состояние инкрементальной загрузки (`endpoint_name`, `key`, `value`) — step_id → last_page для submissions, last_time_course_X для comments |

PK — UUID (кроме `raw_sync_state`: PK `(endpoint_name, key)`). Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`.

Плюс служебные таблицы raw-слоя (`raw_*`, 24 шт.), реестр `meta_endpoint` и `meta_field_mapping` (создаются скриптами/mиграцией `20fc60296db6`).

## Синхронизация (пайплайн API → raw → app)

Все синхронизации идут через два слоя:

### Raw-слой (`app/services/raw_sync.py`)
- `sync_courses_structure()` — курсы + sections/units/lessons/steps
- `sync_course_grades_and_certs()` — оценки + сертификаты
- `sync_submissions()` — отправки + попытки (инкрементально)
- **`/submissions?step=` НЕ возвращает поле `step` в объектах** — шаг известен только из контекста запроса; `sync_submissions()` пишет его в колонку `raw_submission.step` (миграция 015, loader-injected, без маппинга), `transform_submissions()` как fallback определяет шаг через `raw_attempt.step` по `submission.attempt`
- `sync_financials()` — финансы (course-benefit-by-months + course-benefits)
- `sync_community()` — рейтинги + комментарии
- `sync_users()` — анкеты (`/users?ids[]=`, батчи по 100) в raw_user; ID из `student_enrollments.student_id` + `submissions.user_id` + raw_course_grade/raw_certificate/raw_course_review (`USER_ID_SOURCES`); не-цифровые ID фильтруются (raw_comment.user хранит имя OAuth-клиента, не user id)
- Использует `_request()` из `stepik_api.py`, пишет в `raw_*` таблицы
- `_replace_raw_table()` (TRUNCATE + INSERT) для full_reload
- `_upsert_raw_table()` (INSERT ON CONFLICT) для incremental
- `_sync_id_sequence()` — после INSERT с явными id подтягивает serial-последовательность (PG; SQLite — no-op). Иначе следующий upsert-insert получит nextval из «прошлой жизни» и упадёт на pkey (регрессия `raw_comment_pkey`)
- `sync_submissions()` скипает шаги с HTTP 404 (удалённые на Stepik) — не убивает весь sync
- Все параметры для TEXT-колонок raw-слоя биндятся как `str()` (asyncpg строгая типизация: int в text-колонку → DataError)
- Работает с маппингом полей из `meta_field_mapping` (API → raw columns)

### Transform-слой (`app/services/transform.py`)
- `transform_courses()` — raw_course → courses (upsert + delete orphaned)
- `transform_enrollments()` — raw_course_grade + raw_certificate → student_enrollments
- `transform_submissions()` — raw_submission + raw_attempt → submissions (upsert)
- `transform_financials()` — raw_course_benefit_by_month + raw_course_benefit → financial_snapshots
  - Снапшот: `summary`, `months`, `courses`, `promos`, `utms` (агрегат по UTM-метке: payments/turnover/income/refunds/last_used), `recent_payments` (все платежи, без лимита), `community`
  - `recent_payments[i]`: id, course, amount, payment_amount, status, time, buyer, student (имя из raw_user по buyer), promo_code, currency, channel («А-ссылка»/«Stepik»/«По счету» из is_z_link_used/is_invoice_payment), is_gift, utm_source, utm_source_label, raw (полный объект API)
  - Возвраты в агрегациях (courses/promos/utms) хранятся положительными (`abs(amount)`)
- `transform_community()` — raw_course_review_summary + raw_comment → financial_snapshots community data
- `transform_students()` — student_enrollments + submissions + raw_comment + raw_user → student_marts (полная пересборка в конце синка)
- Использует сырой SQL (`text()`), UUID-параметры конвертируются в `str()` для SQLite-совместимости
- Для SQLite-совместимости JSON-обращения используют `json_extract(_raw_json, '$.field')` вместо PG `->>`

### Оркестратор (`app/services/sync.py`)
- `sync_all_sync()` — вызывает raw_sync.* → transform.* последовательно, обновляя прогресс (0% → 100%)
- Этапы: courses/enrollments (40%), submissions (85%), financials (95%), community (100%)
- Хранит `SYNC_COOLDOWN_SECONDS=60`, `can_sync()` проверяет соoldown
- Когортная сегментация и названия месяцев — единый источник `app/constants.py` + `transform.calculate_cohort_status`

### Статус синка (`GET /api/sync/status`)

- Поля: `in_progress`, `progress`, `step`, `last_sync`, `last_error`, `cooldown_remaining_seconds`
- `last_error` — текст ошибки последнего упавшего sync (`sync._last_sync_error`), `null` при успехе; сбрасывается при старте нового sync
- `last_sync` — `financial_snapshots.updated_at`; колонка в PG — `timestamp without time zone`, значение UTC (naive) — **при сериализации обязательно `+00:00`** (иначе фронтенд трактует строку как локальное время — регрессия «дата в тултипе не в локальном TZ»)
- Фронтенд-кнопка синка: синяя «вода» прогресса во время sync, розовая заливка на всю высоту при `last_error`, тултип — дата последней синхронизации (idle) / ошибка / прогресс

## Фильтр по курсам (глобальный)

Кнопка **«Фильтр»** в сайдбаре над «Обновить» (иконка-воронка, акцент `text-cyber-blue` при активном фильтре) открывает дропдаун со списком всех курсов автора — общая галка «Выбрать все курсы» (indeterminate при частичном выборе), чекбоксы курсов, счётчик «Выбрано: N из M» (надпись «Курсы» выровнена по названиям курсов). Меню закреплено у нижнего края экрана (fixed, `bottom-3`, правее сайдбара), закрывается повторным кликом на кнопку / Escape / кликом снаружи. Все 6 страниц показывают данные только по выбранным курсам.

### Семантика (фронтенд)

- Состояние живёт в `SyncContext`: `selectedCourseIds` (`null` = все курсы, `[]` = ничего не выбрано), `toggleCourse`, `selectAllCourses` (→ `null`), `selectNoneCourses` (→ `[]`), `isFilterActive`. Без localStorage — после перезагрузки фильтр сбрасывается на «все».
- Пустой выбор (`[]`) — реальное состояние «ничего не выбрано»: пустой дашборд (нули/пустые срезы), все чекбоксы сняты. Отличается от «без фильтра» (`null`).
- `fetchAll` при подмножестве добавляет `?course_ids=u1,u2` (comma-joined, один параметр) ко **всем** дашборд-эндпоинтам, кроме `GET /courses` — он всегда полный (это источник списка для дропдауна; на странице Курсов таблица фильтруется клиентом по `selectedCourseIds`). При `[]` шлётся пустой `?course_ids=` (пустой выбор), при `null` — без параметра.
- `Solutions` hardest-вкладка передаёт `course_ids` в `/dashboard/hardest-steps`; перезапрашивается при смене фильтра.
- Страницы Курсов/Решений/Студентов/Финансов/Дашборда читают `data` из контекста — после перезапроса с параметром все числа уже отфильтрованы.

### Бэкенд (`?course_ids=u1,u2`)

- Парсинг: `parse_course_ids()` в `app/api/dashboard/course_filter.py` (comma-joined, мусор отбрасывается): параметр отсутствует → `None` = без фильтра; пустая строка/только мусор → `[]` = пустой выбор. Все эндпоинты ветвятся по `parsed is None`, а не по falsy.
- `get_courses_for_user(db, user, course_ids)` — пересекает запрошенные UUID с курсами пользователя: чужие курсы увидеть нельзя (безопасность); `[]` → ноль курсов.
- SQL-эндпоинты — `course_id IN (...)` в WHERE: `/dashboard/submissions`, `/active-students`, `/active-enrolled-students`, `/cohorts`, `/alerts`, `/hardest-steps`, KPI-части (студенты/сертификаты/решения), `/dashboard/students` — через `EXISTS (SELECT 1 FROM student_enrollments ...)` (у витрины нет course-колонки).
- Снапшот-данные пересчитываются на лету (`course_filter.py`), т.к. `months`/`summary`/`comments_monthly` глобальны:
  - `filter_financials()` — из `recent_payments[i].raw` (у каждого платежа есть course + time): `summary`/`months`/`courses`/`promos`/`utms`/`recent_payments`. Месяц — из `time` платежа; возвраты вычитаются из turnover (как в `transform_financials`), поэтому отфильтрованный «все курсы» == глобальный снапшот (инвариант проверен тестом).
  - `filter_community()` — рейтинг/отзывы/комментарии из `community.per_course` + помесячные `comments_monthly`/`solutions_monthly` пересобираются из `raw_comment` через step→course map (`raw_step JOIN raw_unit JOIN raw_section`).
  - `filter_steps_average_grade()` — средняя оценка шагов по выбранным курсам (raw_step + step→course map).
- Без параметра — быстрый путь без изменений (значения снапшота как есть).

### Порядок этапов

```
sync_all:
  1. sync_courses_and_enrollments  (0→40%)
     - raw_sync.sync_courses_structure + sync_course_grades_and_certs
     - transform.transform_courses + transform_enrollments
     - raw_sync.sync_users (анкеты студентов — после свежих зачислений)
  2. sync_submissions (40→85%)
     - raw_sync.sync_submissions
     - transform.transform_submissions
  3. sync_financials (85→95%)
     - raw_sync.sync_financials
     - transform.transform_financials
  4. sync_community_stats (95→100%)
     - raw_sync.sync_community
     - transform.transform_community
     - transform.transform_students (витрина студентов — все входные данные свежие)
```

### Инкрементальная загрузка submissions

- Таблица `raw_sync_state`: `(endpoint_name='submissions', key='step_{id}')` → `value` = последняя загруженная страница
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

**Никаких loading-заглушек:** страницы всегда рендерят реальные элементы (KPI-карточки, графики, вкладки, таблицы) с пустыми/нулевыми данными по умолчанию — данные подгружаются в уже существующие элементы. Скелетоны, «Загрузка...», подменяющие плейсхолдеры запрещены (дёрганье экрана).

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

Градиент рейтинга (средний рейтинг курсов / средняя оценка шагов):
| Диапазон | RGB |
|----------|-----|
| 1.0 | `rgb(255,0,0)` |
| 2.0 | `rgb(255,120,0)` |
| 3.0 | `rgb(255,210,0)` |
| 4.0 | `rgb(160,230,0)` |
| 4.5 | `rgb(0,180,0)` |
| 4.9+ | `rgb(0,255,0)` |

Дашборд — 2 ряда по 6 KPI-карточек:
- **Ряд 1:** Доход /месяц (trend), Покупки /месяц (trend), Курсы, Студенты, Средняя оценка шагов (градиент), Средний рейтинг курсов (градиент)
- **Ряд 2:** Возвраты (₽) /месяц (trend), Возвраты (шт) /месяц (trend), Сертификаты, Публичные решения, Комментарии, Отзывы

KPI-карточки с трендом показывают `↑ N%` или `↓ N%` справа от заголовка (зелёный/красный). Возвраты — `trendInverted` (рост возвратов = красный).

Y-ось графиков:
- SubmissionsChart: `0, 0.5k, 1.0k, 1.5k, 2.0k` — `toFixed(1)` + `k`
- RevenueChart: `0, 2k, 4k, 6k` — `value/1000` + `.0` cleanup

График «Отправленные решения» (`SubmissionsChart`, дашборд + страница Активности) — 3 категории: **Правильные** (яркий синий `#38bdf8`, низ стека) → **Опубликованные** (светлый синий `#7dd3fc`, над Правильными) → **Не завершён** (тёмный `#1a6a9e`, верх). Опубликованные = `community.solutions_monthly` (комментарии к сабмишн-тредам), **всегда часть Правильных**: `published = min(published, correct)`, сегмент правильных уменьшается на `published` (высота стека = total). Данные мержатся по метке месяца в `SyncContext` (`mergePublishedIntoSubmissions()` из `utils/mergePublished.js`: `published-solutions` → `submissions.months[*].published`, 0 по умолчанию) — обе страницы используют один и тот же объект. Тултип показывает `correctTotal`/`publishedTotal` (полные значения). Серия рисуется только если в данных есть ключ `published` (график «Комментарии» не затрагивается).

График «Выданные сертификаты» (страница Активности, `ActiveStudentsChart`) — сертификаты по месяцам выдачи, 2 категории: **С отличием** (яркий пурпур `#c084fc`, верх стека) и **Обычные** (тёмный `#581c87`, низ). Источник: `GET /api/dashboard/certificates` (в `app/api/dashboard/charts.py`) — читает `raw_certificate._raw_json`, группирует по `issue_date[:7]`, `type == 'distinction'` → «С отличием». Ответ `{months: [{month, dark, light}]}`: `dark` = всего, `light` = обычные — сегмент «С отличием» = `overlap = dark − light` (компонент рисует light снизу, overlap сверху). Фильтр курсов: `WHERE course_id IN (...)` по stepik-курсам. Легенда/тултип через пропы `lightLabel`/`darkLabel`; тултип верхнего сегмента показывает `overlap` при `darkTooltipOverlap` (`darkTooltipValue()`), т.к. `dark` = всего, а не «С отличием».

Графики используют `CHART_COLORS` из `frontend/src/constants.js`.

## Страница «Решения» (4 вкладки)

- Вкладки: **По месяцам / По годам / По курсам / Самые сложные** (`frontend/src/pages/Solutions.jsx`)
- Таблицы: колонки `Группа | Студенты | Всего | Правильно | Неверно | Успех (цвет)` + `Шаг | Взв. успех (цвет)` у hardest
- **«Шаг» = путь `модуль.урок-шаг`** (например `3.7-2`): модуль из `raw_section.position`, урок — **сквозной номер в курсе** (сумма уроков предыдущих модулей + позиция внутри своего модуля из `raw_unit.position`), шаг — позиция в `raw_lesson.steps`. Если данных структуры нет — fallback на `stepik_step_id`. Внутри — ссылка на Stepik (`lesson_id`/`step_number`), в tooltip — **название модуля — название урока** (`raw_section.title`/`raw_lesson.title`, fallback: курс и числовой ID шага)
- **`students`** — уникальные студенты в группировке = `COUNT(DISTINCT submissions.user_id)` (NULL игнорируются, `is_author=False`)
- **«Успех» = Wilson-нижняя граница 95% доверительного интервала** (`wilson_success_pct()` в `app/api/dashboard/common.py`), а не `correct/total`: чем меньше попыток, тем сильнее число занижается (данным нельзя верить); чем больше попыток, тем ближе к наблюдённому. 1 верная из 5 (20%) → 3.6%; 200 из 1000 (20%) → 17.6%. API отдаёт `success_pct` для всех группировок (months/years/by_course/steps); фронт использует его с fallback на raw-расчёт
- **«Взв. успех» = наблюдённый процент, притянутый к среднему по шагам** (`weighted_success_pct()` в `app/api/dashboard/common.py`): `(correct + 20 × global_pct) / (total + 20) × 100`, где `global_pct` — **unweighted mean** успеха по строкам группировки (не по попыткам — иначе доминирующий шаг сдвигает среднее). Мало попыток → цифра ≈ среднего, не лезет в топ; много попыток → честный `correct/total`. Колонка показывается **только на вкладке «Самые сложные»** (там она осмысленна — малые выборки шагов); API отдаёт `weighted_success_pct` для всех группировок
- Источники: `GET /dashboard/submissions` → `{months, by_course, years}` (в `app/api/dashboard/charts.py`); `GET /dashboard/hardest-steps` → `{steps}` (в `app/api/dashboard/steps.py`). Годы считают `students` **отдельным запросом** (не суммой по месяцам — один студент в нескольких месяцах одного года посчитался бы дважды). hardest сортирует по `weighted_success_pct` в Python (не в SQL) — мусор с 1-2 попытками не всплывает наверх
- Сортировка: первый клик — «естественный порядок» (числа/даты — больше/новые сверху, текст — А→Я), стрелка указывает **на главные значения** (`┴`/`↑` по типу в `NATURAL_DIR_BY_KEY`); повторный клик — наоборот
- Верхние KPI-плашки: Всего решений / Правильных / Неправильных (белые) + Успех (цвет как в колонке: `successColor` <33 красный, <66 жёлтый, ≥66 зелёный)

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
| `incremental_page` | Догрузка по `last_page` (raw_sync_state) | submissions, attempts |
| `incremental_time` | Догрузка по дате (фильтр на клиенте) | comments |

Скрипт: `backend/scripts/sync_raw.py`:
```
python scripts/sync_raw.py              # все активные
python scripts/sync_raw.py submissions  # конкретный
```

Скрипт пересборки витрин из raw-слоя (без API-запросов): `backend/scripts/rebuild_marts.py`:
```
python scripts/rebuild_marts.py
```
Порядок как в `sync_all`: courses → enrollments → submissions → financials → community → students. Abort, если `raw_course` пуст.

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
| raw_submission | 81351 | 7 | ✓ | incremental_page |
| raw_attempt | 54663 | 6 | ✓ | incremental_page |
| raw_comment | 1560 | 22 | ✓ | incremental_time |
| raw_course_grade | 814 | 14 | ✓ | full_reload |
| raw_certificate | 187 | 20 | ✓ | full_reload |
| raw_course_benefit_by_month | 18 | 15 | ✓ | full_reload |
| raw_course_benefit | 733 | 18 | ✓ | full_reload |
| raw_course_review_summary | 7 | 5 | ✓ | full_reload |
| raw_course_review | 20 | 16 | ✓ | full_reload |
| raw_enrollment | — | — | пусто | — |
| raw_progress | 659 | 9 | ✓ | full_reload |
| raw_user | 7603 | 28 | ✓ | full_reload |
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
- users ← __multi__ (student_enrollments + submissions + raw-таблицы)
- profiles ← raw_user.profile

**COURSE_ENDPOINTS:** course_grades, certificates, comments, course_reviews, enrollments, course_period_statistics, course_total_statistics, course_ranks

**Работа с эндпоинтами (порядок):**
1. Показать пользователю поля (`docs/fields_*.md`), получить отметку Sync
2. `explore_endpoint.py --create-table --load` — создаёт таблицу, грузит данные
3. `rebuild_raw.py` — применяет sync-отметки, убирает неотмеченные колонки
4. Для `?ids[]=` эндпоинтов — сначала добавить источник в `IDS_SOURCE_MAP`

## Документация

- `docs/api_propose.md` — предложенные эндпоинты Stepik API
- `docs/fields_*.md` — описания полей эндпоинтов
- `docs/` — прочие рабочие заметки

## Константы

Единый источник `app/constants.py`: `MONTH_NAMES` (1–12), когортные пороги
(`COHORT_ACTIVE_DAYS=7`, `COHORT_PASSIVE_DAYS=30`, `COHORT_FADING_DAYS=90`,
`ZOMBIE_DAYS_AFTER_JOIN=3`), `UTM_SOURCE_LABELS` (метки источников для колонки UTM:
`yandex_stpk`/`ya_stpk` → «Я.Директ», email-источники → «E-mail», `stepik_telegram` → «Telegram»,
`stepik_vk_smm` → «VK», `notification` → «Уведомления»; неизвестные — как есть).
Когортная сегментация — `transform.calculate_cohort_status()`.
URL-ы Stepik: `STEPIK_API_BASE` и `STEPIK_OAUTH_TOKEN_URL` в `app/services/stepik_api.py`.

## Тесты

396 тестов, 0 skipped, 0 failures (`pytest -v`, требует запущенный docker-compose для live-PG).

| Файл | Тестов | Что тестирует |
|---|---|---|
| `tests/test_stepik_api.py` | 20 | `_request`, `exchange_code`, `refresh_token`, `get_user_profile` |
| `tests/test_stepik_api_comprehensive.py` | 14 | `get_finance_token`, 5xx retries, constants |
| `tests/test_raw_sync.py` | 15 | `sync_courses_structure`, `sync_grades_and_certs`, `sync_submissions` (+404-шаги, конфликтные upsert'ы, str-bind для TEXT-колонок), `sync_financials`, `sync_community`, регрессии `became_published_at` и stale sequence |
| `tests/test_raw_sync_edge_cases.py` | 12 | `_paginated_fetch`, пустые/ошибочные данные transform и raw_sync |
| `tests/test_transform.py` | 17 | `transform_courses/enrollments/submissions/financials/community` (+ utms, channel/gift, student name, recent_payments без лимита) |
| `tests/test_sync_integration.py` | 18 | `sync_all`, cohort status, интеграция raw_sync → transform, stepwise-коммиты raw_sync внутри sync-этапов |
| `tests/test_sync_comprehensive.py` | 21 | `sync_all`, `sync_community_stats`, `sync_financials` |
| `tests/test_sync_edge_cases.py` | 24 | Разрешение конфликтов, отсутствие данных, ошибки API, регрессии `_last_sync_error` (падение → error виден в статусе, успех → очищен) |
| `tests/test_data_contract.py` | 5 | Глобальные контракты снапшота/API/фронта (price, per_course, поля страниц, recent_payments/utms) |
| `tests/test_schema_contract.py` | 9 | Schema-contract: статический скан SQL трансформов, TEXT-типизация raw-слоя, live-PG parity (raw-схема, meta_field_mapping, покрытие mapping'ом читаемых колонок, полный пайплайн, снапшот), **live-PG свежесть данных** (трансформы на реальных данных производят строки и догоняют raw — регрессия «0 submissions upserted») |
| `tests/test_architecture.py` | 19 | Архитектурные гарантии: один alembic head, нет dead-артефактов (step_sync_state, orphan-скрипты), единый источник констант, дефолты конфига = docker-compose, сплит dashboard-пакета, rebuild_marts.py (все трансформы, без API) |
| `tests/test_steps.py` | 35 | hardest-steps: `_parse_step_positions` (jsonb/list vs TEXT-строка), lesson_id/step_number, сортировка, min_submissions, limit, чужие курсы, `students` (COUNT DISTINCT user_id), `wilson_success_pct` (объём попыток: 1/5 → 3.6%, 200/1000 → 17.6%), `weighted_success_pct` (мусор с малым числом попыток не всплывает в топ), `module_number`/`lesson_number` (сквозная нумерация уроков по курсу), `module_title`/`lesson_title` |
| `tests/test_course_filter.py` | 18 | Фильтр по курсам: `parse_course_ids` (None/`[]`), безопасность (чужие UUID отбрасываются), SQL-эндпоинты (submissions/active-students/cohorts/alerts/hardest-steps/students), пересчёт снапшота (financials/revenue/kpi/published-solutions/community), инвариант «фильтр = все курсы» == «без фильтра», пустой `?course_ids=` = пустой выбор |
| Остальные | 169 | API endpoints, dashboard, financials, crypto, rate limiter, ... |

Live-PG тесты: изменения в БД — **только через явный `await trans.rollback()`**, не `async with session.begin():` + rollback снаружи (begin()-контекст коммитит на выходе, rollback после него — no-op).

Schema-contract тесты (`test_schema_contract.py`) — глобальная защита от дрейфа схемы:
- Статический парсинг всех `text(...)` SQL-блоков в `transform.py`/`raw_sync.py`: каждая `table.column` обязана существовать в фикстуре `RAW_TABLES` и моделях
- Все raw-колонки, читаемые трансформациями, обязаны быть TEXT в фикстуре (реальная PG хранит raw-слой как TEXT)
- Live PG (skip без `DATABASE_URL` в `.env`): колонки, потребляемые трансформациями, существуют в PG и имеют тип text/jsonb; каждый `meta_field_mapping.db_column` активных эндпоинтов существует в PG; **каждая читаемая трансформациями колонка покрыта is_loaded-строкой mapping'а** (иначе loader молча оставляет NULL — регрессия `became_published_at`); полный пайплайн `transform_*` отрабатывает в транзакции (rollback) без ошибок; снапшот финансов содержит `courses` (с `price`) и `community.per_course`
