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
  - `GET /submissions?course=` — отправки решений (отключён из-за производительности)
  - `GET /course-benefit-by-months` — финансовые данные
  - `GET /course-benefits` — детали по курсам
  - `GET /course-review-summaries?ids[]=` — рейтинги и отзывы (side-loading по ID из `courses.review_summary`)
  - `GET /comments?course=` — комментарии студентов

### Важные нюансы API

- `courses.review_summary` — это **int ID**, а не dict. Для получения `average`/`count` нужен отдельный запрос к `/course-review-summaries`
- `courses.is_published` всегда `None` — используй `courses.is_public` для определения статуса публикации
- Stepik API возвращает максимум 20 комментариев на страницу (игнорирует `page_size > 20`)

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

## База данных (5 таблиц)

| Таблица | Назначение |
|---|---|
| `users` | Авторы/владельцы, зашифрованные токены (Fernet) |
| `courses` | Курсы, health_score |
| `student_enrollments` | Прогресс студентов, когортный статус |
| `submissions` | Отправки решений по шагам (correct/wrong) |
| `financial_snapshots` | Снапшоты финансовой сводки + community (отзывы, рейтинг, комментарии) |

PK — UUID. Токены шифруются через `cryptography.fernet`, ключ `ENCRYPTION_KEY` из `.env`.

## Когортные пороги

| Сегмент | Дни с последней активности |
|---|---|
| Active | ≤ 7 |
| Passive | 8–30 |
| Fading | 30–90 |
| Sleeping | > 90 |

## UI-тема

«Spaceship Control Panel» — тёмный фон, неоновые акценты, glassmorphism-карточки.

Цвета Tailwind:
- `space-black` `#0b0f19` — фон
- `space-gray` `#162032` — панели
- `cyber-blue` `#38bdf8` — базовые элементы / яркий синий на диаграмме
- `neon-green` `#4ade80` — растущие метрики / яркий зелёный на диаграмме
- `amber-alert` `#f59e0b` — предупреждения
- `crimson-alert` `#f43f5e` — критические алерты

Дополнительные цвета KPI-карточек (из RevenueChart):
- `dim-green` `#22763d` — тёмный зелёный (оборот, текущий месяц)
- `dim-blue` `#1a6a9e` — тёмный синий (оборот, прошлые месяцы)
- `white` / `text-gray-300` — приглушённый белый (Курсы, Студенты, Сертификаты, Отзывы, Комментарии)

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
- **Ряд 1:** Доход /месяц, Доход /весь, Покупки /все, Курсы (опубл.+черновики), Студенты, Сертификаты
- **Ряд 2:** Оборот /месяц, Оборот /весь, Возвраты /все, Средний рейтинг (градиент), Отзывы, Комментарии

Графики используют `CHART_COLORS` из `frontend/src/constants.js`.

## Критерии приёмки

1. Нет ни одного POST/PUT/PATCH/DELETE к `stepik.org` в кодовой базе
2. Рендер дашборда < 2 сек на курсах до 100k студентов
3. Graceful обработка 429 (Retry-After → sleep → 202)
4. Нет захардкоженных секретов — всё из `.env`

## Документация

- `docs/brd.md` — бизнес-требования, модули, бизнес-правила
- `docs/api.md` — справочник по Stepik API
