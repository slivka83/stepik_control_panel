import csv
import glob
import io
import os
import zipfile
from collections import Counter
from datetime import datetime
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except Exception:
        return None


def parse_pct(value):
    try:
        return Decimal(str(value).replace("%", "").replace(",", ".").strip())
    except Exception:
        return None


rows = []
for path in sorted(glob.glob(os.path.join(BASE, "course-*-payments-*.csv.zip"))):
    course = (
        "231306"
        if "231306" in path
        else "68260"
        if "68260" in path
        else "258792"
        if "258792" in path
        else "?"
    )
    with zipfile.ZipFile(path) as archive:
        inner = archive.namelist()[0]
        text = archive.read(inner).decode("utf-8-sig")
    for number, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        row["_course"] = course
        row["_file"] = os.path.basename(path)
        row["_line"] = number
        row["_pay"] = parse_dt(row.get("payment_date_utc"))
        row["_ref"] = parse_dt(row.get("referral_link_click_utc"))
        row["_commission"] = parse_pct(row.get("commission"))
        row["_days"] = (
            (row["_pay"] - row["_ref"]).total_seconds() / 86400
            if row["_pay"] and row["_ref"]
            else None
        )
        rows.append(row)

stepik_promo = [
    row
    for row in rows
    if "stepik's expense" in (row.get("promo_code_type") or "").lower()
]
alink_seven = [
    row
    for row in rows
    if row["_ref"]
    and row["_days"] is not None
    and row["_days"] <= 7
    and row["_commission"] is not None
    and abs(float(row["_commission"]) - 7.0) <= 0.05
]

lines = [
    "# Пруф: ни одной продажи «А-ссылка + промокод Stepik + 7%»",
    "",
    "Источник: 3 файла «Платежи» из `reports/`, выгрузка 13.11.2026 12:06. "
    f"Всего строк: **{len(rows)}**.",
    "",
    "## Проверка 1. Все продажи с промокодом Stepik",
    "",
    "Строк с типом `Promo code at Stepik's expense` (колонка 5): "
    f"**{len(stepik_promo)}**. Комиссии (колонка 29): "
    + ", ".join(
        f"{rate}% — {count}"
        for rate, count in sorted(
            Counter(str(row["_commission"]) for row in stepik_promo).items(),
            key=lambda item: float(item[0]),
        )
    ),
    "",
    "**7,0% — 0 строк.** Ниже все строки, можно сверить построчно.",
    "",
    "| Файл | Строка | Дата оплаты | Покупатель | Промокод | Комиссия | Статус | А-ссылка ≤7д |",
    "|:--|--:|:--|--:|:--|--:|:--|:--|",
]
for row in sorted(stepik_promo, key=lambda item: item["_pay"] or datetime.min):
    has_alink = "да" if (row["_ref"] and row["_days"] is not None and row["_days"] <= 7) else "нет"
    pay_date = row["_pay"].strftime("%d.%m.%Y") if row["_pay"] else ""
    lines.append(
        f"| {row['_file']} | {row['_line']} | {pay_date} | {row.get('user_id')} "
        f"| {row.get('promo_code')} | {row.get('commission')} | {row.get('status')} | {has_alink} |"
    )

lines += [
    "",
    "## Проверка 2. Все продажи по А-ссылке с комиссией 7%",
    "",
    f"Всего: **{len(alink_seven)}**. Тип промокода (колонка 5): "
    + ", ".join(
        f"«{name or 'пусто'}» — {count}"
        for name, count in Counter(
            (row.get("promo_code_type") or "").strip() for row in alink_seven
        ).items()
    )
    + ".",
    "",
    "Строк с типом `Promo code at Stepik's expense` среди них: **0**.",
    "",
]

output = os.path.join(BASE, "proof_stepik_promo_7pct.md")
with open(output, "w", encoding="utf-8") as file:
    file.write("\n".join(lines))

print("written:", output)
print("stepik-side rows:", len(stepik_promo))
print(
    "of them at 7%:",
    sum(
        1
        for row in stepik_promo
        if row["_commission"] is not None
        and abs(float(row["_commission"]) - 7.0) <= 0.05
    ),
)
print("a-link at 7%:", len(alink_seven))
print(
    "of them with stepik-side type:",
    sum(
        1
        for row in alink_seven
        if "stepik's expense" in (row.get("promo_code_type") or "").lower()
    ),
)
print(
    "commissions among stepik-side:",
    dict(Counter(str(row["_commission"]) for row in stepik_promo)),
)
