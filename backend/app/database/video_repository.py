"""PHẦN 2 – bảng video_plates (biển số xử lý từ video cho trước). Chỉ file này chứa SQL của bảng này."""

from backend.app.database.connection import escape_like, get_connection

_COLUMNS = "id, license_plate, detection_confidence, ocr_confidence, source_type, filename, created_at"


def add_many(records: list[dict]) -> int:
    """Lưu nhiều biển số trong một giao dịch; trả về số bản ghi đã lưu.

    source_type là 'video' (mặc định) hoặc 'image'.
    """
    if not records:
        return 0
    rows = [
        (
            record["license_plate"],
            record.get("detection_confidence"),
            record.get("ocr_confidence"),
            record.get("source_type", "video"),
            record.get("filename"),
        )
        for record in records
    ]
    with get_connection() as connection:
        connection.executemany(
            """INSERT INTO video_plates
               (license_plate, detection_confidence, ocr_confidence, source_type, filename)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
    return len(rows)


def get_by_id(plate_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM video_plates WHERE id = ?", (plate_id,)
        ).fetchone()
    return dict(row) if row else None


def _filters(license_plate: str | None, filename: str | None) -> tuple[str, list]:
    conditions, params = [], []
    if license_plate:
        conditions.append("license_plate LIKE ? ESCAPE '\\'")
        params.append(f"%{escape_like(license_plate)}%")
    if filename:
        conditions.append("filename = ?")
        params.append(filename)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


def list_plates(
    limit: int = 50, offset: int = 0, license_plate: str | None = None, filename: str | None = None
) -> list[dict]:
    """Bản ghi mới nhất trước."""
    where, params = _filters(license_plate, filename)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT {_COLUMNS} FROM video_plates {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [dict(row) for row in rows]


def count_plates(license_plate: str | None = None, filename: str | None = None) -> int:
    where, params = _filters(license_plate, filename)
    with get_connection() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM video_plates {where}", params).fetchone()[0]
