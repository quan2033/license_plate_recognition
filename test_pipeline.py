"""Kiem thu cac thanh phan khong can webcam hay cua so hien thi.

Chay: python -m unittest test_pipeline.py
"""

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

import frame_processor
import media
import plate_ocr
from plate_ocr import crop_plate, format_plate, is_two_line, read_plate
from plate_tracking import CsvLogger, PlateStabilizer


class PlatePipelineTests(unittest.TestCase):
    def test_format_plate(self):
        self.assertEqual(format_plate("51A03442"), "51A-034.42")
        self.assertEqual(format_plate("51A-034.42"), "51A-034.42")
        self.assertEqual(format_plate("59F1\n123.45", two_line=True), "59F1-123.45")
        self.assertEqual(format_plate("65B104566", two_line=True), "65B1-045.66")
        self.assertEqual(format_plate("khong phai bien so"), "")
        self.assertEqual(format_plate("V0209"), "")

    def test_format_plate_old_four_digit_series(self):
        self.assertEqual(format_plate("50Z0618"), "50Z-0618")
        # Crop oto bị nghiêng có tỉ lệ cao như biển xe máy: vẫn phải đọc được
        self.assertEqual(format_plate("50Z0618", two_line=True), "50Z-0618")
        self.assertEqual(format_plate("43H16799", two_line=True), "43H1-6799")

    def test_format_plate_accepts_old_r_series_motorcycle_plate(self):
        self.assertEqual(format_plate("36R30829", two_line=True), "36R3-0829")
        # OCR đôi khi phân loại nhầm bố cục, nhưng seri R3 vẫn phải được giữ đúng.
        self.assertEqual(format_plate("36R30829", two_line=False), "36R3-0829")

    def test_format_plate_fixes_confusable_characters(self):
        self.assertEqual(format_plate("5IA69172"), "51A-691.72")  # I -> 1 ở vị trí số
        self.assertEqual(format_plate("51A6917Z"), "51A-691.72")  # Z -> 2 ở phần chữ số
        self.assertEqual(format_plate("501D04411"), "50LD-044.11")  # 1 -> L ở vị trí seri
        self.assertEqual(format_plate("510 69172"), "51D-691.72")  # 0 -> D ở vị trí seri

    def test_format_plate_fixes_second_series_letter(self):
        self.assertEqual(format_plate("60LO00584"), "60LD-005.84")  # Biển VN không có "O"

    def test_is_two_line_uses_box_ratio_when_clear(self):
        self.assertFalse(is_two_line(np.full((50, 140, 3), 255, dtype=np.uint8)))
        self.assertTrue(is_two_line(np.full((140, 120, 3), 255, dtype=np.uint8)))

    def test_is_two_line_ignores_tilt_of_one_line_plate(self):
        # Biển ô tô 1 dòng (nền sáng, chữ đen) xoay 25 độ: box cao như biển 2 dòng nhưng thân biển vẫn dài
        plate = np.full((60, 200, 3), 40, dtype=np.uint8)
        cv2.rectangle(plate, (4, 6), (195, 53), (235, 235, 235), -1)
        cv2.putText(plate, "51A 691.72", (14, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
        canvas = np.full((200, 200, 3), 40, dtype=np.uint8)
        canvas[70:130, :] = plate
        matrix = cv2.getRotationMatrix2D((100, 100), 25, 1.0)
        tilted = cv2.warpAffine(canvas, matrix, (200, 200), borderValue=(40, 40, 40))
        crop = tilted[40:160, 0:200]
        self.assertGreaterEqual(crop.shape[0] / crop.shape[1], 0.5)
        self.assertFalse(is_two_line(crop[:, :]))

    def test_format_plate_rejects_invalid_province(self):
        self.assertEqual(format_plate("00A69172"), "")

    def test_stabilizer_requires_consensus_for_uncertain_reads(self):
        stabilizer = PlateStabilizer(min_votes=3)
        box = (10, 10, 110, 50)
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.7, 1), ("", False))
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.7, 2), ("", False))
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.7, 3), ("51A-034.42", True))

    def test_stabilizer_shows_confident_read_immediately_but_not_confirmed(self):
        stabilizer = PlateStabilizer(min_votes=2)
        box = (10, 10, 110, 50)
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.99, 1), ("51A-034.42", False))
        # Frame không chạy OCR vẫn giữ nhãn, không nhấp nháy.
        self.assertEqual(stabilizer.update(box, "", 0.0, 2), ("51A-034.42", False))
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.99, 3), ("51A-034.42", True))

    def test_stabilizer_single_misread_does_not_override(self):
        stabilizer = PlateStabilizer(min_votes=2)
        box = (10, 10, 110, 50)
        stabilizer.update(box, "51F-448.14", 0.95, 1)
        self.assertEqual(stabilizer.update(box, "51L-448.14", 0.95, 2), ("51F-448.14", False))
        self.assertEqual(stabilizer.update(box, "51F-448.14", 0.95, 3), ("51F-448.14", True))

    def test_stabilizer_signals_ready_to_log_only_once_per_track(self):
        stabilizer = PlateStabilizer(min_votes=2)
        box = (10, 10, 110, 50)
        stabilizer.update(box, "51F-448.14", 0.7, 1)
        self.assertEqual(stabilizer.update(box, "51F-448.14", 0.7, 2), ("51F-448.14", True))
        self.assertEqual(stabilizer.update(box, "51F-448.14", 0.7, 3), ("51F-448.14", False))
        # Dao động giữa F/L sau khi đã ghi không phát sinh thêm bản ghi nào
        for frame, text in enumerate(["51L-448.14", "51L-448.14", "51L-448.14", "51L-448.14"], start=4):
            self.assertFalse(stabilizer.update(box, text, 0.7, frame)[1])

    def test_stabilizer_starts_new_track_for_different_plate_in_same_box(self):
        stabilizer = PlateStabilizer(min_votes=2)
        box = (10, 10, 110, 50)
        stabilizer.update(box, "82K3-7689", 0.99, 1)
        self.assertTrue(stabilizer.update(box, "82K3-7689", 0.99, 2)[1])
        # Xe khác vào chỗ cũ: hiện ngay, ghi lại khi đủ phiếu
        self.assertEqual(stabilizer.update(box, "51G-510.08", 0.99, 3), ("51G-510.08", False))
        self.assertEqual(stabilizer.update(box, "51G-510.08", 0.99, 4), ("51G-510.08", True))

    def test_stabilizer_prefers_consistent_reading(self):
        stabilizer = PlateStabilizer(min_votes=2)
        box = (10, 10, 110, 50)
        stabilizer.update(box, "51A-034.42", 0.7, 1)
        stabilizer.update(box, "51A-034.49", 0.6, 2)
        self.assertEqual(stabilizer.update(box, "51A-034.42", 0.7, 3), ("51A-034.42", True))

    def test_stabilizer_remembers_plate_after_track_expires(self):
        stabilizer = PlateStabilizer(min_votes=2, max_age=1)
        first_box = (10, 10, 110, 50)
        stabilizer.update(first_box, "36R3-0829", 0.99, 1)
        stabilizer.update(first_box, "36R3-0829", 0.99, 2)

        second_box = (300, 300, 400, 350)
        stabilizer.update(second_box, "29N1-478.54", 0.99, 4)

        self.assertNotIn(
            "36R3-0829",
            [track.get("accepted") for track in stabilizer.tracks.values()],
        )
        self.assertEqual(stabilizer.recognized_plates["36R3-0829"], 0.99)

    def test_logger_only_receives_confirmed_plates(self):
        detected_box = SimpleNamespace(xyxy=[np.array([10, 10, 110, 50])], conf=[np.array(0.9)])
        model = lambda *_args, **_kwargs: [SimpleNamespace(boxes=[detected_box])]
        logger = SimpleNamespace(logged=[], log=lambda plate: logger.logged.append(plate))
        stabilizer = PlateStabilizer(min_votes=2)
        frame = np.zeros((100, 160, 3), dtype=np.uint8)
        with patch.object(frame_processor, "read_plate", return_value=("51A-034.42", 0.99)):
            frame_processor.process_frame(frame.copy(), model, 0.5, stabilizer, logger, frame_number=1)
            self.assertEqual(logger.logged, [])
            frame_processor.process_frame(frame.copy(), model, 0.5, stabilizer, logger, frame_number=2)
            self.assertEqual(logger.logged, ["51A-034.42"])

    def test_crop_plate_pads_without_overflowing_frame(self):
        frame = np.arange(100 * 200 * 3, dtype=np.uint8).reshape(100, 200, 3)
        crop = crop_plate(frame, (50, 40, 150, 60), padding=0.1)
        self.assertEqual(crop.shape[:2], (24, 120))
        corner = crop_plate(frame, (0, 0, 20, 10), padding=0.5)
        self.assertEqual(corner.shape[:2], (15, 30))
        crop[:] = 0
        self.assertTrue(frame[40:60, 50:150].any())  # crop là bản sao, không sửa frame gốc

    def test_csv_logger_respects_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "records.csv"
            logger = CsvLogger(csv_path, cooldown_seconds=60)
            self.assertTrue(logger.log("51A-034.42"))
            self.assertFalse(logger.log("51A-034.42"))
            with csv_path.open(encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))
            self.assertEqual(rows[0], ["timestamp", "license_plate"])
            self.assertEqual(rows[1][1], "51A-034.42")

    def test_ocr_sample_plate(self):
        image_path = Path(__file__).with_name("plate_0.jpg")
        if not image_path.exists():
            self.skipTest("Không có  plate_0.jpg để kiểm tra thử OCR")
        image = cv2.imread(str(image_path))
        text, confidence = read_plate(image)
        self.assertEqual(text, "51A-691.72")
        self.assertGreater(confidence, 0.6)

    def test_read_plate_handles_empty_crop(self):
        self.assertEqual(read_plate(np.zeros((0, 0, 3), dtype=np.uint8)), ("", 0.0))

    def test_read_plate_stops_after_confident_fast_model(self):
        prediction = SimpleNamespace(
            plate="51A03442",
            char_probs=np.ones(8, dtype=np.float32),
        )
        recognizers = [object(), object(), object()]
        plate = np.full((80, 160, 3), 255, dtype=np.uint8)

        with (
            patch.object(plate_ocr, "_get_recognizers", return_value=recognizers),
            patch.object(plate_ocr, "_run_model", return_value=prediction) as run_model,
        ):
            self.assertEqual(read_plate(plate), ("51A-034.42", 1.0))

        self.assertEqual(run_model.call_count, 1)

    def test_ocr_runs_only_on_configured_frames(self):
        detected_box = SimpleNamespace(
            xyxy=[np.array([10, 10, 110, 50])],
            conf=[np.array(0.9)],
        )
        result = SimpleNamespace(boxes=[detected_box])
        model = lambda *_args, **_kwargs: [result]
        frame = np.zeros((100, 160, 3), dtype=np.uint8)

        with patch.object(frame_processor, "read_plate", return_value=("51A-034.42", 0.95)) as mocked_read_plate:
            frame_processor.process_frame(frame.copy(), model, 0.5, frame_number=1, ocr_every=3)
            mocked_read_plate.assert_not_called()
            frame_processor.process_frame(frame.copy(), model, 0.5, frame_number=3, ocr_every=3)
            mocked_read_plate.assert_called_once()

    def test_stream_releases_capture_and_writer(self):
        frame = np.zeros((60, 100, 3), dtype=np.uint8)

        class FakeCapture:
            def __init__(self):
                self.frames = [frame.copy(), frame.copy()]
                self.released = False

            def isOpened(self):
                return True

            def set(self, *_args):
                return True

            def read(self):
                return (True, self.frames.pop(0)) if self.frames else (False, None)

            def get(self, *_args):
                return 25

            def release(self):
                self.released = True

        class FakeWriter:
            def __init__(self):
                self.frames = []
                self.released = False

            def write(self, output):
                self.frames.append(output)

            def release(self):
                self.released = True

        capture, writer = FakeCapture(), FakeWriter()
        with (
            patch.object(media.cv2, "VideoCapture", return_value=capture),
            patch.object(media.cv2, "VideoWriter", return_value=writer),
            patch.object(media.cv2, "VideoWriter_fourcc", return_value=0),
            patch.object(media.cv2, "imshow"),
            patch.object(media.cv2, "waitKey", return_value=0),
            patch.object(media.cv2, "destroyAllWindows"),
            patch.object(media, "process_frame", side_effect=lambda value, *_args, **_kwargs: value),
        ):
            media.run_stream(0, object(), 0.5, "output.mp4", PlateStabilizer(), None, 3)

        self.assertTrue(capture.released)
        self.assertTrue(writer.released)
        self.assertEqual(len(writer.frames), 2)


if __name__ == "__main__":
    unittest.main()
