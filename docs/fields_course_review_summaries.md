# Поля сводок отзывов (raw_course_review_summary)

Всего полей: 5. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | id | integer | да | ID сводки (→ review_summary_id) |
| 2 | average | numeric | да | средний рейтинг |
| 3 | count | integer | да | количество отзывов |
| 4 | course | integer | да | ID курса |
| 5 | distribution | jsonb | да | распределение оценок |
