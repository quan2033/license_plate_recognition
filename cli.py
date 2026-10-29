"""Điểm vào dòng lệnh của ứng dụng"""

import argparse

from ultralytics import YOLO

from media import is_image_source, run_image, run_stream
from plate_tracking import CsvLogger, PlateStabilizer


def parse_args():
    parser = argparse.ArgumentParser(description="Nhận diện biển số xe")
    parser.add_argument("--source", default="0", help="Đường dẫn ảnh/video hoặc 0 cho camera")
    parser.add_argument("--weights", default="best.pt", help="File trọng số YOLO")
    parser.add_argument("--conf", type=float, default=0.3, help="Ngưỡng tin cậy YOLO")
    parser.add_argument("--save", default=None, help="Đường dẫn video kết quả (chỉ video/webcam)")
    parser.add_argument(
        "--image-output", default=None,
        help="Đường dẫn lưu ảnh kết quả (để trống nếu chỉ muốn hiển thị)",
    )
    parser.add_argument("--csv", default="plate_records.csv", help="File CSV lưu biển số đã nhận diện")
    parser.add_argument(
        "--min-votes", type=int, default=2,
        help="Số frame cùng kết quả để xác nhận biển số bị mờ (biển hiển thị rõ được xác nhận ngay)",
    )
    parser.add_argument("--cooldown", type=int, default=10, help="Số giây cho phép ghi lại cùng biển số")
    parser.add_argument(
        "--ocr-every", type=int, default=1,
        help="Chỉ OCR mỗi N frame khi dùng video/camera (mặc định: 1)",
    )
    return parser.parse_args()


def run():
    args = parse_args()
    model = YOLO(args.weights)
    source = int(args.source) if args.source.isdigit() else args.source
    logger = CsvLogger(args.csv, args.cooldown)
    if is_image_source(source):
        run_image(str(source), model, args.conf, args.image_output, logger)
        return
    stabilizer = PlateStabilizer(args.min_votes)
    run_stream(source, model, args.conf, args.save, stabilizer, logger, max(1, args.ocr_every))
