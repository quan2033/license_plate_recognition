"""Đọc ảnh, video và webcam; xuất frame kết quả"""

from pathlib import Path

import cv2

from frame_processor import process_frame


def is_image_source(source):
    return Path(str(source)).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def run_image(image_path, model, confidence_threshold, output_path, logger):
    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(f"Khong the doc anh: {image_path}")
    annotated = process_frame(frame, model, confidence_threshold, logger=logger)
    if output_path:
        cv2.imwrite(output_path, annotated)
        print(f"Đã lưu kết quả: {output_path}")
    cv2.imshow("Nhận diện biển số - nhấn phím bất kì để đóng", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def run_stream(source, model, confidence_threshold, output_path, stabilizer, logger, ocr_every):
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise RuntimeError(f"Không thể mở nguồn video/camera: {source}")

    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    writer = None
    frame_number = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frame_number += 1
        annotated = process_frame(
            frame, model, confidence_threshold, stabilizer, logger, frame_number, ocr_every
        )

        if output_path and writer is None:
            height, width = annotated.shape[:2]
            fps = capture.get(cv2.CAP_PROP_FPS) or 25
            writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if writer:
            writer.write(annotated)
        cv2.imshow("Nhan dien bien so - nhan q de dung", annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    capture.release()
    if writer:
        writer.release()
        print(f"Da luu video: {output_path}")
    cv2.destroyAllWindows()
