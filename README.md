# Stepik Control Panel

CRM/BI-панель для авторов курсов на платформе [Stepik](https://stepik.org). Аналитика, финансы, удержание студентов в одном окне.

> **Режим чтения:** Все данные берутся из Stepik API. Прямая модификация данных на платформе исключена. Интерактивные действия реализуются через Deep Links на оригинальный интерфейс Stepik.

---

## ⚠️ Дисклеймер

**Используйте программу на свой страх и риск.**

Автор не несёт никакой ответственности за любой прямой или косвенный ущерб, причинённый использованием данного программного обеспечения. Несмотря на то, что программа работает **только на чтение** данных из Stepik API и не модифицирует данные на платформе, автор не гарантирует отсутствие негативных последствий, включая, но не ограничиваясь:

- Блокировку аккаунта Stepik из-за повышенной нагрузки на API
- Неверное отображение данных или принятие решений на основе некорректной аналитики
- Любые иные убытки, возникающие в результате использования программы

OAuth2 токены хранятся в зашифрованном виде в локальной базе данных. При этом пользователь несёт ответственность за защиту своего `.env` файла и базы данных от несанкционированного доступа.

---

## Технологии

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler
- **Frontend:** React 18+, Vite, Tailwind CSS v3, Recharts
- **База данных:** PostgreSQL 16, Redis 7
- **Шрифты:** Inter (текст), JetBrains Mono (числовые показателя, ID, финансы)
- **Что установить:** Node.js + npm, [uv](https://docs.astral.sh/uv/) (ставит Python-окружение), Podman + podman-compose (или Docker)

## Быстрый старт

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/slivka83/stepik_control_panel.git
cd stepik_control_panel

# 2. Создайте файл .env по шаблону
cp .env.example .env
# Заполните OAuth2 Client ID/Secret, ENCRYPTION_KEY и данные БД

# 3. Запустите
start.bat          # Windows (Podman)
./start.sh         # Linux/Mac/WSL
```

PostgreSQL и Redis поднимаются через **Podman** — Docker Desktop не требуется. На Windows `start.bat` использует установленный Podman и постоянные тома; на Linux/WSL — `podman-compose` (или Docker: `CONTAINER_ENGINE=docker ./start.sh`).

Порты настраиваются в `.env` (корень проекта):
```
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

Откройте http://localhost:3000

**Примечание:** Файл `.env` должен находиться **в корне проекта**. Скрипты запуска автоматически применяют миграции. Если виртуальное окружение или `node_modules` ещё не созданы, `start.bat` сообщит, чего не хватает.

### Данные и бэкапы

Данные панели живут в постоянных томах Podman (`stepik_pgdata`, `stepik_redisdata`) и **не удаляются** при остановке или перезапуске.

- `start.bat` никогда не пересоздаёт базу. Если том пропал, а в `backups/` есть дамп — база восстанавливается из последнего бэкапа.
- Если порт базы (5433) занят посторонним процессом, запуск останавливается с ошибкой: панель не подключится к чужой или пустой базе.
- Бэкап делается автоматически при запуске (если последнему больше суток) и при остановке; вручную — `backup.bat`. Хранятся последние 10 дампов в `backups/` (в Git не попадают).
- Остановка — `stop.bat` (контейнеры и тома сохраняются).

> **Важно:** не выполняйте `podman volume rm`, `podman volume prune` и `podman compose down -v` — это удаляет данные панели.

### Миграции БД

`start.sh` / `start.bat` применяют миграции автоматически. Вручную (из папки `backend`):

```bash
alembic upgrade head

# Посмотреть текущую версию
alembic current
```

## Модули

| Модуль | Описание |
|---|---|
| Дашборд | KPI-метрики, алерты, графики активности и когорт |
| Активности | Графики решений, комментариев, активных студентов и сертификатов |
| Курсы | Список курсов, тепловая карта шагов, воронка прохождения |
| Решения | Отправки по месяцам/годам/курсам, самые сложные шаги |
| Комментарии | Агрегаты по месяцам/годам/курсам, неотвеченные, дизлайки |
| Финансы | Доходы по месяцам/годам/дням/курсам, промокоды, UTM, последние операции |
| Студенты | Таблица студентов с серверной пагинацией, сегментация (Active/Passive/Fading/Sleeping/Zombie) |
| Сертификаты | Выдача по месяцам/годам/курсам, «С отличием» vs обычные |
| Отзывы | Оценки и тексты отзывов по месяцам/годам/курсам |

## Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI роутеры (auth, courses, financials, sync, dashboard/)
│   │   ├── models/       # SQLAlchemy модели (курсы, mart_*, student_marts)
│   │   ├── services/     # Бизнес-логика (raw_sync, transform, sync, stepik_api, crypto)
│   │   └── config.py     # Настройки из .env
│   ├── migrations/       # Миграции БД (Alembic)
│   ├── tests/            # Backend тесты (pytest)
│   │   ├── conftest.py   # Фикстуры, test DB engine
│   │   └── test_*.py     # Модульные тесты API и бизнес-логики
│   ├── scripts/         # Скрипты: sync_raw.py (API→raw), rebuild_marts.py (raw→витрины), explore_endpoint.py
│   ├── pytest.ini        # Конфигурация pytest (asyncio_mode=auto)
│   ├── requirements.txt  # Python зависимости
│   └── requirements-test.txt  # Тестовые зависимости
├── frontend/
│   ├── src/
│   │   ├── components/   # React компоненты (таблицы, вкладки, графики)
│   │   ├── pages/        # Страницы + конфигурации колонок (pages/*/columns.jsx)
│   │   ├── hooks/        # useTabState, useTabSorts, useServerTable
│   │   ├── contexts/     # AuthContext, SyncContext
│   │   ├── utils/        # format, formatNumber, monthWindow, financials
│   │   ├── api.js / config.js / session.js
│   │   ├── constants.jsx # Цвета (CHART_COLORS), лейблы, навигация, когорты
│   │   └── test/         # Frontend тесты (vitest + jsdom)
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml    # PostgreSQL + Redis (Linux/WSL)
├── scripts/              # Windows: start.ps1, stop.ps1, backup.ps1
├── backups/              # Дампы базы (создаётся автоматически, не в Git)
├── .env.example          # Шаблон переменных окружения
├── start.sh              # Запуск (Linux/Mac/WSL, Podman)
├── stop.sh               # Остановка (Linux/Mac/WSL)
├── start.bat             # Запуск (Windows)
├── stop.bat              # Остановка (Windows)
└── backup.bat            # Бэкап базы (Windows)
```

### Тестирование

```bash
# Backend — 576 тестов (live-PG проверки пропускаются без запущенного PostgreSQL)
cd backend
python -m pytest tests/ -v

# Frontend — 446 тестов
cd frontend
npx vitest run
```

## База данных

Данные идут в два слоя: сырые ответы Stepik API (`raw_*`) и производные витрины, из которых читает API.

| Таблица | Описание |
|---|---|
| `users` | Авторы, зашифрованные OAuth2 токены (Fernet) |
| `courses` | Курсы автора |
| `student_enrollments` | Прогресс и когортный статус студентов |
| `submissions` | Отправки решений по шагам (correct/wrong) |
| `student_marts` | Витрина студентов: одна строка на студента |
| `financial_snapshots` | Финансовая сводка по месяцам и курсам + community (JSONB) |
| `mart_modules` / `mart_lessons` / `mart_steps` | Витрина структуры курса с метриками шагов |
| `mart_comments` / `mart_reviews` / `mart_certificates` | Витрины комментариев, отзывов и сертификатов |
| `raw_*` (17 базовых) | Сырые ответы Stepik API — источник для витрин; дополнительные зеркала создаёт `explore_endpoint.py` |
| `raw_sync_state` | Инкрементальное состояние загрузки (PK: endpoint_name, key) |
| `meta_endpoint` / `meta_field_mapping` | Реестр эндпоинтов и маппинг полей API → колонки |

PK — UUID (кроме `raw_sync_state`). Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`. Пересобрать витрины из сырого слоя без обращений к API: `python scripts/rebuild_marts.py`.

### Миграции

Миграции применяются через Alembic:

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "описание"

# Применить все миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

## Документация

| Файл | Описание |
|---|---|
| [`docs/api_propose.md`](docs/api_propose.md) | Архивный каталог полей Stepik API (не схема БД) |
| [`AGENTS.md`](AGENTS.md) | Архитектура, синхронизация, тесты |
