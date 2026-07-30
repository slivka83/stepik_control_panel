# Поля секций (raw\_section)

Всего полей: 35. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | actions | jsonb | ✅ | да | Действия текущего пользователя |
| 2 | begin\_date | text | ✅ | да | Дата начала |
| 3 | begin\_date\_source | text |  |  | Источник даты начала |
| 4 | course | integer | ✅ | да | ID родительского курса |
| 5 | create\_date | text | ✅ | да | Дата создания |
| 6 | description | text | ✅ | да | Описание секции |
| 7 | discounting\_policy | text |  | да | Политика скидок |
| 8 | end\_date | text | ✅ | да | Дата окончания |
| 9 | end\_date\_source | text |  |  | Источник даты окончания |
| 10 | exam\_duration\_minutes | integer |  |  | Длительность экзамена (минуты) |
| 11 | exam\_session | text |  |  | ID сессии экзамена |
| 12 | grading\_policy | text |  | да | Политика оценок |
| 13 | grading\_policy\_source | text |  |  | Источник политики оценок |
| 14 | hard\_deadline | text |  | да | Жёсткий дедлайн |
| 15 | hard\_deadline\_source | text |  |  | Источник жёсткого дедлайна |
| 16 | id | integer | ✅ | да | Уникальный ID секции |
| 17 | is\_active | boolean | ✅ | да | Секция активна и видна |
| 18 | is\_exam | boolean | ✅ | да | Секция является экзаменом |
| 19 | is\_exam\_without\_progress | boolean |  |  | Экзамен без отображения прогресса |
| 20 | is\_proctoring\_can\_be\_scheduled | boolean |  |  | Прокторинг может быть запланирован |
| 21 | is\_random\_exam | boolean |  |  | Случайный набор заданий для экзамена |
| 22 | is\_requirement\_satisfied | boolean |  |  | Требования секции выполнены |
| 23 | position | integer | ✅ | да | Порядковый номер секции в курсе |
| 24 | proctor\_session | text |  |  | ID сессии прокторинга |
| 25 | progress | text | ✅ |  | ID прогресса текущего пользователя |
| 26 | random\_exam\_problems\_count | integer |  |  | Количество заданий при случайном выборе |
| 27 | random\_exam\_problems\_course | text |  |  | ID курса для случайного выбора заданий |
| 28 | required\_percent | integer |  | да | Проходной процент для секции |
| 29 | required\_section | text |  |  | ID обязательной секции |
| 30 | slug | text | ✅ | да | URL-идентификатор секции |
| 31 | soft\_deadline | text |  | да | Мягкий дедлайн |
| 32 | soft\_deadline\_source | text |  |  | Источник мягкого дедлайна |
| 33 | title | text | ✅ | да | Название секции |
| 34 | units | jsonb | ✅ | да | Массив ID юнитов в секции |
| 35 | update\_date | text | ✅ | да | Дата обновления |