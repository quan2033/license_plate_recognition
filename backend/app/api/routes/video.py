
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.services.video_service import recognize_video

router = APIRouter(prefix="/recognize", tags=["Video Recognition"])

MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "outputs"


@router.post("/video")
async def recognize_uploaded_video(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Chỉ hỗ trợ video MP4, AVI, MOV hoặc MKV",
        )

    try:
        video_bytes = await file.read(MAX_VIDEO_SIZE + 1)

        if not video_bytes:
            raise HTTPException(status_code=400, detail="Video tải lên bị trống")

        if len(video_bytes) > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Video phải có dung lượng không quá 100 MB",
            )

        try:
            return recognize_video(video_bytes, file.filename or "video.mp4")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="Không tìm thấy file trọng số YOLO",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi xử lý video: {type(exc).__name__}",
            ) from exc
    finally:
        await file.close()


@router.get("/video/result/{filename}")
def get_video_result(filename: str):
    # Chỉ cho phép tên file kết quả do backend tạo.
    if (
        not filename.startswith("result_")
        or Path(filename).name != filename
        or Path(filename).suffix.lower() != ".mp4"
    ):
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")

    video_path = OUTPUT_DIR / filename

    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy video kết quả")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
    )
