import os
import pytest
from app.config import get_settings

os.environ["GCP_PROJECT_ID"] = "test-studio-project"
os.environ["GCS_BUCKET"] = "test-studio-bucket"
os.environ["ENVIRONMENT"] = "local"
os.environ["GEMINI_API_KEY"] = "fake-test-key-for-unit-tests"

get_settings.cache_clear()

