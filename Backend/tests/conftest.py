"""Keep the test process off MongoDB, Atlas, and the language-model API."""
import os

os.environ["BUILDSURE_STORAGE"] = "memory"
os.environ["GROQ_API_KEY"] = ""

import pytest

from src.db import reset_storage


@pytest.fixture(autouse=True)
def clean_memory_store():
    reset_storage()
    yield
    reset_storage()
