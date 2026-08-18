# AGENTS.md

> ## ⚠️ ВАЖНО, ПРОЧИТАЙ ПЕРВЫМ
>
> **Пользователь этого проекта — НЕ программист.** Он понимает общие термины (таблицы, данные, запросы к API и т.п.), но **не писал этот код**.
>
> **ПРАВИЛО:** объясняй всё **на человеческом языке** — простыми словами, коротко. Говори о данных и о том, что они означают, а не о внутренностях кода. **Не называй имена функций, переменных и файлов, которые пользователь не писал** (например `sync_submissions()`, `transform.py`, `_is_text_step()`). Если имя функции нужно — объясни его одной простой фразой: «функция, которая качает решения».
>
> Не вываливай на пользователя кучи технической информации за раз: **одна вещь за шаг**, дожидайся реакции.
>
> Пользователь раздражается, когда с ним говорят как с ребёнком ИЛИ как с программистом. Будь ровным, уважительным, конкретным и простым.

## Проект

Stepik Control Panel — CRM/BI-панель для авторов курсов на Stepik. Приложение **только для чтения**: все данные берутся из Stepik API, прямая модификация данных на платформе исключена.

## Архитектура: два слоя данных (КРИТИЧЕСКИЙ ПРИОРИТЕТ)

В проекте **строго два слоя данных**. Это архитектурный инвариант, нарушение = баг.

```
Stepik API ──► СЛОЙ СЫРЫХ ДАННЫХ ──► СЛОЙ ВИТРИН ──► API ──► Фронтенд
               (24 таблицы raw_*)      (витрины)     (чтение ТОЛЬКО витрин)
```

1. **Слой сырых данных** — таблицы `raw_*` (raw_course, raw_comment, raw_certificate, raw_course_review, raw_step, raw_lesson, raw_unit, raw_section, raw_user, ...). Получаются из Stepik API через `raw_sync.py`/`sync_raw.py` и пишутся как есть (JSON в `_raw_json`).
2. **Слой витрин** — производные таблицы, которые пересобираются из raw-слоя **трансформами** (`transform.py`) в конце синка:
   - `courses`, `student_enrollments`, `submissions` — «низкие» витрины (детальные строки),
   - `financial_snapshots` — JSON-снапшот финансов + community,
   - `student_marts` — витрина студентов,
   - `mart_modules`, `mart_lessons`, `mart_steps`, `mart_comments`, `mart_certificates`, `mart_reviews` — «высокие» витрины структуры/комментариев/сертификатов/отзывов: атрибуция шага к курсу/модулю/уроку, сквозная нумерация уроков, метрики шага (`viewed_by`/`passed_by`/`correct_ratio`/`grade`), лайки/дизлайки комментариев и пути шагов пресчитаны на этапе трансформа (миграция `017`, модели в `app/models/mart.py`).

**Жёсткие правила:**
- **API-слой читает ТОЛЬКО витрины.** Ни один эндпоинт в `app/api/` не должен делать `SELECT` из `raw_*` таблиц. Это защищено тестами (`test_architecture.py`, `test_schema_contract.py`).
- **В витрины данные попадают только из raw-слоя** — через трансформы. Никаких промежуточных кэшей в памяти.
- **Никакой прямой модификации данных на платформе** (см. Zero-Write Policy).
- Шаг→курс/модуль/урок и пути шагов (`build_step_path_maps`) — это **трансформ-логика** (в `transform.py`), а не API-логика: пути и атрибуция пресчитываются в `mart_steps`/`mart_lessons`/`mart_modules`/`mart_comments`, API их только читает.
- Группировки по месяцам/годам/курсам на API допустимы **только по витринам** (SQL GROUP BY), не по raw.
- `mart_steps` хранит и шаги без атрибуции к курсу (`course_id` NULL, только из `raw_step`): они питают среднюю оценку шагов (KPI) и пути в hardest-steps.

Если видишь в `app/api/` обращение к `raw_*` — это баг: данные должны прийти из витрины, а недостающая витрина — быть построена трансформом из raw.

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

## База данных (прикладные таблицы)

| Таблица | Назначение |
|---|---|
| `users` | Авторы/владельцы, зашифрованные токены (Fernet) |
| `courses` | Курсы автора (без health_score — удалён миграцией 010) |
| `student_enrollments` | Прогресс студентов, когортный статус |
| `submissions` | Отправки решений по шагам (correct/wrong), `is_author` |
| `financial_snapshots` | Снапшоты финансовой сводки + community (отзывы, рейтинг, комментарии по месяцам) |
| `student_marts` | Витрина студентов: одна строка на студента (имя, статус, курсы, сертификаты, решения, опубликованные решения, комментарии, активность). Пересобирается в конце синка |
| `mart_modules` | Витрина модулей (секций): одна строка на модуль курса; модули без юнитов/шагов сохраняются (структура/воронка) |
| `mart_lessons` | Витрина уроков: одна строка на юнит; сквозная нумерация уроков по курсу; уроки без шагов сохраняются |
| `mart_steps` | Витрина шагов: путь (модуль.урок-шаг) + метрики (`viewed_by`/`passed_by`/`correct_ratio`/`grade`/`block`); `course_id` NULL у шагов без атрибуции (не участвуют в структуре/воронке, но питают KPI и hardest-steps) |
| `mart_comments` | Витрина комментариев: одна строка на атрибутированный комментарий (`comment_id`, `is_solution`, `likes`/`dislikes` из `vote_delta`, `is_unanswered`, путь шага денормализован); не-атрибутируемые пропускаются |
| `mart_certificates` | Витрина сертификатов: одна строка на сертификат (`certificate_id`, `type` = distinction/regular, `year`/`month`) |
| `mart_reviews` | Витрина отзывов: одна строка на отзыв (`review_id`, `score`, `year`/`month`) |
| `raw_sync_state` | Состояние инкрементальной загрузки (`endpoint_name`, `key`, `value`) — step_id → last_page для submissions, course_{id} → last_page для author pass, last_time_course_X для comments, sync-статус |

