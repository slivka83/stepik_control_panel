"""Shared domain constants for the Stepik Control Panel backend.

Single source of truth for month names and cohort segmentation thresholds.
"""

MONTH_NAMES: dict[int, str] = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

COHORT_ACTIVE_DAYS = 7
COHORT_PASSIVE_DAYS = 30
COHORT_FADING_DAYS = 90
ZOMBIE_DAYS_AFTER_JOIN = 3

UTM_SOURCE_LABELS: dict[str, str] = {
    "yandex_stpk": "Я.Директ",
    "ya_stpk": "Я.Директ",
    "stepik_email_stepik": "E-mail",
    "stepik_email_mautic": "E-mail",
    "stepik_newsletter": "E-mail",
    "stepik_telegram": "Telegram",
    "stepik_vk_smm": "VK",
    "notification": "Уведомления",
}
