# Поля отправок (raw\_submission)

Всего полей: 11. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | attempt | integer | ✅ | да | ID попытки |
| 2 | eta | integer | ✅ | да | ETA проверки |
| 3 | feedback | text | ✅ |  | обратная связь |
| 4 | hint | text | ✅ |  | подсказка |
| 5 | id | integer | ✅ | да | ID отправки (→ submission\_id) |
| 6 | reply | jsonb | ✅ |  | ответ пользователя |
| 7 | reply\_url | text | ✅ |  | временная ссылка на ответ |
| 8 | score | numeric | ✅ | да | балл |
| 9 | session | text | ✅ |  | сессия |
| 10 | status | text | ✅ | да | статус (correct/wrong/evaluation) |
| 11 | time | text | ✅ | да | время отправки |