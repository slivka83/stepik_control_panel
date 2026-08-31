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


def _simulate_migrations() -> tuple[dict[str, set[str]], list[str]]:
    """Прогнать upgrade() всех миграций по порядку и вернуть итоговую схему
    {table: {columns}}. Чистый AST-парсинг — без выполнения кода миграций."""
    import ast

    versions_dir = BACKEND_DIR / "migrations" / "versions"
    revisions: dict[str, dict] = {}
    for path in versions_dir.glob("*.py"):
        tree = ast.parse(_read(path))
        rev = down = None
        for node in ast.walk(tree):
            assign = None
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                assign = node
            if assign is None:
                continue
            targets = assign.targets if isinstance(assign, ast.Assign) else [assign.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    rev = assign.value.value
                if isinstance(target, ast.Name) and target.id == "down_revision":
                    v = assign.value
                    if isinstance(v, ast.Constant):
                        down = v.value
                    elif isinstance(v, ast.Tuple):
                        down = tuple(elt.value for elt in v.elts)
        assert rev is not None, f"{path}: revision not found"
        revisions[rev] = {"path": path, "tree": tree, "down": down}

    # Топологический порядок: от корня (down=None) по цепочке down_revision
    order: list[str] = []
    placed: set[str] = set()
    while len(order) < len(revisions):
        progressed = False
        for rev, info in revisions.items():
            if rev in placed:
                continue
            parents = info["down"] if isinstance(info["down"], tuple) else (
                (info["down"],) if info["down"] else ()
            )
            if all(p in placed for p in parents):
                order.append(rev)
                placed.add(rev)
                progressed = True
        assert progressed, "migration graph has a cycle or unknown parent"

    schema: dict[str, set[str]] = {}
    unsupported_ddl: list[str] = []
    for rev in order:
        for node in ast.walk(revisions[rev]["tree"]):
            # upgrade() и его хелперы (downgrade/деструктивные хелперы исключаем)
            if not (isinstance(node, ast.FunctionDef) and not node.name.startswith(("downgrade", "_drop"))):
                continue
            for stmt in ast.walk(node):
                if not (isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute)):
                    continue
                fn = stmt.func.attr
                if fn == "create_table" and stmt.args:
                    table = stmt.args[0].value
                    cols = {
                        arg.args[0].value
                        for arg in stmt.args[1:]
                        if isinstance(arg, ast.Call) and getattr(arg.func, "attr", None) == "Column"
                    }
                    schema[table] = cols
                elif fn == "add_column" and len(stmt.args) >= 2:
                    table = stmt.args[0].value
                    col_call = stmt.args[1]
                    if isinstance(col_call, ast.Call) and col_call.args:
                        schema.setdefault(table, set()).add(col_call.args[0].value)
                elif fn == "drop_column" and len(stmt.args) >= 2:
                    table, col = stmt.args[0].value, stmt.args[1].value
                    schema.get(table, set()).discard(col)
                elif fn == "drop_table" and stmt.args:
                    schema.pop(stmt.args[0].value, None)
                elif fn == "execute" and stmt.args and isinstance(stmt.args[0], ast.Constant):
                    _apply_raw_ddl(stmt.args[0].value, schema, unsupported_ddl)
    return schema, unsupported_ddl


