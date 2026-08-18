import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.api.financials import DAYS_BACK, _build_daily_stats
from app.database import get_db
from app.main import app
from app.models import FinancialSnapshot, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


class TestFinancials:
    async def test_returns_snapshot_data(self, db_session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("test_access"),
            refresh_token=encrypt_token("test_refresh"),
            token_expires_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(user)
        await db_session.flush()

        now = datetime.now(UTC)
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "total_turnover": 200000,
                        "total_income": 150000,
                        "total_refunds": 5000,
                        "total_payments": 42,
                    },
                    "months": [
                        {
                            "month": "Январь 2025",
                            "year": 2025,
                            "month_num": 1,
                            "income": 50000,
                            "turnover": 70000,
                            "refunds": 0,
                            "payments_count": 15,
                            "refunds_count": 0,
                        },
                        {
                            "month": "Февраль 2025",
                            "year": 2025,
                            "month_num": 2,
                            "income": 30000,
                            "turnover": 40000,
                            "refunds": 2000,
                            "payments_count": 10,
                            "refunds_count": 1,
                        },
                        {
                            "month": "Январь 2026",
                            "year": 2026,
                            "month_num": 1,
                            "income": 70000,
                            "turnover": 90000,
                            "refunds": 0,
                            "payments_count": 17,
                            "refunds_count": 0,
                        },
                    ],
                    "courses": [{"title": "Python", "income": 100000}],
                    "recent_payments": [
                        {
                            "id": 1,
                            "amount": 2940,
                            "payment_amount": 4000,
                            "status": "debited",
                            "time": (now - timedelta(days=1)).isoformat(),
                        },
                        {
                            "id": 2,
                            "amount": -1000,
                            "payment_amount": 1200,
                            "status": "refunded",
                            "time": (now - timedelta(days=1)).isoformat(),
                        },
                        {
                            "id": 3,
                            "amount": 500,
                            "payment_amount": 500,
                            "status": "debited",
                            "time": (now - timedelta(days=3)).isoformat(),
                        },
                    ],
                },
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 200000
            assert "net_income" not in data["summary"]
            assert len(data["months"]) == 3
            assert len(data["courses"]) == 1
            assert [y["year"] for y in data["years"]] == [2025, 2026]
            assert data["years"][0]["payments_count"] == 25
            assert data["years"][0]["turnover"] == 110000
            assert data["years"][0]["income"] == 80000
            assert data["years"][0]["refunds"] == 2000
            assert data["years"][1]["payments_count"] == 17
            assert data["years"][1]["income"] == 70000

            today = datetime.now(UTC).date()
            assert len(data["days"]) == 30
            assert data["days"][0]["day"] == today.isoformat()
            assert data["days"][0]["payments_count"] == 0
            yesterday = (today - timedelta(days=1)).isoformat()
            y = next(d for d in data["days"] if d["day"] == yesterday)
            assert y["payments_count"] == 2
            assert y["turnover"] == 2800
            assert y["income"] == 1940
            assert y["refunds"] == 1000
            assert y["refunds_count"] == 1
            d3 = (today - timedelta(days=3)).isoformat()
            day3 = next(d for d in data["days"] if d["day"] == d3)
            assert day3["payments_count"] == 1
            assert day3["turnover"] == 500
            assert day3["income"] == 500
            assert day3["refunds"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_no_snapshot_returns_defaults(self, db_session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("test_access"),
            refresh_token=encrypt_token("test_refresh"),
            token_expires_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(user)
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            response = client.get("/api/financials")
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["total_turnover"] == 0
            assert data["months"] == []
            assert data["years"] == []
            assert data["days"] == []
        finally:
            app.dependency_overrides.clear()


class TestBuildDailyStats:
    """Pure-function edge cases for the «By days» aggregation window."""

    def _payment(self, days_offset, **overrides):
        dt = datetime.now(UTC) - timedelta(days=days_offset)
        base = {
            "id": 1,
            "amount": 100,
            "payment_amount": 100,
            "status": "debited",
            "time": dt.isoformat(),
        }
        base.update(overrides)
        return base

    def _by_day(self, days, day_str):
        return next(d for d in days if d["day"] == day_str)

    def test_today_included(self):
        today = datetime.now(UTC).date().isoformat()
        days = _build_daily_stats([self._payment(0)])
        assert self._by_day(days, today)["payments_count"] == 1

    def test_window_start_included_outside_excluded(self):
        start = (datetime.now(UTC).date() - timedelta(days=DAYS_BACK - 1)).isoformat()
        outside = (datetime.now(UTC).date() - timedelta(days=DAYS_BACK)).isoformat()
        days = _build_daily_stats([self._payment(DAYS_BACK - 1), self._payment(DAYS_BACK)])
        assert self._by_day(days, start)["payments_count"] == 1
        # the day 31 days back is outside the window and must not be present
        assert outside not in {d["day"] for d in days}

    def test_future_excluded(self):
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        days = _build_daily_stats([self._payment(0, time=future)])
        assert all(d["payments_count"] == 0 for d in days)

    def test_z_suffix_parsed(self):
        dt = datetime.now(UTC) - timedelta(days=2)
        ztime = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        days = _build_daily_stats([self._payment(0, time=ztime)])
        assert self._by_day(days, dt.date().isoformat())["payments_count"] == 1

    def test_malformed_time_skipped(self):
        days = _build_daily_stats([self._payment(0, time="not-a-date")])
        assert all(d["payments_count"] == 0 for d in days)

    def test_missing_time_skipped(self):
        days = _build_daily_stats([self._payment(0, time="")])
        assert all(d["payments_count"] == 0 for d in days)

    def test_positive_refund_uses_abs(self):
        dt = datetime.now(UTC) - timedelta(days=1)
        pay = {
            "id": 1,
            "amount": 1000,
            "payment_amount": 1200,
            "status": "refunded",
            "time": dt.isoformat(),
        }
        days = _build_daily_stats([pay])
        b = self._by_day(days, dt.date().isoformat())
        assert b["refunds"] == 1000
        assert b["refunds_count"] == 1
        assert b["turnover"] == -1200
        assert b["income"] == 1000

    def test_zero_payment(self):
        dt = datetime.now(UTC) - timedelta(days=1)
        pay = {
            "id": 1,
            "amount": 0,
            "payment_amount": 0,
            "status": "debited",
            "time": dt.isoformat(),
        }
        days = _build_daily_stats([pay])
        b = self._by_day(days, dt.date().isoformat())
        assert b["payments_count"] == 1
        assert b["turnover"] == 0
        assert b["income"] == 0

    def test_empty_returns_30_zero_buckets(self):
        days = _build_daily_stats([])
        assert len(days) == 30
        assert all(d["payments_count"] == 0 for d in days)

    def test_multiple_same_day_aggregate(self):
        dt = datetime.now(UTC) - timedelta(days=1)
        t = dt.isoformat()
        pays = [
            {"id": 1, "amount": 100, "payment_amount": 100, "status": "debited", "time": t},
            {"id": 2, "amount": 200, "payment_amount": 200, "status": "debited", "time": t},
        ]
        days = _build_daily_stats(pays)
        b = self._by_day(days, dt.date().isoformat())
        assert b["payments_count"] == 2
        assert b["turnover"] == 300
        assert b["income"] == 300


class TestFinancialsEdge:
    async def _seed_user(self, db_session):
        user = User(
            id=uuid.uuid4(),
            stepik_id=64381531,
            access_token=encrypt_token("test_access"),
            refresh_token=encrypt_token("test_refresh"),
            token_expires_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(user)
        await db_session.commit()
        return user

    async def test_snapshot_empty_recent_payments_days_are_zero(self, db_session):
        user = await self._seed_user(db_session)
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {
                        "total_turnover": 1000,
                        "total_income": 500,
                        "total_refunds": 0,
                        "total_payments": 5,
                    },
                    "months": [
                        {
                            "month": "Январь 2026",
                            "year": 2026,
                            "month_num": 1,
                            "income": 500,
                            "turnover": 1000,
                            "refunds": 0,
                            "payments_count": 5,
                            "refunds_count": 0,
                        }
                    ],
                    "courses": [],
                    "recent_payments": [],
                },
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            data = client.get("/api/financials").json()
            assert len(data["days"]) == 30
            assert all(d["payments_count"] == 0 for d in data["days"])
            assert data["years"][0]["year"] == 2026
        finally:
            app.dependency_overrides.clear()

    async def test_yearly_aggregation_skips_month_without_year(self, db_session):
        user = await self._seed_user(db_session)
        db_session.add(
            FinancialSnapshot(
                id=uuid.uuid4(),
                data={
                    "summary": {},
                    "months": [
                        {
                            "month": "Январь 2026",
                            "year": 2026,
                            "month_num": 1,
                            "income": 500,
                            "turnover": 1000,
                            "refunds": 0,
                            "payments_count": 5,
                            "refunds_count": 0,
                        },
                        {
                            "month": "Без года",
                            "income": 999,
                            "turnover": 999,
                            "refunds": 0,
                            "payments_count": 9,
                            "refunds_count": 0,
                        },
                    ],
                    "courses": [],
                    "recent_payments": [],
                },
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.commit()

        async def override_db():
            yield db_session

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_user] = override_user
        try:
            data = client.get("/api/financials").json()
            assert len(data["years"]) == 1
            assert data["years"][0]["year"] == 2026
        finally:
            app.dependency_overrides.clear()
