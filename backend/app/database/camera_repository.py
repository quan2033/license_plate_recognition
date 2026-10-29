"""PHẦN 1 – bảng camera_plates (biển số nhận từ camera). Chỉ file này chứa SQL của bảng này."""

from backend.app.database.connection import escape_like, get_connection

_COLUMNS = (
    "id, camera_id, location, license_plate, detection_confidence, "
    "ocr_confidence, captured_at, created_at"
)


def add_many(records: list[dict]) -> list[int]:
    """Lưu nhiều biển số từ camera trong một giao dịch; trả về danh sách id mới.

    Mỗi record cần camera_id và license_plate; captured_at để trống thì dùng giờ hiện tại.
    """
    ids = []
    with get_connection() as connection:
        for record in records:
            cursor = connection.execute(
                """INSERT INTO camera_plates
                       (camera_id, location, license_plate, detection_confidence,
                        ocr_confidence, captured_at)
                   VALUES (?, ?, ?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))""",
                (
                    record["camera_id"],
                    record.get("location"),
                    record["license_plate"],
                    record.get("detection_confidence"),
                    record.get("ocr_confidence"),
                    record.get("captured_at"),
                ),
            )
            ids.append(cursor.lastrowid)
    return ids


def get_by_id(plate_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM camera_plates WHERE id = ?", (plate_id,)
        ).fetchone()
    return dict(row) if row else None


def _filters(license_plate: str | None, camera_id: str | None) -> tuple[str, list]:
    conditions, params = [], []
    if license_plate:
        conditions.append("license_plate LIKE ? ESCAPE '\\'")
        params.append(f"%{escape_like(license_plate)}%")
    if camera_id:
        conditions.append("camera_id = ?")
        params.append(camera_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


def list_plates(
    limit: int = 50, offset: int = 0, license_plate: str | None = None, camera_id: str | None = None
) -> list[dict]:
    """Bản ghi chụp gần nhất trước."""
    where, params = _filters(license_plate, camera_id)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_COLUMNS} FROM camera_plates {where} "
            "ORDER BY captured_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [dict(row) for row in rows]


def count_plates(license_plate: str | None = None, camera_id: str | None = None) -> int:
    where, params = _filters(license_plate, camera_id)
    with get_connection() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM camera_plates {where}", params).fetchone()[0]
