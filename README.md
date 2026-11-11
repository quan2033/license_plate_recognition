# Hệ thống nhận diện biển số xe Việt Nam

Hệ thống nhận diện biển số xe từ **camera**, **ảnh** và **video**. Dự án cung cấp hai cách sử dụng:

- **Giao diện web:** React + Vite ở frontend, FastAPI ở backend và SQLite để lưu lịch sử.
- **Dòng lệnh:** xử lý trực tiếp ảnh, video hoặc webcam bằng Python và OpenCV.

Pipeline nhận diện kết hợp YOLO để phát hiện vùng biển số, ba model `fast-plate-ocr` để đọc ký tự, bộ quy tắc chuẩn hóa biển số Việt Nam và cơ chế ổn định kết quả qua nhiều frame.

## Tính năng chính

- Phát hiện biển số bằng trọng số YOLO đã huấn luyện trong `best.pt`.
- Nhận dạng biển ô tô một dòng và biển xe máy hai dòng.
- Chạy OCR trên CPU bằng ONNX Runtime, không cần Tesseract hoặc GPU.
- Dùng ba model OCR cùng nhận dạng và chọn kết quả có mức đồng thuận tốt nhất.
- Chuẩn hóa định dạng biển số Việt Nam và sửa một số ký tự dễ nhầm theo vị trí.
- Ổn định kết quả trên nhiều frame để giảm nhấp nháy và hạn chế ghi sai.
- Nhận diện camera trình duyệt tự động theo chu kỳ 500 ms.
- Tải ảnh hoặc video trên giao diện web và tải video kết quả.
- Lưu lịch sử vào SQLite, tự tải lại khi mở ứng dụng và hiển thị chi tiết từng bản ghi.
- Hỗ trợ CLI, lưu ảnh/video đã chú thích và ghi lịch sử vào CSV.
- Có API tra cứu dữ liệu camera, ảnh và video.

## Mục lục

1. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
2. [Công nghệ sử dụng](#công-nghệ-sử-dụng)
3. [Cấu trúc dự án](#cấu-trúc-dự-án)
4. [Yêu cầu môi trường](#yêu-cầu-môi-trường)
5. [Cài đặt](#cài-đặt)
6. [Chạy giao diện web](#chạy-giao-diện-web)
7. [Sử dụng giao diện web](#sử-dụng-giao-diện-web)
8. [Sử dụng dòng lệnh](#sử-dụng-dòng-lệnh)
9. [Quy trình nhận diện](#quy-trình-nhận-diện)
10. [REST API](#rest-api)
11. [Lưu trữ dữ liệu](#lưu-trữ-dữ-liệu)
12. [Huấn luyện lại YOLO](#huấn-luyện-lại-yolo)
13. [Kiểm thử và kiểm tra chất lượng](#kiểm-thử-và-kiểm-tra-chất-lượng)
14. [Xử lý sự cố](#xử-lý-sự-cố)
15. [Giới hạn hiện tại](#giới-hạn-hiện-tại)

## Kiến trúc hệ thống

```text
Người dùng
   │
   ├── Trình duyệt ──► React + Vite ──HTTP──► FastAPI
   │                                         │
   │                                         ├── YOLO phát hiện biển số
   │                                         ├── OCR và chuẩn hóa ký tự
   │                                         ├── Xử lý ảnh/video bằng OpenCV
   │                                         └── SQLite lưu lịch sử
   │
   └── CLI Python ──► YOLO + OCR + OpenCV ──► CSV/ảnh/video kết quả
```

Frontend chạy mặc định tại `http://localhost:5173`. Backend chạy tại `http://127.0.0.1:8000` và cung cấp tài liệu OpenAPI ở `http://127.0.0.1:8000/docs`.

## Công nghệ sử dụng

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Ngôn ngữ backend | Python 3.10+ | Pipeline nhận diện, API và lưu trữ |
| Phát hiện | Ultralytics YOLO | Tìm vùng chứa biển số |
| Xử lý media | OpenCV | Đọc/ghi ảnh, video, camera và vẽ kết quả |
| OCR | `fast-plate-ocr` | Đọc ký tự biển số |
| Suy luận OCR | ONNX Runtime | Chạy model OCR trên CPU |
| Backend web | FastAPI + Uvicorn | REST API và máy chủ ASGI |
| Frontend | React 19 + Vite 8 | Giao diện và quản lý trạng thái |
| Cơ sở dữ liệu | SQLite | Lưu lịch sử nhận diện |
| Kiểm thử | `unittest`, pytest, HTTPX | Kiểm thử pipeline, repository và API |
| Chất lượng frontend | ESLint | Kiểm tra JavaScript và React Hooks |

## Cấu trúc dự án

```text
ProjPython/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # API health, ảnh, video và lịch sử
│   │   ├── core/              # Cấu hình đường dẫn database
│   │   ├── database/          # Kết nối và repository SQLite
│   │   ├── schemas/           # Schema Pydantic
│   │   ├── services/          # Dịch vụ nhận diện ảnh và video
│   │   └── main.py            # Ứng dụng FastAPI
│   ├── data/                  # plates.db, được tạo tự động và không commit
│   ├── outputs/               # Video kết quả, không commit
│   ├── tests/                 # Kiểm thử backend
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx            # Logic và giao diện chính
│   ├── src/App.css            # Kiểu trình bày
│   └── package.json
├── dataset/                   # Dữ liệu train/valid/test, không commit
├── best.pt                    # Trọng số YOLO đang dùng để nhận diện
├── yolo26n.pt                 # Model nền dùng khi huấn luyện
├── main.py                    # Điểm vào CLI
├── cli.py                     # Tham số dòng lệnh
├── detector.py                # Phát hiện biển số bằng YOLO
├── frame_processor.py         # Pipeline trên từng frame
├── plate_ocr.py               # OCR và chuẩn hóa biển số
├── plate_tracking.py          # Ổn định nhiều frame và ghi CSV
├── media.py                   # Ảnh, video và webcam
├── visualization.py           # Vẽ box và nhãn
├── train.py                   # Huấn luyện YOLO
├── data.yaml                  # Cấu hình dataset
├── test_pipeline.py           # Kiểm thử pipeline
├── requirement.txt            # Dependency lõi
└── run.bat                    # Khởi động backend và frontend
```

## Yêu cầu môi trường

- Windows 10 hoặc Windows 11.
- Python 3.10 trở lên.
- Node.js và npm để chạy frontend.
- Webcam nếu sử dụng camera trực tiếp.
- `best.pt` phải nằm tại thư mục gốc dự án.
- Internet ở lần chạy OCR đầu tiên để tải ba model OCR, tổng dung lượng khoảng 20 MB. Các lần sau model được đọc từ cache.

GPU không bắt buộc. YOLO và OCR có thể chạy trên CPU, nhưng tốc độ phụ thuộc cấu hình máy và độ phân giải đầu vào.

## Cài đặt

Các lệnh dưới đây chạy trong PowerShell tại thư mục gốc dự án.

### 1. Tạo môi trường ảo

```powershell
py -3.12 -m venv venv
```

Nếu thư mục `venv` được sao chép từ máy khác hoặc đang trỏ đến một bản Python không còn tồn tại, hãy đổi tên/xóa môi trường cũ rồi tạo lại. Không nên commit `venv` lên Git.

### 2. Cài dependency Python

`backend/requirements.txt` đã bao gồm các dependency lõi từ `requirement.txt` và các gói dùng cho FastAPI/test.

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\venv\Scripts\python.exe -m pip install --no-deps fast-plate-ocr
```

> **Quan trọng:** phải cài `fast-plate-ocr` với `--no-deps`. Cài theo cách mặc định có thể kéo theo `opencv-python-headless` và thay thế `opencv-python`, làm `cv2.imshow` không mở được cửa sổ.

### 3. Cài dependency frontend

```powershell
cd frontend
npm.cmd install
cd ..
```

`npm.cmd` được dùng để tránh trường hợp PowerShell chặn script `npm.ps1` bởi Execution Policy.

## Chạy giao diện web

### Cách nhanh

Sau khi cài đủ dependency:

```powershell
.\run.bat
```

`run.bat` sẽ:

1. Mở backend Uvicorn tại cổng `8000`.
2. Mở frontend Vite tại cổng `5173`.
3. Chờ 8 giây rồi mở `http://localhost:5173`.

Frontend có cơ chế thử tải lịch sử lại mỗi giây, tối đa 10 lần, nếu backend chưa sẵn sàng khi trang vừa mở.

### Chạy thủ công

Mở hai terminal tại thư mục dự án.

Terminal backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Terminal frontend:

```powershell
cd frontend
npm.cmd run dev
```

Các địa chỉ cần dùng:

- Giao diện: `http://localhost:5173`
- Backend: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`

## Sử dụng giao diện web

### Tổng quan

Hiển thị số phiên xử lý, phiên có biển số, trạng thái camera, trạng thái API và các hoạt động gần đây.

### Nhận diện camera

1. Mở mục **Nhận diện**.
2. Chọn **Bật camera** và cấp quyền cho trình duyệt.
3. Chọn thiết bị camera nếu máy có nhiều camera.
4. Hệ thống thử chụp một frame mỗi 500 ms và gửi đến API nhận diện ảnh. Nếu lượt nhận diện trước chưa hoàn tất, lượt mới sẽ được bỏ qua để tránh gửi các yêu cầu chồng lên nhau.
5. Kết quả mới nhất và biển số phát hiện được hiển thị bên cạnh luồng camera.
6. Chọn **Dừng camera** để giải phóng thiết bị.

MediaStream được gắn lại vào thẻ video khi quay về trang Nhận diện, vì vậy camera không bị mất hình sau khi chuyển sang trang khác.

### Nhận diện ảnh hoặc video

- **Ảnh:** hỗ trợ JPG/JPEG, PNG và WEBP; API giới hạn 10 MB.
- **Video:** hỗ trợ MP4, AVI, MOV và MKV; API giới hạn 100 MB.

Sau khi xử lý ảnh, frontend hiển thị ảnh đã vẽ box. Sau khi xử lý video, frontend hiển thị số frame, danh sách biển số và liên kết tải video kết quả.

### Lịch sử

Trang Lịch sử tải tối đa 200 bản ghi gần nhất từ hai nguồn dữ liệu. Nút **Xem** mở hộp chi tiết gồm:

- Biển số đã quét.
- Thời gian quét.
- Loại nguồn.
- Tên ảnh, video hoặc camera.

Lịch sử chữ được lưu trong SQLite và tự nạp lại khi mở trang. Ảnh/video nguồn không được lưu cùng bản ghi lịch sử.

## Sử dụng dòng lệnh

Nên gọi trực tiếp Python trong `venv` để không phụ thuộc trạng thái kích hoạt PowerShell.

### Nhận diện ảnh

Hiển thị kết quả:

```powershell
.\venv\Scripts\python.exe main.py --source plate_0.jpg
```

Hiển thị và lưu ảnh đã chú thích:

```powershell
.\venv\Scripts\python.exe main.py --source plate_0.jpg --image-output ketqua.jpg
```

### Nhận diện video

```powershell
.\venv\Scripts\python.exe main.py --source video.mp4 --save output.mp4
```

Nhấn `q` để dừng trước khi video kết thúc.

### Nhận diện webcam

```powershell
.\venv\Scripts\python.exe main.py --source 0
```

Máy yếu có thể giảm số lần gọi OCR:

```powershell
.\venv\Scripts\python.exe main.py --source 0 --ocr-every 3
```

Tùy chỉnh ngưỡng, số phiếu và CSV:

```powershell
.\venv\Scripts\python.exe main.py --source 0 --conf 0.4 --min-votes 3 --cooldown 15 --csv plate_records.csv
```

### Tham số CLI

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--source` | `0` | Đường dẫn ảnh/video hoặc chỉ số camera |
| `--weights` | `best.pt` | Tệp trọng số YOLO |
| `--conf` | `0.3` | Ngưỡng tin cậy phát hiện |
| `--save` | Không lưu | Đường dẫn video đầu ra |
| `--image-output` | Không lưu | Đường dẫn ảnh đã chú thích |
| `--csv` | `plate_records.csv` | Tệp lịch sử CSV |
| `--min-votes` | `2` | Số frame đồng thuận để xác nhận biển mờ |
| `--cooldown` | `10` giây | Thời gian chờ trước khi ghi lại cùng biển |
| `--ocr-every` | `1` | Chỉ OCR mỗi N frame |

## Quy trình nhận diện

```text
Frame
  └─► YOLO phát hiện biển
        └─► Cắt vùng biển và nới biên 4%
              └─► Xác định biển một dòng hoặc hai dòng
                    └─► Ba model OCR cùng nhận dạng
                          └─► Chuẩn hóa biển số Việt Nam
                                └─► Ổn định kết quả qua nhiều frame
                                      └─► Vẽ và lưu kết quả
```

### Phát hiện

`detector.py` chạy YOLO và trả về box `(x1, y1, x2, y2)` cùng độ tin cậy. CLI cho phép đổi ngưỡng bằng `--conf`; backend ảnh/video hiện dùng ngưỡng `0.3`.

### Cắt và phân loại bố cục

`crop_plate` nới box mặc định 4% và giới hạn tọa độ trong frame. Hệ thống dùng tỷ lệ cao/rộng và hình chữ nhật xoay của vùng nền để phân biệt biển một dòng với biển hai dòng.

### OCR và chuẩn hóa

Ba model sau được nạp khi cần:

- `cct-s-v1-global-model`
- `cct-s-v2-global-model`
- `cct-xs-v2-global-model`

Kết quả được tính theo độ tin cậy ký tự và mức đồng thuận giữa các model. Chuỗi dưới ngưỡng OCR `0.6` hoặc không khớp định dạng biển Việt Nam sẽ không được chấp nhận.

Backend ảnh còn thử crop rộng hơn 15% và 30% nếu lần đọc đầu có độ tin cậy dưới `0.9`.

### Ổn định nhiều frame

`PlateStabilizer` ghép box giữa các frame bằng IoU, giữ tối đa tám phiếu OCR gần nhất và loại track sau 30 frame không xuất hiện. Biển có độ tin cậy cao được hiển thị sớm; biển mờ cần đủ số phiếu đồng thuận trước khi được xác nhận và ghi log.

## REST API

Tất cả route nghiệp vụ có tiền tố `/api`.

| Phương thức | Đường dẫn | Chức năng |
|---|---|---|
| `GET` | `/` | Thông tin dịch vụ và đường dẫn tài liệu |
| `GET` | `/api/health` | Kiểm tra trạng thái backend |
| `POST` | `/api/recognize/image` | Nhận diện ảnh và trả ảnh base64 |
| `POST` | `/api/recognize/video` | Nhận diện video và tạo video kết quả |
| `GET` | `/api/recognize/video/result/{filename}` | Tải video kết quả |
| `POST` | `/api/plates/camera` | Thêm bản ghi camera từ hệ thống tích hợp |
| `GET` | `/api/plates/camera` | Liệt kê/lọc lịch sử camera |
| `GET` | `/api/plates/camera/{plate_id}` | Lấy một bản ghi camera |
| `GET` | `/api/plates/video` | Liệt kê/lọc lịch sử ảnh và video |
| `GET` | `/api/plates/video/{plate_id}` | Lấy một bản ghi ảnh hoặc video |

Hai API danh sách hỗ trợ `limit`, `offset` và bộ lọc. Giới hạn `limit` từ 1 đến 200.

Ví dụ health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Ví dụ nhận diện ảnh:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/recognize/image" `
  -H "accept: application/json" `
  -F "file=@plate_0.jpg"
```

## Lưu trữ dữ liệu

### SQLite

Database mặc định: `backend/data/plates.db`.

Có thể thay đổi bằng biến môi trường `LPR_DATABASE_PATH`, chủ yếu dùng trong kiểm thử.

Database gồm hai bảng:

| Bảng | Nội dung |
|---|---|
| `camera_plates` | Dữ liệu được gửi qua API camera, gồm camera ID, vị trí, biển số, độ tin cậy và thời gian |
| `video_plates` | Kết quả từ ảnh hoặc video, gồm biển số, loại nguồn, tên tệp, độ tin cậy và thời gian |

SQLite chạy ở chế độ WAL và tạo chỉ mục cho biển số, nguồn và thời gian. Khi phát hiện database cũ có bảng `plates`, hệ thống tự chuyển dữ liệu sang `video_plates` rồi đổi tên bảng cũ thành `plates_legacy`.

Camera trình duyệt gửi frame qua API ảnh, do đó bản ghi được lưu trong `video_plates` với `source_type = image` và tên tệp `camera-frame.jpg`. Frontend dùng tên này để hiển thị nguồn là **Camera trực tiếp**.

### CSV của CLI

CLI ghi vào `plate_records.csv` theo cấu trúc:

```csv
timestamp,license_plate
2026-10-08T20:23:32,51A-034.42
```

`--cooldown` ngăn ghi lại cùng một biển trong khoảng thời gian quá ngắn.

### Tệp kết quả

- Ảnh CLI: đường dẫn từ `--image-output`.
- Video CLI: đường dẫn từ `--save`.
- Video API: `backend/outputs/result_*.mp4`.
- Database và output runtime đã được thêm vào `.gitignore`.

## Huấn luyện lại YOLO

`data.yaml` cấu hình một lớp `license_plate` và các tập:

```text
dataset/train/images
dataset/valid/images
dataset/test/images
```

Chạy:

```powershell
.\venv\Scripts\python.exe train.py
```

Cấu hình hiện tại trong `train.py`:

| Tham số | Giá trị |
|---|---|
| Model nền | `yolo26n.pt` |
| Epoch | `50` |
| Kích thước ảnh | `640` |
| Batch | `8` |
| Lớp | `license_plate` |

Kết quả huấn luyện được Ultralytics lưu trong `runs/`. Có thể sao chép trọng số tốt nhất thành `best.pt` hoặc truyền đường dẫn khác qua `--weights` khi chạy CLI.

## Kiểm thử và kiểm tra chất lượng

### Pipeline nhận diện

```powershell
.\venv\Scripts\python.exe -m unittest test_pipeline.py
```

Bộ test bao gồm:

- Chuẩn hóa biển một dòng/hai dòng và ký tự dễ nhầm.
- Phân loại bố cục khi biển bị nghiêng.
- Crop có padding và không vượt khỏi frame.
- Cơ chế bỏ phiếu, đổi xe và chống ghi lặp.
- CSV cooldown.
- OCR trên `plate_0.jpg` nếu ảnh mẫu tồn tại.
- Tần suất `ocr-every`.
- Giải phóng `VideoCapture` và `VideoWriter`.

### Database và API lịch sử

```powershell
.\venv\Scripts\python.exe -m unittest backend/tests/test_plate_repository.py
```

Bộ test kiểm tra schema, di trú database cũ, thêm/lọc/phân trang dữ liệu, validation API, parameter binding và việc tái tạo database sau khi xóa.

### Frontend

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

## Xử lý sự cố

### `venv` trỏ đến Python cũ

Triệu chứng thường gặp:

```text
did not find executable at ...python.exe
```

Tạo lại môi trường ảo bằng bản Python đang cài:

```powershell
Rename-Item venv venv_old
py -3.12 -m venv venv
```

Sau khi cài lại dependency và xác nhận dự án chạy ổn định, có thể xóa `venv_old`.

### PowerShell chặn `npm.ps1`

Dùng `npm.cmd`:

```powershell
npm.cmd install
npm.cmd run dev
```

### `cv2.imshow` không mở cửa sổ

Kiểm tra xem `opencv-python-headless` có thay thế `opencv-python` hay không. Cài `fast-plate-ocr` bằng `--no-deps` như phần hướng dẫn cài đặt.

### Frontend không kết nối backend

1. Mở `http://127.0.0.1:8000/api/health`.
2. Kiểm tra cửa sổ Uvicorn có lỗi hay không.
3. Kiểm tra frontend đang chạy ở cổng `5173`.
4. Kiểm tra `API_URL` trong `frontend/src/App.jsx` nếu đã đổi cổng backend.

### Camera không mở

- Cấp quyền camera cho trình duyệt.
- Đóng ứng dụng khác đang giữ camera.
- Chọn lại camera trong danh sách thiết bị.
- Chỉ dùng `localhost` hoặc HTTPS khi triển khai ngoài môi trường cục bộ, vì trình duyệt hạn chế camera trên origin không an toàn.

### Lịch sử trống khi mở lần đầu

Frontend tự thử tải lại trong 10 giây. Nếu vẫn trống, kiểm tra backend, file `backend/data/plates.db` và hai API:

```text
GET /api/plates/video
GET /api/plates/camera
```

## Giới hạn hiện tại

- Biển quá nhỏ, mờ, thiếu sáng hoặc bị cắt mất ký tự có thể không đọc được.
- Biển quân đội/công vụ nền đỏ chưa nằm trong bộ quy tắc chuẩn hóa hiện tại.
- Biển ô tô một dòng nghiêng mạnh có thể bị phân loại nhầm thành biển hai dòng.
- Camera web thử gửi ảnh định kỳ 500 ms, chưa phải pipeline stream liên tục bằng WebSocket/WebRTC; lượt chụp mới sẽ được bỏ qua nếu backend vẫn đang xử lý lượt trước.
- Backend xử lý video đồng bộ trong request; video dài có thể mất nhiều thời gian.
- `API_URL` và CORS đang cấu hình cho môi trường cục bộ.
- Hệ thống chưa có xác thực, phân quyền hoặc giới hạn tần suất cho môi trường production.
- Lịch sử chỉ lưu dữ liệu chữ và metadata, không lưu lại ảnh/video nguồn.

## Ghi chú triển khai

Cấu hình hiện tại phù hợp cho phát triển và chạy cục bộ. Trước khi đưa lên môi trường mạng, cần bổ sung ít nhất HTTPS, xác thực, phân quyền, giới hạn request, quản lý biến môi trường, sao lưu database và chính sách lưu dữ liệu biển số.
