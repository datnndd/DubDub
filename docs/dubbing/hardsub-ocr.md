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

## V2 — chọn vùng quét + timing chính xác + file SRT

Kể từ bản hardsub v2:

1. Bấm "OCR phụ đề" → mở **dialog chọn vùng**: preview video (tua được),
   kéo hình chữ nhật phủ vùng phụ đề, hoặc bấm "Dải dưới mặc định".
2. "Bắt đầu quét" chạy 2 lớp:
   - **Pass 1 (OCR, 2 fps)**: nhận diện text từng khung;
   - **Pass 2 (timing refine, 10 fps, không OCR)**: aHash từng khung dải phụ
     đề, mở rộng/thu biên mỗi cue tới khung thực sự hiển thị phụ đề —
     độ chính xác ±0.1s thay vì ±0.5s của v1. Fail-soft: refinement lỗi →
     giữ biên coarse.
3. Khi user không vẽ vùng: hệ thống **tự đề xuất dải phụ đề** bằng mật độ
   cạnh dọc (edge-density) trên nửa dưới khung (sample ~90 khung trải đều,
   tối đa 10 phút đầu); không dò được → dải mặc định.
4. Kết quả: transcript thay bằng text OCR **+ file `hardsub.srt`** lưu trong
   job dir — tải tại `GET /dub/hardsub-srt/{job_id}` hoặc nút "Tải .srt"
   trong dialog.

Tham số request mở rộng: `crop {left, top, right, bottom}` (0..1, tuỳ chọn),
`refine_fps` (mặc định 10, 4–30). `band_top` vẫn tương thích ngược.

## Giới hạn

- Timing chính xác ±(1/fps) —fps cao hơn = chính xác hơn nhưng chậm hơn.
- OCR thay thế transcript hiện tại — luôn có dialog xác nhận; sau khi thay,
  mọi thao tác edit/restore cũ không còn ý nghĩa với text cũ.
- Video không có phụ đề / phụ đề quá mờ → cues rỗng hoặc nhiều noise —
  kiểm tra trong bảng segment trước khi dịch.