PK — UUID (кроме `raw_sync_state`: PK `(endpoint_name, key)`). Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`.

Плюс служебные таблицы raw-слоя (`raw_*`, 24 шт.), реестр `meta_endpoint` и `meta_field_mapping` (создаются скриптами/mиграцией `20fc60296db6`).

## Синхронизация (пайплайн API → raw → app)

Все синхронизации идут через два слоя:

### Raw-слой (`app/services/raw_sync.py`)
- `sync_courses_structure()` — курсы + sections/units/lessons/steps
- `sync_course_grades_and_certs()` — оценки + сертификаты
- `sync_submissions()` — отправки + попытки (инкрементально: по шагам, по курсам author pass, попытки — только delta)
- **`/submissions?step=` НЕ возвращает поле `step` в объектах** — шаг известен только из контекста запроса; `sync_submissions()` пишет его в колонку `raw_submission.step` (миграция 015, loader-injected, без маппинга), `transform_submissions()` как fallback определяет шаг через `raw_attempt.step` по `submission.attempt`
- **Author pass** (`/submissions?course=X`, авторские решения) — инкрементальный по страницам через `raw_sync_state` (ключ `course_{id}` → last_page), как step-pass; курсы с HTTP 404 скипаются; страница-маркер и данные коммитятся per-course. Попытки качаются только по новым ID (`attempt_id` уже есть в `raw_attempt` → не перекачиваются; попытки неизменяемы)
- `sync_financials()` — финансы (course-benefit-by-months + course-benefits)
- `sync_community()` — рейтинги (сводки `course-review-summaries`) + **сами отзывы** (`course-reviews`, full_reload по курсам, упавший курс скипается) + комментарии
- **Сводки и отзывы коммитятся явно** (`session.commit()` после каждого `_replace_raw_table`) — раньше персистенция зависела от новых комментариев (commit только в comments-цикле); при +0 комментариев запись откатывалась — регрессия «плашка Отзывы 22 vs страница 20»
- `sync_users()` — анкеты (`/users?ids[]=`, батчи по 100) в raw_user; ID из `student_enrollments.student_id` + `submissions.user_id` + raw_course_grade/raw_certificate/raw_course_review (`USER_ID_SOURCES`); не-цифровые ID фильтруются (raw_comment.user хранит имя OAuth-клиента, не user id)
- Использует `_request()` из `stepik_api.py`, пишет в `raw_*` таблицы
- `_replace_raw_table()` (TRUNCATE + INSERT) для full_reload
- `_upsert_raw_table()` (INSERT ON CONFLICT) для incremental
- `_sync_id_sequence()` — после INSERT с явными id подтягивает serial-последовательность (PG; SQLite — no-op). Иначе следующий upsert-insert получит nextval из «прошлой жизни» и упадёт на pkey (регрессия `raw_comment_pkey`)
- `sync_submissions()` не опрашивает теоретические text-шаги (`_raw_json.block.name == 'text'`, у них решений нет) — фильтр по свежим данным `raw_step` (full_reload), экономия ~60% запросов к `/submissions`; оставшиеся шаги скипаются при HTTP 404 (удалённые на Stepik) и HTTP 400 «Bad step parameter» — не убивают весь sync; step-pass качает до лимита **500 страниц** (10000 строк на шаг, лимит защищает от вечного `has_next=true`) — при достижении лимита пишется warning
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
- `transform_steps()` — raw_section + raw_unit + raw_lesson + raw_step → `mart_modules`/`mart_lessons`/`mart_steps` (полная пересборка: DELETE + INSERT). Атрибуция шага к курсу/модулю/уроку, сквозная нумерация уроков (`lesson_number` = сумма юнитов предыдущих модулей + позиция юнита, `module_number` = индекс секции по position), метрики шага (`viewed_by`/`passed_by`/`correct_ratio`/`block`/`grade`/`grade_votes` из `raw_step._raw_json`). Шаги из `raw_lesson.steps` без юнита/секции пишутся с `course_id` NULL (только `lesson_id`/`step_number`). **Если шаг уже атрибутирован из `raw_lesson.steps`, колонка `raw_step.lesson` не перезаписывает его** (структура — источник истины)
- `transform_comments()` — raw_comment → `mart_comments` (атрибуция через mart_steps; `comment_id` из `_raw_json.id`, `is_solution` = thread содержит 'solution', `likes`/`dislikes` из `vote_delta`, `is_unanswered`, путь шага денормализован). Не-атрибутируемые шаги пропускаются
- `transform_certificates()` — raw_certificate → `mart_certificates` (только курсы из `courses`; `year`/`month` из `issue_date`, `type`)
- `transform_reviews()` — raw_course_review → `mart_reviews` (только курсы из `courses`; `year`/`month` из `create_date`, `score`)
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
- **Статус синка персистится** в `raw_sync_state` (`endpoint_name='sync'`, ключи `in_progress`/`progress`/`step`/`last_error`/`last_completed_at`), чтобы переживать перезапуск сервера (`uvicorn --reload`). Загрузка — лениво через `sync.ensure_state_loaded()` (первый запрос `/status` или `/sync`). Если процесс умер во время синка (`in_progress=true` в БД) — после рестарта `last_error` = «Синхронизация прервана перезапуском сервера». Запись best-effort (try/except, не роняет sync)
- `last_sync` — `financial_snapshots.updated_at`; колонка в PG — `timestamp without time zone`, значение UTC (naive) — **при сериализации обязательно `+00:00`** (иначе фронтенд трактует строку как локальное время — регрессия «дата в тултипе не в локальном TZ»)
- Фронтенд-кнопка синка: синяя «вода» прогресса во время sync, розовая заливка на всю высоту при `last_error`, тултип — дата последней синхронизации (idle) / ошибка / прогресс

## Фильтр по курсам (глобальный)

Кнопка **«Фильтр»** в сайдбаре над «Обновить» (иконка-воронка, акцент `text-cyber-blue` при активном фильтре) открывает дропдаун со списком всех курсов автора — общая галка «Выбрать все курсы» (indeterminate при частичном выборе), чекбоксы курсов, счётчик «Выбрано: N из M» (надпись «Курсы» выровнена по названиям курсов). Меню закреплено у нижнего края экрана (fixed, `bottom-3`, правее сайдбара), закрывается повторным кликом на кнопку / Escape / кликом снаружи. Все 6 страниц показывают данные только по выбранным курсам — **кроме страницы Курсов**: она фильтром не затрагивается (всегда полный список и полные KPI, вычисляемые из `data.courses`).

### Семантика (фронтенд)

- Состояние живёт в `SyncContext`: `selectedCourseIds` (`null` = все курсы, `[]` = ничего не выбрано), `toggleCourse`, `selectAllCourses` (→ `null`), `selectNoneCourses` (→ `[]`), `isFilterActive`. Без localStorage — после перезагрузки фильтр сбрасывается на «все».
- Пустой выбор (`[]`) — реальное состояние «ничего не выбрано»: пустой дашборд (нули/пустые срезы), все чекбоксы сняты. Отличается от «без фильтра» (`null`).
- `fetchAll` при подмножестве добавляет `?course_ids=u1,u2` (comma-joined, один параметр) ко **всем** дашборд-эндпоинтам, кроме `GET /courses` — он всегда полный (это источник списка для дропдауна). При `[]` шлётся пустой `?course_ids=` (пустой выбор), при `null` — без параметра.
- `Solutions` hardest-вкладка передаёт `course_ids` в `/dashboard/hardest-steps`; перезапрашивается при смене фильтра.
- Страница **Студентов** не читает `data` для списка — у неё **серверная пагинация**: каждая страница запрашивается с `/dashboard/students?skip=..&limit=..&sort=..&order=..` (+ `course_ids` при фильтре), сортировка на бэкенде (белый список колонок, `NULLS LAST` для `last_activity`), при смене фильтра сброс на первую страницу, обновление после синка (`last_sync`). `Students.jsx` грузит и сам список, и свою ошибку; из контекста берутся только когорты/фильтр/статус синка.
- Колонка **«Опубликованные»** (страница Студентов) — количество опубликованных решений студента: комментарии в тредах решений (`raw_comment._raw_json.thread` содержит `solutions`), та же семантика, что у «Публичных решений» на дашборде. Считается `transform_students` → `student_marts.published_solutions` (миграция 016), сортируется как числовая колонка.
- Страницы Решений/Финансов/Дашборда читают `data` из контекста — после перезапроса с параметром все числа уже отфильтрованы. Страница **Курсов** фильтром не затрагивается: таблица всегда рендерит полный `data.courses`, а KPI-плашки (Всего курсов/Опубликовано/Черновиков/Всего студентов/Средний рейтинг) считаются на клиенте из этого полного списка (не из отфильтрованного `data.kpi`).

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
     - transform.transform_steps (витрины структуры — нужны трансформам ниже)
     - transform.transform_comments
     - transform.transform_certificates
     - transform.transform_reviews
     - transform.transform_students (витрина студентов — все входные данные свежие)
```

