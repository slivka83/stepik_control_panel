# Поля оценок курса (raw_course_grade)

Всего полей: 17. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | id | integer | да | ID записи (→ course_grade_id) |
| 2 | course | integer | да | ID курса |
| 3 | user | integer | да | ID пользователя |
| 4 | results | jsonb | да | результаты по секциям |
| 5 | score | numeric | да | итоговый балл |
| 6 | rank | text | да | ранг |
| 7 | rank_max | text | да | макс. ранг |
| 8 | rank_position | text | да | позиция в рейтинге |
| 9 | users_count | text | да | всего пользователей |
| 10 | is_teacher | boolean | да | преподаватель |
| 11 | date_joined | text | да | дата записи |
| 12 | last_viewed | text | да | последний просмотр |
| 13 | certificate_issue_date | text | да | дата выдачи сертификата |
| 14 | certificate_url | text | да | URL сертификата |
| 15 | certificate_issue_distinction_date | text |  | дата сертификата с отличием |
| 16 | certificate_issue_regular_date | text |  | дата обычного сертификата |
| 17 | certificate_update_date | text |  | дата обновления сертификата |
