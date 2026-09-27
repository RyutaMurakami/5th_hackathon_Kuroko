import pytest
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.gateway import app as gateway_app
from src.main import app

SIGNING_SECRET = "test-signing-secret"
KUROKO_API_URL = "https://kuroko-api.test"
GATEWAY_SA = "sa-gateway@test.iam.gserviceaccount.com"


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
    monkeypatch.setenv("KUROKO_API_URL", KUROKO_API_URL)
    monkeypatch.setenv("GATEWAY_SERVICE_ACCOUNT", GATEWAY_SA)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def gateway_client():
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
