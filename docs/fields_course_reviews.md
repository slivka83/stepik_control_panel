# Поля отзывов (raw\_course\_review)

Всего полей: 17. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | id | integer | да | ID отзыва (→ review\_id) |
| 2 | course | integer | да | ID курса |
| 3 | user | integer | да | ID автора |
| 4 | score | integer | да | оценка |
| 5 | text | text | да | текст отзыва |
| 6 | reply\_text | text | да | ответ администрации |
| 7 | reply\_created\_at | text | да | дата ответа |
| 8 | reply\_updated\_at | text | да | обновление ответа |
| 9 | reply\_created\_by | text | да | кто ответил |
| 10 | reply\_updated\_by | text | да | кто обновил ответ |
| 11 | create\_date | text | да | дата создания |
| 12 | update\_date | text | да | дата обновления |
| 13 | translations | jsonb |  | переводы |
| 14 | epic\_count | integer | да | epic |
| 15 | abuse\_count | integer | да | жалобы |
| 16 | vote\_delta | integer | да | голоса |
| 17 | vote | text | да | голос |