"""Đọc kí tự trên biển số bằng fast-plate-ocr với chiến lược OCR thích ứng."""

import re
from collections import defaultdict

import cv2
import numpy as np
import onnxruntime
from fast_plate_ocr import LicensePlateRecognizer


# Nhiều model cùng đọc rồi bỏ phiếu: mỗi model sai ở chỗ khác nhau
# Chạy model nhỏ trước. Hai model lớn chỉ dùng khi kết quả nhanh chưa đủ chắc chắn.
MODEL_NAMES = ("cct-xs-v2-global-model", "cct-s-v2-global-model", "cct-s-v1-global-model")
FAST_ACCEPT_CONFIDENCE = 0.98

#Biển 2 dòng (xe máy) gần vuông, biển 1 dòng (ô tô) dài. Phân bố trong dataset
#Biển 1 dòng chủ yếu 0.3-0.7, biển 2 dòng từ 0.8 trở lên, 0.75-1.0 là cùng mờ do độ nghiêng
TWO_LINE_RATIO = 0.75
CERTAIN_TWO_LINE_RATIO = 1.0
TWO_LINE_BODY_RATIO = 0.58
BODY_MIN_FRACTION = 0.2
BODY_MAX_FRACTION = 0.97

#Tỷ lệ thêm vào mỗi cạnh crop để không cắt mất kí tự ở sát mép
CROP_PADDING = 0.04

#Dưới mức này thì coi như không đọc được
MIN_CONFIDENCE = 0.6

#Khung YOLO đôi khi hụt mất ký tự cuối: nếu đọc chưa chắc chắn thì thử lại với vùng cắt rộng hơn
RETRY_BELOW_CONFIDENCE = 0.9
WIDER_PADDINGS = (0.15, 0.3)

# I, J, O, Q, W không dùng làm seri. R vẫn xuất hiện trên một số biển xe máy cũ.
SERIES_LETTERS = set("ABCDEFGHKLMNPRSTUVXYZ")

#Sửa kí tự hay bị nhầm theo vị trí: vị trí số <- chữ, vị trí chữ <- số
TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "Z": "2", "S": "5", "G": "6", "B": "8"}
# "1"/"I" ở vị trí seri thường là chữ L (I không dùng làm seri).
TO_LETTER = {"0": "D", "1": "L", "I": "L", "8": "B", "5": "S", "2": "Z", "6": "G"}

SECOND_SERIES_FIX = {"O": "D", "Q": "D"}

_recognizers = []


def _get_recognizers():
    #Nạp model 1 lần (model chạy lần đầu được tải về)
    if not _recognizers:
        # Chi hien loi nghiem trong; onnxruntime hay in canh bao shape vo hai khi nap model
        options = onnxruntime.SessionOptions()
        options.log_severity_level = 3
        for name in MODEL_NAMES:
            _recognizers.append(LicensePlateRecognizer(name, sess_options=options))
    return _recognizers


def _as_digits(chars):
    fixed = "".join(TO_DIGIT.get(char, char) for char in chars)
    return fixed if fixed.isdigit() else ""


def format_plate(text, two_line=False):
    #Chuan hoa chuoi OCR thanh bien so VN; tra ve "" neu khong hop le. Chuẩn hóa chuỗi OCR thành biển số, trả về "" nếu không không hợp lệ
    text = re.sub(r"[^A-Z0-9]", "", text.upper())
    # Biển xe máy cũ dạng 36-R3 0829 có 8 ký tự. Seri R kèm một chữ số,
    # không được diễn giải thành biển một dòng 36R-308.29.
    if len(text) == 8 and text[2:3] == "R" and text[3:4].isdigit():
        two_line = True
    return _parse_plate(text, two_line) or _parse_plate(text, not two_line)


def _parse_plate(text, two_line):
    if len(text) not in (7, 8, 9):
        return ""

    province = _as_digits(text[:2])
    series = TO_LETTER.get(text[2], text[2])
    if not province or not 11 <= int(province) <= 99 or series not in SERIES_LETTERS:
        return ""

    rest = text[3:]
    if len(text) == 9 or (len(text) == 8 and two_line):
        # Seri có 2 kí tự (chữ + chữ/số) rồi tiếp đến là 4 hoặc 5 chữ số. Biển VN không có "O"
        series += SECOND_SERIES_FIX.get(rest[0], rest[0])
        rest = rest[1:]
    digits = _as_digits(rest)
    if len(digits) == 5:
        return f"{province}{series}-{digits[:3]}.{digits[3:]}"
    if len(digits) == 4 and (len(series) == 2 or not two_line):
        return f"{province}{series}-{digits}"
    return ""


