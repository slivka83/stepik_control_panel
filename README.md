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

## Быстрый старт

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/slivka83/stepik_control_panel.git
cd stepik_control_panel

# 2. Создайте файл .env по шаблону
cp .env.example .env
# Заполните OAuth2 Client ID/Secret, ENCRYPTION_KEY и данные БД

# 3. Запустите
./start.sh        # Linux/Mac/WSL
start.bat          # Windows
```

PostgreSQL и Redis поднимаются через **Podman** (`podman-compose`) — Docker Desktop не требуется. В Windows `start.bat` сам запускает всё через WSL/Podman, если `podman-compose` установлен. Если нужен Docker вместо Podman:

```bash
CONTAINER_ENGINE=docker ./start.sh
CONTAINER_ENGINE=docker ./stop.sh
```

Порты настраиваются в `.env` (корень проекта):
```
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

Откройте http://localhost:3000

**Примечание:** Файл `.env` должен находиться **в корне проекта**. Скрипты запуска автоматически создают виртуальное окружение Python 3.12 и устанавливают зависимости при первом запуске.

### Миграции БД

```bash
# Применить все миграции
alembic upgrade head

# Посмотреть текущую версию
alembic current
```

## Модули

| Модуль | Описание |
|---|---|
| Дашборд | KPI-метрики, алерты, графики активности и когорт |
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
│   │   ├── components/   # React компоненты
│   │   ├── pages/        # Страницы (Dashboard, Courses, Solutions, Comments, Financials, Students, Activities, Certificates, Reviews)
│   │   ├── contexts/     # AuthContext, SyncContext
│   │   ├── utils/        # format, formatNumber, monthWindow
│   │   ├── constants.jsx # Цвета (CHART_COLORS), лейблы, навигация, когорты
│   │   └── test/         # Frontend тесты (vitest + jsdom)
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml    # PostgreSQL + Redis
├── .env.example          # Шаблон переменных окружения
├── start.sh              # Запуск (Linux/Mac/WSL, Podman)
├── stop.sh               # Остановка (Linux/Mac/WSL)
└── start.bat             # Запуск (Windows)
```

### Тестирование

```bash
# Backend — 520 тестов (нужен запущенный PostgreSQL)
cd backend
python -m pytest tests/ -v

# Frontend — 397 тестов
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
| `raw_*` (24 шт.) | Сырые ответы Stepik API — источник для витрин |
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
| [`docs/api_propose.md`](docs/api_propose.md) | Предложенные эндпоинты Stepik API |
| [`AGENTS.md`](AGENTS.md) | Архитектура, синхронизация, тесты |
