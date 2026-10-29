"""Định dạng dữ liệu biển số gửi/nhận qua API."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------- Phần 1: camera ----------
class CameraPlateCreate(BaseModel):
    camera_id: str = Field(min_length=1, max_length=50)
    location: str | None = Field(None, max_length=100)
    license_plate: str = Field(min_length=1, max_length=20)
    detection_confidence: float | None = Field(None, ge=0, le=1)
    ocr_confidence: float | None = Field(None, ge=0, le=1)
    captured_at: str | None = Field(None, description="ISO 8601; bỏ trống = giờ hiện tại")

    @field_validator("captured_at")
    @classmethod
    def _normalize_captured_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("captured_at phải theo định dạng ISO 8601") from exc
        if parsed.tzinfo is None:  # không có múi giờ thì coi là UTC
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CameraPlateRecord(BaseModel):
    id: int
    camera_id: str
    location: str | None = None
    license_plate: str
    detection_confidence: float | None = None
    ocr_confidence: float | None = None
    captured_at: str  # ISO 8601, giờ UTC (kết thúc bằng Z)
    created_at: str


class CameraPlateList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CameraPlateRecord]


# ---------- Phần 2: video ----------
class VideoPlateRecord(BaseModel):
    id: int
    license_plate: str
    detection_confidence: float | None = None
    ocr_confidence: float | None = None
    source_type: Literal["video", "image"]
    filename: str | None = None
    created_at: str  # ISO 8601, giờ UTC (kết thúc bằng Z)


class VideoPlateList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[VideoPlateRecord]
