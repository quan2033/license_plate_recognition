from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.services.recognition_service import recognize_image

router = APIRouter(prefix="/recognize", tags=["Recognition"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/image")
async def recognize_uploaded_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG, and WebP images are supported",
        )

    image_bytes = await file.read(MAX_FILE_SIZE + 1)

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller")

    try:
        return recognize_image(image_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="YOLO model file was not found") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Recognition failed: {type(exc).__name__}",
        ) from exc
    finally:
        await file.close()
