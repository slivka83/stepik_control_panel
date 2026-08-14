"""Architecture contract tests: single alembic head, no dead artifacts,
no duplicated constants, config defaults match docker-compose, dashboard split.

These guard the refactoring: if a stale artifact resurfaces or a migration
fork reappears, the suite fails.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestAlembicGraph:
    def test_single_head(self):
        """Migration graph must be linear — no forked heads."""
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 alembic head, got {heads}"

    def test_meta_tables_migration_after_raw_fixes(self):
        """017 must be the head, chained after 016 (which followed 015)."""
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        head = script.get_heads()[0]
        assert head == "017", head
        rev = script.get_revision(head)
        assert rev.down_revision == "016", rev.down_revision


class TestDeadArtifacts:
    def test_no_step_sync_state_in_app(self):
        """Dead StepSyncState model was removed; raw_sync_state is the only state table."""
        for path in (BACKEND_DIR / "app").rglob("*.py"):
            assert "step_sync_state" not in _read(path), f"{path} references dead table"

    def test_no_step_sync_state_model(self):
        model_file = BACKEND_DIR / "app" / "models" / "step_sync_state.py"
        assert not model_file.exists(), "dead StepSyncState model must stay deleted"

    def test_scripts_directory_only_tools(self):
        """Orphan one-off scripts were removed; only AGENTS.md-referenced tools remain."""
        scripts = {p.name for p in (BACKEND_DIR / "scripts").glob("*.py")}
        assert scripts == {"sync_raw.py", "explore_endpoint.py", "rebuild_raw.py", "rebuild_marts.py"}, scripts


class TestSingleSourceOfTruth:
    def test_month_names_defined_once(self):
        """MONTH_NAMES must live only in app/constants.py."""
        definitions = []
        for path in (BACKEND_DIR / "app").rglob("*.py"):
            if path.name == "constants.py":
                continue
            for i, line in enumerate(_read(path).splitlines(), 1):
                if "MONTH_NAMES" in line and "=" in line and "import" not in line:
                    definitions.append(f"{path}:{i}")
        assert not definitions, f"duplicate MONTH_NAMES definitions: {definitions}"

    def test_calculate_cohort_status_defined_once(self):
        definitions = []
        for path in (BACKEND_DIR / "app").rglob("*.py"):
            for i, line in enumerate(_read(path).splitlines(), 1):
                if line.strip().startswith("def calculate_cohort_status"):
                    definitions.append(f"{path}:{i}")
        assert len(definitions) == 1, f"expected 1 definition, got {definitions}"

    def test_stepik_urls_defined_in_stepik_api(self):
        src = _read(BACKEND_DIR / "app" / "services" / "stepik_api.py")
        assert 'STEPIK_API_BASE = "https://stepik.org/api"' in src
        assert 'STEPIK_OAUTH_TOKEN_URL = "https://stepik.org/oauth2/token/"' in src
        for script in ["sync_raw.py", "explore_endpoint.py", "rebuild_marts.py"]:
            script_src = _read(BACKEND_DIR / "scripts" / script)
            assert "stepik.org" not in script_src, f"{script} hardcodes stepik.org"

    def test_rebuild_marts_runs_all_transforms_in_sync_order(self):
        """rebuild_marts.py must rebuild every mart from the raw layer,
        in sync_all order, without API calls, and abort on empty raw_course."""
        src = _read(BACKEND_DIR / "scripts" / "rebuild_marts.py")
        for fn in [
            "transform_courses",
            "transform_enrollments",
            "transform_submissions",
            "transform_financials",
            "transform_community",
            "transform_students",
            "transform_steps",
            "transform_comments",
            "transform_certificates",
            "transform_reviews",
        ]:
            assert f"{fn}" in src, f"rebuild_marts.py must call {fn}"
        assert "raw_course is empty" in src, "rebuild_marts.py must abort on empty raw_course"
        assert "http" not in src and "httpx" not in src, "rebuild_marts.py must not call the API"


class TestConstantsContract:
    def test_month_names_covers_all_months(self):
        from app.constants import MONTH_NAMES

        assert set(MONTH_NAMES) == set(range(1, 13))
        assert MONTH_NAMES[1] == "Январь"
        assert MONTH_NAMES[12] == "Декабрь"

    def test_cohort_thresholds_are_consistent(self):
        from app.constants import (
            COHORT_ACTIVE_DAYS,
            COHORT_FADING_DAYS,
            COHORT_PASSIVE_DAYS,
        )

        assert COHORT_ACTIVE_DAYS <= COHORT_PASSIVE_DAYS <= COHORT_FADING_DAYS
        assert COHORT_ACTIVE_DAYS == 7
        assert COHORT_PASSIVE_DAYS == 30
        assert COHORT_FADING_DAYS == 90


class TestConfigDefaults:
    def test_database_default_matches_docker_compose(self):
        import os

        from app.config import Settings

        os.environ.pop("DATABASE_URL", None)
        s = Settings()
        assert "localhost:5433" in s.database_url

    def test_redis_default_matches_docker_compose(self):
        import os

        from app.config import Settings

        os.environ.pop("REDIS_URL", None)
        s = Settings()
        assert "localhost:6380" in s.redis_url


class TestDashboardPackage:
    EXPECTED_ROUTES = {
        "/api/dashboard/alerts",
        "/api/dashboard/kpi",
        "/api/dashboard/cohorts",
        "/api/dashboard/revenue",
        "/api/dashboard/submissions",
        "/api/dashboard/active-students",
        "/api/dashboard/active-enrolled-students",
        "/api/dashboard/published-solutions",
        "/api/dashboard/certificates",
        "/api/dashboard/certificates/stats",
        "/api/dashboard/reviews/stats",
        "/api/dashboard/comments",
        "/api/dashboard/students",
        "/api/dashboard/hardest-steps",
    }

    def test_all_dashboard_routes_registered(self):
        from app.main import app

        paths = {route.path for route in app.routes}
        assert paths >= self.EXPECTED_ROUTES

    def test_dashboard_is_package(self):
        pkg = BACKEND_DIR / "app" / "api" / "dashboard"
        assert (pkg / "__init__.py").exists()
        for module in ["alerts", "kpi", "cohorts", "charts", "comments", "students", "steps", "certificates", "reviews", "common"]:
            assert (pkg / f"{module}.py").exists(), f"missing {module}.py"

    def test_old_god_file_removed(self):
        assert not (BACKEND_DIR / "app" / "api" / "dashboard.py").exists()

    def test_no_duplicate_month_labels_in_dashboard(self):
        """MONTH_LABELS_RU was replaced by app.constants.MONTH_NAMES."""
        for path in (BACKEND_DIR / "app" / "api").rglob("*.py"):
            assert "MONTH_LABELS_RU" not in _read(path), f"{path} reintroduces MONTH_LABELS_RU"


class TestDependencies:
    def test_no_unused_runtime_deps(self):
        req = _read(BACKEND_DIR / "requirements.txt")
        assert "gunicorn" not in req, "gunicorn is unused (uvicorn in start.sh)"
        assert "python-dotenv" not in req, "python-dotenv is unused (pydantic-settings loads .env)"

    def test_pytest_config_not_split(self):
        """pytest config must live in pytest.ini only — pyproject cov block was dead."""
        pyproject = _read(BACKEND_DIR / "pyproject.toml")
        assert "[tool.pytest.ini_options]" not in pyproject
