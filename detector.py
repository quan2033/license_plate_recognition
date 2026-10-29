"""Phát hiện vị trí biển số bằng YOLO"""


def detect_plates(frame, model, confidence_threshold):

    """Trả về danh sách (box, confidence) của các biển số phát hiện được."""
    result = model(frame, conf=confidence_threshold, verbose=False)[0]
    detections = []
    for detected_box in result.boxes:
        box = tuple(map(int, detected_box.xyxy[0].tolist()))
        confidence = float(detected_box.conf[0])
        detections.append((box, confidence))
    return detections
