# Hệ thống nhận diện biển số xe Việt Nam

Ứng dụng dòng lệnh nhận diện biển số xe từ **ảnh**, **video** hoặc **webcam**. Kết quả được vẽ trực tiếp lên hình và tự động ghi vào file CSV.

- **Phát hiện biển số:** YOLO (`best.pt`, huấn luyện trên 1 lớp `license_plate`).
- **Đọc ký tự:** `fast-plate-ocr` (ONNX, chạy hoàn toàn trên CPU, không cần GPU hay Tesseract).
- **Loại biển hỗ trợ:**
  - Biển ô tô 1 dòng: `51A-123.45`, `51A-1234`
  - Biển xe máy 2 dòng: `59C1-239.68`, `59F1-1234`

## Mục lục

1. [Cách hoạt động](#1-cách-hoạt-động)
2. [Cấu trúc thư mục](#2-cấu-trúc-thư-mục)
3. [Cài đặt](#3-cài-đặt)
4. [Hướng dẫn sử dụng](#4-hướng-dẫn-sử-dụng)
5. [Bảng tham số](#5-bảng-tham-số)
6. [Kết quả đầu ra](#6-kết-quả-đầu-ra)
7. [Huấn luyện lại model](#7-huấn-luyện-lại-model)
8. [Kiểm thử](#8-kiểm-thử)
9. [Giới hạn đã biết](#9-giới-hạn-đã-biết)

## 1. Cách hoạt động

```
Khung hình ──► YOLO tìm biển ──► Cắt biển ──► 3 model OCR bỏ phiếu ──► Chuẩn hoá ──► Ổn định nhiều frame ──► Ghi CSV
```

1. **Phát hiện:** YOLO xác định vị trí biển số trong khung hình (ngưỡng `--conf`, mặc định 0.3; đạt khoảng 99% biển trên tập kiểm tra).
2. **Cắt biển:** vùng biển được nới rộng 4% mỗi cạnh để không mất ký tự sát mép. Hệ thống tự đoán biển 1 dòng hay 2 dòng, kể cả khi biển bị chụp nghiêng.
3. **Đọc ký tự:** 3 model OCR cùng đọc và bỏ phiếu để chọn kết quả tốt nhất.
4. **Chuẩn hoá theo định dạng biển Việt Nam:** kiểm tra mã tỉnh, tự sửa các ký tự dễ nhầm (ví dụ `I`→`1`, `O`→`D`). Chuỗi không hợp lệ hoặc độ tin cậy thấp sẽ hiển thị **"Chưa đọc được"** thay vì trả về biển sai.
5. **Ổn định nhiều frame (video/webcam):**
   - Biển đọc rõ (độ tin cậy ≥ 90%) được hiển thị ngay từ frame đầu.
   - Biển mờ được gộp kết quả qua nhiều frame.
   - Chỉ ghi CSV khi có đủ `--min-votes` frame đồng ý, và mỗi biển chỉ ghi **một lần**.

**Tốc độ trên CPU:** khoảng 120 ms/frame (≈ 8 FPS) với video, khoảng 0,2 giây với một ảnh đơn.

## 2. Cấu trúc thư mục

| File | Chức năng |
|---|---|
| `main.py` | Điểm khởi chạy: `python main.py` |
| `cli.py` | Đọc tham số dòng lệnh và khởi tạo ứng dụng |
| `detector.py` | Chạy YOLO, trả về toạ độ biển số |
| `frame_processor.py` | Kết hợp phát hiện, OCR và theo dõi trên từng frame |
| `plate_ocr.py` | OCR, nhận dạng bố cục 1/2 dòng, chuẩn hoá biển số Việt Nam |
| `plate_tracking.py` | Ổn định kết quả nhiều frame và ghi CSV |
| `media.py` | Đọc/ghi ảnh, video và webcam |
| `visualization.py` | Vẽ khung và nhãn kết quả lên hình |
| `train.py`, `data.yaml` | Huấn luyện model YOLO |
| `test_pipeline.py` | Bộ kiểm thử tự động |
| `best.pt` | Trọng số YOLO đã huấn luyện |
| `requirement.txt` | Danh sách thư viện cần cài |

## 3. Cài đặt

**Yêu cầu:** Python 3.10 trở lên, Windows (các lệnh dưới đây dùng PowerShell).

**Bước 1.** Kích hoạt môi trường ảo:

```powershell
.\venv\Scripts\Activate.ps1
```

**Bước 2.** Cài các thư viện:

```powershell
pip install -r requirement.txt
pip install --no-deps fast-plate-ocr
```

> **Quan trọng:** bắt buộc dùng `--no-deps` khi cài `fast-plate-ocr`. Nếu không, gói này kéo theo `opencv-python-headless` và ghi đè `opencv-python`, khiến `cv2.imshow` không hiển thị được cửa sổ.

**Lần chạy đầu tiên** cần có Internet để tải 3 model OCR (khoảng 20 MB). Model được lưu vào bộ nhớ đệm, các lần sau chạy offline.

## 4. Hướng dẫn sử dụng

**Ảnh** (chỉ hiển thị kết quả):

```powershell
python main.py --source images.jpg
```

**Ảnh** (lưu thêm ảnh đã vẽ khung):

```powershell
python main.py --source images.jpg --image-output ketqua.jpg
```

**Video** (nhấn `q` để dừng):

```powershell
python main.py --source video.mp4 --save output.mp4
```

**Webcam** (nhấn `q` để dừng):

```powershell
python main.py --source 0
```

**Máy yếu:** chỉ chạy OCR mỗi 3 frame để giảm tải:

```powershell
python main.py --source 0 --ocr-every 3
```

**Tuỳ chỉnh ngưỡng nhận diện và file CSV:**

```powershell
python main.py --source 0 --conf 0.4 --min-votes 3 --csv plate_records.csv
```

## 5. Bảng tham số

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--source` | `0` | Nguồn đầu vào: đường dẫn ảnh/video, hoặc `0` cho webcam |
| `--weights` | `best.pt` | File trọng số YOLO |
| `--conf` | `0.3` | Ngưỡng tin cậy của YOLO; vùng thấp hơn ngưỡng bị loại |
| `--save` | không lưu | Đường dẫn lưu video kết quả (chỉ video/webcam) |
| `--image-output` | không lưu | Đường dẫn lưu ảnh kết quả (chỉ ảnh) |
| `--csv` | `plate_records.csv` | File CSV ghi các biển số đã nhận diện |
| `--min-votes` | `2` | Số frame cùng đọc ra một biển mờ trước khi xác nhận; biển rõ được xác nhận ngay |
| `--cooldown` | `10` | Số giây chờ trước khi cho phép ghi lại cùng một biển số |
| `--ocr-every` | `1` | Chỉ chạy OCR mỗi N frame (video/webcam); số lớn hơn thì nhanh hơn nhưng ít chính xác hơn |

## 6. Kết quả đầu ra

File CSV (mặc định `plate_records.csv`) gồm hai cột: thời gian và biển số.

```csv
timestamp,license_plate
2026-10-08T20:23:32,51A-034.42
```

Cùng một biển số chỉ được ghi lại sau khoảng `--cooldown` giây, nhằm tránh ghi trùng khi xe đứng yên trước camera.

## 7. Huấn luyện lại model

Cấu hình dữ liệu nằm trong `data.yaml` (1 lớp: `license_plate`; thư mục `dataset/` gồm `train`, `valid`, `test`). Chạy:

```powershell
python train.py
```

Mặc định: model nền `yolo26n.pt`, 50 epoch, ảnh 640 px, batch 8. Sau khi huấn luyện, dùng file trọng số mới qua tham số `--weights`.

## 8. Kiểm thử

```powershell
python -m unittest test_pipeline.py
```

Bộ kiểm thử không cần webcam hay cửa sổ hiển thị, bao gồm: định dạng biển số, nhận dạng bố cục 1/2 dòng, cơ chế ổn định nhiều frame, ghi CSV, giải phóng tài nguyên camera và OCR trên ảnh mẫu `plate_0.jpg` (tự bỏ qua nếu thiếu file này).

## 9. Giới hạn đã biết

- **Biển quá nhỏ hoặc mờ** (cao dưới khoảng 30 px) hoặc bị cắt mất ký tự: hệ thống báo "Chưa đọc được". Với video, nhiều frame sẽ bỏ phiếu và thường đọc được khi xe lại gần hơn.
- **Biển quân đội, công vụ nền đỏ** (ví dụ `KV-74-84`, `KP-45-79`) không theo định dạng dân sự nên bị bỏ qua.
- **Biển ô tô 1 dòng chụp nghiêng nhiều** có thể bị chia sai bố cục (ví dụ `51A7-7529` thay vì `51A-775.29`). Các chữ số vẫn đúng, chỉ vị trí dấu `-` và `.` bị sai.
