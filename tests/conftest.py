import os
import pytest
from app.config import get_settings

os.environ["GCP_PROJECT_ID"] = "test-studio-project"
os.environ["GCS_BUCKET"] = "test-studio-bucket"
os.environ["ENVIRONMENT"] = "local"

get_settings.cache_clear()