def _apply_raw_ddl(sql: str, schema: dict[str, set[str]], unsupported: list[str]) -> None:
    """Разобрать идемпотентный DDL из op.execute(). Нераспознаваемый DDL
    фиксируется в unsupported — тест дрейфа требует расширить симулятор."""
    import re

    sql = sql.strip().rstrip(";")
    m = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*)\)\s*$", sql, re.S)
    if m:
        table, body = m.group(1), m.group(2)
        cols = set()
        for line in body.splitlines():
            token = line.strip().split()[0] if line.strip() else ""
            if token and token.upper() not in {"PRIMARY", "UNIQUE", "FOREIGN", "CONSTRAINT"}:
                cols.add(token)
        schema[table] = cols
        return
    m = re.match(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", sql)
    if m:
        schema.setdefault(m.group(1), set()).add(m.group(2))
        return
    m = re.match(r"ALTER TABLE (\w+) DROP COLUMN IF EXISTS (\w+)", sql)
    if m:
        schema.get(m.group(1), set()).discard(m.group(2))
        return
    m = re.match(r"DROP TABLE IF EXISTS (\w+)", sql)
    if m:
        schema.pop(m.group(1), None)
        return
    if re.match(r"CREATE (UNIQUE )?INDEX IF NOT EXISTS", sql):
        return  # индексы не меняют состав колонок
    if sql.upper().startswith(("UPDATE", "INSERT", "DELETE", "COMMENT")):
        return  # не DDL
    unsupported.append(sql[:80])


class TestMigrationsBuildModelSchema:
    """Regression: цепочка миграций обязана строить схему, совпадающую с
    моделями (Base.metadata). Раньше financial_snapshots вообще не создавалась
    миграциями, у submissions не хватало score/language/attempt_id/eta и
    оставались зомби-колонки step_id/student_id, у student_enrollments не было
    date_joined — свежая `alembic upgrade head` была нерабочей."""

    def test_migrations_match_models(self):
        from app.models.base import Base

        schema, unsupported = _simulate_migrations()
        problems = [f"unparseable DDL (extend the simulator): {sql!r}" for sql in unsupported]
        for table, model in Base.metadata.tables.items():
            # raw-таблицы создаются скриптами (explore_endpoint.py), не миграциями
            if table.startswith("raw_"):
                continue
            if table not in schema:
                problems.append(f"table {table}: not created by migrations")
                continue
            missing = set(model.columns.keys()) - schema[table]
            extra = schema[table] - set(model.columns.keys())
            if missing:
                problems.append(f"{table}: migrations miss columns {sorted(missing)}")
            if extra:
                problems.append(f"{table}: migrations create zombie columns {sorted(extra)}")
        assert not problems, "Migration/model schema drift:\n  " + "\n  ".join(problems)


class TestAlembicGraph:
    def test_single_head(self):
        """Migration graph must be linear — no forked heads."""
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 alembic head, got {heads}"

    def test_meta_tables_migration_after_raw_fixes(self):
        """Single head must descend from 017 and the meta-tables revision."""
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 alembic head, got {heads}"
        head = heads[0]
        assert head == "020", head
        rev = script.get_revision(head)
        assert rev.down_revision == "019", rev.down_revision
        merge = script.get_revision("018")
        assert set(merge.down_revision) == {"017", "20fc60296db6"}, merge.down_revision


class TestDeadArtifacts:
    def test_no_step_sync_state_in_app(self):
        """Dead StepSyncState model was removed; raw_sync_state is the only state table."""
        for path in (BACKEND_DIR / "app").rglob("*.py"):
            assert "step_sync_state" not in _read(path), f"{path} references dead table"

    def test_no_step_sync_state_model(self):
        model_file = BACKEND_DIR / "app" / "models" / "step_sync_state.py"
        assert not model_file.exists(), "dead StepSyncState model must stay deleted"

    def test_no_step_sync_state_table_in_migrations(self):
        """Zombie table step_sync_state (created in 006, never used) must be dropped."""
        schema, _unsupported = _simulate_migrations()
        assert "step_sync_state" not in schema, "zombie table step_sync_state survives migrations"

    def test_scripts_directory_only_tools(self):
        """Orphan one-off scripts were removed; only AGENTS.md-referenced tools remain.
        rebuild_raw.py удалён: зависел от docs/fields_*.md, которых никогда не
        было в репозитории (каждый запуск — FileNotFoundError); схема raw-слоя
        управляется миграциями."""
        scripts = {p.name for p in (BACKEND_DIR / "scripts").glob("*.py")}
        assert scripts == {"sync_raw.py", "explore_endpoint.py", "rebuild_marts.py"}, scripts


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

        def _walk(router):
            paths = set()
            for route in getattr(router, "routes", router):
                if hasattr(route, "path") and not hasattr(route, "routes"):
                    paths.add(route.path)
                elif hasattr(route, "original_router"):
                    sub = route.original_router
                    sub_prefix = getattr(sub, "prefix", "")
                    sub_paths = _walk(sub)
                    for p in sub_paths:
                        if sub_prefix and not p.startswith(sub_prefix):
                            p = sub_prefix + p
                        paths.add(p)
                elif hasattr(route, "routes"):
                    paths |= _walk(route)
            return paths

        paths = _walk(app)
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
