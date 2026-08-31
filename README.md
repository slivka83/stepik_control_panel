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
./start.sh        # Linux/Mac
start.bat          # Windows
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
| Дашборд | KPI-метрики, алерты по сертификатам, здоровье курсов |
| Курсы | Список курсов, статусы, количество студентов |
| Финансы | Доходы по месяцам, возвраты, чистая выручка, последние платежи |
| Когорты | Сегментация студентов (Active/Passive/Fading/Sleeping) |

## Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI роутеры
│   │   ├── models/       # SQLAlchemy модели
│   │   ├── services/     # Бизнес-логика (sync, stepik_api, crypto)
│   │   └── config.py     # Настройки из .env
│   ├── migrations/       # Миграции БД (Alembic)
│   ├── tests/            # Backend тесты (pytest)
│   │   ├── conftest.py   # Фикстуры, test DB engine
│   │   └── test_*.py     # Модульные тесты API и бизнес-логики
│   ├── pytest.ini        # Конфигурация pytest (asyncio_mode=auto)
│   ├── requirements.txt  # Python зависимости
│   └── requirements-test.txt  # Тестовые зависимости
├── frontend/
│   ├── src/
│   │   ├── components/   # React компоненты
│   │   ├── pages/        # Страницы (Dashboard, Courses, Financials, Cohorts)
│   │   ├── contexts/     # AuthContext, SyncContext
│   │   ├── constants.jsx # Цвета (CHART_COLORS), лейблы, навигация, когорты
│   │   └── test/         # Frontend тесты (vitest + jsdom)
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml    # PostgreSQL + Redis
├── .env.example          # Шаблон переменных окружения
├── .dockerignore         # Игнорирование файлов для Docker
├── start.sh              # Запуск (Linux/Mac)
└── start.bat             # Запуск (Windows)
```

### Тестирование

```bash
# Backend — 516 тестов + 7 live-PG (нужен docker-compose)
cd backend
python -m pytest tests/ -v

# Frontend — 399 тестов
cd frontend
npx vitest run
```

## База данных

| Таблица | Описание |
|---|---|
| `users` | Авторы, зашифрованные OAuth2 токены (Fernet) |
| `courses` | Курсы автора |
| `student_enrollments` | Прогресс и когортный статус студентов |
| `submissions` | Отправки решений по шагам (correct/wrong) |
| `financial_snapshots` | Финансовая сводка по месяцам и курсам (JSONB) |
| `raw_sync_state` | Инкрементальное состояние загрузки (PK: endpoint_name, key) |

PK — UUID. Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`.

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
| `docs/fields_*.md` | Описания полей эндпоинтов |
| [`AGENTS.md`](AGENTS.md) | Архитектура, синхронизация, тесты |
