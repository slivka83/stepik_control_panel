"""
Rebuild a raw table: parse fields doc → recreate table with only sync=Да cols → restore data.

Usage: python scripts/rebuild_raw.py <endpoint_name>

Example: python scripts/rebuild_raw.py units
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


def get_synced_fields(endpoint_name: str) -> list[str]:
    """Parse docs/fields_{endpoint_name}.md → list of sync=Да API field names."""
    path = Path(__file__).resolve().parent.parent.parent / "docs" / f"fields_{endpoint_name}.md"
    content = path.read_text()
    synced = []
    sync_idx = None
    for line in content.split("\n"):
        if not line.startswith("| ") or "|---|" in line.replace(" ", ""):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]

        # Detect sync column index from header
        if sync_idx is None and "Поле API" in parts:
            for idx, val in enumerate(parts):
                if val == "Sync":
                    sync_idx = idx
                    break
            continue

        if sync_idx is not None and len(parts) > sync_idx:
            api_field = parts[1].replace("\\_", "_")
            sync = parts[sync_idx].strip().lower()
            if sync == "да" and api_field not in ("#", "Поле API", ""):
                synced.append(api_field)
    return synced


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rebuild_raw.py <endpoint_name>")
        return
    ep_name = sys.argv[1]
    sync_fields = get_synced_fields(ep_name)
    print(f"{ep_name}: sync=Да = {len(sync_fields)} fields")

    s = get_settings()
    engine = create_async_engine(s.database_url)

    # Read meta: endpoint info + api_field → db_column mapping
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT raw_table FROM meta_endpoint WHERE endpoint_name = :en"),
            {"en": ep_name},
        )
        ep_row = r.fetchone()
        if not ep_row:
            print(f"Endpoint '{ep_name}' not found in meta_endpoint")
            return
        raw_table = ep_row[0]

        r = await conn.execute(
            text("SELECT api_field, db_column FROM meta_field_mapping WHERE endpoint_name = :en"),
            {"en": ep_name},
        )
        meta_map = {row[0]: row[1] for row in r.fetchall()}  # api_field → db_column

    # Get db columns for synced fields (skip id — maps to serial PK)
    sync_db_cols = []
    for f in sync_fields:
        db_c = meta_map.get(f, f)
        if db_c == "id":
            continue
        sync_db_cols.append((f, db_c))

    # Get sample _raw_json for type detection
    async with engine.begin() as conn:
        r = await conn.execute(text(f'SELECT _raw_json FROM "{raw_table}" LIMIT 1'))
        row = r.fetchone()
        if not row:
            print("ERROR: table is empty")
            return
        sample = row[0]

    types = {}
    for api_f, db_c in sync_db_cols:
        val = sample.get(api_f)
        if val is not None and isinstance(val, (list, dict)):
            types[db_c] = "jsonb"
        else:
            types[db_c] = "text"
    jsonb_cols = [c for c, t in types.items() if t == "jsonb"]
    print(f"  jsonb: {len(jsonb_cols)}, text: {len(types) - len(jsonb_cols)}")

    # Rebuild
    async with engine.begin() as conn:
        backup_name = f"_raw_{ep_name}_backup"
        await conn.execute(text(f'CREATE TABLE "{backup_name}" AS SELECT id, _raw_json, _loaded_at FROM "{raw_table}"'))
        count = (await conn.execute(text(f'SELECT COUNT(*) FROM "{backup_name}"'))).scalar()
        print(f"  Backed up {count} rows")

        # Drop old
        await conn.execute(text(f'DROP TABLE "{raw_table}"'))

        # Create new
        col_defs = ['"id" SERIAL PRIMARY KEY']
        for db_c in (c for _, c in sync_db_cols):
            col_defs.append(f'"{db_c}" {types[db_c]}')
        col_defs.append('"_raw_json" jsonb')
        col_defs.append('"_loaded_at" timestamptz DEFAULT now()')
        await conn.execute(text(f'CREATE TABLE "{raw_table}" (\n  ' + ",\n  ".join(col_defs) + "\n)"))

        # Restore
        backup = await conn.execute(text(f'SELECT id, _raw_json, _loaded_at FROM "{backup_name}"'))
        for row in backup.fetchall():
            rid, obj, loaded_at = row
            col_names = ['"id"']
            col_values = [rid]
            for api_f, db_c in sync_db_cols:
                val = obj.get(api_f)
                if val is not None and isinstance(val, (dict, list)):
                    col_values.append(json.dumps(val, ensure_ascii=False))
                elif val is not None:
                    col_values.append(str(val))
                else:
                    col_values.append(None)
                col_names.append(f'"{db_c}"')
            col_names.append('"_raw_json"')
            col_values.append(json.dumps(obj, ensure_ascii=False))
            col_names.append('"_loaded_at"')
            col_values.append(loaded_at)

            ph = ", ".join(f":p{i}" for i in range(len(col_names)))
            sql = f'INSERT INTO "{raw_table}" ({", ".join(col_names)}) VALUES ({ph})'
            await conn.execute(text(sql), {f"p{i}": col_values[i] for i in range(len(col_values))})

        await conn.execute(text(f'DROP TABLE "{backup_name}"'))

        # Update meta is_loaded
        for api_f, db_c in sync_db_cols:
            await conn.execute(
                text("""
                    UPDATE meta_field_mapping
                    SET is_loaded = true, skip_reason = NULL
                    WHERE endpoint_name = :en AND (api_field = :af OR db_column = :dc)
                """),
                {"en": ep_name, "af": api_f, "dc": db_c},
            )
        # Mark the rest as not loaded
        loaded_api = [f for f, _ in sync_db_cols]
        if loaded_api:
            placeholders = ", ".join(f"'{f}'" for f in loaded_api)
            r = await conn.execute(
                text(f"""
                    UPDATE meta_field_mapping
                    SET is_loaded = false, skip_reason = 'not needed for dashboard'
                    WHERE endpoint_name = :en AND api_field NOT IN ({placeholders})
                      AND (is_loaded IS NULL OR is_loaded = true)
                """),
                {"en": ep_name},
            )
            print(f"  Meta updated: {r.rowcount} fields unloaded")

        # Verify
        cnt = (await conn.execute(text(f'SELECT COUNT(*) FROM "{raw_table}"'))).scalar()
        r = await conn.execute(
            text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = :t AND column_name NOT IN ('id','_raw_json','_loaded_at')
                ORDER BY ordinal_position
            """),
            {"t": raw_table},
        )
        data_cols = [row[0] for row in r.fetchall()]
        col_list = ", ".join(f'"{c}"' for c in data_cols[:6])
        r2 = await conn.execute(text(f'SELECT {col_list} FROM "{raw_table}" LIMIT 3'))
        print(f"Done. {cnt} rows, {len(data_cols)} data columns")
        for row2 in r2:
            vals = ", ".join(f"{c}={str(row2[i])[:30]}" for i, c in enumerate(data_cols[:6]))
            print(f"  {vals}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
