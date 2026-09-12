"""Environment-backed configuration shared across the application."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.environ["DATABASE_URL"]
CORPUS_DIR = Path(os.environ.get("CORPUS_DIR", "test_corpus"))
