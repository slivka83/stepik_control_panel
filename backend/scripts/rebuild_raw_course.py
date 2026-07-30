"""
Rebuild raw_course with only synced columns (based on docs/fields_courses.md Sync column).
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings


def get_synced_fields():
    path = Path(__file__).resolve().parent.parent.parent / "docs" / "fields_courses.md"
    content = path.read_text()
    fields = []
    for line in content.split("\n"):
        if not line.startswith("| ") or "|---|" in line.replace(" ", ""):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 5:
            field = parts[1].replace("\\_", "_")
            sync = parts[4].strip().lower() if len(parts) > 4 else ""
            if sync and field not in ("#", "Поле API", ""):
                fields.append(field)
    return fields


async def main():
    sync_fields = get_synced_fields()
    print(f"Sync=Да: {len(sync_fields)} fields")

    s = get_settings()
    engine = create_async_engine(s.database_url)

    # Read mapping: api_field → db_column from meta
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT api_field, db_column FROM meta_field_mapping WHERE endpoint_name = 'courses'")
        )
        mapping = {row[1]: row[0] for row in r.fetchall()}  # db_column → api_field

    # Get sample _raw_json to determine types
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT _raw_json FROM raw_course LIMIT 1"))
        row = r.fetchone()
        if not row:
            print("ERROR: raw_course is empty")
            return
        sample = row[0]

    types = {}
    for f in sync_fields:
        api_key = mapping.get(f, f)
        if api_key in sample and isinstance(sample[api_key], (list, dict)):
            types[f] = "jsonb"
        else:
            types[f] = "text"

    jsonb_fields = [f for f, t in types.items() if t == "jsonb"]
    print(f"  jsonb: {len(jsonb_fields)}, text: {len(types) - len(jsonb_fields)}")

    async with engine.begin() as conn:
        # Backup
        await conn.execute(text("CREATE TABLE _raw_course_backup AS SELECT id, _raw_json, _loaded_at FROM raw_course"))
        count = (await conn.execute(text("SELECT COUNT(*) FROM _raw_course_backup"))).scalar()
        print(f"Backed up {count} rows")

        # Drop old
        await conn.execute(text("DROP TABLE raw_course"))

        # Create new
        cols = ['"id" SERIAL PRIMARY KEY']
        for f in sync_fields:
            cols.append(f'"{f}" {types[f]}')
        cols.append('"_raw_json" jsonb')
        cols.append('"_loaded_at" timestamptz DEFAULT now()')
        await conn.execute(text("CREATE TABLE raw_course (\n  " + ",\n  ".join(cols) + "\n)"))

        # Restore from backup — extract from _raw_json using API field names
        backup = await conn.execute(text("SELECT id, _raw_json, _loaded_at FROM _raw_course_backup"))
        for row in backup.fetchall():
            rid, obj, loaded_at = row
            col_names = ['"id"']
            col_values = [rid]
            for f in sync_fields:
                api_key = mapping.get(f, f)
                val = obj.get(api_key)
                if val is not None and isinstance(val, (dict, list)):
                    col_values.append(json.dumps(val, ensure_ascii=False))
                elif val is not None:
                    col_values.append(str(val))
                else:
                    col_values.append(None)
                col_names.append(f'"{f}"')
            col_names.append('"_raw_json"')
            col_values.append(json.dumps(obj, ensure_ascii=False))
            col_names.append('"_loaded_at"')
            col_values.append(loaded_at)

            ph = ", ".join(f":p{i}" for i in range(len(col_names)))
            sql = f"INSERT INTO raw_course ({', '.join(col_names)}) VALUES ({ph})"
            await conn.execute(text(sql), {f"p{i}": col_values[i] for i in range(len(col_values))})

        await conn.execute(text("DROP TABLE _raw_course_backup"))

        # Update meta_field_mapping — use db_column here since that's what sync_fields are
        for f in sync_fields:
            api_f = mapping.get(f, f)
            await conn.execute(
                text("UPDATE meta_field_mapping SET is_loaded = true, skip_reason = NULL WHERE endpoint_name = 'courses' AND (api_field = :f1 OR db_column = :f2)"),
                {"f1": api_f, "f2": f},
            )
        r = await conn.execute(text("SELECT api_field FROM meta_field_mapping WHERE endpoint_name = 'courses' AND is_loaded IS DISTINCT FROM true"))
        for row in r.fetchall():
            await conn.execute(
                text("UPDATE meta_field_mapping SET is_loaded = false, skip_reason = 'not needed for dashboard' WHERE endpoint_name = 'courses' AND api_field = :f"),
                {"f": row[0]},
            )

        # Verify
        cnt = (await conn.execute(text("SELECT COUNT(*) FROM raw_course"))).scalar()
        r = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'raw_course' ORDER BY ordinal_position"))
        all_cols = [c[0] for c in r.fetchall()]
        data_cols = [c for c in all_cols if c not in ("id", "_raw_json", "_loaded_at")]
        print(f"Done. {cnt} rows, {len(data_cols)} data columns")
        # Spot check
        r = await conn.execute(text("SELECT course_id, title, slug FROM raw_course LIMIT 3"))
        for row in r:
            print(f"  course_id={row[0]} title={str(row[1])[:50]} slug={str(row[2])[:30]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