### Инкрементальная загрузка submissions

- Таблица `raw_sync_state`: `(endpoint_name='submissions', key='step_{id}')` → `value` = последняя загруженная страница; **`key='course_{id}'`** — то же для авторских решений (author pass)
- При первом sync: загрузка с страницы 1 до `has_next=false`
- При повторном sync: загрузка с `last_page` (перезаписывается), продолжение до `has_next=false`
- **Попытки качаются только по delta**: `attempt_id`, уже присутствующие в `raw_attempt`, не перекачиваются (попытки неизменяемы). «Грязные» id из `raw_submission._raw_json.attempt` минус `raw_attempt.attempt_id`
- **Внимание:** author pass и попытки коммитятся отдельно (`session.commit()` per-course и после attempts) — без этого данные не персистятся (сессия откатывается при закрытии; регрессия: попытки с `_loaded_at` начала августа при синке августа)
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

KPI-карточки с трендом показывают `↑ N%` или `↓ N%` справа от заголовка (зелёный/красный). Возвраты — `trendInverted` (рост возвратов = красный). У каждого процента на дашборде есть нативный `title`-тултип (`KpiCard.trendTooltip`, собирается в `Dashboard.buildTrendTooltip`) с реальными числами и формулой: «Изменение за месяц / X: сейчас A, в прошлом месяце B / Расчёт: (A − B) ÷ B × 100». Числа приходят с бэкенда полями `*_change_detail` (`{current, previous}`, `null` когда процента нет — не показывать тултип).

Y-ось графиков:
- SubmissionsChart: `0, 0.5k, 1.0k, 1.5k, 2.0k` — `toFixed(1)` + `k`
- RevenueChart: `0, 2k, 4k, 6k` — `value/1000` + `.0` cleanup

График «Решения» (`SubmissionsChart`, дашборд + страница Активности) — 3 категории: **Правильные** (яркий синий `#38bdf8`, низ стека) → **Опубликованные** (среднее между «Правильные» и «Всего» — динамически `mixColors(bright, dim)`, над Правильными) → **Не завершён** (тёмный `#1a6a9e`, верх). Опубликованные = `community.solutions_monthly` (комментарии к сабмишн-тредам), **всегда часть Правильных**: `published = min(published, correct)`, сегмент правильных уменьшается на `published` (высота стека = total). `published` приходит **с бэкенда** в `/dashboard/submissions` (`published_solutions_stats()` в `course_filter.py`: скан `raw_comment`, комментарии с `thread`, содержащим `solution`, атрибуция через step→course map; месяцы/годы/курсы) — без фронт-мержа. Тултип показывает `correctTotal`/`publishedTotal` (полные значения). Серия рисуется только если в данных есть ключ `published` (график «Комментарии» не затрагивается).

График «Сертификаты» (страница Активности, `ActiveStudentsChart`) — сертификаты по месяцам выдачи, 2 категории: **С отличием** (светлый пурпур `#DB62C4`, верх стека) и **Обычные** (яркий маджента `#B70094`, низ). Источник: `GET /api/dashboard/certificates` (в `app/api/dashboard/charts.py`) — читает `raw_certificate._raw_json`, группирует по `issue_date[:7]`, `type == 'distinction'` → «С отличием». Ответ `{months: [{month, dark, light}]}`: `dark` = всего, `light` = обычные — сегмент «С отличием» = `overlap = dark − light` (компонент рисует light снизу, overlap сверху). Фильтр курсов: `WHERE course_id IN (...)` по stepik-курсам. Легенда/тултип через пропы `lightLabel`/`darkLabel`; тултип верхнего сегмента показывает `overlap` при `darkTooltipOverlap` (`darkTooltipValue()`), т.к. `dark` = всего, а не «С отличием».

