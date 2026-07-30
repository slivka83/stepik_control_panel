# Поля уроков (raw\_lesson)

Всего полей: 41. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | abuse\_count | integer |  | да | количество жалоб |
| 2 | actions | jsonb | ✅ |  | ссылки действий (learn, edit, statistics) |
| 3 | admins\_group | integer |  |  | ID группы администраторов |
| 4 | assistants\_group | integer |  |  | ID группы ассистентов |
| 5 | canonical\_url | text |  | да | канонический URL урока |
| 6 | courses | jsonb |  | да | список ID курсов, содержащих урок |
| 7 | cover\_url | text | ✅ |  | URL обложки |
| 8 | create\_date | text | ✅ | да | дата создания |
| 9 | discussion\_proxy | text |  |  | прокси для обсуждений |
| 10 | discussion\_threads | jsonb |  |  | треды обсуждений |
| 11 | discussions\_count | integer | ✅ | да | количество комментариев |
| 12 | epic\_count | integer |  | да | количество epic (голосов) |
| 13 | id | integer | ✅ | да | ID урока (→ lesson\_id) |
| 14 | is\_blank | boolean |  | да | пустой урок |
| 15 | is\_comments\_enabled | boolean |  | да | включены комментарии |
| 16 | is\_draft | boolean | ✅ | да | черновик |
| 17 | is\_exam\_without\_progress | boolean |  |  | экзамен без прогресса |
| 18 | is\_featured | boolean | ✅ | да | избранный |
| 19 | is\_orphaned | boolean |  | да | осиротевший (без курса) |
| 20 | is\_public | boolean | ✅ | да | опубликован |
| 21 | language | text | ✅ | да | язык |
| 22 | learners\_group | integer |  |  | ID группы учащихся |
| 23 | lti\_consumer\_key | text |  |  | LTI consumer key |
| 24 | lti\_private\_profile | boolean |  |  | LTI приватный профиль |
| 25 | lti\_secret\_key | text |  |  | LTI secret key |
| 26 | moderators\_group | integer |  |  | ID группы модераторов |
| 27 | owner | integer | ✅ | да | ID владельца |
| 28 | passed\_by | integer |  | да | количество сдавших |
| 29 | progress | text | ✅ | да | URL прогресса |
| 30 | slug | text | ✅ | да | slug |
| 31 | steps | jsonb | ✅ | да | список ID шагов |
| 32 | subscriptions | jsonb |  |  | подписки |
| 33 | teachers\_group | integer |  |  | ID группы учителей |
| 34 | testers\_group | integer |  |  | ID группы тестеров |
| 35 | time\_to\_complete | integer | ✅ | да | время на прохождение (мин) |
| 36 | title | text | ✅ | да | название |
| 37 | units | jsonb |  | да | список ID юнитов |
| 38 | update\_date | text | ✅ | да | дата обновления |
| 39 | viewed\_by | integer |  | да | количество просмотревших |
| 40 | vote | text |  | да | голосование |
| 41 | vote\_delta | integer |  | да | дельта голосов |