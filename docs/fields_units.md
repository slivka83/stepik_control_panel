# Поля юнитов (raw\_unit)

Всего полей: 20. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | id | integer | ✅ | да | Уникальный ID юнита |
| 2 | section | integer | ✅ | да | ID родительской секции |
| 3 | lesson | integer | ✅ | да | ID связанного урока |
| 4 | assignments | jsonb | ✅ |  | Массив ID назначений шагов |
| 5 | position | integer | ✅ | да | Позиция юнита в секции |
| 6 | progress | text | ✅ |  | ID прогресса текущего пользователя |
| 7 | actions | jsonb | ✅ |  | Действия текущего пользователя |
| 8 | is\_active | boolean | ✅ | да | Юнит активен |
| 9 | begin\_date | text | ✅ | да | Дата начала |
| 10 | end\_date | text | ✅ | да | Дата окончания |
| 11 | create\_date | text | ✅ | да | Дата создания |
| 12 | update\_date | text | ✅ | да | Дата обновления |
| 13 | begin\_date\_source | text |  |  | Источник даты начала |
| 14 | end\_date\_source | text |  |  | Источник даты окончания |
| 15 | grading\_policy | text |  | да | Политика оценок (no\_deadlines/hard/soft) |
| 16 | grading\_policy\_source | text |  |  | Источник политики оценок |
| 17 | hard\_deadline | text |  | да | Жёсткий дедлайн |
| 18 | hard\_deadline\_source | text |  |  | Источник жёсткого дедлайна |
| 19 | soft\_deadline | text |  | да | Мягкий дедлайн |
| 20 | soft\_deadline\_source | text |  |  | Источник мягкого дедлайна |