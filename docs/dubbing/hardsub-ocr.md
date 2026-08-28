# Phụ đề cứng (hardsub) — trích xuất bằng OCR

Tính năng **"OCR phụ đề"** cho phép dùng phụ đề **đã có sẵn trong video** làm
nguồn text cho luồng dub, thay vì Whisper ASR:

- **Soft-sub** (text track trong container) — trích trực tiếp bằng ffmpeg,
  chính xác 100%.
- **Hardsub** (chữ đốt vào hình) — quét khung hình bằng
  **RapidOCR** (ONNX conversion của model PP-OCR/PaddleOCR — nhanh, cài nhẹ,
  không cần paddlepaddle runtime), gom thành cue có timestamp.

## Dùng

1. Upload video vào Dub như bình thường (hoặc ingest URL).
2. Trong thanh actions của cột trái, bấm **"OCR phụ đề"** → xác nhận.
3. Chờ quét (progress theo khung hình; chỉ crop dải dưới của video nên nhanh).
4. Segments thay bằng text trích từ phụ đề → soát/sửa trong bảng segment như
   text thường → dịch/TTS bình thường.

Cảnh báo: OCR **thay thế transcript hiện tại** — có dialog xác nhận trước.

## Cấu hình (request)

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `mode` | `auto` | `auto` = ưu tiên soft-sub, không có thì OCR; `soft` = chỉ soft-sub; `ocr` = luôn OCR |
| `fps` | `2.0` | Số khung hình lấy mẫu mỗi giây |
| `band_top` | `0.55` | Crop từ đây xuống đáy (dải phụ đề) |
| `text_score` | `0.5` | Ngưỡng lọc OCR noise |

## Engine OCR

Sidecar dùng **RapidOCR** (ONNX) — cài tự động vào
`backend/engines/hardsub_ocr/.venv` lần đầu dùng (cần `uv`). Lý do chọn
RapidOCR thay vì paddlepaddle native (đo 2026-08-28 trên Windows CPU):

| Engine | Tốc độ | Ghi chú |
|---|---|---|
| **RapidOCR (ONNX)** | **~0.60 s/khung** | cài nhẹ; CER 5.7% trên fixture |
| PaddleOCR native (mkldnn tắt) | 3.27 s/khung | bug PIR/oneDNN của paddle 3.3.1 CPU |

⚠️ Model PP-OCR mặc định của RapidOCR thiên về Trung/Anh — dấu tiếng Việt có
thể thiếu (CER ~6% trên fixture 640×360). Cải thiện dự kiến: dùng model
PP-OCRv5/v6 multilingual cho tiếng Việt khi tích hợp sâu hơn.

## Giới hạn

- Timing chính xác ±(1/fps) —fps cao hơn = chính xác hơn nhưng chậm hơn.
- OCR thay thế transcript hiện tại — luôn có dialog xác nhận; sau khi thay,
  mọi thao tác edit/restore cũ không còn ý nghĩa với text cũ.
- Video không có phụ đề / phụ đề quá mờ → cues rỗng hoặc nhiều noise —
  kiểm tra trong bảng segment trước khi dịch.
