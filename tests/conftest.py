import pytest
import pytest_asyncio
from app.config import get_settings
from app.db.database import DatabaseManager

@pytest_asyncio.fixture(autouse=True)
async def init_test_database():
    settings = get_settings()
    db_mgr = DatabaseManager(settings.DATABASE_URL)
    await db_mgr.init_db()
