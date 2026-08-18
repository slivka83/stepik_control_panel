# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fix (Исправления логических/семантических ошибок)
- Счётчик комментариев в снапшоте (`transform_community`) теперь считает только комментарии, привязанные к курсам пользователя (как `mart_comments`) — устранён разрыв инварианта «фильтр = все курсы» == «без фильтра» (`total_comments`/`comments_monthly`/`total_solutions`/`solutions_monthly`); регрессионный тест `test_community_skips_non_attributable`
- Средняя оценка шагов (KPI) при фильтре по курсам теперь включает шаги без привязки к курсу (`stepik_course_id IS NULL`), как и в режиме «без фильтра» (`filter_steps_average_grade`); регрессионный тест `test_null_course_step_included_in_average`
- «Опубликованные решения» в группировках решений теперь ограничены числом правильных (`published = min(published, correct)`) на уровне API (`charts.get_submissions`) — раньше таблицы/KPI могли показать опубликованных больше, чем правильных
- Тренд «Доход /месяц» (KPI) сравнивает текущий месяц с предыдущим **календарным**, а не с предпоследним месяцем в данных (раньше в начале нового месяца «перепрыгивал» месяц); регрессионный тест `test_revenue_trend_uses_previous_calendar_month`
- Дефолт `redis_url` в `config.py` теперь содержит пароль, совпадающий с `docker-compose.yml` (иначе Redis-лимитер/чёрный список молча не работали)
- Фронтенд: вкладка «Самые сложные» учитывает выбор «ни одного курса» (раньше показывала все курсы); подписи на графиках «Доход» и «Решения» исправлены («Комиссия» вместо «Оборот», «Не завершён» вместо «Всего»); тепловая карта шагов корректно показывает значение 0 (не путает с «нет данных»); KPI с рейтингом при отсутствии оценки показывает красный, а не «лучший зелёный»

### Tests (Пограничные тесты — финансы, когорты, алерты, студенты, KPI, фильтр курсов)
- Добавлено ~37 пограничных тестов для мест, где раньше покрытия не было (граничные даты, пустые/неверные данные, «ровно на границе» условия):
  - `tests/test_financials.py` (было 2 → стало 14): чистая функция `_build_daily_stats` — окно в 30 дней (ровно сегодня / ровно 30 дней назад попадают, 31-й день и будущее отсекаются), даты с суффиксом `Z`, битая/пустая дата пропускается, возврат с положительной суммой (`abs`), нулевой платёж, пустой список → 30 нулевых дней, несколько платежей в один день склеиваются; эндпоинт: снапшот с пустыми `recent_payments` → 30 нулей, годовая сводка игнорирует месяц без года
  - `tests/test_cohorts.py` (новый, 5): границы сегментации 7/30/90 дней (ровно на границе), «Зомби» не попадает ни в один сегмент, `last_viewed_at IS NULL` не считается
  - `tests/test_alerts.py` (новый, 5): `points_earned == 100` → алерт, выданный сертификат исключается, `HAVING count > 10` на границе 10/11 студентов, оба типа алертов одновременно
  - `tests/test_students.py` (новый, 4): неверный `limit` (0 / 201) и отрицательный `skip` → 422, `skip` за пределами списка → пусто при верном `total`
  - `tests/test_kpi.py` (новый, 5): январь корректно берёт предыдущий месяц = декабрь прошлого года, тренд при нуле в прошлом месяце = `None`, `max(0,…)` для «предыдущих месяцев», средняя оценка шагов = 0 без голосов, средний рейтинг = 0 без оценок
  - `tests/test_course_filter.py` (было 20 → стало 25): `filter_financials` пропускает платёж без `raw` / с не-dict `raw` / не из выбранных курсов, `filter_community` на пустом сообществе → нули, `filter_steps_average_grade` для выбранных курсов без шагов → 0
- Полный прогон: **516 passed, 0 failed**

### Fix (Финансы — `filter_financials` падал на платеже без/с битым `raw`)
- `filter_financials` выбрасывал `AttributeError` (500 на странице финансов), если в данных попадался платёж с `raw = null` или не-dict значением `raw`. Теперь такие платежи безопасно пропускаются (как и в `_filtered_payments`). Регрессионный тест `test_skips_missing_nondict_and_nonmember_raw` в `tests/test_course_filter.py`

