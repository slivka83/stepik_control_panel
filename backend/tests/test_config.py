import os
from pathlib import Path


class TestProjectRoot:
    def test_project_root_is_path(self):
        from app.config import PROJECT_ROOT
        assert isinstance(PROJECT_ROOT, Path)

    def test_project_root_points_to_stepik_control_panel(self):
        from app.config import PROJECT_ROOT
        assert PROJECT_ROOT.name == "stepik_control_panel"

    def test_project_root_has_env_file(self):
        from app.config import PROJECT_ROOT
        env_file = PROJECT_ROOT / ".env"
        assert env_file.exists()

    def test_project_root_has_backend_dir(self):
        from app.config import PROJECT_ROOT
        assert (PROJECT_ROOT / "backend").is_dir()

    def test_project_root_has_frontend_dir(self):
        from app.config import PROJECT_ROOT
        assert (PROJECT_ROOT / "frontend").is_dir()


class TestSettingsProperties:
    def test_frontend_url_uses_frontend_port(self):
        from app.config import Settings
        s = Settings(frontend_port=3001, database_url="sqlite+aiosqlite:///:memory:")
        assert s.frontend_url == "http://localhost:3001"

    def test_frontend_url_default_port(self):
        from app.config import Settings
        s = Settings(database_url="sqlite+aiosqlite:///:memory:")
        assert s.frontend_url == "http://localhost:3000"

    def test_stepik_redirect_uri(self):
        from app.config import Settings
        s = Settings(frontend_port=3001, database_url="sqlite+aiosqlite:///:memory:")
        assert s.stepik_redirect_uri == "http://localhost:3001/api/auth/callback"

    def test_stepik_redirect_uri_default_port(self):
        from app.config import Settings
        s = Settings(database_url="sqlite+aiosqlite:///:memory:")
        assert s.stepik_redirect_uri == "http://localhost:3000/api/auth/callback"

    def test_settings_extras_ignored(self):
        from app.config import Settings
        os.environ["UNKNOWN_KEY"] = "value"
        try:
            s = Settings(database_url="sqlite+aiosqlite:///:memory:")
            assert hasattr(s, "database_url")
        finally:
            del os.environ["UNKNOWN_KEY"]
