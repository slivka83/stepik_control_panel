"""
Reload raw_course from API with correct teacher=64381531.
Uses existing raw_course schema (only sync=Да columns) — no column changes.
"""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.services.crypto import decrypt_token
from app.services.stepik_api import STEPIK_API_BASE

s = get_settings()
engine = create_async_engine(s.database_url)


async def main():
    # Get token
    token_enc = None
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT access_token FROM users ORDER BY created_at DESC LIMIT 1"))
        token_enc = r.scalar()
    if not token_enc:
        print("No token in DB")
        return
    token = decrypt_token(token_enc)

    # Fetch courses
    all_courses = []
    page = 1
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{STEPIK_API_BASE}/courses",
                headers={"Authorization": f"Bearer {token}"},
                params={"teacher": s.stepik_user_id, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            courses = data.get("courses", [])
            all_courses.extend(courses)
            if not data.get("meta", {}).get("has_next"):
                break
            page += 1

    print(f"Fetched {len(all_courses)} courses from API")

    # Truncate and reload
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE raw_course RESTART IDENTITY CASCADE"))

        r = await conn.execute(
            text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'raw_course' ORDER BY ordinal_position")
        )
        db_cols = [row for row in r.fetchall() if row[0] not in ("id", "_raw_json", "_loaded_at")]

        # Get mapping: db_column → api_field
        r = await conn.execute(
            text("SELECT api_field, db_column FROM meta_field_mapping WHERE endpoint_name = 'courses'")
        )
        mapping = {row[1]: row[0] for row in r.fetchall()}  # db_column → api_field

        col_names = [f'"{c[0]}"' for c in db_cols] + ['"_raw_json"']
        ph = ", ".join(f":p{i}" for i in range(len(col_names)))
        sql = f"INSERT INTO raw_course ({', '.join(col_names)}) VALUES ({ph})"

        loaded = 0
        for obj in all_courses:
            raw_json = json.dumps(obj, ensure_ascii=False)
            values = []
            for c, _ in db_cols:
                api_key = mapping.get(c, c)
                val = obj.get(api_key)
                if val is not None and isinstance(val, (dict, list)):
                    values.append(json.dumps(val, ensure_ascii=False))
                elif val is not None:
                    values.append(str(val))
                else:
                    values.append(None)
            params = {f"p{i}": values[i] for i in range(len(values))}
            params[f"p{len(values)}"] = raw_json
            await conn.execute(text(sql), params)
            loaded += 1

        cnt = await conn.execute(text("SELECT COUNT(*) FROM raw_course"))
        print(f"Reloaded {loaded} courses. Total rows: {cnt.scalar()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
