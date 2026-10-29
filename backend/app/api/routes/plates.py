from fastapi import APIRouter, HTTPException, Query

from backend.app.database import camera_repository, video_repository
from backend.app.schemas.plate import (
    CameraPlateCreate,
    CameraPlateList,
    CameraPlateRecord,
    VideoPlateList,
    VideoPlateRecord,
)

router = APIRouter(prefix="/plates", tags=["Plates"])


# ---------- Phần 1: dữ liệu từ camera ----------
@router.post("/camera", response_model=CameraPlateRecord, status_code=201)
def add_camera_plate(payload: CameraPlateCreate):
    """Camera (hoặc tiến trình đọc camera) gửi biển số vừa nhận diện được."""
    plate_id = camera_repository.add_many([payload.model_dump()])[0]
    return camera_repository.get_by_id(plate_id)


@router.get("/camera", response_model=CameraPlateList)
def list_camera_plates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    license_plate: str | None = Query(None, min_length=1, max_length=20, description="Tìm theo đoạn biển số"),
    camera_id: str | None = Query(None, min_length=1, max_length=50),
):
    return {
        "total": camera_repository.count_plates(license_plate, camera_id),
        "limit": limit,
        "offset": offset,
        "items": camera_repository.list_plates(limit, offset, license_plate, camera_id),
    }


@router.get("/camera/{plate_id}", response_model=CameraPlateRecord)
def get_camera_plate(plate_id: int):
    plate = camera_repository.get_by_id(plate_id)
    if plate is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy biển số")
    return plate


# ---------- Phần 2: dữ liệu xử lý từ video ----------
@router.get("/video", response_model=VideoPlateList)
def list_video_plates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    license_plate: str | None = Query(None, min_length=1, max_length=20, description="Tìm theo đoạn biển số"),
    filename: str | None = Query(None, min_length=1, max_length=255, description="Lọc theo tên video"),
):
    return {
        "total": video_repository.count_plates(license_plate, filename),
        "limit": limit,
        "offset": offset,
        "items": video_repository.list_plates(limit, offset, license_plate, filename),
    }


@router.get("/video/{plate_id}", response_model=VideoPlateRecord)
def get_video_plate(plate_id: int):
    plate = video_repository.get_by_id(plate_id)
    if plate is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy biển số")
    return plate