### Architecture (Двухслойная архитектура: витрины mart_* — API не читает raw_*)
- **Новые витрины** `mart_modules`/`mart_lessons`/`mart_steps`/`mart_comments`/`mart_certificates`/`mart_reviews` (миграция `017`, модели `app/models/mart.py`): атрибуция шага к курсу/модулю/уроку, сквозная нумерация уроков, метрики шага (`viewed_by`/`passed_by`/`correct_ratio`/`grade` из `raw_step._raw_json`), лайки/дизлайки и `is_unanswered` комментариев, пути шагов пресчитаны **трансформами** (`transform_steps`/`transform_comments`/`transform_certificates`/`transform_reviews`)
- **API-слой переведён на витрины**: `build_step_path_maps` (пути шагов), hardest-steps, комментарии (агрегаты + списки неотвеченных/дизлайков), сертификаты, отзывы, `published_solutions_stats`, `filter_community`, средняя оценка шагов (KPI), структура и воронка курса читают только `mart_*` — ни одного `SELECT` из `raw_*` в `app/api/`
- `mart_steps` хранит и шаги без атрибуции (`course_id` NULL) — питают KPI средней оценки и пути hardest-steps
- Синк и `rebuild_marts.py`: новые трансформы в конце (после community, перед студентами); `_parse_step_positions` переехал в `transform.py`
- Тесты: API-тесты сидят raw-слой и пересобирают витрины хелпером `build_marts` из `tests/conftest.py`; вся ветка 478/478

### Fix (Синхронизация — авторские решения и попытки теперь докачиваются инкрементально)
- **Author pass** (`/submissions?course=X`) — раньше при каждом синке перекачивался целиком с page=1 (+7000 строк). Теперь запоминает последнюю страницу каждого курса (`raw_sync_state`, ключ `course_{id}`) и догружает только новые, как step-pass. Курсы с HTTP 404 скипаются
- **Попытки** — раньше при каждом синке перекачивались все (36401 попытки, ~364 запроса). Теперь качаются только по новым ID (попытки неизменяемы). Экономия ~8 минут на синке (26 → ~17 мин)
- **Фикс скрытого бага:** author pass и попытки не коммитились (данные с `_loaded_at` откатывались при закрытии сессии — в БД лежали только старые записи начала августа). Теперь коммитятся отдельно (per-course и после attempts)
- Регрессионные тесты в `tests/test_raw_sync.py`: `test_author_pass_incremental_continues_from_last_page`, `test_attempts_incremental_fetches_only_new_ids`

### Fix (Синхронизация — причина падения больше не теряется)
- **Причина падения последней синхронизации теперь сохраняется в БД** (`raw_sync_state`, ключ `endpoint_name='sync'`) и переживает перезапуск сервера (`uvicorn --reload`). Раньше `last_error` жил только в памяти и после рестарта статус молчал — невозможно было понять, почему упал синк
- Если процесс умер во время синхронизации (например, из-за авто-перезагрузки при правке файлов) — после рестарта статус показывает «Синхронизация прервана перезапуском сервера»
- Загрузка статуса — лениво через `sync.ensure_state_loaded()` (первый запрос `/status` или `/sync`); запись best-effort (не роняет сам синк). Регрессионные тесты `TestSyncStatePersistence` в `tests/test_sync_edge_cases.py`

### Features (Воронка — прямоугольные сегменты)
- Сегменты воронки теперь — **прямоугольники** без скошенных боков: кастомный `shape={FunnelRectangle}` (`<rect>` из геометрии трапеции) на recharts `<Funnel>`, `activeShape` тот же. Цвета (градиент cyber→dim, финальный neon-green), обводка `#0b0f19`, лейблы значений и тултип не изменились. Тест `CourseFunnel.test.jsx` проверяет, что сегменты рендерятся как `<rect>`

### Features (Воронка — вид «Модули»/«Уроки»)
- На вкладке **«Воронка»** слева от селектора курса добавлен переключатель вида **Модули / Уроки** (две иконки-сегмента, активная `text-cyber-blue`, неактивная белая с неоном при наведении — как метрики «Шагов»). `GET /api/courses/{course_id}/funnel` принимает `?view=modules|lessons` (по умолчанию `modules`)
- `view=lessons`: воронка строится по **урокам** — этапы «Урок N» со сквозной нумерацией как в структуре (`lesson_offset + unit_pos`, `raw_unit.position`), значение — distinct-студенты с ≥1 решением в этом уроке или позже (cumulative suffix, монотонно убывает). Уроки без шагов остаются в воронке (как пустые модули), не-атрибутируемые шаги и авторские решения исключены
- Тесты: `tests/test_course_funnel.py` — `TestCourseFunnelLessonsView` (7 тестов: cumulative/distinct, монотонность, исключение авторов, не-атрибутируемые шаги, пустая структура, урок без шагов со сквозной нумерацией, fallback невалидного `view` на modules), фронт `CourseFunnel.test.jsx` (view=lessons, refetch при смене view) и `Courses.test.jsx` (переключение вида)

