# Phụ đề cứng (hardsub) — trích xuất bằng OCR

Tính năng **OCR phụ đề** lấy chữ đã có trong video làm transcript cho luồng Dub:

- **Soft-sub:** trích text track trực tiếp bằng ffmpeg.
- **Hardsub:** quét vùng hình ảnh bằng RapidOCR hoặc PaddleOCR, tạo cue có timestamp.

## Quy trình trong Dub

1. Upload hoặc nhập video, rồi bấm **OCR phụ đề**.
2. Chọn model. Tên hiển thị gồm provider, phiên bản/model thực tế và thiết bị.
3. Tua tới khung có phụ đề; vẽ, kéo hoặc đổi kích thước vùng OCR. Có thể nhập tọa độ hoặc chọn dải dưới mặc định.
4. Bấm **Bắt đầu quét**. Giao diện hiển thị phần trăm, thời gian đã chạy, ETA, timestamp video, chữ mới nhất, số khung đã đọc, số lần gọi OCR và số khung bỏ qua.
5. Khi hoàn tất, ứng dụng tự mở **Prepare OCR result**. Sửa/xóa cue nếu cần rồi bấm tiếp tục để đưa kết quả vào trình sửa Dub hiện tại.
6. Tiếp tục dịch, TTS và xuất video như quy trình dubbing thông thường. File `hardsub.srt` cũng được lưu trong thư mục job và có thể tải từ giao diện.

OCR chỉ thay transcript sau khi người dùng xác nhận kết quả ở Prepare. Hủy hoặc lỗi không ghi đè transcript/SRT đang có.

## Model

RapidOCR và PaddleOCR dùng chung một provider contract. Scanner không phụ thuộc hình dạng kết quả riêng của từng phiên bản:

- RapidOCR dùng môi trường sidecar hiện có.
- PaddleOCR là lựa chọn tùy chọn; môi trường `.paddle-venv` chỉ được cài khi người dùng chọn model và bắt đầu.
- PaddleOCR 2.x dùng adapter được chuyển từ pyVideoTrans; PaddleOCR 3.x giữ adapter `predict` hiện có.
- Việc liệt kê model chỉ đọc trạng thái cài đặt cục bộ, không tải model hoặc gọi mạng.

Model PP-OCR mặc định thiên về Trung/Anh; video tiếng Việt có thể cần model đa ngôn ngữ phù hợp để giữ dấu tốt hơn.

## Scanner

Luồng mặc định là scanner được chuyển từ pyVideoTrans revision `c5788f7f342d8ee4f480cf034b85855d09b253ba`:

- ffmpeg giải mã tuần tự trực tiếp vùng ROI dưới dạng raw BGR, không tạo chuỗi PNG;
- thumbnail grayscale phát hiện thay đổi trước inference;
- frame đầu, thay đổi đáng kể, confidence thấp và mốc xác nhận định kỳ mới gọi provider;
- `SegmentBuilder` ổn định OCR jitter, giữ chữ hiển thị tốt nhất và tách lại cùng một câu sau khoảng trống thật;
- checkpoint gắn với video, ROI, model và tham số scanner; resume khôi phục cả cue đã xong lẫn trạng thái đang hoạt động;
- tinh chỉnh timing là tùy chọn (`refine: false` mặc định) và dùng frame thật trong cửa sổ cục bộ quanh chuyển cảnh.

Fallback cũ chỉ chạy khi đặt `OMNIVOICE_OCR_LEGACY=1`, phục vụ hồi phục trong một chu kỳ phát hành.

## API

`POST /dub/hardsub-extract/{job_id}` nhận:

| Tham số | Mặc định | Ý nghĩa |
|---|---:|---|
| `mode` | `auto` | `auto`: ưu tiên soft-sub; `soft`: chỉ soft-sub; `ocr`: luôn OCR |
| `model` | `rapidocr` | `rapidocr` hoặc `paddleocr` |
| `fps` | `2.0` | Tần suất lấy mẫu coarse |
| `crop` | dải dưới | `{left, top, right, bottom}` chuẩn hóa 0..1 |
| `band_top` | `0.55` | Tương thích ngược khi không gửi `crop` |
| `text_score` | `0.5` | Ngưỡng confidence lọc noise |
| `refine` | `false` | Tinh chỉnh biên cue bằng frame cục bộ |
| `refine_fps` | `10` | Tần suất frame cho tinh chỉnh, 4..30 |

Nhánh OCR trả `task_id`; frontend theo dõi SSE. Progress giữ các trường cũ và thêm `decoded_frames`, `ocr_calls`, `skipped_frames`, `cache_hits`, `current_text`, `video_time`, `elapsed_seconds`, `eta_seconds`. SRT tải tại `GET /dub/hardsub-srt/{job_id}`.

## Kết quả đo trên video mẫu

Video `BV1gAgS6DEAx-40216888013.mp4`, dài 675,1 giây, ROI 1/5 phía dưới, 2 FPS, PaddleOCR 2.10, model đã warm:

| Luồng | Thời gian | Cue | Khớp chuỗi với pyVideoTrans |
|---|---:|---:|---:|
| pyVideoTrans gốc | 592,66 s | 272 | mốc tham chiếu |
| VoiceStudio scanner mới | 230,70 s | 272 | 270/272 (99,26%) |
| VoiceStudio legacy aHash | 201,34 s | 271 | 259/272 (95,40%) |

Hai khác biệt của scanner mới được kiểm tra trên frame thật tại 314,5 s và 419 s; chữ của VoiceStudio đúng hơn kết quả tham chiếu ở cả hai. Scanner mới nhanh hơn pyVideoTrans gốc 2,57 lần. Legacy nhanh hơn 29,36 giây nhưng bỏ hoặc giữ sai nhiều câu, nên không dùng làm mặc định.

Scanner mới gọi OCR 918/1350 frame (giảm 32,0%). Mục tiêu thử nghiệm giảm 70% không phù hợp với chu kỳ xác nhận mỗi 4 frame của pyVideoTrans trên video có phụ đề thay đổi dày; tăng khoảng xác nhận có thể nhanh hơn nhưng làm thay đổi mặc định độ chính xác đã được chọn.

## Giới hạn

- Timing coarse có độ phân giải `1/fps`; bật refine khi cần biên sát hơn.
- Phụ đề quá mờ, chuyển động mạnh trong ROI hoặc chọn vùng quá rộng làm tăng inference/noise.
- Luôn kiểm tra cue ở Prepare trước khi dịch.
