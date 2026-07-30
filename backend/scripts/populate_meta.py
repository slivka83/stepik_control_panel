"""
Parse docs/api_propose.md and populate meta_endpoint + meta_field_mapping tables.
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings

SECTION_RE = re.compile(r"^\*\*endpoint:\*\*")
HEADER_RE = re.compile(r"\*\*(.+?):\*\*\s*(.*?)(?=\*\*|$)")
TABLE_SEP_RE = re.compile(r"^\|[\s\-:]+\|")

DB_TYPE_MAP = {
    "bigint": "bigint",
    "int": "integer",
    "text": "text",
    "boolean": "boolean",
    "numeric": "numeric",
    "timestamptz": "datetime(timezone)",
    "jsonb": "jsonb",
    "bigint[]": "jsonb",
}


def parse_table_rows(lines):
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            break
        if TABLE_SEP_RE.match(line):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 6:
            rows.append({
                "name": parts[0].replace("\\*", "*").replace("\\", ""),
                "db_field": parts[1].replace("`", "").replace("*", "").replace("\\", ""),
                "db_type": parts[2].replace("\\", ""),
                "description": parts[3].replace("\\", ""),
                "sync": parts[4].strip(),
                "key": parts[5].strip(),
            })
    return rows


def normalize_endpoint_name(path):
    m = re.match(r"/api/([a-z][a-z0-9\-]*)", path)
    if m:
        return m.group(1).replace("-", "_")
    return path.strip("/").replace("/", "_")


def target_to_raw(table):
    if not table or table == "-":
        return None
    parts = table.split("__", 1)
    if len(parts) == 2:
        return "raw_" + parts[1]
    if table.startswith("dim_") or table.startswith("fact_") or table.startswith("bridge_"):
        return "raw_" + table.split("_", 1)[1]
    return table


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    md_path = Path(__file__).resolve().parent.parent.parent / "docs" / "api_propose.md"
    md_text = md_path.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    sections = []
    current = None
    table_lines = []

    for line in lines:
        if SECTION_RE.match(line):
            if current:
                current["table"] = parse_table_rows(table_lines)
                sections.append(current)
            current = {"headers": {}}
            table_lines = []
        if current is None:
            continue
        for hm in re.finditer(HEADER_RE, line):
            key = hm.group(1).strip().lower().replace("\\", "")
            val = hm.group(2).strip().replace("\\", "")
            current["headers"][key] = val
        if line.startswith("|") and not TABLE_SEP_RE.match(line):
            table_lines.append(line)

    if current:
        current["table"] = parse_table_rows(table_lines)
        sections.append(current)

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM meta_field_mapping"))
        await conn.execute(text("DELETE FROM meta_endpoint"))

        for sec in sections:
            h = sec["headers"]
            endpoint_path = h.get("endpoint", "").strip("`")
            endpoint_name = normalize_endpoint_name(endpoint_path)
            api_object = h.get("api_object", "").strip("`")
            target = h.get("target_table", "").strip("`") or h.get("raw_table", "").strip("`")
            download = h.get("download", "Нет").strip()
            pk = h.get("primary_key", "").strip("`")
            incremental = h.get("incremental", "").strip()
            description = h.get("description", "").strip()

            raw_table = target_to_raw(target) if target and target != "-" else None
            if not raw_table:
                raw_table = "raw_" + endpoint_name

            is_active = download.lower() in ("да", "yes", "true")
            if download.strip() == "Опц":
                is_active = False

            auth = "user_token"
            if any(p in endpoint_path for p in ("course-benefit", "course-beneficiar", "stripe")):
                auth = "client_credentials"

            await conn.execute(
                text("""
                    INSERT INTO meta_endpoint
                        (endpoint_name, api_path, api_object, auth_method, raw_table,
                         pk_field, incremental, description, is_active, sync_order)
                    VALUES (:en, :ap, :ao, :am, :rt, :pk, :inc, :desc, :act, :so)
                """),
                {
                    "en": endpoint_name,
                    "ap": endpoint_path,
                    "ao": api_object,
                    "am": auth,
                    "rt": raw_table,
                    "pk": pk,
                    "inc": incremental if incremental else None,
                    "desc": description[:1000] if description else None,
                    "act": is_active,
                    "so": None,
                },
            )

            for row in sec.get("table", []):
                db_type = DB_TYPE_MAP.get(row["db_type"].strip(), "text")
                sync_val = row["sync"].strip()
                is_loaded = sync_val.lower() in ("да", "yes", "true")

                await conn.execute(
                    text("""
                        INSERT INTO meta_field_mapping
                            (endpoint_name, api_field, db_column, db_type, is_loaded, skip_reason, description)
                        VALUES (:en, :af, :dc, :dt, :il, :sr, :desc)
                    """),
                    {
                        "en": endpoint_name,
                        "af": row["name"],
                        "dc": row["db_field"],
                        "dt": db_type,
                        "il": is_loaded,
                        "sr": None if is_loaded else (row.get("description", "")[:500] or None),
                        "desc": row["description"][:500] if row.get("description") else None,
                    },
                )

        result = await conn.execute(
            text("SELECT endpoint_name, is_active FROM meta_endpoint ORDER BY endpoint_name")
        )
        rows = result.fetchall()
        active = sum(1 for r in rows if r[1])
        total = len(rows)
        mapping_count = (await conn.execute(text("SELECT COUNT(*) FROM meta_field_mapping"))).scalar()

    await engine.dispose()
    print(f"Done. {total} endpoints ({active} active, {total-active} inactive), {mapping_count} field mappings.")


if __name__ == "__main__":
    asyncio.run(main())
