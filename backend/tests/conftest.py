from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-openrouter-live",
        action="store_true",
        default=False,
        help="run the live OpenRouter connectivity test",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-openrouter-live"):
        return
    skip_live = pytest.mark.skip(reason="requires --run-openrouter-live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "project_management.db"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200
    return client