### Features (Курсы — метрики матрицы «Шаги»)
- Метрика **«Успешно»** теперь показывает **процент успешности** `correct/total` (не количество решений); градиент — по проценту. Метрика **«Оценка»** — **средняя оценка шага пользователями** (`grade` из `raw_step._raw_json.num_grades`, распределение 5 смайликов на странице шага), `grade.toFixed(2)`, градиент 1..5 напрямую
- Структура шага в `GET /api/courses/{course_id}/structure` дополнена полями `grade`/`grade_votes` (бэкенд-хелпер `_step_grade`); `correct_ratio` сохранён
- Тултип матрицы: добавлены строки «Успешность: %» и «Оценка: 4.86 · 14 гол.»
- Шапка вкладок: иконки-переключатели метрик (уменьшены `w-3.5 h-3.5`) и селектор курса вынесены на уровень вкладок (общие для «Шаги»/«Воронка»); внутренние селекторы/заголовки («Воронка прохождения», «Этапы», легенда) убраны
- Тесты: юнит-тесты `_step_grade`, фронт `CourseStructureMatrix` (grade/%/dash/tooltip), `Courses` (refetch при смене курса), `CourseFunnel` (без селектора/заголовков)

### Features (Курсы — вкладки «Курсы»/«Шаги», тепловая карта структуры)
- Страница «Курсы» разделена на вкладки **«Курсы»** (прежняя таблица + empty-state «Подключить Stepik») и **«Шаги»** — тепловая карта структуры **одного** курса (не зависит от глобального фильтра, свой селектор курса). KPI-плашки общие над вкладками
- **Матрица**: строки = уроки (заголовки-полосы модулей), столбцы = № шага в уроке, ячейка = шаг; CSS-grid, без recharts. Переключатель метрики: **Просмотры / Отправлено / Успешных / Оценка / Тип блока**
- Цвета: Просмотры/Отправлено — последовательная шкала `rgba(56,189,248, α)` (по счётчику), Успешных — та же шкала по **проценту** `correct/total`, Оценка — красно-жёлто-зелёный градиент (средняя оценка шага пользователями `grade` 1..5 напрямую), Тип блока — категориальная палитра (`text`/`code`/`external-grader`/`choice` из `_raw_json.block.name`); нет данных — тёмная клетка. Значение ячейки: Просмотры/Отправлено — счётчик, Успешных — `%`, Оценка — `grade.toFixed(2)` (5 смайликов), Тип блока — буква
- Ховер-тултип (portal): модуль — урок, шаг, все метрики; клик — deep link `stepik.org/lesson/{lesson_id}/step/{n}` (`target="_blank"`)
- Новый **`GET /api/courses/{course_id}/structure`** (в `app/api/courses.py`) — владение курсом (404 иначе), сборка из raw-слоя: `raw_section` → модули, `raw_unit` → уроки, `raw_lesson` (`title`, `steps[]` → `step_number` через `_parse_step_positions` из `common.py`, работает и с TEXT, и с jsonb); сквозной `lesson_number` по курсу; метрики шага: `viewed_by`/`passed_by`/`correct_ratio`/`grade`/`grade_votes` из `raw_step._raw_json` (`_parse_raw` для dict-jsonb и TEXT-строки; `grade` — средняя оценка шага из `num_grades` = `[g1..g5]`), `total`/`correct`/`students` из `submissions` (ORM-запрос — `text()`-биндинг UUID в SQLite не совпадает: hex без дефисов), `is_author=False`
- Тесты: `tests/test_course_structure.py` (19, включая юнит-тесты `_step_grade`), фронт `frontend/src/test/CourseStructureMatrix.test.jsx` + вкладки в `Courses.test.jsx`

### Features (Финансы — вкладка «По дням» и колонка «Комиссия»)
- Новая вкладка **«По дням»** (между «По годам» и «По курсам»): агрегация `recent_payments` по календарному дню за последние **30 дней включительно с нулевыми днями** (все 30 строк), новые сверху. Считается на лету в `/api/financials` (`_build_daily_stats`, `DAYS_BACK=30`) из полей `time`/`amount`/`payment_amount`/`status`; формула как в `filter_financials` (`refunded` → `refunds += abs(amount)`, `turnover -= payment_amount`). Фильтр по курсам работает автоматически. Даты рендерятся как `dd.mm.yyyy` без timezone-сдвигов
- Колонка **«Комиссия»** (между «Оплата» и «Доход») во вкладке «Последние операции» — комиссия Stepik в % от платежа: `(payment_amount − abs(amount)) / payment_amount × 100`, округление до целых; тултип — сумма комиссии в ₽ (`commissionOf()` в `Financials.jsx`). API готовый процент не отдаёт (в `raw_course._raw_json` есть только курсовые ставки `commission_basic`/`commission_promo`, которые не объясняют промо-платежи)