Графики используют `CHART_COLORS` из `frontend/src/constants.js`.

## Единые таблицы (DataTable) и вкладки (Tabs)

Все таблицы (Решения ×4, Финансы ×7, Студенты, Курсы) построены на общем компоненте **`frontend/src/components/DataTable.jsx`** — сортировка, пагинация, авто-высота строк и вёрстка живут в одном месте; панель вкладок — **`frontend/src/components/Tabs.jsx`**. Будущие изменения сортировки/пагинации/стилей вносятся один раз и применяются ко всем таблицам.

**Схема колонки** (отличия таблиц задаются конфигурацией):
```
{ key, label, width, align: 'left'|'right', numeric?, nullLast?, naturalDir?,
  getValue?(row) -> значение для сортировки (составной месяц, «Неверно»=всего−правильно, алиасы step_id→stepik_step_id и т.п.),
  render?(row) -> полный <td> (ссылки, бейджи, цвета, валюта), cellClassName?, headerClassName? }
```
- `naturalDir` — «естественное направление» стрелки; по умолчанию `numeric → 'asc'`, текст → `'desc'`. Явно задаётся для дат-строк: `time`/`last_used` (Финансы), `last_activity` (Студенты), `published_at` (Курсы)
- `makeComparator(columns)` — единый компаратор (numeric/nullLast/getValue) вместо набора per-page функций
- Хуки: `useSortState(columns, initialSort)`, `useRowsPerPage()` (ResizeObserver, авто-высота строк)
- **Клиентский режим** (по умолчанию): `rows` сортируются и нарезаются внутри; состояние сортировки страница передаёт контролируемо (`sort`/`onSort`) для сохранения сортировки по вкладкам (Решения/Финансы), страница — внутри
- **Серверный режим** (Студенты): передаётся `totalPages` + контролируемые `sort`/`onSort`/`page`/`setPage`/`rowsPerPage`/`tableRef` — `rows` уже отсортированы и нарезаны бэкендом, DataTable только рендерит
- `emptyText` (пустая строка `colSpan = columns.length`), `emptyCentered` (блок по центру — «Нет данных» на hardest), `error` (красный блок — «Не удалось загрузить данные» на hardest), `loading` гасит пустое/ошибочное состояние
- Хелперы ячеек-заголовков: `yearMonthLabel`/`fmtDate` в `frontend/src/utils/format.js`
- Юнит-тесты компонента: `frontend/src/test/DataTable.test.jsx`, `frontend/src/test/Tabs.test.jsx`

## Страница «Курсы» (3 вкладки)

- Вкладки: **Курсы / Шаги / Воронка** (`frontend/src/pages/Courses.jsx`), KPI-плашки общие над вкладками
- **«Курсы»** — прежняя таблица (`DataTable`, `COURSE_COLUMNS`), пустой-state с «Подключить Stepik»
- **«Шаги»** — тепловая карта структуры **одного** курса (не зависит от глобального фильтра):
  - Свой селектор курса + переключатель метрики: **Просмотры / Отправлено / Успешных / Оценка / Тип блока** (`STEP_METRICS` в `CourseStructureMatrix.jsx`)
  - Матрица: **строки = уроки** (заголовки-полосы модулей), **столбцы = № шага в уроке** (максимум шагов среди уроков курса), ячейка = шаг; CSS-grid, без recharts
  - Цвета: Просмотры/Отправлено — последовательная шкала `rgba(56,189,248, α)` (по счётчику), Успешных — красно-жёлто-зелёный градиент по **проценту** `correct/total` (0% = красный, 100% = зелёный), Оценка — красно-жёлто-зелёный градиент (средняя оценка шага пользователями `grade` 1..5 напрямую), Тип блока — категориальная палитра (`text`/`code`/`external-grader`/`choice` из `_raw_json.block.name`); нет данных — тёмная клетка
  - Значение ячейки: Просмотры/Отправлено — счётчик (`fmtCompact`), Успешных — `%` от `correct/total` (не счётчик), Оценка — `grade.toFixed(2)` (5 смайликов на странице шага), Тип блока — буква
  - Ховер-тултип (portal): модуль — урок, шаг, все метрики; клик — deep link `stepik.org/lesson/{lesson_id}/step/{n}` (`target="_blank"`)
- **«Воронка»** — воронка прохождения **одного** курса (свой селектор курса, не зависит от глобального фильтра), `frontend/src/components/CourseFunnel.jsx`:
  - Слева от селектора — переключатель вида **Модули / Уроки** (`FUNNEL_VIEWS` в `Courses.jsx`, две иконки-сегмента как метрики «Шагов»); `view` передаётся в `GET /api/courses/{course_id}/funnel?view=modules|lessons` (рефетч при смене)
  - Вид «Модули»: этапы **«Записались»** (строки `student_enrollments`) → **«Модуль N. {title}»** по порядку `raw_section.position` → **«Получили сертификат»** (`certificate_issued`)
  - Вид «Уроки»: этапы **«Урок N. {title}»** со **сквозной нумерацией** (`lesson_offset + raw_unit.position`, как `lesson_number` в структуре), уроки из `raw_lesson` без шагов остаются в воронке (как пустые модули)
  - Значение этапа — **distinct-студенты с ≥1 решением в этом модуле/уроке или позже** (cumulative suffix-union из `submissions` через step→module/lesson карту: `raw_section` → `raw_unit` → `raw_lesson.steps`), поэтому воронка монотонно убывает; первый этап фактически = «начали курс»
  - Шаги submissions, не атрибутированные в структуру, пропускаются (как не-атрибутируемые комментарии); авторские решения исключены (`is_author=False`)
  - Визуал: recharts `FunnelChart` (градиент cyber-blue → dim-blue, финальный этап neon-green) + таблица «Этап | Студентов | % от записи | Отсев»; конверсия/отсев считаются на фронте из `value`. Сегменты — **прямоугольники** (кастомный `shape={FunnelRectangle}` на `<Funnel>`, рисует `<rect>` из геометрии трапеции; `activeShape` тот же), не скошенные трапеции; цвета/обводка/лейблы/тултип не меняются
  - Тесты: `tests/test_course_funnel.py`, фронт `frontend/src/test/CourseFunnel.test.jsx` + вкладки в `Courses.test.jsx`
