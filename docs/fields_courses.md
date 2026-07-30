# Поля курсов (raw\_course)

Всего полей: 136. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | acquired\_assets | jsonb | ✅ | да | Ресурсы, которые получит студент после прохождения (скиллы, сертификаты) |
| 2 | acquired\_skills | jsonb | ✅ | да | Навыки, которые приобретёт студент |
| 3 | admins\_group | text | ✅ |  | ID группы администраторов курса |
| 4 | announcements | jsonb | ✅ |  | Массив анонсов/объявлений курса |
| 5 | assistants\_group | text | ✅ |  | ID группы ассистентов курса |
| 6 | authors | jsonb | ✅ |  | Массив ID авторов курса |
| 7 | became\_paid\_at | text | ✅ | да | Дата когда курс стал платным |
| 8 | became\_published\_at | text | ✅ | да | Дата когда курс был опубликован |
| 9 | begin\_date\_source | text | ✅ | да | Источник даты начала (устанавливается автором) |
| 10 | certificate | text | ✅ | да | Тип сертификата (regular/distinction) |
| 11 | certificate\_cover\_org | text | ✅ |  | Организация в поле обложки сертификата |
| 12 | certificate\_distinction\_link | text | ✅ |  | Ссылка на сертификат с отличием |
| 13 | certificate\_footer | text | ✅ |  | Текст подвала сертификата |
| 14 | certificate\_link | text | ✅ | да | Ссылка на обычный сертификат |
| 15 | certificate\_regular\_link | text | ✅ |  | Ссылка на обычный сертификат |
| 16 | challenges\_count | text | ✅ | да | Количество испытаний/челленджей |
| 17 | child\_courses | jsonb | ✅ | да | Дочерние курсы (для branching) |
| 18 | child\_courses\_count | text | ✅ | да | Количество дочерних курсов |
| 19 | commission\_basic | text | ✅ | да | Базовая комиссия платформы |
| 20 | commission\_promo | text | ✅ | да | Комиссия платформы по промокоду |
| 21 | content\_details | jsonb | ✅ | да | Детальная информация о контенте |
| 22 | continue\_url | text | ✅ |  | URL для продолжения обучения |
| 23 | course\_format | text | ✅ | да | Формат курса |
| 24 | course\_type | text | ✅ | да | Тип курса |
| 25 | default\_promo\_code\_discount | text | ✅ | да | Скидка промокода по умолчанию |
| 26 | default\_promo\_code\_expire\_date | text | ✅ | да | Дата истечения промокода по умолчанию |
| 27 | default\_promo\_code\_is\_percent\_discount | text | ✅ | да | Скидка в процентах (true/false) |
| 28 | default\_promo\_code\_name | text | ✅ | да | Название промокода по умолчанию |
| 29 | default\_promo\_code\_price | text | ✅ | да | Цена по промокоду по умолчанию |
| 30 | difficulty | text | ✅ | да | Сложность курса (easy/medium/hard) |
| 31 | discussion\_proxy | text | ✅ |  | ID прокси обсуждения курса |
| 32 | discussion\_threads | jsonb | ✅ |  | ID веток обсуждений курса |
| 33 | end\_date\_source | text | ✅ |  | Источник даты окончания (устанавливается автором) |
| 34 | first\_deadline | text | ✅ | да | Дата первого дедлайна |
| 35 | grading\_policy | text | ✅ | да | Политика оценивания |
| 36 | grading\_policy\_source | text | ✅ |  | Источник политики оценивания |
| 37 | hard\_deadline | text | ✅ | да | Жёсткий дедлайн |
| 38 | hard\_deadline\_source | text | ✅ |  | Источник жёсткого дедлайна |
| 39 | has\_tutors | text | ✅ |  | Есть тьюторы на курсе |
| 40 | instructor\_reviews\_count | text | ✅ |  | Количество рецензий от инструкторов |
| 41 | intro\_video | text | ✅ |  | ID вступительного видео |
| 42 | is\_censored | text | ✅ | да | Контент проверен цензурой |
| 43 | is\_certificate\_auto\_issued | text | ✅ | да | Сертификат выдаётся автоматически |
| 44 | is\_certificate\_with\_score | text | ✅ |  | Сертификат с отображением баллов |
| 45 | is\_contest | text | ✅ |  | Курс является соревнованием |
| 46 | is\_idea\_compatible | text | ✅ |  | Совместимость с Idea платформой |
| 47 | is\_in\_wishlist | text | ✅ |  | Курс в списке желаемого у текущего пользователя |
| 48 | is\_popular | text | ✅ | да | Курс отмечен как популярный |
| 49 | is\_processed\_with\_paddle | text | ✅ |  | Обработка платежей через Paddle |
| 50 | is\_proctored | text | ✅ |  | Прокторинг включён |
| 51 | is\_unsuitable | text | ✅ |  | Курс непригоден (помечен модератором) |
| 52 | issue | text | ✅ |  | ID связанного issue/тикета |
| 53 | last\_deadline | text | ✅ |  | Дата последнего дедлайна |
| 54 | last\_step | text | ✅ |  | Последний шаг в формате lesson\_id-step\_id |
| 55 | last\_update\_price\_date | text | ✅ | да | Дата последнего изменения цены |
| 56 | learners\_group | text | ✅ |  | ID группы обучающихся |
| 57 | learners\_limit | text | ✅ | да | Лимит обучающихся на курс |
| 58 | learning\_format | text | ✅ | да | Описание формата обучения |
| 59 | lti\_consumer\_key | text | ✅ |  | LTI consumer key для интеграции |
| 60 | lti\_private\_profile | text | ✅ |  | LTI скрывает профиль пользователя |
| 61 | lti\_secret\_key | text | ✅ |  | LTI секретный ключ для интеграции |
| 62 | moderators\_group | text | ✅ |  | ID группы модераторов курса |
| 63 | options | jsonb | ✅ | да | Дополнительные настройки курса |
| 64 | parent\_courses | jsonb | ✅ |  | Родительские курсы (для branching) |
| 65 | peer\_reviews\_count | text | ✅ |  | Количество взаимных рецензий |
| 66 | position | text | ✅ | да | Позиция курса в каталоге/подборке |
| 67 | possible\_currencies | jsonb | ✅ | да | Доступные валюты для оплаты |
| 68 | possible\_type | text | ✅ | да | Возможный тип курса при смене |
| 69 | preview\_lesson | text | ✅ | да | ID урока для превью |
| 70 | preview\_unit | text | ✅ | да | ID юнита для превью |
| 71 | price\_tier | text | ✅ | да | Ценовой уровень/категория |
| 72 | proctor\_url | text | ✅ |  | URL прокторинг-сессии |
| 73 | product\_kind | text | ✅ | да | Вид продукта (plain/bundle/…) |
| 74 | readiness | text | ✅ | да | Готовность курса (0.0-1.0) |
| 75 | referral\_link | text | ✅ | да | Реферальная ссылка |
| 76 | requirements | text | ✅ | да | Требования к обучающимся |
| 77 | schedule\_link | text | ✅ | да | Ссылка на расписание |
| 78 | schedule\_long\_link | text | ✅ | да | Полная ссылка на расписание |
| 79 | social\_providers | jsonb | ✅ | да | Провайдеры соцсетей для курса |
| 80 | soft\_deadline | text | ✅ | да | Мягкий дедлайн |
| 81 | soft\_deadline\_source | text | ✅ |  | Источник мягкого дедлайна |
| 82 | subscriptions | jsonb | ✅ | да | ID подписок на курс |
| 83 | tags | jsonb | ✅ | да | Теги курса |
| 84 | target\_audience | text | ✅ | да | Целевая аудитория курса |
| 85 | teachers\_group | text | ✅ |  | ID группы преподавателей |
| 86 | testers\_group | text | ✅ |  | ID группы тестировщиков |
| 87 | user\_certificate | text | ✅ |  | Сертификат текущего пользователя |
| 88 | videos\_duration | text | ✅ | да | Суммарная длительность видео в секундах |
| 89 | with\_certificate | text | ✅ | да | Курс выдаёт сертификат |
| 90 | actions\_json | jsonb | ✅ |  | Доступные действия текущего пользователя |
| 91 | begin\_date | text | ✅ | да | Дата начала курса |
| 92 | canonical\_url | text | ✅ | да | Канонический URL страницы курса |
| 93 | certificate\_distinction\_threshold | text | ✅ | да | Порог баллов для сертификата с отличием |
| 94 | certificate\_regular\_threshold | text | ✅ | да | Порог баллов для обычного сертификата |
| 95 | certificates\_count | text | ✅ | да | Количество выданных сертификатов |
| 96 | cover\_url | text | ✅ |  | URL обложки курса |
| 97 | created\_at | text | ✅ | да | Дата создания записи |
| 98 | currency\_code | text | ✅ | да | Код валюты цены |
| 99 | description | text | ✅ | да | Полное описание курса |
| 100 | discussions\_count | text | ✅ | да | Количество обсуждений |
| 101 | display\_price | text | ✅ | да | Форматированная цена для отображения |
| 102 | end\_date | text | ✅ | да | Дата окончания курса |
| 103 | current\_enrollment\_id | text | ✅ |  | ID записи текущего пользователя |
| 104 | first\_lesson\_id | text | ✅ | да | ID первого урока |
| 105 | first\_unit\_id | text | ✅ | да | ID первого юнита |
| 106 | course\_id | text | ✅ | да | Уникальный идентификатор курса |
| 107 | instructor\_ids | jsonb | ✅ |  | Массив ID преподавателей курса |
| 108 | intro\_text | text | ✅ |  | Вступительный текст |
| 109 | is\_active | text | ✅ | да | Курс активен |
| 110 | is\_adaptive | text | ✅ | да | Адаптивный курс |
| 111 | is\_archived | text | ✅ | да | Курс в архиве |
| 112 | is\_certificate\_issued | text | ✅ | да | Сертификаты выдаются |
| 113 | is\_enabled | text | ✅ | да | Курс включен администратором |
| 114 | is\_favorite | text | ✅ |  | Курс в избранном у текущего пользователя |
| 115 | is\_featured | text | ✅ | да | Курс рекомендован платформой |
| 116 | is\_paid | text | ✅ | да | Курс платный |
| 117 | is\_public | text | ✅ | да | Курс виден всем |
| 118 | is\_self\_paced | text | ✅ | да | Курс в собственном темпе |
| 119 | language\_code | text | ✅ | да | Языковой код курса |
| 120 | learners\_count | text | ✅ | да | Количество записавшихся обучающихся |
| 121 | lessons\_count | text | ✅ | да | Количество уроков в курсе |
| 122 | owner\_user\_id | text | ✅ | да | ID владельца курса |
| 123 | price | text | ✅ | да | Цена курса |
| 124 | current\_progress\_id | text | ✅ |  | ID прогресса текущего пользователя |
| 125 | quizzes\_count | text | ✅ | да | Количество квизов |
| 126 | review\_summary\_json | text | ✅ | да | ID сводки отзывов |
| 127 | schedule\_type | text | ✅ | да | Тип расписания |
| 128 | section\_ids | jsonb | ✅ | да | Массив ID секций курса |
| 129 | slug | text | ✅ | да | URL-идентификатор курса для ЧПУ |
| 130 | summary | text | ✅ | да | Краткое описание для карточки курса |
| 131 | time\_to\_complete | text | ✅ | да | Ожидаемое время завершения в секундах |
| 132 | title | text | ✅ | да | Название курса на языке курса |
| 133 | title\_en | text | ✅ | да | Английское название курса |
| 134 | total\_units | text | ✅ | да | Общее количество юнитов в курсе |
| 135 | updated\_at | text | ✅ | да | Дата последнего обновления |
| 136 | workload | text | ✅ | да | Описание нагрузки на обучающегося |

---

✅ — поле описано в meta  
Sync: Да/Нет для каждого поля