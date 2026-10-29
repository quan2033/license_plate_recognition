"""Kết nối SQLite và tạo bảng.

Một file database (plates.db) gồm 2 phần:
  - camera_plates : biển số nhận được từ camera
  - video_plates  : biển số được xử lý từ video (hoặc ảnh) tải lên
"""

import sqlite3
from contextlib import closing, contextmanager

from backend.app.core.config import get_database_path

SCHEMA = """
-- PHẦN 1: dữ liệu từ camera
CREATE TABLE IF NOT EXISTS camera_plates (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id            TEXT NOT NULL,
    location             TEXT,
    license_plate        TEXT NOT NULL,
    detection_confidence REAL,
    ocr_confidence       REAL,
    captured_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_camera_plates_license_plate ON camera_plates(license_plate);
CREATE INDEX IF NOT EXISTS idx_camera_plates_camera_id     ON camera_plates(camera_id);
CREATE INDEX IF NOT EXISTS idx_camera_plates_captured_at   ON camera_plates(captured_at);

-- PHẦN 2: dữ liệu xử lý từ video cho trước (ảnh tải lên cũng lưu ở đây)
CREATE TABLE IF NOT EXISTS video_plates (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    license_plate        TEXT NOT NULL,
    detection_confidence REAL,
    ocr_confidence       REAL,
    source_type          TEXT NOT NULL DEFAULT 'video' CHECK (source_type IN ('video', 'image')),
    filename             TEXT,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_video_plates_license_plate ON video_plates(license_plate);
CREATE INDEX IF NOT EXISTS idx_video_plates_filename      ON video_plates(filename);
CREATE INDEX IF NOT EXISTS idx_video_plates_created_at    ON video_plates(created_at);
"""


def escape_like(text: str) -> str:
    """Escape % và _ để chuỗi tìm kiếm không bị hiểu là ký tự đại diện (dùng với ESCAPE '\\')."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _migrate_legacy_table(connection: sqlite3.Connection) -> None:
    """Database cũ chỉ có bảng `plates`: chép sang video_plates rồi đổi tên thành plates_legacy."""
    has_legacy = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'plates'"
    ).fetchone()
    if not has_legacy:
        return
    with connection:
        connection.execute(
            """INSERT INTO video_plates
                   (license_plate, detection_confidence, ocr_confidence, source_type, filename, created_at)
               SELECT license_plate, detection_confidence, ocr_confidence, source, filename, created_at
               FROM plates ORDER BY id"""
        )
        connection.execute("ALTER TABLE plates RENAME TO plates_legacy")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode = WAL")  # đọc/ghi đồng thời tốt hơn
    connection.executescript(SCHEMA)
    _migrate_legacy_table(connection)


@contextmanager
def get_connection():
    """Mở kết nối cho mỗi thao tác; tự commit khi xong, rollback nếu lỗi, rồi đóng."""
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not path.exists()  # file bị xóa để reset thì tự tạo lại bảng, không cần restart server
    # FastAPI chạy route trong nhiều thread nên mỗi lần dùng một kết nối riêng
    with closing(sqlite3.connect(path, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if is_new_file:
            _create_schema(connection)
        with connection:
            yield connection


def init_db() -> None:
    """Tạo file và bảng nếu chưa có (an toàn khi gọi nhiều lần)."""
    with get_connection() as connection:
        _create_schema(connection)
