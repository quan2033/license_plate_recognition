"""Nhận diện biển số xe từ ảnh, video hoặc camera.

Nguồn vào:
    python main.py --source images.jpg
    python main.py --source video.mp4 --save output.mp4
    python main.py --source 0
"""

# Diem vao giu lai de tuong thich voi lenh `python main.py`.
# Logic moi nam trong cli.py, detector.py, frame_processor.py, media.py,
# plate_ocr.py va plate_tracking.py.
if __name__ == "__main__":
    from cli import run

    raise SystemExit(run())
