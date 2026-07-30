**endpoint:** `/api/courses?ids[]=`  
**method:** GET  
**api\_object:** course  
**target\_table:** `dim_stepik__course`  
**download:** Да  
**primary\_key:** course\_id  
**incremental:** update\_date  
**description:** Каталог курсов Stepik. Содержит всю основную информацию о курсе: название, описание, обложку, цену, язык, публичность, сертификаты, инструкторов, секции, счетчики обучающихся и уроков, расписание, отзывы. Это корневая сущность всей платформы — без неё невозможно построить ни одну аналитическую модель. Качать обязательно.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_id | bigint | Уникальный идентификатор курса | Да | PK | dim\_stepik\_\_course.course\_id |
| title | title | text | Название курса на языке курса | Да | \- | \- |
| title\_en | title\_en | text | Английское название курса | Да | \- | \- |
| slug | slug | text | URL-идентификатор курса для ЧПУ | Да | UQ | \- |
| summary | summary | text | Краткое описание для карточки курса | Да | \- | \- |
| description | description | text | Полное описание курса | Да | \- | \- |
| cover | cover\_url | text | URL обложки курса | Да | \- | \- |
| intro | intro\_text | text | Вступительный текст | Да | \- | \- |
| workload | workload | text | Описание нагрузки на обучающегося | Да | \- | \- |
| instructors | instructor\_ids | jsonb | Массив ID преподавателей курса | Да | FK\_array | bridge\_stepik\_\_course\_instructor.user\_id=>dim\_stepik\_\_user.user\_id |
| sections | section\_ids | jsonb | Массив ID секций курса | Да | FK\_array | bridge\_stepik\_\_course\_section.section\_id=>dim\_stepik\_\_section.section\_id |
| total\_units | total\_units | int | Общее количество юнитов в курсе | Да | \- | \- |
| lessons\_count | lessons\_count | int | Количество уроков | Да | \- | \- |
| learners\_count | learners\_count | int | Количество записавшихся обучающихся | Да | \- | \- |
| certificates\_count | certificates\_count | int | Количество выданных сертификатов | Да | \- | \- |
| quizzes\_count | quizzes\_count | int | Количество квизов | Да | \- | \- |
| is\_paid | is\_paid | boolean | Курс платный | Да | \- | \- |
| price | price | numeric | Цена курса | Да | \- | \- |
| currency\_code | currency\_code | text | Код валюты цены | Да | \- | \- |
| display\_price | display\_price | text | Форматированная цена для отображения | Да | \- | \- |
| is\_adaptive | is\_adaptive | boolean | Адаптивный курс | Да | \- | \- |
| is\_self\_paced | is\_self\_paced | boolean | Курс в собственном темпе | Да | \- | \- |
| is\_public | is\_public | boolean | Курс виден всем | Да | \- | \- |
| is\_featured | is\_featured | boolean | Курс рекомендован платформой | Да | \- | \- |
| is\_active | is\_active | boolean | Курс активен | Да | \- | \- |
| is\_archived | is\_archived | boolean | Курс в архиве | Да | \- | \- |
| is\_enabled | is\_enabled | boolean | Курс включен администратором | Да | \- | \- |
| is\_certificate\_issued | is\_certificate\_issued | boolean | Сертификаты выдаются | Да | \- | \- |
| certificate\_regular\_threshold | certificate\_regular\_threshold | numeric | Порог баллов для обычного сертификата | Да | \- | \- |
| certificate\_distinction\_threshold | certificate\_distinction\_threshold | numeric | Порог баллов для сертификата с отличием | Да | \- | \- |
| review\_summary | review\_summary\_json | jsonb | Агрегированная сводка отзывов | Да | \- | \- |
| schedule\_type | schedule\_type | text | Тип расписания | Да | \- | \- |
| time\_to\_complete | time\_to\_complete | int | Ожидаемое время завершения в секундах | Да | \- | \- |
| owner | owner\_user\_id | bigint | ID владельца курса | Да | FK | dim\_stepik\_\_user.user\_id |
| language | language\_code | text | Языковой код курса | Да | \- | \- |
| first\_lesson | first\_lesson\_id | bigint | ID первого урока | Да | FK | dim\_stepik\_\_lesson.lesson\_id |
| first\_unit | first\_unit\_id | bigint | ID первого юнита | Да | FK | dim\_stepik\_\_unit.unit\_id |
| enrollment | current\_enrollment\_id | bigint | ID записи текущего пользователя | Нет | FK | fact\_stepik\_\_enrollment.enrollment\_id |
| progress | current\_progress\_id | text | ID прогресса текущего пользователя | Нет | FK | fact\_stepik\_\_progress.progress\_id |
| is\_favorite | is\_favorite | boolean | Курс в избранном у текущего пользователя | Нет | \- | \- |
| actions | actions\_json | jsonb | Доступные действия текущего пользователя | Нет | \- | \- |
| begin\_date | begin\_date | timestamptz | Дата начала курса | Да | \- | \- |
| end\_date | end\_date | timestamptz | Дата окончания курса | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата создания записи | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Дата последнего обновления | Да | \- | \- |
| discussions\_count | discussions\_count | int | Количество обсуждений | Да | \- | \- |
| canonical\_url | canonical\_url | text | Канонический URL страницы курса | Да | \- | \- |

---

**endpoint:** `/api/sections?ids[]=`  
**method:** GET  
**api\_object:** section  
**target\_table:** `dim_stepik__section`  
**download:** Да  
**incremental:** update\_date  
**primary\_key:** section\_id  
**description:** Секции (модули) курса. Каждая секция группирует юниты внутри курса. Содержит название, позицию, ссылку на курс, массив юнитов, флаги экзамена, даты начала/окончания. Без секций невозможно понять структуру курса и порядок прохождения. Качать обязательно вместе с курсами.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | section\_id | bigint | Уникальный ID секции | Да | PK | dim\_stepik\_\_section.section\_id |
| course | course\_id | bigint | ID родительского курса | Да | FK | dim\_stepik\_\_course.course\_id |
| units | unit\_ids | jsonb | Массив ID юнитов в секции | Да | FK\_array | bridge\_stepik\_\_section\_unit.unit\_id=>dim\_stepik\_\_unit.unit\_id |
| position | position | int | Порядковый номер секции в курсе | Да | \- | \- |
| title | title | text | Название секции | Да | \- | \- |
| slug | slug | text | URL-идентификатор секции | Да | \- | \- |
| description | description | text | Описание секции | Да | \- | \- |
| is\_exam | is\_exam | boolean | Секция является экзаменом | Да | \- | \- |
| is\_active | is\_active | boolean | Секция активна и видна | Да | \- | \- |
| progress | progress\_id | text | ID прогресса текущего пользователя | Нет | FK | fact\_stepik\_\_progress.progress\_id |
| actions | actions\_json | jsonb | Действия текущего пользователя | Нет | \- | \- |
| begin\_date | begin\_date | timestamptz | Дата начала | Да | \- | \- |
| end\_date | end\_date | timestamptz | Дата окончания | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата создания | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Дата обновления | Да | \- | \- |

---

**endpoint:** `/api/units?ids[]=`  
**method:** GET  
**api\_object:** unit  
**target\_table:** `dim_stepik__unit`  
**download:** Да  
**incremental:** update\_date  
**primary\_key:** unit\_id  
**description:** Юниты — промежуточный объект между секцией и уроком. Один урок может входить в несколько юнитов разных курсов. Юнит хранит ссылку на секцию, ссылку на урок, позицию, назначения и даты. Без юнитов невозможно корректно связать структуру курса с уроками. Качать обязательно.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | unit\_id | bigint | Уникальный ID юнита | Да | PK | dim\_stepik\_\_unit.unit\_id |
| section | section\_id | bigint | ID родительской секции | Да | FK | dim\_stepik\_\_section.section\_id |
| lesson | lesson\_id | bigint | ID связанного урока | Да | FK | dim\_stepik\_\_lesson.lesson\_id |
| assignments | assignment\_ids | jsonb | Массив ID назначений шагов | Нет | FK\_array | fact\_stepik\_\_assignment.assignment\_id |
| position | position | int | Позиция юнита в секции | Да | \- | \- |
| progress | progress\_id | text | ID прогресса текущего пользователя | Нет | FK | fact\_stepik\_\_progress.progress\_id |
| actions | actions\_json | jsonb | Действия текущего пользователя | Нет | \- | \- |
| is\_active | is\_active | boolean | Юнит активен | Да | \- | \- |
| begin\_date | begin\_date | timestamptz | Дата начала | Да | \- | \- |
| end\_date | end\_date | timestamptz | Дата окончания | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата создания | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Дата обновления | Да | \- | \- |

