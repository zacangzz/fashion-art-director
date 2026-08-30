import os
import tempfile
import pytest
import pytest_asyncio

# Create an isolated temporary test directory for all pytest runs
_test_temp_dir = tempfile.TemporaryDirectory()
_test_db_path = os.path.join(_test_temp_dir.name, "test_studio.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["STORAGE_DIR"] = _test_temp_dir.name

from app.config import get_settings
from app.db.database import DatabaseManager

# Clear settings & dependency caches to ensure they use the test environment
get_settings.cache_clear()
try:
    from app.dependencies import (
        get_db_manager,
        get_wardrobe_service,
        get_generation_service,
        get_vision_service,
        get_export_service,
    )
    get_db_manager.cache_clear()
    get_wardrobe_service.cache_clear()
    get_generation_service.cache_clear()
    get_vision_service.cache_clear()
    get_export_service.cache_clear()
except ImportError:
    pass


@pytest_asyncio.fixture(autouse=True)
async def init_test_database():
    settings = get_settings()
    db_mgr = DatabaseManager(settings.DATABASE_URL)
    await db_mgr.init_db()
    return db_mgr
