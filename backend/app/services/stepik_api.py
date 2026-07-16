import httpx
from typing import Any
import time

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


async def get_courses(user_id: int | None = None, token: str | None = None) -> list[dict]:
    params: dict[str, Any] = {}
    if user_id:
        params["teacher"] = user_id
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


async def get_courses_batch(ids: list[int], token: str | None = None) -> list[dict]:
    params = {"ids[]": ids}
    data = await _request("GET", "/courses", token, params)
    return data.get("courses", [])


async def get_wrong_submissions(course_id: int, token: str | None = None) -> list[dict]:
    params = {"course": course_id, "status": "wrong"}
    data = await _request("GET", "/submissions", token, params)
    return data.get("submissions", [])


async def get_user_profile(token: str) -> dict:
    data = await _request("GET", "/profiles", token)
    profiles = data.get("profiles", [])
    if profiles:
        return profiles[0]
    users_data = await _request("GET", "/users", token)
    users = users_data.get("users", [])
    return users[0] if users else {}


async def get_user_courses(course_id: int, token: str) -> list[dict]:
    params = {"course": course_id}
    data = await _request("GET", "/user-courses", token, params)
    return data.get("user-courses", [])


async def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://stepik.org/oauth2/token/",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        return response.json()


async def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://stepik.org/oauth2/token/",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": "http://localhost:3000/api/auth/callback",
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        return response.json()


_finance_token_cache: dict[str, Any] = {"token": None, "expires_at": 0}


async def get_finance_token(client_id: str, client_secret: str) -> str:
    now = time.time()
    if _finance_token_cache["token"] and _finance_token_cache["expires_at"] > now + 60:
        return _finance_token_cache["token"]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://stepik.org/oauth2/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "read",
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise StepikAPIError(response.status_code, response.text)
        data = response.json()
        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 36000)
        _finance_token_cache["token"] = token
        _finance_token_cache["expires_at"] = now + expires_in
        return token
