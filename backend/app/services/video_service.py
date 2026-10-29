
import base64
import csv
import logging
import sqlite3
import tempfile
from pathlib import Path

import cv2
from ultralytics import YOLO

from backend.app.database import video_repository
from backend.app.services.recognition_service import get_model
from frame_processor import process_frame
from plate_tracking import PlateStabilizer, CsvLogger


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "backend" / "outputs"


def _track_confidence(track: dict) -> float | None:
    """Độ tin cậy OCR trung bình của các lần đọc trùng với biển đã được chấp nhận."""
    scores = [score for text, score in track["votes"] if text == track["accepted"]]
    return round(sum(scores) / len(scores), 4) if scores else None


def recognize_video(video_bytes: bytes, filename: str) -> dict:
    """Nhận diện biển số trong video tải lên và lưu video kết quả."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        suffix = ".mp4"

    temp_path = None
    output_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False
        ) as temp_file:
            temp_file.write(video_bytes)
            temp_path = Path(temp_file.name)

        capture = cv2.VideoCapture(str(temp_path))

        if not capture.isOpened():
            raise ValueError("Không thể đọc video đã tải lên")

        fps = capture.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 25.0

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if width <= 0 or height <= 0:
            capture.release()
            raise ValueError("Video không có kích thước hợp lệ")

        output_path = OUTPUT_DIR / f"result_{temp_path.stem}.mp4"
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )

        if not writer.isOpened():
            capture.release()
            raise RuntimeError("Không thể tạo video kết quả")

        stabilizer = PlateStabilizer(min_votes=2)
        frame_number = 0

        try:
            model = get_model()

            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                frame_number += 1

                annotated = process_frame(
                    frame,
                    model,
                    confidence_threshold=0.3,
                    stabilizer=stabilizer,
                    logger=None,
                    frame_number=frame_number,
                    ocr_every=1,
                )

                writer.write(annotated)
        finally:
            capture.release()
            writer.release()

        if frame_number == 0:
            raise ValueError("Video không có frame hợp lệ")

        # Đọc các biển số đã được ổn định từ những track.
        plates = sorted({
            track["accepted"]
            for track in stabilizer.tracks.values()
            if track.get("accepted")
        })

        # Mỗi biển lưu một lần; nếu nhiều track cùng biển thì lấy độ tin cậy cao nhất
        confidences = {}
        for track in stabilizer.tracks.values():
            plate = track.get("accepted")
            if plate:
                score = _track_confidence(track)
                if plate not in confidences or (score or 0) > (confidences[plate] or 0):
                    confidences[plate] = score
        try:
            video_repository.add_many([
                {"license_plate": plate, "ocr_confidence": confidences.get(plate),
                 "source_type": "video", "filename": filename}
                for plate in plates
            ])
        except sqlite3.Error:
            logger.exception("Không lưu được biển số vào database")

        return {
            "message": "Video recognition completed",
            "frames_processed": frame_number,
            "plates": plates,
            "video_url": f"/api/recognize/video/result/{output_path.name}",
        }

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