### Architecture / Refactoring (единые DataTable и Tabs)
- Введён общий компонент **`DataTable`** (`frontend/src/components/DataTable.jsx`): вся сортировка, пагинация, авто-высота строк (ResizeObserver) и вёрстка таблиц живут в одном месте. Все таблицы (Решения ×4 вкладки, Финансы ×7, Студенты, Курсы — 11 штук) переведены на него
- **Настраиваемые параметры колонки** (отличия таблиц): `key`/`label`/`width`/`align`, `numeric`, `nullLast`, `naturalDir` (направление стрелки), `getValue` (вычисляемое значение для сортировки — составной месяц, «Неверно» = всего−правильно, алиасы `step_id→stepik_step_id` и т.п.), `render` (ячейка-ссылка/бейдж/цвет), `cellClassName`/`headerClassName`
- Режимы: **клиентский** (Решения, Финансы, Курсы — сортировка и пагинация внутри компонента) и **серверный** (`totalPages` + контролируемые `sort/page/rowsPerPage/tableRef` — Студенты)
- Дубли убраны: `SortableTh`, `Pagination`, `makeComparator`, `useSortState`, `useRowsPerPage` вынесены из страниц; хелперы `yearMonthLabel`/`fmtDate` — в `frontend/src/utils/format.js`; панель вкладок — общий компонент **`Tabs`**
- Поведение и внешний вид не изменились: все 299 прежних тестов проходят без правок; добавлены юнит-тесты `DataTable.test.jsx` (14) и `Tabs.test.jsx` (3)

### Features (Студенты — колонка «Опубликованные»)
- В таблицу «Студенты» добавлена колонка **«Опубликованные»** (справа от «Решений»): количество опубликованных решений студента = комментарии в тредах решений (`raw_comment._raw_json.thread` содержит `solutions`) — та же семантика, что у «Публичных решений» на дашборде и серии «Опубликованные» на графике «Решения». Данные уже в базе, новых запросов к Stepik не требуется
- Источник: `transform_students` считает solution-комментарии по пользователю → поле `published_solutions` в `student_marts` (модель + миграция `016`); `/api/dashboard/students` отдаёт поле и сортирует по нему (белый список колонок)

### Features (Студенты — серверная пагинация, видны все студенты)
- Список студентов переведён на **серверную пагинацию**: таблица больше не скачивает только первые 200 — каждая страница запрашивается с `/api/dashboard/students?skip=..&limit=..` (страница рендерит реальные строки, старые остаются на экране во время загрузки следующей)
- Сортировка переехала на бэкенд: `GET /dashboard/students?sort=..&order=asc|desc` по любой из 7 колонок (белый список колонок, неизвестные → 400), `NULLS LAST` для даты активности. Схема стрелок/направлений та же
- Список убран из глобального `fetchAll` в `SyncContext` — теперь это отдельная страница; фильтр по курсам (`course_ids`) передаётся, при смене фильтра страница сбрасывается на первую; после завершения синка страница обновляется (`last_sync`)
- Теперь доступны все студенты, а не 200 самых активных (~427 страниц при 7 600 студентах)

### Features (Студенты — сортировка и пагинация таблицы)
- Таблица «Студенты» перенесена на паттерн страниц Решений/Курсов: сортировка по заголовкам (первый клик — «естественный порядок», повторный — наоборот; «Активность» — новые сверху по умолчанию), авто-пагинация под высоту экрана (ResizeObserver, «Страница X из Y» + «← Назад / Вперёд →»), единый стиль `fin-table sol-table`
- Сортировка работает по всем 7 колонкам: Имя, Статус, Курсы, Сертификаты, Решения, Комментарии, Активность; строки с пустой датой активности всегда внизу (`nullLast`)
- Сохранены полоса когорт, цветные бейджи статуса, ссылки на профили и ячейка «Решения» в формате «N (M%)»

### Features (Курсы — колонка «Сертификаты»)
- Колонка «Решения» в таблице курсов заменена на **«Сертификаты»**: количество выданных по курсу сертификатов (`certificates_count` в `/api/courses`, источник — `student_enrollments.certificate_issued`). Сортировка/пагинация колонки сохранены

