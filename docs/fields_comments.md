# Поля комментариев (raw_comment)

Всего полей: 34. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | abuse_count | integer | да | количество жалоб |
| 2 | actions | jsonb |  | доступные действия |
| 3 | attachments | jsonb |  | вложения |
| 4 | can_delete | boolean |  | можно удалить |
| 5 | can_edit | boolean |  | можно редактировать |
| 6 | can_moderate | boolean |  | можно модерировать |
| 7 | deleted_at | text | да | дата удаления |
| 8 | deleted_by | text | да | кем удалён |
| 9 | edited_at | text | да | дата редактирования |
| 10 | edited_by | text | да | кем отредактирован |
| 11 | epic_count | integer | да | количество epic |
| 12 | id | integer | да | ID комментария (→ comment_id) |
| 13 | is_banned | boolean | да | забанен |
| 14 | is_deleted | boolean | да | удалён |
| 15 | is_pinned | boolean | да | закреплён |
| 16 | is_reported | boolean | да | пожаловались |
| 17 | is_staff_replied | boolean | да | ответ сотрудника |
| 18 | last_time | text | да | последнее время |
| 19 | parent | text | да | родительский комментарий |
| 20 | pinned_at | text |  | дата закрепления |
| 21 | pinned_by | text |  | кто закрепил |
| 22 | replies | jsonb |  | ответы |
| 23 | reply_count | integer | да | количество ответов |
| 24 | submission | integer | да | ID отправки |
| 25 | subscriptions | jsonb |  | подписки |
| 26 | target | integer | да | ID цели (шаг/урок) |
| 27 | text | text | да | текст |
| 28 | thread | text |  | тред |
| 29 | time | text | да | время |
| 30 | translations | jsonb |  | переводы |
| 31 | user | integer | да | ID пользователя |
| 32 | user_role | text |  | роль |
| 33 | vote | text | да | голос |
| 34 | vote_delta | integer | да | дельта голосов |