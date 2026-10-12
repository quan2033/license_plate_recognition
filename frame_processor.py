"""Kết hợp detector, OCR, tracking và hiển thị trên 1 frame."""

from detector import detect_plates
from plate_ocr import crop_plate, read_plate
from visualization import draw_detection


def process_frame(
    frame, model, confidence_threshold, stabilizer=None, logger=None,
    frame_number=0, ocr_every=1,
):
    # Crop biển sạch trước vì draw_detection vẽ lên frame
    detections = [
        (box, confidence, crop_plate(frame, box))
        for box, confidence in detect_plates(frame, model, confidence_threshold)
    ]
    for box, confidence, plate in detections:
        if plate.size == 0:
            continue

        plate_text, ocr_confidence = "", 0.0
        if frame_number % ocr_every == 0:
            plate_text, ocr_confidence = read_plate(plate)
        if stabilizer:
            stable_text, ready_to_log = stabilizer.update(box, plate_text, ocr_confidence, frame_number)
        else:
            stable_text, ready_to_log = plate_text, True
        # Chỉ ghi vào CSV khi nhiều frame cho kết quả trùng nhau
        if stable_text and ready_to_log and logger:
            logger.log(stable_text)
        draw_detection(frame, box, stable_text, confidence)
    return frame
