# Поля доходов по курсам (raw\_course\_benefit)

Всего полей: 18. Отметь Да/Нет в колонке Sync.

| # | Поле API | Тип | Sync | Описание |
| --- | --- | --- | --- | --- |
| 1 | id | integer | да | ID записи (→ benefit\_id) |
| 2 | user | integer | да | пользователь-бенефициар |
| 3 | course | integer | да | ID курса |
| 4 | time | text | да | время дохода |
| 5 | status | text | да | статус (1 или 2) |
| 6 | amount | text | да | сумма дохода |
| 7 | currency\_code | text | да | валюта |
| 8 | payment\_amount | text | да | сумма платежа |
| 9 | buyer | integer | да | покупатель |
| 10 | is\_gift | boolean | да | подарок |
| 11 | promo\_code | text | да | промокод |
| 12 | is\_stepik\_side | boolean | да | доход Stepik |
| 13 | first\_course\_click\_utm | jsonb | да | UTM первого клика |
| 14 | last\_course\_click\_utm | jsonb | да | UTM последнего клика |
| 15 | description | text | да | описание |
| 16 | is\_invoice\_payment | boolean | да | платёж по счету |
| 17 | is\_z\_link\_used | boolean | да | использована Z-ссылка |
| 18 | seats\_count | integer | да | количество мест |