def crop_plate(frame, box, padding=CROP_PADDING):
    #Cắt biển số từ frame, nới rộng box để không mất kí tự
    x1, y1, x2, y2 = box
    pad_x = int((x2 - x1) * padding)
    pad_y = int((y2 - y1) * padding)
    height, width = frame.shape[:2]
    # copy() để crop không bị khung vẽ của các đè lên (frame dùng dung bộ nhớ).
    return frame[max(0, y1 - pad_y):min(height, y2 + pad_y), max(0, x1 - pad_x):min(width, x2 + pad_x)].copy()


def _run_model(recognizer, color, gray):
    # Chạy một model, mỗi model đòi số kênh ảnh khác nhau, thử màu trước, nếu lỗi thì thử ảnh xám
    for image in (color, gray):
        try:
            return recognizer.run(image, return_confidence=True)[0]
        except Exception:
            continue
    return None


def _body_ratio(plate):
     # Tỉ lệ cao/rộng của hình chữ nhật xoay bao nền biển, None nếu không tách được nền
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (160, 100), interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    best_fraction, best_contour = 0.0, None
    # Thử cả 2 cực (nền biển sáng hoặc tối), lấy vùng liên tục lớn nhất
    for mask in (binary, 255 - binary):
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        fraction = cv2.contourArea(contour) / (160 * 100)
        if fraction <= BODY_MAX_FRACTION and fraction > best_fraction:
            best_fraction, best_contour = fraction, contour
    if best_contour is None or best_fraction < BODY_MIN_FRACTION:
        return None
    _, (width, height), _ = cv2.minAreaRect(best_contour)
    return min(width, height) / max(width, height, 1)


def is_two_line(plate):
    """Đoán biển xe máy 2 dòng hay biển ô tô 1 dòng"""
    height, width = plate.shape[:2]
    box_ratio = height / max(width, 1)
    if box_ratio < TWO_LINE_RATIO:
        return False
    if box_ratio >= CERTAIN_TWO_LINE_RATIO:
        return True
    body = _body_ratio(plate)
    return body >= TWO_LINE_BODY_RATIO if body is not None else box_ratio >= 0.9


def read_plate(plate):
    """Đọc biển số từ crop, trả về (biển số , độ tin cậy 0-1), ("" , 0.0) nếu không được"""
    if plate is None or plate.size == 0:
        return "", 0.0
    two_line = is_two_line(plate)
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    recognizers = _get_recognizers()
    totals = defaultdict(float)
    supporters = defaultdict(int)
    for index, recognizer in enumerate(recognizers):
        prediction = _run_model(recognizer, plate, gray)
        if prediction is None or not prediction.plate:
            continue
        text = format_plate(prediction.plate, two_line)
        if not text:
            continue
        chars = prediction.char_probs[:len(prediction.plate)]
        char_confidence = float(chars.mean())
        # Model XS đủ chắc chắn và chuỗi đã qua kiểm tra định dạng thì không cần
        # chạy thêm hai model lớn. Trường hợp khó vẫn dùng đủ bộ model để bỏ phiếu.
        if index == 0 and char_confidence >= FAST_ACCEPT_CONFIDENCE:
            return text, char_confidence
        totals[text] += char_confidence
        supporters[text] += 1

    if not totals:
        return "", 0.0
    # Chọn kết quả được nhiều model xác định nhất, độ tin cậy = avg(xs kí tự)
    text = max(totals, key=totals.get)
    agreement = supporters[text] / len(recognizers)
    confidence = totals[text] / supporters[text] * (0.5 + 0.5 * agreement)
    return (text, confidence) if confidence >= MIN_CONFIDENCE else ("", confidence)


def read_plate_wider(frame, box, text, confidence):
    """Đọc chưa chắc chắn thì thử cắt rộng hơn, giữ kết quả có độ tin cậy cao nhất"""
    if confidence >= RETRY_BELOW_CONFIDENCE:
        return text, confidence
    best_text, best_confidence = text, confidence
    for padding in WIDER_PADDINGS:
        wider_text, wider_confidence = read_plate(crop_plate(frame, box, padding))
        if wider_text and wider_confidence > best_confidence:
            best_text, best_confidence = wider_text, wider_confidence
    return best_text, best_confidence