- Источник: **`GET /api/courses/{course_id}/structure`** (в `app/api/courses.py`) — владение курсом (404 иначе), сборка из raw-слоя:
  - `raw_section` (`course = stepik_course_id`, `ORDER BY position`) → модули; `raw_unit` → уроки модуля (`position`); `raw_lesson` (`title`, `steps[]` → `step_number` через `_parse_step_positions` из `common.py` — работает и с TEXT, и с jsonb)
  - Сквозной `lesson_number` по курсу (смещение = сумма уроков предыдущих модулей)
  - Метрики шага: `viewed_by`/`passed_by`/`correct_ratio`/`grade`/`grade_votes` из `raw_step._raw_json` (агрегаты Stepik API, `_parse_raw` обрабатывает dict-jsonb и TEXT-строку; `grade` — средняя оценка шага пользователями из `num_grades` = `[g1..g5]`, распределение 5 смайликов, `_step_grade` — `Σ(cnt[i]·(i+1))/Σ(cnt)`, без голосов → `None/0`), `total`/`correct`/`students` из `submissions` (**ORM-запрос** — `text()`-биндинг UUID в SQLite не совпадает: там hex без дефисов, а `str(uuid)` с дефисами), `is_author=False`
  - Источник воронки: **`GET /api/courses/{course_id}/funnel?view=modules|lessons`** (там же) — та же проверка владения, step→module/lesson карта (`raw_unit.position` для сквозной нумерации уроков, `raw_lesson.title` для лейблов), `SELECT DISTINCT stepik_step_id, user_id FROM submissions` (ORM), ответ `{course, stages: [{key, module_number?|lesson_number?, label, value}]}`; невалидный `view` → `modules`
  - Тесты: `tests/test_course_structure.py`, `tests/test_course_funnel.py`, фронт `frontend/src/test/CourseStructureMatrix.test.jsx` + `CourseFunnel.test.jsx` + вкладки в `Courses.test.jsx`

## Страница «Решения» (4 вкладки)

- Вкладки: **По месяцам / По годам / По курсам / Самые сложные** (`frontend/src/pages/Solutions.jsx`)
- Таблицы (по месяцам/годам/курсам): колонки `Группа | Студенты | Всего | Правильно | Опубликованные | Неверно | Успех (цвет)` + `Шаг | Взв. успех (цвет)` у hardest
- **«Опубликованные»** — решения, опубликованные студентами на Stepik (комментарии в тредах решений): приходит **с бэкенда** в `/dashboard/submissions` полем `published` для всех группировок (`published_solutions_stats()` в `course_filter.py` — скан `raw_comment`, `_raw_json.thread` содержит `solution`, атрибуция через `build_step_course_map`; та же семантика, что у «Публичных решений» на дашборде и «Опубликованных» у студентов). KPI-плашка «Опубликованные» = сумма `published` по месяцам
- **«Шаг» = путь `модуль.урок-шаг`** (например `3.7-2`): модуль из `raw_section.position`, урок — **сквозной номер в курсе** (сумма уроков предыдущих модулей + позиция внутри своего модуля из `raw_unit.position`), шаг — позиция в `raw_lesson.steps`. Если данных структуры нет — fallback на `stepik_step_id`. Внутри — ссылка на Stepik (`lesson_id`/`step_number`), в tooltip — **название модуля — название урока** (`raw_section.title`/`raw_lesson.title`, fallback: курс и числовой ID шага). Считается единым хелпером **`build_step_path_maps(db, step_ids)`** в `app/api/dashboard/common.py` (переиспользуется списками комментариев)
- **`students`** — уникальные студенты в группировке = `COUNT(DISTINCT submissions.user_id)` (NULL игнорируются, `is_author=False`)
- **«Успех» = Wilson-нижняя граница 95% доверительного интервала** (`wilson_success_pct()` в `app/api/dashboard/common.py`), а не `correct/total`: чем меньше попыток, тем сильнее число занижается (данным нельзя верить); чем больше попыток, тем ближе к наблюдённому. 1 верная из 5 (20%) → 3.6%; 200 из 1000 (20%) → 17.6%. API отдаёт `success_pct` для всех группировок (months/years/by_course/steps); фронт использует его с fallback на raw-расчёт
- **«Взв. успех» = наблюдённый процент, притянутый к среднему по шагам** (`weighted_success_pct()` в `app/api/dashboard/common.py`): `(correct + 20 × global_pct) / (total + 20) × 100`, где `global_pct` — **unweighted mean** успеха по строкам группировки (не по попыткам — иначе доминирующий шаг сдвигает среднее). Мало попыток → цифра ≈ среднего, не лезет в топ; много попыток → честный `correct/total`. Колонка показывается **только на вкладке «Самые сложные»** (там она осмысленна — малые выборки шагов); API отдаёт `weighted_success_pct` для всех группировок
- Источники: `GET /dashboard/submissions` → `{months, by_course, years}` (в `app/api/dashboard/charts.py`); `GET /dashboard/hardest-steps` → `{steps}` (в `app/api/dashboard/steps.py`). Годы считают `students` **отдельным запросом** (не суммой по месяцам — один студент в нескольких месяцах одного года посчитался бы дважды). hardest сортирует по `weighted_success_pct` в Python (не в SQL) — мусор с 1-2 попытками не всплывает наверх
- Сортировка: первый клик — «естественный порядок» (числа/даты — больше/новые сверху, текст — А→Я), стрелка указывает **на главные значения** (по `naturalDir` в конфиге колонки); повторный клик — наоборот
- Верхние KPI-плашки: Всего решений / Правильных / Неправильных / Опубликованные (белые) + Успех (цвет как в колонке: `successColor` <33 красный, <66 жёлтый, ≥66 зелёный)