---

**endpoint:** `/api/lessons?ids[]=`  
**method:** GET  
**api\_object:** lesson  
**target\_table:** `dim_stepik__lesson`  
**download:** Да  
**incremental:** update\_date  
**primary\_key:** lesson\_id  
**description:** Уроки. Содержат массив шагов, владельца, язык, обложку, время прохождения, статусы публичности и черновика, счетчики обсуждений. Урок — это контейнер для шагов. Один урок может переиспользоваться в нескольких курсах через разные юниты. Качать обязательно.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | lesson\_id | bigint | Уникальный ID урока | Да | PK | dim\_stepik\_\_lesson.lesson\_id |
| title | title | text | Название урока | Да | \- | \- |
| slug | slug | text | URL-идентификатор урока | Да | \- | \- |
| steps | step\_ids | jsonb | Массив ID шагов урока | Да | FK\_array | bridge\_stepik\_\_lesson\_step.step\_id=>dim\_stepik\_\_step.step\_id |
| owner | owner\_user\_id | bigint | ID владельца урока | Да | FK | dim\_stepik\_\_user.user\_id |
| cover\_url | cover\_url | text | URL обложки урока | Да | \- | \- |
| time\_to\_complete | time\_to\_complete | int | Ожидаемое время прохождения | Да | \- | \- |
| is\_public | is\_public | boolean | Урок публичный | Да | \- | \- |
| is\_featured | is\_featured | boolean | Урок рекомендован | Да | \- | \- |
| is\_draft | is\_draft | boolean | Урок в черновике | Да | \- | \- |
| language | language\_code | text | Язык урока | Да | \- | \- |
| progress | progress\_id | text | Прогресс текущего пользователя | Нет | FK | fact\_stepik\_\_progress.progress\_id |
| actions | actions\_json | jsonb | Действия текущего пользователя | Нет | \- | \- |
| discussions\_count | discussions\_count | int | Количество обсуждений | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата создания | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Дата обновления | Да | \- | \- |

---

