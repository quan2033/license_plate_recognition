"""Ổn định OCR qua nhiêu frame và lưu sự kiện biển số"""

import csv
from collections import Counter, deque
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path


def box_iou(first_box, second_box):
    left = max(first_box[0], second_box[0])
    top = max(first_box[1], second_box[1])
    right = min(first_box[2], second_box[2])
    bottom = min(first_box[3], second_box[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    if not intersection:
        return 0.0
    first_area = max(0, first_box[2] - first_box[0]) * max(0, first_box[3] - first_box[1])
    second_area = max(0, second_box[2] - second_box[0]) * max(0, second_box[3] - second_box[1])
    return intersection / (first_area + second_area - intersection)


class PlateStabilizer:
    """Gop ket qua OCR cua cung mot bien so qua nhieu frame. Gộp kết quả OCR của cùng một biển số qua nhiều frame"""

    def __init__(self, min_votes=2, max_age=30, instant_confidence=0.9):
        self.min_votes = min_votes
        self.max_age = max_age
        # Biển rõ thì xác nhận ngay ở frame đầu, không cần bỏ phiếu
        self.instant_confidence = instant_confidence
        self.new_plate_confidence = 0.8
        self.same_plate_similarity = 0.6
        self.tracks = {}
        # Lưu toàn bộ biển đã xác nhận trong phiên, độc lập với các track còn sống.
        # Video có thể làm track cũ hết hạn trước khi xử lý xong toàn bộ file.
        self.recognized_plates = {}
        self.next_track_id = 0

    def update(self, box, text, confidence, frame_number):
        best_id, best_iou = None, 0.0
        for track_id, track in self.tracks.items():
            overlap = box_iou(box, track["box"])
            if overlap > best_iou:
                best_id, best_iou = track_id, overlap

        if best_iou < 0.3:
            best_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[best_id] = {"box": box, "votes": deque(maxlen=8), "last_seen": frame_number}

        track = self.tracks[best_id]
        track["box"] = box
        track["last_seen"] = frame_number
        # Xe khác vào chỗ xe cũ thì track lại biển mới
        accepted = track.get("accepted")
        if (text and accepted and confidence >= self.new_plate_confidence
                and SequenceMatcher(None, text, accepted).ratio() < self.same_plate_similarity):
            track["votes"].clear()
            for key in ("accepted", "confirmed", "logged"):
                track.pop(key, None)
        if text:
            track["votes"].append((text, confidence))

        expired = [track_id for track_id, value in self.tracks.items()
                   if frame_number - value["last_seen"] > self.max_age]
        for track_id in expired:
            del self.tracks[track_id]

        if track["votes"]:
            counts = Counter(vote_text for vote_text, _ in track["votes"])
            weights = Counter()
            for vote_text, vote_confidence in track["votes"]:
                weights[vote_text] += vote_confidence
            candidate = max(weights, key=weights.get)
            if counts[candidate] >= self.min_votes and counts[candidate] / len(track["votes"]) > 0.5:
                track["accepted"], track["confirmed"] = candidate, True
        #  Biển đọc được chắc chắn được hiển thị ngay ở frame đầu, chưa "confirmed" thì chưa ghi
        # CSV và một frame đọc nhầm sau đó không ghi đè lên kết quả đã có
        if text and confidence >= self.instant_confidence and "accepted" not in track:
            track["accepted"], track["confirmed"] = text, False
        accepted = track.get("accepted")
        if accepted and track.get("confirmed", False):
            accepted_scores = [
                score for vote_text, score in track["votes"]
                if vote_text == accepted
            ]
            accepted_confidence = (
                sum(accepted_scores) / len(accepted_scores)
                if accepted_scores else confidence
            )
            previous_confidence = self.recognized_plates.get(accepted)
            if (
                previous_confidence is None
                or accepted_confidence > previous_confidence
            ):
                self.recognized_plates[accepted] = round(accepted_confidence, 4)
        ready = track.get("confirmed", False) and not track.get("logged", False)
        if ready:
            track["logged"] = True
        # Giữ kết quả cho các frame không chạy OCR để nhãn không bị nhấp nháy
        return track.get("accepted", ""), ready


class CsvLogger:
    """Lưu biển số, đồng thời chặn bản ghi trùng lặp liên tiếp"""

    def __init__(self, path, cooldown_seconds=10):
        self.path = Path(path)
        self.cooldown_seconds = cooldown_seconds
        self.last_logged = {}
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as file:
                csv.writer(file).writerow(["timestamp", "license_plate"])

    def log(self, plate):
        now = datetime.now()
        previous = self.last_logged.get(plate)
        if previous and (now - previous).total_seconds() < self.cooldown_seconds:
            return False
        with self.path.open("a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow([now.isoformat(timespec="seconds"), plate])
        self.last_logged[plate] = now
        print(f"Da ghi nhan: {plate}")
        return True