## Страница «Комментарии» (5 вкладок)

- Вкладки: **По месяцам / По годам / По курсам / Не отвеченные / Дизлайки** (`frontend/src/pages/Comments.jsx`)
- Таблицы (агрегаты): колонки `Группа | Студенты | Всего | Лайки (цвет) | Дизлайки (цвет) | Ответы`
- Источник агрегатов: `GET /api/dashboard/comments` → `{months, years, by_course, totals}` (в `app/api/dashboard/comments.py`) — скан `raw_comment._raw_json` (как `filter_community`), курс комментария через `build_step_course_map()` (raw_step JOIN raw_unit JOIN raw_section)
- **«Не отвеченные» / «Дизлайки»** — списки отдельных комментариев через **`GET /api/dashboard/comments/list?type=unanswered|disliked&skip&limit&sort&order&course_ids`** (тот же `comments.py`). Серверная пагинация/сортировка (как `/students`): ответ `{comments: [...], total}`, whitelist сортировки `time/student/course/text/likes/dislikes/replies/step`, NULLS LAST, `step` — числовой композит `module*100000+lesson*1000+step`
  - `unanswered`: `_raw_json.is_staff_replied != true` **и** `_raw_json.user_role != "teacher"` (только обращения студентов; колонка `is_staff_replied` в БД пустая — не в `meta_field_mapping`, данные только в `_raw_json`)
  - `disliked`: `vote_delta < 0`
  - оба: `is_deleted` truthy пропускается; не-атрибутируемые шаги пропускаются и при фильтре, и без (инвариант держится)
- Колонки списков: `Дата (fmtDate) | Студент (имя из raw_user, fallback «—») | Курс (ссылка) | Комментарий (HTML вырезан `_strip_html`, truncate + title) | Лайки (green) | Дизлайки (red) | Ответы | Шаг (модуль.урок-шаг)`
- Колонка **«Шаг»** в списках — путь `модуль.урок-шаг` (fallback `step_number`/`comment_id`), tooltip «модуль — урок», ссылка на комментарий: `https://stepik.org/lesson/{lesson_id}?discussion={comment_id}` (`STEPIK_URLS.comment`), `target="_blank"`
- Пути шагов — единый хелпер **`build_step_path_maps(db, step_ids)`** в `app/api/dashboard/common.py` (модуль/урок/шаг из raw_section/raw_unit/raw_lesson; используется и `steps.py`, и `comments.py`); `_parse_step_positions` тоже в common.py, из `steps.py` re-exportится (тест `test_steps.py` импортирует оттуда)
- Списки грузятся **lazy** при активации вкладки (серверный режим DataTable по образцу Students.jsx: `useRowsPerPage`/`useSortState`/`reqIdRef`, сброс на стр. 1 при смене фильтра/сортировки, refetch при смене `last_sync`); агрегаты из контекста, 4 KPI-плашки общие
- `students` в группировке — **distinct авторов** (`_raw_json.user`, не-числовые значения — имена OAuth-клиентов — пропускаются); KPI «Студенты» = distinct по всем комментариям (сумма по месяцам задвоила бы)
- **Лайки/Дизлайки считаются из `vote_delta`** (Stepik не отдаёт раздельных счётчиков: `/votes?ids[]=` возвращает только собственный голос вызывающего, агрегатных полей в синкаемых данных нет): **Лайки = сумма положительных `vote_delta`**, **Дизлайки = модуль суммы отрицательных** по комментариям в группе. Это «суммарный балл оценок», а не точное число нажатий
- «Ответы» = сумма `reply_count`
- Комментарии, чей шаг не атрибутирован к курсам (`target` не в step→course map), **пропускаются и при фильтре, и без него** — инвариант «фильтр = все курсы» == «без фильтра» держится (как в `filter_community`)
- KPI-плашки: Всего комментариев / Студенты (белые) + Лайки (`neon-green`) + Дизлайки (`crimson-alert`)

## Страница «Сертификаты» (3 вкладки)

- Вкладки: **По месяцам / По годам / По курсам** (`frontend/src/pages/Certificates.jsx`)
- Источник: `GET /api/dashboard/certificates/stats` → `{months, years, by_course, totals}` (в `app/api/dashboard/certificates.py`) — читает `raw_certificate` напрямую (курс на строке, step→course map не нужен), `issue_date`/`type` из `_raw_json` (в SQLite-фикстуре колонок нет; live PG хранит raw как TEXT/jsonb)
- **«С отличием» = `type == 'distinction'`**, «Обычные» = остальные (то же разделение, что у графика на Активностях: `dark` = всего, `light` = обычные, overlap = с отличием). Кэшированный `/api/dashboard/certificates` (график) не затрагивается
- `students` — distinct `user_id` (колонка `raw_certificate.user_id`, fallback `_raw_json.user`; не-числовые значения — имена OAuth-клиентов — пропускаются). Сертификаты без `issue_date` пропускаются; курс фильтруется по пересечению с курсами пользователя (`get_courses_for_user`, чужие курсы не видны)
- `totals` = `{certificates, students, distinction, regular}`; фильтр `course_ids` работает через `WHERE course_id IN (...)`; инвариант «фильтр = все курсы» == «без фильтра»; пустой `?course_ids=` → пустой ответ
- KPI-плашки: Всего сертификатов / Студенты (белые) + С отличием (`distinction` `#DB62C4`) + Обычные (`regular` `#B70094`). Новые цвета добавлены в палитру `KpiCard.COLOR_CLASSES` (chart-цвета пурпур/маджента)

## Страница «Отзывы» (3 вкладки)

