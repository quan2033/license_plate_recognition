"""Kiểm thử database biển số (2 phần: camera và video). Chạy từ thư mục gốc dự án:

    python -m unittest backend/tests/test_plate_repository.py
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.database import camera_repository, init_db, video_repository
from backend.app.database.connection import get_connection

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.api.routes.plates import router as plates_router
except ImportError:  # chưa cài fastapi/httpx thì bỏ qua phần test API
    TestClient = None


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / "data" / "plates.db"
        patcher = patch.dict(os.environ, {"LPR_DATABASE_PATH": str(self.db_path)})
        patcher.start()
        self.addCleanup(patcher.stop)
        init_db()


class SchemaTests(DatabaseTestCase):
    def test_has_two_parts(self):
        with get_connection() as connection:
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"camera_plates", "video_plates"} <= tables)

    def test_init_db_is_repeatable(self):
        init_db()
        self.assertTrue(self.db_path.exists())

    def test_recreates_tables_if_database_file_was_deleted(self):
        video_repository.add_many([{"license_plate": "51A-034.42"}])
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db_path) + suffix).unlink(missing_ok=True)
        self.assertEqual(video_repository.count_plates(), 0)
        self.assertEqual(camera_repository.count_plates(), 0)

    def test_parts_are_independent(self):
        camera_repository.add_many([{"camera_id": "cam1", "license_plate": "51A-034.42"}])
        self.assertEqual(camera_repository.count_plates(), 1)
        self.assertEqual(video_repository.count_plates(), 0)

    def test_migrates_legacy_plates_table(self):
        legacy = Path(self.db_path.parent) / "legacy.db"
        with patch.dict(os.environ, {"LPR_DATABASE_PATH": str(legacy)}):
            legacy.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(legacy)
            con.executescript(
                """CREATE TABLE plates (id INTEGER PRIMARY KEY AUTOINCREMENT, license_plate TEXT NOT NULL,
                   detection_confidence REAL, ocr_confidence REAL, source TEXT NOT NULL,
                   filename TEXT, created_at TEXT NOT NULL);
                   INSERT INTO plates (license_plate, source, filename, created_at)
                   VALUES ('51A-034.42','image','a.jpg','2026-01-01T00:00:00Z'),
                          ('30F-123.45','video','b.mp4','2026-01-02T00:00:00Z');"""
            )
            con.close()
            init_db()
            init_db()  # lần 2 không được chép trùng
            items = video_repository.list_plates()
            self.assertEqual([i["license_plate"] for i in items], ["30F-123.45", "51A-034.42"])
            self.assertEqual(items[1]["source_type"], "image")
            self.assertEqual(items[1]["created_at"], "2026-01-01T00:00:00Z")


class CameraRepositoryTests(DatabaseTestCase):
    def test_add_and_list_newest_captured_first(self):
        ids = camera_repository.add_many([
            {"camera_id": "cam1", "license_plate": "51A-034.42", "captured_at": "2026-10-28T08:00:00Z"},
            {"camera_id": "cam2", "location": "Cổng B", "license_plate": "59C1-239.68",
             "detection_confidence": 0.9, "ocr_confidence": 0.95, "captured_at": "2026-10-28T09:00:00Z"},
        ])
        self.assertEqual(len(ids), 2)
        items = camera_repository.list_plates()
        self.assertEqual([i["license_plate"] for i in items], ["59C1-239.68", "51A-034.42"])
        self.assertEqual(items[0]["location"], "Cổng B")
        self.assertTrue(items[1]["created_at"].endswith("Z"))

    def test_captured_at_defaults_to_now(self):
        plate_id = camera_repository.add_many([{"camera_id": "cam1", "license_plate": "51A-034.42"}])[0]
        self.assertTrue(camera_repository.get_by_id(plate_id)["captured_at"].endswith("Z"))

    def test_filter_by_plate_and_camera(self):
        camera_repository.add_many([
            {"camera_id": "cam1", "license_plate": "51A-034.42"},
            {"camera_id": "cam2", "license_plate": "51A-111.11"},
            {"camera_id": "cam1", "license_plate": "30F-123.45"},
        ])
        self.assertEqual(camera_repository.count_plates("51A"), 2)
        self.assertEqual(camera_repository.count_plates("51A", "cam2"), 1)
        self.assertEqual(camera_repository.count_plates(camera_id="cam1"), 2)
        self.assertEqual(camera_repository.count_plates("%"), 0)

    def test_requires_camera_id(self):
        with self.assertRaises(sqlite3.IntegrityError):
            camera_repository.add_many([{"camera_id": None, "license_plate": "51A-034.42"}])

    def test_sql_injection_is_stored_as_text(self):
        evil = "x'); DROP TABLE camera_plates;--"
        camera_repository.add_many([{"camera_id": "cam1", "license_plate": evil}])
        self.assertEqual(camera_repository.list_plates()[0]["license_plate"], evil)


class VideoRepositoryTests(DatabaseTestCase):
    def test_add_many_and_list_newest_first(self):
        saved = video_repository.add_many([
            {"license_plate": "51A-034.42", "detection_confidence": 0.9, "ocr_confidence": 0.95,
             "source_type": "image", "filename": "a.jpg"},
            {"license_plate": "59C1-239.68", "filename": "b.mp4"},
        ])
        self.assertEqual(saved, 2)
        items = video_repository.list_plates()
        self.assertEqual([i["license_plate"] for i in items], ["59C1-239.68", "51A-034.42"])
        self.assertEqual(items[0]["source_type"], "video")  # mặc định
        self.assertIsNone(items[0]["ocr_confidence"])

    def test_add_many_empty_list(self):
        self.assertEqual(video_repository.add_many([]), 0)

    def test_filter_by_plate_and_filename(self):
        video_repository.add_many([
            {"license_plate": "51A-034.42", "filename": "a.mp4"},
            {"license_plate": "51A-111.11", "filename": "b.mp4"},
            {"license_plate": "30F-123.45", "filename": "a.mp4"},
        ])
        self.assertEqual(video_repository.count_plates("51A"), 2)
        self.assertEqual(video_repository.count_plates("51A", "b.mp4"), 1)
        self.assertEqual(video_repository.count_plates(filename="a.mp4"), 2)
        self.assertEqual(video_repository.count_plates("%"), 0)

    def test_paging(self):
        video_repository.add_many([{"license_plate": f"51A-000.0{i}"} for i in range(5)])
        page = video_repository.list_plates(limit=2, offset=2)
        self.assertEqual([p["license_plate"] for p in page], ["51A-000.02", "51A-000.01"])

    def test_rejects_invalid_source_type(self):
        with self.assertRaises(sqlite3.IntegrityError):
            video_repository.add_many([{"license_plate": "51A-034.42", "source_type": "camera"}])


@unittest.skipIf(TestClient is None, "cần cài fastapi và httpx")
class PlateApiTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(plates_router, prefix="/api")
        self.client = TestClient(app)
        video_repository.add_many([
            {"license_plate": "51A-034.42", "source_type": "image", "filename": "a.jpg"},
            {"license_plate": "30F-123.45", "filename": "b.mp4"},
        ])

    def test_post_and_get_camera_plate(self):
        response = self.client.post("/api/plates/camera", json={
            "camera_id": "cam1", "license_plate": "51A-034.42", "ocr_confidence": 0.9,
            "captured_at": "2026-10-28T15:00:00+07:00",
        })
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["captured_at"], "2026-10-28T08:00:00Z")  # đổi về UTC
        self.assertEqual(self.client.get(f"/api/plates/camera/{body['id']}").json()["camera_id"], "cam1")
        listing = self.client.get("/api/plates/camera", params={"camera_id": "cam1"}).json()
        self.assertEqual(listing["total"], 1)

    def test_post_camera_plate_validation(self):
        post = lambda **kw: self.client.post("/api/plates/camera", json=kw).status_code
        self.assertEqual(post(license_plate="51A"), 422)  # thiếu camera_id
        self.assertEqual(post(camera_id="c", license_plate="51A", ocr_confidence=1.5), 422)
        self.assertEqual(post(camera_id="c", license_plate="51A", captured_at="hôm qua"), 422)

    def test_camera_and_video_lists_are_separate(self):
        self.assertEqual(self.client.get("/api/plates/camera").json()["total"], 0)
        body = self.client.get("/api/plates/video").json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["items"][0]["license_plate"], "30F-123.45")

    def test_video_filter_get_and_not_found(self):
        body = self.client.get("/api/plates/video", params={"license_plate": "51A", "filename": "a.jpg"}).json()
        self.assertEqual([i["license_plate"] for i in body["items"]], ["51A-034.42"])
        self.assertEqual(self.client.get("/api/plates/video/1").json()["license_plate"], "51A-034.42")
        self.assertEqual(self.client.get("/api/plates/video/999").status_code, 404)
        self.assertEqual(self.client.get("/api/plates/camera/999").status_code, 404)

    def test_invalid_query_is_rejected(self):
        self.assertEqual(self.client.get("/api/plates/video", params={"limit": 0}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