### Features (UI — сайдбар и таблицы «Решений»)
- Кнопки навигации сайдбара выровнены по высоте: фиксированные 50px (`h-[50px]`) + `leading-none` у иконок — раньше эмодзи (📖, 🎓) раздували кнопки, а `iconScale` (transform) не влиял на layout
- Колонки-«группы» в таблицах «Решений» (Месяц / Год / Курс / Шаг) окрашены в серый `text-gray-300` — раньше были белыми
- Колонка «Месяц» на вкладке «По месяцам» показывает формат «год месяц» («2026 Январь» вместо «Январь 2026»), сортировка не затронута

### Features (Решения — «Шаг» = путь модуль.урок-шаг)
- Колонка «Step ID» в «Самых сложных» переименована в **«Шаг»** и показывает путь до шага на Stepik: `3.7-2` = модуль 3, урок 7 (сквозной номер в курсе), шаг 2. Модуль — `raw_section.position`, урок — сумма уроков предыдущих модулей + `raw_unit.position`, шаг — позиция в `raw_lesson.steps`; fallback на `stepik_step_id`, если данных структуры нет. Ссылка на Stepik (`lesson_id`/`step_number`) сохранена, в тултипе — **название модуля — название урока** (`raw_section.title`/`raw_lesson.title`; fallback: курс + числовой ID)
- API `/dashboard/hardest-steps` отдаёт `module_number`, `lesson_number`, `module_title`, `lesson_title` для каждого шага

### Features (Решения — «Успех» и «Взв. успех»)
- «Успех» во всех 4 вкладках «Решений» — это нижняя граница 95% доверительного интервала (Wilson), а не `correct/total`: чем меньше попыток, тем сильнее число занижается (малым объёмом верить нельзя); чем больше попыток, тем ближе к наблюдённому. 1 верная из 5 (20%) → 3.6%, 200 из 1000 (20%) → 17.6%
- Новая колонка **«Взв. успех»**: наблюдённый процент, притянутый к среднему по шагам (`weighted_success_pct()`), — шаги с 1–2 попытками не всплывают в топ «Самых сложных», а реальные проблемы (много попыток + низкий успех) видны. Показывается только на вкладке «Самые сложные»
- «Самые сложные» сортируются по `weighted_success_pct` (в Python, не в SQL) — мусор с мизерным числом попыток остаётся в середине
- API отдаёт `success_pct` и `weighted_success_pct` для всех группировок: `GET /dashboard/submissions` (months/years/by_course) и `GET /dashboard/hardest-steps`
- Общие хелперы `wilson_success_pct()` и `weighted_success_pct()` в `app/api/dashboard/common.py`

### Backend (fix)
- **Regression fix:** решения не синхронизировались — Stepik API не возвращает `step` в объекте submission (шаг известен только из контекста `?step=`); `transform_submissions` пропускал все строки. Шаг переведён в колонку `raw_submission.step` (миграция 015, loader-injected через `extra_columns`), transform читает колонку, fallback через `raw_attempt.step` по `submission.attempt`. Бэкфилл существующих строк
- **Архитектура против «молчаливых нулей»:** новый live-PG тест `test_pg_transforms_produce_fresh_rows` — трансформы на реальных данных обязаны производить строки и догонять raw-слой по времени (регрессия «0 submissions upserted» не могла бы пройти незамеченной)
- `scripts/sync_raw.py` (step-режим): та же запись `step` в колонку при загрузке submissions
- Маппинг-покрытие schema-contract: allowlist `LOADER_INJECTED_COLUMNS` для контекстных колонок без маппинга

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

### Features (Решения — колонка «Студенты»)
- Колонка «Студенты» во всех 4 вкладках «Решений» (По месяцам / По годам / По курсам / Самые сложные): уникальные студенты, отправлявшие решения в группировке — `COUNT(DISTINCT submissions.user_id)` (`is_author=False`, NULL игнорируются)
- Годы считают `students` отдельным запросом (не суммой по месяцам — студент с отправками в нескольких месяцах одного года посчитался бы дважды)
- Верхние KPI-плашки: Всего решений / Правильных / Неправильных (белые) + Успех (цвет как в колонке: красный <33%, жёлтый <66%, зелёный ≥66%)

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
- Убраны loading-заглушки со всех страниц (Dashboard, Courses, Students, Activities, Financials, Solutions): страницы рендерят реальные элементы с пустыми данными, никаких скелетонов и «Загрузка...» — нет дёрганья экрана
- Вкладки «Финансы» и «Решения» видны всегда (пустые таблицы), без сообщений «данные недоступны»
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
