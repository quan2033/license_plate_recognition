import base64
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from detector import detect_plates
from plate_ocr import crop_plate, read_plate
from visualization import draw_detection


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "best.pt"


@lru_cache(maxsize=1)
def get_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"YOLO weights not found: {MODEL_PATH}")

    return YOLO(str(MODEL_PATH))


def recognize_image(image_bytes: bytes) -> dict:
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Cannot decode uploaded image")

    model = get_model()
    detections = detect_plates(frame, model, 0.3)
    results = []

    for box, detection_confidence in detections:
        plate_crop = crop_plate(frame, box)

        if plate_crop is None or plate_crop.size == 0:
            continue

        plate_text, ocr_confidence = read_plate(plate_crop)

        draw_detection(frame, box, plate_text, detection_confidence)

        results.append({
            "license_plate": plate_text or None,
            "detection_confidence": round(detection_confidence, 4),
            "ocr_confidence": round(float(ocr_confidence), 4),
            "box": list(box),
        })

    success, encoded_image = cv2.imencode(".jpg", frame)
    if not success:
        raise RuntimeError("Failed to encode processed image")

    image_base64 = base64.b64encode(encoded_image.tobytes()).decode("ascii")

    return {
        "count": len(results),
        "results": results,
        "image_base64": image_base64,
    }
