"""Vẽ kết quả nhận diện được lên frame"""

import cv2


def draw_detection(frame, box, label, confidence):
    x1, y1, x2, y2 = box
    color = (0, 200, 0) if label else (0, 165, 255)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = label or "Chưa đọc được"
    cv2.putText(
        frame, f"{text} ({confidence:.0%})", (x1, max(25, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA,
    )
