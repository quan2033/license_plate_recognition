"""Phat hien vi tri bien so bang YOLO."""


def detect_plates(frame, model, confidence_threshold):
    """Tra ve danh sach (box, confidence) cua cac bien so phat hien duoc."""
    result = model(frame, conf=confidence_threshold, verbose=False)[0]
    detections = []
    for detected_box in result.boxes:
        box = tuple(map(int, detected_box.xyxy[0].tolist()))
        confidence = float(detected_box.conf[0])
        detections.append((box, confidence))
    return detections
