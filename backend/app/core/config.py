"""Cấu hình chung của backend."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # thư mục backend/
DATA_DIR = BACKEND_DIR / "data"  # đã nằm trong .gitignore
DEFAULT_DATABASE_PATH = DATA_DIR / "plates.db"


def get_database_path() -> Path:
    """Đường dẫn file SQLite; đặt biến môi trường LPR_DATABASE_PATH để đổi (dùng khi test)."""
    return Path(os.environ.get("LPR_DATABASE_PATH", DEFAULT_DATABASE_PATH))