**endpoint:** `/api/steps?ids[]=`  
**method:** GET  
**api\_object:** step  
**target\_table:** `dim_stepik__step`  
**download:** Да  
**incremental:** update\_date  
**primary\_key:** step\_id  
**description:** Шаги — атомарные единицы контента. Каждый шаг содержит блок с типом (текст, видео, квиз, код), текст задания, видео, опции, субтитры. Также хранит метрики: correct\_ratio, worth, количество обсуждений, ограничения отправок. Это ядро контента — без шагов нет заданий. Качать обязательно.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | step\_id | bigint | Уникальный ID шага | Да | PK | dim\_stepik\_\_step.step\_id |
| lesson | lesson\_id | bigint | ID родительского урока | Да | FK | dim\_stepik\_\_lesson.lesson\_id |
| position | position | int | Позиция шага в уроке | Да | \- | \- |
| status | status | text | Статус шага | Да | \- | \- |
| block | block\_json | jsonb | Полный блок контента и задания | Нет | \- | \- |
| [block.name](http://block.name) | block\_type | text | Тип блока: text, video, choice, code, math | Да | \- | \- |
| block.text | block\_text | text | Текстовое содержимое шага | Нет | \- | \- |
| block.video | block\_video\_json | jsonb | Метаданные видео | Да | \- | \- |
| block.options | block\_options\_json | jsonb | Опции задания: варианты ответов, формулы | Нет | \- | \- |
| block.subtitle\_files | subtitle\_files\_json | jsonb | Файлы субтитров | Нет | \- | \- |
| [block.is](http://block.is)\_deprecated | block\_is\_deprecated | boolean | Блок устарел | Да | \- | \- |
| correct\_ratio | correct\_ratio | numeric | Доля правильных решений | Да | \- | \- |
| worth | worth | numeric | Баллы за шаг | Да | \- | \- |
| is\_solutions\_unlocked | is\_solutions\_unlocked | boolean | Решения разблокированы | Да | \- | \- |
| max\_submissions\_count | max\_submissions\_count | int | Максимум отправок | Да | \- | \- |
| progress | progress\_id | text | Прогресс текущего пользователя | Нет | FK | fact\_stepik\_\_progress.progress\_id |
| actions | actions\_json | jsonb | Действия текущего пользователя | Нет | \- | \- |
| discussions\_count | discussions\_count | int | Количество обсуждений | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата создания | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Дата обновления | Да | \- | \- |

---

**endpoint:** `/api/step-sources?ids[]=`  
**method:** GET  
**api\_object:** step\_source  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** -  
**description:** Исходный код шагов. В отличие от /api/steps, который возвращает отрендеренный блок, step-source содержит исходную разметку задания — то, что видит автор в редакторе. Нужно для полного экспорта контента, миграции курсов, анализа структуры заданий. Качать если нужен полный контент.

---

**endpoint:** `/api/step-snapshots?ids[]=`  
**method:** GET  
**api\_object:** step\_snapshot  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** -  
**description:** Снапшоты шагов — фиксация состояния шага на момент времени. Используется для версионирования контента: когда автор меняет задание, старый вариант сохраняется как снапшот. Нужно если важна история изменений контента и аудит. Для базовой аналитики не требуется.

---

**endpoint:** `/api/step-issues?ids[]=`  
**method:** GET  
**api\_object:** step\_issue  
**target\_table:** -  
**download:** Нет  
**primary\_key:** step\_issue\_id  
**description:** Сообщения о проблемах в шагах. Пользователи или модераторы могут сообщить об ошибке в задании: неверный ответ, опечатка, неработающий код. Нужно для контроля качества контента и модерации. Для базовой аналитики не требуется.

---

**endpoint:** `/api/step-votes?ids[]=`  
**method:** GET  
**api\_object:** step\_vote  
**target\_table:** `fact_stepik__step_vote`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** step\_vote\_id  
**description:** Голоса пользователей за шаги. Позволяет понять, какие шаги нравятся или не нравятся обучающимся. Нужно для анализа качества контента на уровне отдельных шагов. Для базовой аналитики не требуется.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | step\_vote\_id | bigint | ID голоса | Да | PK | fact\_stepik\_\_step\_vote.step\_vote\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/instructions?ids[]=`  
**method:** GET  
**api\_object:** instruction  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** instruction\_id  
**description:** Инструкции к шагам. Дополнительный текстовый контент, который показывается пользователю перед выполнением задания. Нужно если важен полный контент курса включая вспомогательные материалы.

---

**endpoint:** `/api/last-steps?ids[]=`  
**method:** GET  
**api\_object:** last\_step  
**raw\_table:** `stg_stepik__last_steps_raw`  
**target\_table:** `fact_stepik__last_step`  
**download:** Опц

**incremental:** full snapshot  
**primary\_key:** last\_step\_id  
**description:** Последние шаги пользователей. Фиксирует, на каком шаге пользователь остановился. Используется для функции “продолжить обучение”. Нужно если важна аналитика точек выхода и continue learning.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | last\_step\_id | bigint | ID записи | Опц | PK | fact\_stepik\_\_last\_step.last\_step\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Опц | \- | \- |

---

**endpoint:** `/api/users?ids[]=`  
**method:** GET  
**api\_object:** user  
**target\_table:** `dim_stepik__user`  
**download:** Да  
**incremental:** full snapshot / join\_date  
**primary\_key:** user\_id  
**description:** Пользователи Stepik. Базовая информация: имя, фамилия, full\_name, аватар, псевдоним, флаги приватности и гостя, дата регистрации, счетчики решенных шагов и созданных курсов. Это основной справочник пользователей — к нему привязываются все остальные сущности: владельцы курсов, авторы комментариев, обучающиеся. Качать обязательно.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | user\_id | bigint | Уникальный ID пользователя | Да | PK | dim\_stepik\_\_user.user\_id |
| profile | profile\_id | bigint | ID профиля пользователя | Да | FK | dim\_stepik\_\_user\_profile.profile\_id |
| first\_name | first\_name | text | Имя | Да | \- | \- |
| last\_name | last\_name | text | Фамилия | Да | \- | \- |
| full\_name | full\_name | text | Полное имя | Да | \- | \- |
| alias | alias | text | Псевдоним / username | Да | \- | \- |
| avatar | avatar\_url | text | URL аватара | Да | \- | \- |
| is\_private | is\_private | boolean | Профиль приватный | Да | \- | \- |
| is\_guest | is\_guest | boolean | Гостевой аккаунт | Да | \- | \- |
| join\_date | join\_date | timestamptz | Дата регистрации | Да | \- | \- |
| solved\_steps\_count | solved\_steps\_count | int | Количество решенных шагов | Да | \- | \- |
| created\_courses\_count | created\_courses\_count | int | Количество созданных курсов | Да | \- | \- |
| followers\_count | followers\_count | int | Количество подписчиков | Да | \- | \- |

---

**endpoint:** `/api/profiles?ids[]=`  
**method:** GET  
**api\_object:** profile  
**target\_table:** `dim_stepik__user_profile`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** profile\_id  
**description:** Расширенные профили пользователей. Содержит PII: город, язык, био, настройки уведомлений, подписки, email-адреса, социальные аккаунты, статус верификации email, последний вход. Нужно если нужны детальные данные о пользователях. Хранить с ограниченным доступом из-за PII.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | profile\_id | bigint | ID профиля | Да | PK | dim\_stepik\_\_user\_profile.profile\_id |
| first\_name | first\_name | text | Имя | Да | \- | \- |
| last\_name | last\_name | text | Фамилия | Да | \- | \- |
| full\_name | full\_name | text | Полное имя | Да | \- | \- |
| avatar | avatar\_url | text | Аватар | Да | \- | \- |
| language | language\_code | text | Язык профиля | Да | \- | \- |
| city | city | text | Город | Да | \- | \- |
| short\_bio | short\_bio | text | Краткое био | Да | \- | \- |
| details | details | text | Подробная информация | Да | \- | \- |
| email\_addresses | email\_address\_ids | jsonb | Ссылки на email-адреса | Да | FK\_array | dim\_stepik\_\_email\_address.email\_address\_id |
| social\_accounts | social\_account\_ids | jsonb | Ссылки на соцаккаунты | Да | FK\_array | dim\_stepik\_\_social\_account.social\_account\_id |
| is\_email\_verified | is\_email\_verified | boolean | Email подтвержден | Да | \- | \- |
| last\_login | last\_login\_at | timestamptz | Последний вход | Да | \- | \- |

---

**endpoint:** `/api/stepics/1`  
**method:** GET  
**api\_object:** stepic  
**target\_table:** `dim_stepik__current_user`  
**download:** Нет  
**incremental:** -  
**primary\_key:** stepic\_id  
**description:** Текущий авторизованный пользователь. Возвращает данные пользователя, чей токен используется. Нужно для проверки авторизации, определения прав доступа и отладки. Не является справочником — это сервисный эндпоинт.

---

**endpoint:** `/api/email-addresses?ids[]=`  
**method:** GET  
**api\_object:** email\_address  
**target\_table:** `dim_stepik__email_address`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** email\_address\_id  
**description:** Email-адреса пользователей. Содержит сам email, статус верификации, привязку к пользователю. Нужно только если требуется матчинг пользователей по email или рассылки. PII — качать только при наличии юридического основания и scope.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | email\_address\_id | bigint | ID email-адреса | Да | PK | dim\_stepik\_\_email\_address.email\_address\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/social-accounts?ids[]=`  
**method:** GET  
**api\_object:** social\_account  
**target\_table:** `dim_stepik__social_account`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** social\_account\_id  
**description:** Социальные аккаунты пользователей: привязки к Google, VK, GitHub и другим провайдерам. Нужно для enrichment профилей и анализа источников регистрации.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | social\_account\_id | bigint | ID соцаккаунта | Да | PK | dim\_stepik\_\_social\_account.social\_account\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/social-profiles?ids[]=`  
**method:** GET  
**api\_object:** social\_profile  
**target\_table:** `dim_stepik__social_profile`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** social\_profile\_id  
**description:** Социальные профили — расширенные данные из соцсетей пользователя. Отличается от social-accounts тем, что содержит данные профиля из внешней соцсети, а не просто привязку.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | social\_profile\_id | bigint | ID соцпрофиля | Да | PK | dim\_stepik\_\_social\_profile.social\_profile\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/social-providers?ids[]=`  
**method:** GET  
**api\_object:** social\_provider  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** social\_provider\_id  
**description:** Справочник провайдеров социальной авторизации: Google, VK, GitHub, Facebook и т.д. Маленький справочник, можно захардкодить.

---

**endpoint:** `/api/followers?ids[]=`  
**method:** GET  
**api\_object:** follower  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** follower\_id  
**description:** Подписки пользователей друг на друга. Кто на кого подписан. Нужно для анализа социальных графов и влияния авторов.

---

**endpoint:** `/api/user-activities?ids[]=`  
**method:** GET  
**api\_object:** user\_activity  
**target\_table:** `fact_stepik__user_activity`  
**download:** Нет  
**incremental:** -  
**primary\_key:** user\_activity\_id  
**description:** События активности пользователей: что делал пользователь, когда, на каком объекте. Нужно для поведенческой аналитики, воронок, анализа вовлеченности.

---

**endpoint:** `/api/user-activity-summaries?ids[]=`  
**method:** GET  
**api\_object:** user\_activity\_summary  
**target\_table:** `dim_stepik__user_activity_summary`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** user\_activity\_summary\_id  
**description:** Агрегированные сводки активности пользователей: суммарные счетчики действий. Нужно для быстрых дашбордов без агрегации сырых событий.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | user\_activity\_summary\_id | bigint | ID сводки | Да | PK | dim\_stepik\_\_user\_activity\_summary.user\_activity\_summary\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/user-code-runs?ids[]=`  
**method:** GET  
**api\_object:** user\_code\_run  
**target\_table:** `fact_stepik__user_code_run`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** user\_code\_run\_id  
**description:** Запуски кода пользователями в программных заданиях. Содержит язык, статус выполнения, время. Нужно для анализа программирующих заданий и отладки.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | user\_code\_run\_id | bigint | ID запуска | Да | PK | fact\_stepik\_\_user\_code\_run.user\_code\_run\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/user-courses?ids[]=`  
**method:** GET  
**api\_object:** user\_course  
**target\_table:** `-` **download:** Нет  
**incremental:** -  
**primary\_key:** user\_course\_id  
**description:** Связь пользователь-курс с ролями: автор, модератор, ассистент, обучающийся. Нужно для анализа ролевой модели и прав доступа.

---

**endpoint:** `/api/user-lessons?ids[]=`  
**method:** GET  
**api\_object:** user\_lesson  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** user\_lesson\_id  
**description:** Связь пользователь-урок. Роли и статусы на уровне уроков. Нужно для детального анализа доступа к контенту.

---

**endpoint:** `/api/user-financial-details?ids[]=`  
**method:** GET  
**api\_object:** user\_financial\_detail  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** user\_financial\_detail\_id  
**description:** Финансовые реквизиты пользователей для выплат: банковские данные, налоговая информация. Крайне чувствительные PII + финансовые данные. Качать только при крайней необходимости и строгом контроле доступа.

---

**endpoint:** `/api/user-review-summaries?ids[]=`  
**method:** GET  
**api\_object:** user\_review\_summary  
**target\_table:** `dim_stepik__user_review_summary`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** user\_review\_summary\_id  
**description:** Сводки отзывов по пользователям: средний рейтинг автора, количество отзывов. Нужно для ранжирования авторов.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | user\_review\_summary\_id | bigint | ID сводки | Да | PK | dim\_stepik\_\_user\_review\_summary.user\_review\_summary\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/devices?ids[]=`  
**method:** GET  
**api\_object:** device  
**target\_table:** `dim_stepik__device`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** device\_id  
**description:** Устройства пользователей: тип, ОС, push-токены. Нужно для аналитики платформ и мобильных уведомлений.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | device\_id | bigint | ID устройства | Да | PK | dim\_stepik\_\_device.device\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/profile-images?ids[]=`  
**method:** GET  
**api\_object:** profile\_image  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** profile\_image\_id  
**description:** Изображения профилей: URL, размеры, статус загрузки. Нужно если важен медиа-контент профилей.

---

**endpoint:** `/api/attempts`  
**method:** GET  
**api\_object:** attempt  
**target\_table:** `fact_stepik__attempt`  
**download:** Да  
**incremental:** time  
**primary\_key:** attempt\_id  
**description:** Попытки решения заданий. Каждая попытка привязана к пользователю и шагу, содержит время начала, статус, оставшееся время, dataset с данными задания. Нужно для анализа сложности заданий, времени решения, успешности. Доступ может быть ограничен правами.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | attempt\_id | bigint | ID попытки | Да | PK | fact\_stepik\_\_attempt.attempt\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| step | step\_id | bigint | Шаг | Да | FK | dim\_stepik\_\_step.step\_id |
| time | attempt\_time | timestamptz | Время начала попытки | Да | \- | \- |
| status | status | text | Статус: active, successful, failed | Да | \- | \- |
| time\_left | time\_left\_seconds | int | Оставшееся время в секундах | Да | \- | \- |
| dataset | dataset\_json | jsonb | Данные задания для этой попытки | Нет | \- | \- |
| dataset\_url | dataset\_url | text | Временная ссылка на dataset | Нет | \- | \- |

---

**endpoint:** `/api/submissions`  
**method:** GET  
**api\_object:** submission  
**target\_table:** `fact_stepik__submission`  
**download:** Да  
**incremental:** time  
**primary\_key:** submission\_id  
**description:** Отправки решений. Каждая отправка привязана к попытке, содержит статус, балл, ответ пользователя, фидбек. Пользователь и шаг определяются через attempt. Нужно для анализа правильности ответов, оценок, качества заданий. Содержит пользовательские ответы — чувствительные данные.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | submission\_id | bigint | ID отправки | Да | PK | fact\_stepik\_\_submission.submission\_id |
| attempt | attempt\_id | bigint | Попытка | Да | FK | fact\_stepik\_\_attempt.attempt\_id |
| status | status | text | Статус: correct, wrong, evaluation | Да | \- | \- |
| score | score | numeric | Балл за ответ | Да | \- | \- |
| hint | hint | text | Использованная подсказка | Нет | \- | \- |
| feedback | feedback\_json | jsonb | Обратная связь по ответу | Нет | \- | \- |
| time | submission\_time | timestamptz | Время отправки | Да | \- | \- |
| reply | reply\_json | jsonb | Ответ пользователя | Нет | \- | \- |
| reply\_url | reply\_url | text | Временная ссылка на ответ | Нет | \- | \- |

---

**endpoint:** `/api/progresses?ids[]=`  
**method:** GET  
**api\_object:** progress  
**target\_table:** `fact_stepik__progress`  
**download:** Да  
**incremental:** проверить  
**primary\_key:** progress\_id  
**description:** Прогресс пользователей по объектам: курсам, секциям, юнитам, урокам, шагам. Содержит набранные баллы, максимальные баллы, статус завершения, последний просмотр. Нужно для анализа прохождения, завершения, успеваемости. Ключевая таблица для learning analytics.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | progress\_id | text | ID прогресса, часто составной | Да | PK | fact\_stepik\_\_progress.progress\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| object\_type | object\_type | text | Тип объекта: course, section, unit, lesson, step | Да | \- | \- |
| object\_id | object\_id | bigint | ID объекта | Да | FK\_polymorphic | dim\_stepik\_\_course.course\_id/dim\_stepik\_\_lesson.lesson\_id/dim\_stepik\_\_step.step\_id |
| score | score | numeric | Набранные баллы | Да | \- | \- |
| cost | cost | numeric | Максимальные баллы | Да | \- | \- |
| is\_completed | is\_completed | boolean | Объект завершен | Да | \- | \- |
| last\_viewed | last\_viewed\_at | timestamptz | Последний просмотр | Да | \- | \- |

---

**endpoint:** `/api/enrollments`  
**method:** GET  
**api\_object:** enrollment  
**target\_table:** `fact_stepik__enrollment`  
**download:** Да  
**incremental:** проверить  
**primary\_key:** enrollment\_id  
**description:** Записи пользователей на курсы. Фиксирует кто и когда записался на курс. Нужно для воронок: записался → учился → завершил → получил сертификат. Ключевая таблица для retention-аналитики.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | enrollment\_id | bigint | ID записи | Да | PK | fact\_stepik\_\_enrollment.enrollment\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| time | enrolled\_at | timestamptz | Дата записи | Да | \- | \- |

---

**endpoint:** `/api/assignments?ids[]=`  
**method:** GET  
**api\_object:** assignment  
**target\_table:** `fact_stepik__assignment`  
**download:** Да  
**primary\_key:** assignment\_id  
**description:** Назначения шагов внутри юнитов. Assignment — это шаг в контексте конкретного юнита курса. Содержит ссылку на юнит, шаг, прогресс, даты создания и обновления. Нужно для понимания какие шаги назначены в каких юнитах.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | assignment\_id | bigint | ID назначения | Да | PK | fact\_stepik\_\_assignment.assignment\_id |
| unit | unit\_id | bigint | Юнит | Да | FK | dim\_stepik\_\_unit.unit\_id |
| step | step\_id | bigint | Шаг | Да | FK | dim\_stepik\_\_step.step\_id |
| progress | progress\_id | text | Прогресс | Да | FK | fact\_stepik\_\_progress.progress\_id |
| create\_date | created\_at | timestamptz | Создание | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Обновление | Да | \- | \- |

---

**endpoint:** `/api/subscriptions`  
**method:** GET  
**api\_object:** subscription  
**raw\_table:** `stg_stepik__subscriptions_raw`  
**target\_table:** `fact_stepik__subscription`  
**download:** Да  
**incremental:** проверить  
**primary\_key:** subscription\_id  
**description:** Подписки пользователей на объекты: курсы, уроки, шаги, обсуждения. Нужно для анализа вовлеченности и подписочной активности.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | subscription\_id | text | ID подписки | Да | PK | fact\_stepik\_\_subscription.subscription\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/views?ids[]=`  
**method:** GET  
**api\_object:** view  
**target\_table:** `fact_stepik__view`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** view\_id  
**description:** Просмотры объектов пользователями. Фиксирует что и когда просматривал пользователь. Нужно для анализа популярности контента и поведения.

---

**endpoint:** `/api/visited-courses?ids[]=`  
**method:** GET  
**api\_object:** visited\_course  
**target\_table:** `fact_stepik__visited_course`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** visited\_course\_id  
**description:** Посещенные курсы. Отличается от enrollments тем, что фиксирует визиты без записи. Нужно для анализа интереса к курсам до записи.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | visited\_course\_id | bigint | ID записи | Да | PK | fact\_stepik\_\_visited\_course.visited\_course\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/votes?ids[]=`  
**method:** GET  
**api\_object:** vote  
**target\_table:** `fact_stepik__vote`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** vote\_id  
**description:** Голоса за контент: комментарии, отзывы, уроки. Нужно для анализа качества контента через пользовательские оценки.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | vote\_id | bigint | ID голоса | Да | PK | fact\_stepik\_\_vote.vote\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/wish-lists?ids[]=`  
**method:** GET  
**api\_object:** wish\_list  
**target\_table:** `fact_stepik__wish_list`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** wish\_list\_id  
**description:** Списки желаемого: курсы, которые пользователь хочет пройти. Нужно для анализа спроса и маркетинга.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | wish\_list\_id | bigint | ID записи | Да | PK | fact\_stepik\_\_wish\_list.wish\_list\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/todo-items?ids[]=`  
**method:** GET  
**api\_object:** todo\_item  
**target\_table:** `-`  
**download:** Нет  
**incremental:** full snapshot  
**primary\_key:** todo\_item\_id  
**description:** Задачи to-do пользователей: что нужно сделать в курсе. Нужно для анализа продуктивности и напоминаний.

---

**endpoint:** `/api/queries?ids[]=`  
**method:** GET  
**api\_object:** query  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** query\_id  
**description:** Поисковые запросы пользователей. Что искали, какие результаты получили. Нужно для анализа поискового поведения и улучшения поиска.

---

**endpoint:** `/api/comments`  
**method:** GET  
**api\_object:** comment  
**target\_table:** `fact_stepik__comment`  
**download:** Да  
**incremental:** last\_time  
**primary\_key:** comment\_id  
**description:** Комментарии к шагам, урокам, курсам. Содержит автора, текст, цель, родителя для иерархии, время, голоса, флаги модерации. Нужно для анализа вопросов обучающихся, проблем с контентом, активности сообщества.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | comment\_id | bigint | ID комментария | Да | PK | fact\_stepik\_\_comment.comment\_id |
| user | user\_id | bigint | Автор | Да | FK | dim\_stepik\_\_user.user\_id |
| parent | parent\_comment\_id | bigint | Родительский комментарий | Да | FK | fact\_stepik\_\_comment.comment\_id |
| target | target\_ref | text | Цель: step-123, lesson-456 | Да | \- | \- |
| text | comment\_text | text | Текст комментария | Да | \- | \- |
| time | comment\_time | timestamptz | Время создания | Да | \- | \- |
| last\_time | last\_time | timestamptz | Последняя активность | Да | \- | \- |
| reply\_count | reply\_count | int | Количество ответов | Да | \- | \- |
| is\_deleted | is\_deleted | boolean | Удален | Да | \- | \- |
| vote\_delta | vote\_delta | int | Сумма голосов | Да | \- | \- |
| actions | actions\_json | jsonb | Действия | Нет | \- | \- |

---

**endpoint:** `/api/discussion-threads?ids[]=`  
**method:** GET  
**api\_object:** discussion\_thread  
**target\_table:** `dim_stepik__discussion_thread`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** thread\_id  
**description:** Ветки обсуждений. Группируют комментарии в логические обсуждения. Нужно для навигации по обсуждениям и аналитики на уровне веток.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | thread\_id | bigint | ID ветки | Да | PK | dim\_stepik\_\_discussion\_thread.thread\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/discussion-proxies?ids[]=`  
**method:** GET  
**api\_object:** discussion\_proxy  
**target\_table:** `dim_stepik__discussion_proxy`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** discussion\_proxy\_id  
**description:** Прокси обсуждений. Связывает объект (шаг, урок) с его ветками обсуждений. Технический объект для навигации.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | discussion\_proxy\_id | bigint | ID прокси | Да | PK | dim\_stepik\_\_discussion\_proxy.discussion\_proxy\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/reviews?ids[]=`  
**method:** GET  
**api\_object:** review  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** review\_id  
**description:** Рецензии. Peer review заданий: один пользователь проверяет работу другого. Нужно для анализа peer review процессов.

---

**endpoint:** `/api/course-reviews`  
**method:** GET  
**api\_object:** course\_review  
**target\_table:** `fact_stepik__course_review`  
**download:** Да  
**primary\_key:** course\_review\_id  
**description:** Отзывы на курсы. Содержит курс, автора, оценку (score), текст отзыва, ответ администрации, даты, голоса. Нужно для анализа удовлетворенности, рейтингов, обратной связи по курсам.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_review\_id | bigint | ID отзыва | Да | PK | fact\_stepik\_\_course\_review.course\_review\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| user | user\_id | bigint | Автор отзыва | Да | FK | dim\_stepik\_\_user.user\_id |
| score | score | int | Оценка курса | Да | \- | \- |
| text | review\_text | text | Текст отзыва | Да | \- | \- |
| create\_date | created\_at | timestamptz | Создание | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Обновление | Да | \- | \- |
| vote\_delta | vote\_delta | int | Голоса | Да | \- | \- |

---

**endpoint:** `/api/course-review-summaries?ids[]=`  
**method:** GET  
**api\_object:** course\_review\_summary  
**target\_table:** `dim_stepik__course_review_summary`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_review\_summary\_id  
**description:** Агрегированные сводки отзывов по курсам: средний рейтинг, количество отзывов, распределение оценок. Нужно для быстрых рейтингов без агрегации всех отзывов. Удобно для дашбордов и каталога.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_review\_summary\_id | bigint | ID сводки | Да | PK | dim\_stepik\_\_course\_review\_summary.course\_review\_summary\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/certificates`  
**method:** GET  
**api\_object:** certificate  
**target\_table:** `fact_stepik__certificate`  
**download:** Да  
**primary\_key:** certificate\_id  
**description:** Сертификаты пользователей. Содержит пользователя, курс, тип, оценку, дату выдачи, URL, публичность, название курса. Нужно для анализа завершений, достижений, конверсии в сертификат.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | certificate\_id | text | ID сертификата | Да | PK | fact\_stepik\_\_certificate.certificate\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| type | certificate\_type | text | Тип: regular, distinction | Да | \- | \- |
| grade | grade | numeric | Оценка | Да | \- | \- |
| issue\_date | issued\_at | timestamptz | Дата выдачи | Да | \- | \- |
| url | certificate\_url | text | Публичный URL | Да | \- | \- |
| is\_public | is\_public | boolean | Публичный | Да | \- | \- |
| course\_title | course\_title | text | Название курса | Да | \- | \- |

---

**endpoint:** `/api/achievements?ids[]=`  
**method:** GET  
**api\_object:** achievement  
**target\_table:** `dim_stepik__achievement`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** achievement\_id  
**description:** Справочник достижений (ачивок). Содержит тип достижения (kind), целевой счет для получения, иконку. Нужно для геймификационной аналитики.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | achievement\_id | bigint | ID достижения | Да | PK | dim\_stepik\_\_achievement.achievement\_id |
| kind | kind | text | Тип достижения | Да | \- | \- |
| target\_score | target\_score | int | Целевой счет для получения | Да | \- | \- |
| icon\_url | icon\_url | text | URL иконки | Да | \- | \- |

---

**endpoint:** `/api/achievement-progresses?ids[]=`  
**method:** GET  
**api\_object:** achievement\_progress  
**target\_table:** `fact_stepik__achievement_progress`  
**download:** Да  
**incremental:** full snapshot**primary\_key:** achievement\_progress\_id  
**description:** Прогресс пользователей по достижениям. Содержит пользователя, достижение, текущий счет, дату получения, тип и иконку. Нужно для анализа геймификации и мотивации.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | achievement\_progress\_id | bigint | ID записи | Да | PK | fact\_stepik\_\_achievement\_progress.achievement\_progress\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| achievement | achievement\_id | bigint | Достижение | Да | FK | dim\_stepik\_\_achievement.achievement\_id |
| score | score | int | Текущий счет | Да | \- | \- |
| kind | kind | text | Тип достижения | Да | \- | \- |
| obtain\_date | obtain\_date | timestamptz | Дата получения | Да | \- | \- |
| create\_date | created\_at | timestamptz | Создание | Да | \- | \- |
| update\_date | updated\_at | timestamptz | Обновление | Да | \- | \- |

---

**endpoint:** `/api/course-beneficiaries?ids[]=`  
**method:** GET  
**api\_object:** course\_beneficiary  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_beneficiary\_id  
**description:** Бенефициары курсов — кто получает доход от продаж. Содержит пользователя, курс, процент дохода, валидность. Нужно для финансовой аналитики и распределения выручки между авторами.

---

**endpoint:** `/api/course-benefits`  
**method:** GET  
**api\_object:** course\_benefit  
**target\_table:** `fact_stepik__course_benefit`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_benefit\_id  
**description:** Записи дохода по курсам. Содержит пользователя, курс, время, статус, сумму, валюту, покупателя, промокод, UTM-метки первого и последнего клика, флаги подарка и инвойса. Нужно для детальной финансовой аналитики: сколько заработал курс, от кого, через какой канал.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_benefit\_id | bigint | ID записи дохода | Да | PK | fact\_stepik\_\_course\_benefit.course\_benefit\_id |
| user | user\_id | bigint | Пользователь-бенефициар | Да | FK | dim\_stepik\_\_user.user\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| time | benefit\_time | timestamptz | Время дохода | Да | \- | \- |
| status | status | text | Статус: 1 или 2 | Да | \- | \- |
| amount | amount | numeric | Сумма дохода | Да | \- | \- |
| currency\_code | currency\_code | text | Валюта | Да | \- | \- |
| payment\_amount | payment\_amount | text | Сумма платежа | Да | \- | \- |
| buyer | buyer | text | Покупатель | Да | \- | \- |
| is\_gift | is\_gift | boolean | Подарок | Да | \- | \- |
| promo\_code | promo\_code | text | Промокод | Да | \- | \- |
| is\_stepik\_side | is\_stepik\_side | boolean | Доход на стороне Stepik | Да | \- | \- |
| first\_course\_click\_utm | first\_utm\_json | jsonb | UTM первого клика | Да | \- | \- |
| last\_course\_click\_utm | last\_utm\_json | jsonb | UTM последнего клика | Да | \- | \- |

---

**endpoint:** `/api/course-benefit-by-months`  
**method:** GET  
**api\_object:** course\_benefit\_by\_month  
**target\_table:** `fact_stepik__course_benefit_by_month`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** surrogate key  
**description:** Агрегированный доход по курсам с разбивкой по месяцам. Нужно для месячных финансовых отчетов, динамики выручки, сравнения курсов по периодам.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-benefit-summaries?ids[]=`  
**method:** GET  
**api\_object:** course\_benefit\_summary  
**target\_table:** `dim_stepik__course_benefit_summary`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_benefit\_summary\_id  
**description:** Итоговые сводки дохода по курсам. Агрегированные суммы без разбивки по времени. Нужно для быстрых финансовых дашбордов.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_benefit\_summary\_id | bigint | ID сводки | Да | PK | dim\_stepik\_\_course\_benefit\_summary.course\_benefit\_summary\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-beneficiary-revenues?ids[]=`  
**method:** GET  
**api\_object:** course\_beneficiary\_revenue  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_beneficiary\_revenue\_id  
**description:** Доходы конкретных бенефициаров по курсам. Детализация: сколько каждый автор получил с каждого курса. Нужно для распределения выплат.

---

**endpoint:** `/api/course-beneficiary-transfers?ids[]=`  
**method:** GET  
**api\_object:** course\_beneficiary\_transfer  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_beneficiary\_transfer\_id  
**description:** Выплаты / переводы бенефициарам. Фиксирует когда и сколько было выплачено автору. Нужно для учета выплат и финансовой отчетности.

---

**endpoint:** `/api/course-payments?ids[]=`  
**method:** GET  
**api\_object:** course\_payment  
**target\_table:** `fact_stepik__course_payment`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_payment\_id  
**description:** Платежи за курсы. Содержит пользователя, курс, сумму, валюту, дату платежа, статус, провайдера оплаты, промокод, флаги подарка, gift-данные. Нужно для анализа оплат, возвратов, каналов оплаты.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_payment\_id | bigint | ID платежа | Да | PK | fact\_stepik\_\_course\_payment.course\_payment\_id |
| user | user\_id | bigint | Плательщик | Да | FK | dim\_stepik\_\_user.user\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| amount | amount | numeric | Сумма | Да | \- | \- |
| currency\_code | currency\_code | text | Валюта | Да | \- | \- |
| payment\_date | payment\_date | timestamptz | Дата платежа | Да | \- | \- |
| cancel\_date | cancel\_date | timestamptz | Дата отмены | Да | \- | \- |
| status | status | text | Статус платежа | Да | \- | \- |
| is\_paid | is\_paid | boolean | Оплачен | Да | \- | \- |
| payment\_provider | payment\_provider | text | Провайдер оплаты | Да | \- | \- |
| promo\_code | promo\_code | text | Промокод | Да | \- | \- |
| is\_gift | is\_gift | boolean | Подарок | Да | \- | \- |

---

**endpoint:** `/api/course-purchases?ids[]=`  
**method:** GET  
**api\_object:** course\_purchase  
**target\_table:** `fact_stepik__course_purchase`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_purchase\_id  
**description:** Покупки курсов. Фиксирует факт покупки: пользователь, курс, активность, платеж, даты создания и отмены. Нужно для анализа конверсии в покупку и отмен.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_purchase\_id | bigint | ID покупки | Да | PK | fact\_stepik\_\_course\_purchase.course\_purchase\_id |
| user | user\_id | bigint | Покупатель | Да | FK | dim\_stepik\_\_user.user\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| is\_active | is\_active | boolean | Покупка активна | Да | \- | \- |
| payment | payment\_id | text | Связанный платеж | Да | \- | \- |
| create\_date | created\_at | timestamptz | Дата покупки | Да | \- | \- |
| cancel\_date | cancel\_date | timestamptz | Дата отмены | Да | \- | \- |

---

**endpoint:** `/api/promo-codes?ids[]=`  
**method:** GET  
**api\_object:** promo\_code  
**target\_table:** `dim_stepik__promo_code` **download:** Да  
**incremental:** full snapshot  
**primary\_key:** promo\_code\_id  
**description:** Промокоды для скидок на курсы. Нужно для анализа эффективности промо-кампаний.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | promo\_code\_id | bigint | ID промокода | Да | PK | dim\_stepik\_\_promo\_code.promo\_code\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/stripe-coupons?ids[]=`  
**method:** GET  
**api\_object:** stripe\_coupon  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** stripe\_coupon\_id  
**description:** Stripe купоны. Интеграция с платежной системой Stripe. Нужно если используются Stripe-платежи.

---

**endpoint:** `/api/stripe-plans?ids[]=`  
**method:** GET  
**api\_object:** stripe\_plan  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** stripe\_plan\_id  
**description:** Stripe планы подписок. Тарифные планы для подписочной модели. Нужно если есть подписки через Stripe.

---

**endpoint:** `/api/stripe-subscriptions?ids[]=`  
**method:** GET  
**api\_object:** stripe\_subscriptio  
**target\_table:** `-` \*\*  
download:\*\* Нет  
**incremental:** -  
**primary\_key:** stripe\_subscription\_id  
**description:** Stripe подписки пользователей. Активные и прошлые подписки. Нужно для анализа подписочной модели и MRR.

---

**endpoint:** `/api/paid-features?ids[]=`  
**method:** GET  
**api\_object:** paid\_feature  
**target\_table:** `-` **download:** Нет  
**incremental:** -  
**primary\_key:** paid\_feature\_id  
**description:** Платные фичи платформы. Какие функции доступны по подписке. Нужно для анализа монетизации фич.

---

**endpoint:** `/api/sale-course-applications?ids[]=`  
**method:** GET  
**api\_object:** sale\_course\_application  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** sale\_course\_application\_id  
**description:** Заявки на продажу курсов. Когда автор подает заявку на монетизацию курса. Нужно для анализа воронки монетизации.

---

**endpoint:** `/api/course-subscriptions?ids[]=`  
**method:** GET  
**api\_object:** course\_subscription  
**target\_table:** -  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_subscription\_id  
**description:** Подписки на курсы. Отличается от enrollments: подписка может быть платной и recurring. Нужно для подписочной модели.

---

**endpoint:** `/api/course-grades?course=X`  
**method:** GET  
**api\_object:** course\_grade  
**target\_table:** `fact_stepik__course_grade`  
**download:** Да  
**incremental:** проверить  
**primary\_key:** course\_grade\_id  
**description:** Оценки обучающихся по курсу — gradebook. Содержит курс, пользователя, итоговый балл, ранг, позицию в рейтинге, количество пользователей, дату записи, последний просмотр, даты и URL сертификатов. Фильтруется по course и user. Нужно для анализа успеваемости, ранжирования, certificate tracking. Доступ обычно только для авторов/админов курса.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_grade\_id | bigint | ID записи | Да | PK | fact\_stepik\_\_course\_grade.course\_grade\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| user | user\_id | bigint | Пользователь | Да | FK | dim\_stepik\_\_user.user\_id |
| results | results | text | Детальные результаты по секциям | Да | \- | \- |
| score | score | numeric | Итоговый балл | Да | \- | \- |
| rank | rank | int | Ранг пользователя | Да | \- | \- |
| rank\_max | rank\_max | int | Максимальный ранг | Да | \- | \- |
| rank\_position | rank\_position | int | Позиция в рейтинге | Да | \- | \- |
| users\_count | users\_count | int | Всего пользователей | Да | \- | \- |
| is\_teacher | is\_teacher | boolean | Пользователь преподаватель | Да | \- | \- |
| date\_joined | date\_joined | timestamptz | Дата записи на курс | Да | \- | \- |
| last\_viewed | last\_viewed | timestamptz | Последний просмотр | Да | \- | \- |
| certificate\_issue\_date | certificate\_issue\_date | text | Дата выдачи сертификата | Да | \- | \- |
| certificate\_url | certificate\_url | text | URL сертификата | Да | \- | \- |

---

**endpoint:** `/api/course-period-statistics?ids[]=`  
**method:** GET  
**api\_object:** course\_period\_statistics  
**target\_table:** `fact_stepik__course_period_statistics`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** surrogate key  
**description:** Статистика курса за период: записи, завершения, просмотры, активность. Нужно для анализа динамики курса по неделям/месяцам.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-total-statistics?ids[]=`  
**method:** GET  
**api\_object:** course\_total\_statistics  
**target\_table:** `dim_stepik__course_total_statistics`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** surrogate key  
**description:** Итоговая статистика курса: суммарные записи, завершения, сертификаты, просмотры за все время. Нужно для общих дашбордов по курсам.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-by-language-statistics?ids[]=`  
**method:** GET  
**api\_object:** course\_by\_language\_statistics  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** surrogate key  
**description:** Статистика курсов в разрезе языков. Сколько курсов, записей, завершений по каждому языку. Нужно для языковой аналитики платформы.

---

**endpoint:** `/api/course-progress-changes?ids[]=`  
**method:** GET  
**api\_object:** course\_progress\_change  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_progress\_change\_id  
**description:** Изменения прогресса по курсу. Фиксирует когда и как менялся прогресс пользователя. Нужно для анализа траекторий обучения и точек отвала.

---

**endpoint:** `/api/course-ranks?ids[]=`  
**method:** GET  
**api\_object:** course\_rank  
**target\_table:** `dim_stepik__course_rank`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_rank\_id  
**description:** Ранги курсов. Позиция курса в различных рейтингах. Нужно для анализа конкурентоспособности курсов.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_rank\_id | bigint | ID ранга | Да | PK | dim\_stepik\_\_course\_rank.course\_rank\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-monthly-reports?ids[]=`  
**method:** GET  
**api\_object:** course\_monthly\_report  
**target\_table:** `fact_stepik__course_monthly_report`  
**download:** Опц  
**incremental:** full snapshot  
**primary\_key:** course\_monthly\_report\_id  
**description:** Месячные отчеты по курсам. Агрегированные данные за месяц. Нужно для регулярной отчетности.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_monthly\_report\_id | bigint | ID отчета | Да | PK | fact\_stepik\_\_course\_monthly\_report.course\_monthly\_report\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-monthly-report-files?ids[]=`  
**method:** GET  
**api\_object:** course\_monthly\_report\_file  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_monthly\_report\_file\_id  
**description:** Файлы месячных отчетов. Ссылки на сгенерированные файлы отчетов. Нужно если нужны готовые файлы для скачивания.

---

**endpoint:** `/api/metrics?ids[]=`  
**method:** GET  
**api\_object:** metric  
**target\_table:** `fact_stepik__metric`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** metric\_id  
**description:** Метрики платформы. Различные измеримые показатели. Нужно для мониторинга и аналитики.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | metric\_id | bigint | ID метрики | Да | PK | fact\_stepik\_\_metric.metric\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/rubrics?ids[]=`  
**method:** GET  
**api\_object:** rubric  
**target\_table:** `dim_stepik__rubric`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** rubric\_id  
**description:** Рубрики оценивания. Критерии и шкалы для оценки заданий. Нужно для анализа системы оценивания.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | rubric\_id | bigint | ID рубрики | Да | PK | dim\_stepik\_\_rubric.rubric\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/rubric-scores?ids[]=`  
**method:** GET  
**api\_object:** rubric\_score  
**target\_table:** `fact_stepik__rubric_score`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** rubric\_score\_id  
**description:** Оценки по рубрикам. Конкретные баллы по каждому критерию оценивания. Нужно для детального анализа оценивания.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | rubric\_score\_id | bigint | ID оценки | Да | PK | fact\_stepik\_\_rubric\_score.rubric\_score\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/score-files?ids[]=`  
**method:** GET  
**api\_object:** score\_file  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** score\_file\_id  
**description:** Файлы оценок. Загруженные файлы с массовыми оценками. Нужно для импорта/экспорта оценок.

---

**endpoint:** `/api/course-lists?ids[]=`  
**method:** GET  
**api\_object:** course\_list  
**target\_table:** `dim_stepik__course_list`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_list\_id  
**description:** Подборки и списки курсов: “Курсы по Python”, “Подготовка к экзамену” и т.д. Кураторские подборки для каталога. Нужно для анализа эффективности подборок.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_list\_id | bigint | ID подборки | Да | PK | dim\_stepik\_\_course\_list.course\_list\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-recommendations?ids[]=`  
**method:** GET  
**api\_object:** course\_recommendation  
**target\_table:** `fact_stepik__course_recommendation`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** course\_recommendation\_id  
**description:** Рекомендации курсов: какие курсы рекомендуются после прохождения других. Нужно для анализа рекомендательной системы.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | course\_recommendation\_id | bigint | ID рекомендации | Да | PK | fact\_stepik\_\_course\_recommendation.course\_recommendation\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/course-images?ids[]=`  
**method:** GET  
**api\_object:** course\_image  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_image\_id  
**description:** Изображения курсов: обложки, баннеры, превью. Метаданные медиа-файлов. Нужно если важен медиа-контент курсов.

---

**endpoint:** `/api/lesson-images?ids[]=`  
**method:** GET  
**api\_object:** lesson\_image  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** lesson\_image\_id  
**description:** Изображения уроков. Метаданные медиа-файлов уроков. Нужно если важен медиа-контент уроков.

---

**endpoint:** `/api/catalog-blocks?ids[]=`  
**method:** GET  
**api\_object:** catalog\_block  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** catalog\_block\_id  
**description:** Блоки каталога: секции на главной странице каталога курсов. Нужно для анализа структуры каталога.

---

**endpoint:** `/api/promo-blocks?ids[]=`  
**method:** GET  
**api\_object:** promo\_block  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** promo\_block\_id  
**description:** Промо блоки: рекламные и промо-секции на сайте. Нужно для анализа маркетинговых размещений.

---

**endpoint:** `/api/promo-block-placements?ids[]=`  
**method:** GET  
**api\_object:** promo\_block\_placement  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** promo\_block\_placement\_id  
**description:** Размещения промо блоков: где и когда показывается промо. Нужно для анализа маркетинговых кампаний.

---

**endpoint:** `/api/meta-categories?ids[]=`  
**method:** GET  
**api\_object:** meta\_category  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** meta\_category\_id  
**description:** Мета категории: верхнеуровневые категории каталога. Программирование, Математика, Языки и т.д. Нужно для категоризации курсов.

---

**endpoint:** `/api/subjects?ids[]=`  
**method:** GET  
**api\_object:** subject  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** subject\_id  
**description:** Предметы / темы курсов. Более детальные чем мета категории. Нужно для тематической аналитики.

---

**endpoint:** `/api/tags?ids[]=`  
**method:** GET  
**api\_object:** tag  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** tag\_id  
**description:** Теги курсов. Свободная категоризация. Нужно для поиска и фильтрации.

---

**endpoint:** `/api/specializations?ids[]=`  
**method:** GET  
**api\_object:** specialization  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** specialization\_id  
**description:** Специализации: наборы курсов, объединенные в программу. Нужно для анализа программ обучения.

---

**endpoint:** `/api/author-lists?ids[]=`  
**method:** GET  
**api\_object:** author\_list  
**target\_table:** `dim_stepik__author_list`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** author\_list\_id  
**description:** Списки авторов: кураторские подборки авторов. Нужно для анализа авторского состава.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | author\_list\_id | bigint | ID списка | Да | PK | dim\_stepik\_\_author\_list.author\_list\_id |
| \* | raw\_json | jsonb | Полный ответ. Поля проверить фактическим запросом | Да | \- | \- |

---

**endpoint:** `/api/cities?ids[]=`  
**method:** GET  
**api\_object:** city  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** city\_id  
**description:** Справочник городов. Используется в профилях пользователей. Можно захардкодить.

---

**endpoint:** `/api/countries?ids[]=`  
**method:** GET  
**api\_object:** country  
**target\_table:** -  
**download:** Нет  
**incremental:** -  
**primary\_key:** country\_id  
**description:** Справочник стран. Используется в профилях и геолокации. Можно захардкодить.

---

**endpoint:** `/api/regions?ids[]=`  
**method:** GET  
**api\_object:** region  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** region\_id  
**description:** Справочник регионов. Промежуточный уровень между страной и городом. Можно захардкодить.

---

**endpoint:** `/api/course-issues?ids[]=`  
**method:** GET  
**api\_object:** course\_issue  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** course\_issue\_id  
**description:** Проблемы курсов: сообщения о проблемах на уровне курса. Нужно для модерации и контроля качества.

---

**endpoint:** `/api/exam-sessions?ids[]=`  
**method:** GET  
**api\_object:** exam\_session  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** exam\_session\_id  
**description:** Экзаменационные сессии. Фиксирует сессию экзамена: пользователь, курс, время, статус. Нужно для анализа экзаменов.

---

**endpoint:** `/api/random-exams?ids[]=`  
**method:** GET  
**api\_object:** random\_exam  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** random\_exam\_id  
**description:** Случайные экзамены: экзамены, где задания выбираются случайным образом из пула. Нужно для анализа рандомизированных экзаменов.

---

**endpoint:** `/api/proctor-sessions?ids[]=`  
**method:** GET  
**api\_object:** proctor\_session  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** proctor\_session\_id  
**description:** Прокторские сессии: наблюдение за экзаменом. Нужно для анализа прокторинга.

---

**endpoint:** `/api/review-sessions?ids[]=`  
**method:** GET  
**api\_object:** review\_session  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** review\_session\_id  
**description:** Сессии рецензирования: peer review сессии. Нужно для анализа взаимного оценивания.

---

**endpoint:** `/api/classes?ids[]=`  
**method:** GET  
**api\_object:** class  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** class\_id  
**description:** Классы / учебные группы. Группы обучающихся, привязанные к курсу. Нужно для B2B / образовательных организаций.

---

**endpoint:** `/api/class-plans?ids[]=`  
**method:** GET  
**api\_object:** class\_plan  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** class\_plan\_id  
**description:** Планы классов: расписание и программа для учебной группы. Нужно для управления учебным процессом.

---

**endpoint:** `/api/students?ids[]=`  
**method:** GET  
**api\_object:** student  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** student\_id  
**description:** Студенты в классах. Привязка пользователя к классу. Нужно для B2B аналитики.

---

**endpoint:** `/api/members?ids[]=`  
**method:** GET  
**api\_object:** member  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** member\_id  
**description:** Участники групп. Членство пользователей в группах. Нужно для групповой аналитики.

---

**endpoint:** `/api/assistants?ids[]=`  
**method:** GET  
**api\_object:** assistant  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** assistant\_id  
**description:** Ассистенты классов. Содержит класс, пользователя, дату присоединения. Нужно для анализа ролей в учебных группах.

---

**endpoint:** `/api/groups?ids[]=`  
**method:** GET  
**api\_object:** group  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** group\_id  
**description:** Группы: объединения пользователей для совместного обучения. Нужно для групповой аналитики.

---

**endpoint:** `/api/notifications`  
**method:** GET  
**api\_object:** notification  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** —  
**description:** Уведомления пользователей. Эфемерные данные: прочитано/не прочитано, тип, текст. Не нужны в хранилище — быстро устаревают и содержат PII.

---

**endpoint:** `/api/notification-statuses?ids[]=`  
**method:** GET  
**api\_object:** notification\_status  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** —  
**description:** Статусы уведомлений. Технический объект для отметки прочитано/не прочитано. Не нужен в хранилище.

---

**endpoint:** `/api/reminders?ids[]=`  
**method:** GET  
**api\_object:** reminder  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** reminder\_id  
**description:** Напоминания: автоматические напоминания пользователям о дедлайнах и активности. Нужно для анализа эффективности напоминаний.

---

**endpoint:** `/api/announcements?ids[]=`  
**method:** GET  
**api\_object:** announcement  
**target\_table:** `fact_stepik__announcement`  
**download:** Да  
**incremental:** full snapshot  
**primary\_key:** announcement\_id  
**description:** Анонсы / объявления по курсам. Email-рассылки обучающимся: тема, текст, расписание, статус, счетчики отправок, открытий, кликов. Нужно для анализа email-маркетинга курсов.

| name | db\_field | db\_type | description | sync | key | references |
| --- | --- | ---: | --- | --- | --- | --- |
| id | announcement\_id | bigint | ID анонса | Да | PK | fact\_stepik\_\_announcement.announcement\_id |
| course | course\_id | bigint | Курс | Да | FK | dim\_stepik\_\_course.course\_id |
| user | user\_id | bigint | Автор | Да | FK | dim\_stepik\_\_user.user\_id |
| subject | subject | text | Тема письма | Да | \- | \- |
| text | text | text | Текст письма | Да | \- | \- |
| status | status | text | Статус рассылки | Да | \- | \- |
| create\_date | created\_at | timestamptz | Создание | Да | \- | \- |
| sent\_count | sent\_count | int | Отправлено | Да | \- | \- |
| open\_count | open\_count | int | Открыто | Да | \- | \- |
| click\_count | click\_count | int | Кликов | Да | \- | \- |

---

**endpoint:** `/api/platform-news?ids[]=`  
**method:** GET  
**api\_object:** platform\_news  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** platform\_news\_id  
**description:** Новости платформы Stepik. Официальные новости и обновления. Нужно если важен контент новостей.

---

**endpoint:** `/api/email-templates?ids[]=`  
**method:** GET  
**api\_object:** email\_template  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** email\_template\_id  
**description:** Шаблоны email-писем. Заготовки для рассылок. Нужно для анализа и управления email-коммуникациями.

---

**endpoint:** `/api/magic-links?ids[]=`  
**method:** GET  
**api\_object:** magic\_link  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** —  
**description:** Магические ссылки для авторизации без пароля. Секретные одноразовые ссылки. Категорически не качать.

---

**endpoint:** `/api/invitations?ids[]=`  
**method:** GET  
**api\_object:** invitation  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** invitation\_id  
**description:** Приглашения: приглашения пользователей на курсы, в группы, на платформу. Нужно для анализа реферальных программ.

---

**endpoint:** `/api/attachments?ids[]=`  
**method:** GET  
**api\_object:** attachment  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** attachment\_id  
**description:** Метаданные вложений: файлы, прикрепленные к шагам, комментариям, заданиям. URL, имя, MIME type, размер. Сами файлы не скачиваем. Нужно для учета медиа-контента.

---

**endpoint:** `/api/videos?ids[]=`  
**method:** GET  
**api\_object:** video  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** video\_id  
**description:** Метаданные видео: URL, превью, длительность, статус обработки. Видеофайлы не скачиваем. Нужно для анализа видеоконтента.

---

**endpoint:** `/api/storage-records?ids[]=`  
**method:** GET  
**api\_object:** storage\_record  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** storage\_record\_id  
**description:** Записи хранилища: файлы в облачном хранилище Stepik. Нужно для учета использования хранилища.

---

**endpoint:** `/api/scripts?ids[]=`  
**method:** GET  
**api\_object:** script  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** script\_id  
**description:** Скрипты: пользовательские скрипты для программных заданий. Нужно для анализа кода в заданиях.

---

**endpoint:** `/api/adaptivity-parameters-changes?ids[]=`  
**method:** GET  
**api\_object:** adaptivity\_parameters\_change  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** adaptivity\_parameters\_change\_id  
**description:** Изменения параметров адаптивности курсов. Когда и как менялись настройки адаптивного обучения. Нужно для аудита адаптивных курсов.

---

**endpoint:** `/api/bans?ids[]=`  
**method:** GET  
**api\_object:** ban  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** ban\_id  
**description:** Баны пользователей и контента. Модерационные действия. Нужно для анализа модерации.

---

**endpoint:** `/api/service-requests?ids[]=`  
**method:** GET  
**api\_object:** service\_request  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** service\_request\_id  
**description:** Сервисные запросы / тикеты поддержки. Обращения пользователей в поддержку. Нужно для анализа поддержки.

---

**endpoint:** `/api/features?ids[]=`  
**method:** GET  
**api\_object:** feature  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** feature\_id  
**description:** Фиче-флаги: включение/выключение функций платформы. Нужно для анализа A/B тестов и rollout.

---

**endpoint:** `/api/licenses?ids[]=`  
**method:** GET  
**api\_object:** license  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** license\_id  
**description:** Лицензии: лицензионные соглашения для курсов. Нужно для юридического учета.

---

**endpoint:** `/api/long-tasks?ids[]=`  
**method:** GET  
**api\_object:** long\_task  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** long\_task\_id  
**description:** Долгие задачи: фоновые задачи платформы (генерация отчетов, экспорт). Нужно для мониторинга фоновых процессов.

---

**endpoint:** `/api/long-task-templates?ids[]=`  
**method:** GET  
**api\_object:** long\_task\_template  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** long\_task\_template\_id  
**description:** Шаблоны долгих задач. Конфигурации для фоновых задач. Нужно для управления фоновыми процессами.

---

**endpoint:** `/api/mobile-tiers?ids[]=`  
**method:** GET  
**api\_object:** mobile\_tier  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** mobile\_tier\_id  
**description:** Мобильные тарифы: тарифные планы для мобильного приложения. Нужно для мобильной монетизации.

---

**endpoint:** `/api/recommendation-reactions?ids[]=`  
**method:** GET  
**api\_object:** recommendation\_reaction  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** recommendation\_reaction\_id  
**description:** Реакции пользователей на рекомендации: лайк, дизлайк, скрыть. Нужно для улучшения рекомендательной системы.

---

**endpoint:** `/api/recommendations`  
**method:** GET  
**api\_object:** recommendation  
**target\_table:** —  
**download:** Нет  
**incremental:** —  
**primary\_key:** —  
**description:** Персональные рекомендации. Динамические данные, зависят от пользователя и контекста. Не нужны в статичном хранилище.

---

**endpoint:** `/api/search-reactions?ids[]=`  
**method:** GET  
**api\_object:** search\_reaction  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** search\_reaction\_id  
**description:** Реакции на результаты поиска: клики, пропуски. Нужно для улучшения поиска.

---

**endpoint:** `/api/search-results`  
**method:** GET  
**api\_object:** search\_result  
**target\_table:** —  
**download:** Нет  
**incremental:** —  
**primary\_key:** —  
**description:** Поисковая выдача. Динамические данные, зависят от запроса. Не нужны в хранилище.

---

**endpoint:** `/api/story-templates?ids[]=`  
**method:** GET  
**api\_object:** story\_template  
**target\_table:** `-`  
**download:** Нет  
**incremental:** -  
**primary\_key:** story\_template\_id  
**description:** Шаблоны историй: сторис в мобильном приложении. Нужно для анализа мобильного контента.

---

**endpoint:** `/api/times`  
**method:** GET  
**api\_object:** time  
**raw\_table:** —  
**target\_table:** —  
**download:** Нет  
**incremental:** —  
**primary\_key:** —  
**description:** Серверное время Stepik. Технический эндпоинт для синхронизации часов. Не нужен в хранилище.

---

**endpoint:** `/api/ws`  
**method:** GET  
**api\_object:** ws  
**target\_table:** —  
**download:** Нет  
**incremental:** —  
**primary\_key:** —  
**description:** WebSocket endpoint. Не REST API. Используется для real-time уведомлений. Не выгружается через REST.

---