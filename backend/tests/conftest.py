import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.rag import answer_cache
from app.utils import rate_limit


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Keep test records out of the real database."""
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1000)
    monkeypatch.setattr(settings, "rate_limit_per_day", 0)
    answer_cache.clear()
    rate_limit._daily_counts.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)