- Вкладки: **По месяцам / По годам / По курсам** (`frontend/src/pages/Reviews.jsx`)
- Источник: `GET /api/dashboard/reviews/stats` → `{months, years, by_course, totals}` (в `app/api/dashboard/reviews.py`) — читает `raw_course_review` напрямую (курс на строке, step→course map не нужен), `create_date`/`score`/`user` из `_raw_json` (работает и в SQLite-фикстуре, и в live PG)
- **Без раскола по типу** — колонка **«Средняя оценка»** = средний `score` в группе (round 2, `0` → «—»). Отзывы без `create_date` пропускаются; `score` без числа в avg не входит
- `students` — distinct числовые `_raw_json.user` (не-числовые — имена OAuth-клиентов — пропускаются)
- `totals` = `{reviews, students, avg_score}`; фильтр `course_ids` через `WHERE course IN (...)` (колонка `course` = stepik_course_id); инвариант «фильтр = все курсы» == «без фильтра»; пустой `?course_ids=` → пустой ответ; чужие курсы исключены (`get_courses_for_user`)
- KPI-плашки: Всего отзывов / Студенты (белые) + Средняя оценка (`ratingColor` градиент, ru-RU запятая). В таблице оценка рендерится `toFixed(2)` с градиентом `getRatingColor` (как в Courses.jsx), «—» при 0

## Страница «Финансы» (7 вкладок)

- Вкладки: **По месяцам / По годам / По дням / По курсам / По промокодам / По UTM / Последние операции** (`frontend/src/pages/Financials.jsx`)
- Таблицы — тот же сортируемый/пагинируемый паттерн, что и в Решениях: `DataTable` + схема колонок (`naturalDir` для дат `time`/`last_used`) + авто-`rowsPerPage`
- **Месяцы сортируются по композиту `year*100 + month_num`** (хронология, а не по текстовой метке «Январь 2026»); данные приходят без `.reverse()` — дефолт `{key:'month', dir:'desc'}` даёт «новые сверху»
- **«По дням»** — агрегация `recent_payments` по календарному дню за последние **30 дней включительно с нулевыми днями** (все 30 строк), новые сверху. Считается на лету в `/api/financials` (`_build_daily_stats`, `DAYS_BACK=30`) из `recent_payments` (там есть `time`/`amount`/`payment_amount`/`status`), формула как в `filter_financials` (`refunded` → `refunds += abs(amount)`, `turnover -= payment_amount`). Фильтр по курсам работает автоматически — отфильтрованные `recent_payments` уже ограничены. Даты рендерятся как `dd.mm.yyyy` без timezone-сдвигов
- `nullLast` для nullable-колонок: `price`, `student`, `channel`, `promo_code`, `is_gift`, `utm_source_label`, `last_used` (всегда внизу, даже при desc)
- Финансовая семантика цветов сохранена: белый оборот/суммы, `neon-green` доход, `crimson-alert`+`line-through` для refunded, `formatCurrency` (₽), «—» для пустых ячеек
- `recent`-вкладка: UTM-тултип из `raw.last_course_click_utm` (`formatUtmTooltip`), сортировка «Дата» по raw `time`, «Подарок» (is_gift) — 0/1
- Колонка **«Комиссия»** (между «Оплата» и «Доход») — комиссия Stepik в % от платежа: `(payment_amount − abs(amount)) / payment_amount × 100`, округление до целых (тултип — сумма комиссии в ₽). Считается на фронтенде из полей `recent_payments` (`commissionOf()` в `Financials.jsx`); API готового процента не отдаёт (в `raw_course._raw_json` есть только курсовые ставки `commission_basic`/`commission_promo`, которые не объясняют промо-платежи)

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
Порядок как в `sync_all`: courses → enrollments → submissions → financials → community → steps → comments → certificates → reviews → students. Abort, если `raw_course` пуст.

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

