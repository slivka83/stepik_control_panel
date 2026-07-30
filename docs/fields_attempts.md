# Поля попыток (raw_attempt)

Всего полей: 8. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | dataset | jsonb |  | данные задания |
| 2 | dataset_url | text |  | ссылка на dataset |
| 3 | id | integer | да | ID попытки (→ attempt_id) |
| 4 | status | text | да | статус (active/successful/failed) |
| 5 | step | integer | да | ID шага |
| 6 | time | text | да | время начала |
| 7 | time_left | text | да | оставшееся время (сек) |
| 8 | user | integer | да | ID пользователя |
