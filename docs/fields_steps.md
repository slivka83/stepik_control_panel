# Поля шагов (raw\_step)

Всего полей: 32. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Doc | Sync | Описание |
| --- | --- | --- | --- | --- | --- |
| 1 | actions | jsonb |  |  | ссылки действий |
| 2 | block | jsonb | ✅ |  | блок с контентом (текст, видео, код) |
| 3 | correct\_ratio | text | ✅ | да | соотношение правильных |
| 4 | create\_date | text | ✅ | да | дата создания |
| 5 | discussion\_proxy | text |  |  | прокси обсуждений |
| 6 | discussion\_threads | jsonb |  |  | треды обсуждений |
| 7 | discussions\_count | integer | ✅ | да | количество комментариев |
| 8 | has\_submissions\_restrictions | boolean |  | да | ограничения на отправки |
| 9 | instruction | text |  |  | инструкция |
| 10 | instruction\_type | text |  | да | тип инструкции |
| 11 | is\_enabled | boolean | ✅ | да | включен |
| 12 | is\_solutions\_unlocked | boolean |  | да | решения открыты |
| 13 | lesson | integer | ✅ | да | ID урока |
| 14 | max\_submissions\_count | integer |  | да | макс. попыток |
| 15 | needs\_plan | text |  |  | требует план |
| 16 | num\_grades | jsonb |  | да | оценки |
| 17 | passed\_by | integer | ✅ | да | сдало |
| 18 | position | integer | ✅ | да | позиция в уроке |
| 19 | progress | text | ✅ | да | URL прогресса |
| 20 | session | text |  |  | сессия |
| 21 | solutions\_unlocked\_attempts | integer |  | да | попыток до открытия решений |
| 22 | status | text | ✅ | да | статус |
| 23 | step\_issue | integer |  |  | проблема шага |
| 24 | subscriptions | jsonb |  |  | подписки |
| 25 | update\_date | text | ✅ | да | дата обновления |
| 26 | user\_step\_grade | text |  | да | оценка пользователя |
| 27 | user\_step\_vote | text |  | да | голос пользователя |
| 28 | variation | integer |  | да | вариация |
| 29 | variations\_count | integer |  | да | количество вариаций |
| 30 | viewed\_by | integer | ✅ | да | просмотрело |
| 31 | worth | integer | ✅ | да | баллы |
| 32 | id | integer | ✅ | да | ID шага (→ step\_id) |