516 тестов, 0 skipped, 0 failures (`pytest -v`, требует запущенный docker-compose для live-PG).
| Файл | Тестов | Что тестирует |
|---|---|---|
| `tests/test_stepik_api.py` | 20 | `_request`, `exchange_code`, `refresh_token`, `get_user_profile` |
| `tests/test_stepik_api_comprehensive.py` | 14 | `get_finance_token`, 5xx retries, constants |
| `tests/test_raw_sync.py` | 23 | `sync_courses_structure`, `sync_grades_and_certs`, `sync_submissions` (+404-шаги, 400-теоретические-шаги, **text-шаги не опрашиваются**, **step-pass докачивает до лимита 500 страниц**, конфликтные upsert'ы, str-bind для TEXT-колонок), `sync_financials`, `sync_community` (**сами отзывы course-reviews в raw_course_review**, скип упавшего курса, **персистенция при +0 комментариев**), регрессии `became_published_at`, stale sequence, **инкремент author pass (продолжение с сохранённой страницы) и delta попыток** |
| `tests/test_raw_sync_edge_cases.py` | 12 | `_paginated_fetch`, пустые/ошибочные данные transform и raw_sync |
| `tests/test_transform.py` | 18 | `transform_courses/enrollments/submissions/financials/community` (+ utms, channel/gift, student name, recent_payments без лимита) |
| `tests/test_sync_integration.py` | 18 | `sync_all`, cohort status, интеграция raw_sync → transform, stepwise-коммиты raw_sync внутри sync-этапов |
| `tests/test_sync_comprehensive.py` | 21 | `sync_all`, `sync_community_stats`, `sync_financials` |
| `tests/test_sync_edge_cases.py` | 26 | Разрешение конфликтов, отсутствие данных, ошибки API, регрессии `_last_sync_error` (падение → error виден в статусе, успех → очищен), **персистенция статуса синка** (`TestSyncStatePersistence`: in_progress/error/после рестарта сервера) |
| `tests/test_data_contract.py` | 5 | Глобальные контракты снапшота/API/фронта (price, per_course, поля страниц, recent_payments/utms) |
| `tests/test_schema_contract.py` | 10 | Schema-contract: статический скан SQL трансформов, TEXT-типизация raw-слоя, live-PG parity (raw-схема, meta_field_mapping, покрытие mapping'ом читаемых колонок, полный пайплайн, снапшот), **live-PG свежесть данных** (трансформы на реальных данных производят строки и догоняют raw — регрессия «0 submissions upserted») |
| `tests/test_architecture.py` | 19 | Архитектурные гарантии: один alembic head, нет dead-артефактов (step_sync_state, orphan-скрипты), единый источник констант, дефолты конфига = docker-compose, сплит dashboard-пакета, rebuild_marts.py (все трансформы, без API) |
| `tests/test_steps.py` | 35 | hardest-steps (читает `mart_steps`): `_parse_step_positions` (jsonb/list vs TEXT-строка), lesson_id/step_number, сортировка, min_submissions, limit, чужие курсы, `students` (COUNT DISTINCT user_id), `wilson_success_pct` (объём попыток: 1/5 → 3.6%, 200/1000 → 17.6%), `weighted_success_pct` (мусор с малым числом попыток не всплывает в топ), `module_number`/`lesson_number` (сквозная нумерация уроков по курсу), `module_title`/`lesson_title` |
| `tests/test_course_filter.py` | 25 | Фильтр по курсам: `parse_course_ids` (None/`[]`), безопасность (чужие UUID отбрасываются), SQL-эндпоинты (submissions/active-students/cohorts/alerts/hardest-steps/students), пересчёт снапшота (financials/revenue/kpi/published-solutions/community), `published` в submissions (в т.ч. по курсам, инвариант «фильтр = все курсы» == «без фильтра»), пустой `?course_ids=` = пустой выбор; `filter_financials` пропускает платёж без `raw`/не-dict `raw`/не из выбранных курсов, `filter_community` на пустом сообществе → нули, `filter_steps_average_grade` для выбранных курсов без шагов → 0 |
| `tests/test_cohorts.py` | 5 | `/api/dashboard/cohorts`: границы сегментации 7/30/90 дней (ровно на границе), «Зомби» не попадает ни в один сегмент, `last_viewed_at IS NULL` не считается, нет курсов → нули |
| `tests/test_alerts.py` | 5 | `/api/dashboard/alerts`: `points_earned == 100` → алерт, выданный сертификат исключается, `HAVING count > 10` на границе 10/11 студентов, оба типа алертов одновременно, нет курсов → пусто |
| `tests/test_students.py` | 4 | `/api/dashboard/students`: неверный `limit` (0/201) и отрицательный `skip` → 422, `skip` за пределами списка → пусто при верном `total` |
| `tests/test_kpi.py` | 5 | `/api/dashboard/kpi`: январь корректно берёт предыдущий месяц = декабрь прошлого года, тренд при нуле в прошлом месяце = `None`, `max(0,…)` для «предыдущих месяцев», средняя оценка шагов = 0 без голосов, средний рейтинг = 0 без оценок |
| `tests/test_comments.py` | 12 | `/api/dashboard/comments` (читает `mart_comments`): months/years/by_course группировки, totals, Лайки/Дизлайки из `vote_delta`, distinct-студенты (OAuth-клиенты отбрасываются), атрибуция через mart_steps, инвариант «фильтр = все курсы» == «без фильтра»; `/comments/list`: фильтры `unanswered` (is_staff_replied + teacher + deleted) и `disliked` (vote_delta<0), имена из raw_user, пути шагов, HTML-стрип, фильтр курсов + инвариант, сортировка/пагинация/NULLS LAST, 400 на неверные параметры, пустые данные |
| `tests/test_certificates.py` | 5 | `/api/dashboard/certificates/stats` (читает `mart_certificates`): months/years/by_course группировки, distinction/regular, distinct-студенты, фильтр курсов, чужие курсы исключены, пустой выбор = пустые данные |
| `tests/test_reviews.py` | 5 | `/api/dashboard/reviews/stats` (читает `mart_reviews`): months/years/by_course группировки, avg_score (score без числа не входит), distinct-студенты (OAuth-клиенты отбрасываются), фильтр курсов, чужие курсы исключены, пустой выбор = пустые данные |
| `tests/test_course_structure.py` | 19 | `/api/courses/{id}/structure`: владение курсом (404 чужих/битых ID), порядок модулей/уроков/шагов по position, сквозной `lesson_number`, `lesson_id`/`step_number` у шагов, метрики из `raw_step._raw_json` (dict-jsonb и TEXT-строка), `total`/`correct`/`students` из submissions (ORM, `is_author=False`), пустые уроки; юнит-тесты `_step_grade` (средняя оценка шага из `num_grades`: взвешенное среднее, один голос, без голосов, отсутствие поля, не-список, не-числовые счётчики, короткий список, минимальная оценка) |
| `tests/test_course_funnel.py` | 18 | `/api/courses/{id}/funnel`: владение курсом (404 чужих/битых ID), пустая структура → «Записались» + «Сертификат», cumulative distinct по модулям (монотонность), порядок по position, сертификаты отдельным этапом, исключение авторских submissions, не-атрибутируемые шаги пропускаются, модуль без шагов остаётся в воронке; `view=lessons` — cumulative по урокам, сквозная нумерация `lesson_number`, урок без шагов остаётся, fallback невалидного `view` на modules |
| Остальные | 182 | API endpoints, dashboard, financials, crypto, rate limiter, ... |

Live-PG тесты: изменения в БД — **только через явный `await trans.rollback()`**, не `async with session.begin():` + rollback снаружи (begin()-контекст коммитит на выходе, rollback после него — no-op).

Schema-contract тесты (`test_schema_contract.py`) — глобальная защита от дрейфа схемы:
- Статический парсинг всех `text(...)` SQL-блоков в `transform.py`/`raw_sync.py`: каждая `table.column` обязана существовать в фикстуре `RAW_TABLES` и моделях
- Все raw-колонки, читаемые трансформациями, обязаны быть TEXT в фикстуре (реальная PG хранит raw-слой как TEXT)
- Live PG (skip без `DATABASE_URL` в `.env`): колонки, потребляемые трансформациями, существуют в PG и имеют тип text/jsonb; каждый `meta_field_mapping.db_column` активных эндпоинтов существует в PG; **каждая читаемая трансформациями колонка покрыта is_loaded-строкой mapping'а** (иначе loader молча оставляет NULL — регрессия `became_published_at`); полный пайплайн `transform_*` отрабатывает в транзакции (rollback) без ошибок; снапшот финансов содержит `courses` (с `price`) и `community.per_course`
