import httpx
from typing import Any

from app.services.rate_limiter import acquire_token, handle_rate_limit

STEPIK_API_BASE = "https://stepik.org/api"


class StepikAPIError(Exception):
    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Stepik API error {status_code}: {detail}")


async def _request(method: str, path: str, token: str | None = None, params: dict | None = None) -> dict[str, Any]:
    if method.upper() != "GET":
        raise ValueError("Only GET requests are allowed to Stepik API (Zero-Write Policy)")

    if not await acquire_token():
        await handle_rate_limit(1.0)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{STEPIK_API_BASE}{path}",
            headers=headers,
            params=params,
            timeout=30.0,
        )

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "5"))
            await handle_rate_limit(retry_after)
            return await _request(method, path, token, params)

        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)

        return response.json()


async def get_course(course_id: int, token: str | None = None) -> dict:
    data = await _request("GET", f"/courses/{course_id}", token)
    return data.get("courses", [{}])[0]


async def get_courses_batch(course_ids: list[int], token: str | None = None) -> list[dict]:
    params = {"ids[]": course_ids}
    data = await _request("GET", "/courses", token, params)
    return data.get("courses", [])


async def get_sections(course_id: int, token: str | None = None) -> list[dict]:
    params = {"course": course_id}
    data = await _request("GET", "/sections", token, params)
    return data.get("sections", [])


async def get_units(section_id: int, token: str | None = None) -> list[dict]:
    params = {"section": section_id}
    data = await _request("GET", "/units", token, params)
    return data.get("units", [])


async def get_steps(lesson_id: int, token: str | None = None) -> list[dict]:
    params = {"lesson": lesson_id}
    data = await _request("GET", "/steps", token, params)
    return data.get("steps", [])


async def get_course_grades(course_id: int, token: str | None = None) -> list[dict]:
    params = {"course": course_id}
    data = await _request("GET", "/course-grades", token, params)
    return data.get("course-grades", [])


async def get_wrong_submissions(course_id: int, token: str | None = None) -> list[dict]:
    params = {"course": course_id, "status": "wrong"}
    data = await _request("GET", "/submissions", token, params)
    return data.get("submissions", [])


async def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://stepik.org/oauth2/token/",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": "http://localhost:8000/api/auth/callback",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        return response.json()
