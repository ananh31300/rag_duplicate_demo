# Kế hoạch triển khai demo RAG pháp luật chống dữ liệu trùng

## 1. Mục tiêu và tiêu chí hoàn thành

Demo phải chạy được từ đầu đến cuối trên máy mới theo README và tạo ra bằng chứng có thể kiểm tra cho các nhận định trong bài viết.

Các kịch bản bắt buộc:

1. Nạp văn bản lần đầu và truy vấn được đoạn nguồn.
2. Nạp lại cùng văn bản nhưng không tạo thêm document hoặc chunk.
3. Gửi lại cùng event nhưng trạng thái hệ thống không đổi.
4. Nạp văn bản sửa đổi và chỉ cập nhật các chunk liên quan.
5. Truy vấn theo thời điểm chỉ trả về nội dung có hiệu lực theo bộ dữ liệu thử nghiệm.
6. Mô phỏng lỗi trước khi kích hoạt phiên bản mới; phiên bản cũ vẫn phục vụ được.
7. Xuất báo cáo benchmark và lưu output thô để đối chiếu.

## 2. Phạm vi kỹ thuật

- Python 3.11.
- PostgreSQL làm manifest và quản lý phiên bản.
- OpenSearch lưu và truy xuất chunk.
- RabbitMQ dùng cho kịch bản event bị giao lại.
- Docker Compose khởi động hạ tầng cục bộ.
- Dữ liệu nhỏ, cố định, đủ để chạy nhanh trên máy cá nhân.
- Phần sinh câu trả lời là tùy chọn; phép đo chính tập trung vào ingest, versioning, deduplication và retrieval để kết quả có tính xác định.

## 3. Cấu trúc thư mục dự kiến

```text
rag_legal_duplicate_demo/
├── README.md
├── PLAN.md
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Makefile
├── data/
│   ├── raw/
│   ├── verified/
│   └── queries.json
├── docs/
│   ├── legal-source-audit.md
│   └── metric-definitions.md
├── sql/
│   └── schema.sql
├── src/
│   ├── config.py
│   ├── normalize.py
│   ├── chunking.py
│   ├── manifest.py
│   ├── opensearch_store.py
│   ├── events.py
│   ├── ingest.py
│   ├── retrieve.py
│   └── benchmark.py
├── scripts/
│   ├── seed_demo.py
│   ├── run_scenarios.py
│   └── export_evidence.py
├── tests/
│   ├── test_normalization.py
│   ├── test_idempotency.py
│   ├── test_version_activation.py
│   └── test_temporal_retrieval.py
└── artifacts/
    ├── benchmark.json
    ├── benchmark.md
    └── terminal-output.txt
```

## 4. Giai đoạn A — kiểm chứng nguồn pháp luật

1. Tìm bản chính thức của hai nghị định trên nguồn của cơ quan nhà nước.
2. Ghi lại URL, số hiệu, ngày ban hành, ngày hiệu lực, cơ quan ban hành và trạng thái văn bản.
3. Đối chiếu chính xác điều, khoản được sửa đổi hoặc bổ sung.
4. Phân biệt nội dung của văn bản sửa đổi với vị trí nội dung sau khi được đưa vào văn bản gốc.
5. Lưu phần trích dùng cho demo vào `data/verified/` cùng metadata nguồn.
6. Ghi kết quả kiểm chứng vào `docs/legal-source-audit.md`.
7. Nếu dẫn chiếu hiện tại không đúng, sửa dữ liệu và bài viết trước khi viết benchmark.

Điều kiện hoàn thành: mỗi dữ kiện pháp luật dùng trong demo đều truy ngược được đến URL chính thức và vị trí điều, khoản cụ thể.

## 5. Giai đoạn B — dựng hạ tầng có thể tái tạo

1. Viết `docker-compose.yml` cho PostgreSQL, OpenSearch và RabbitMQ.
2. Cố định phiên bản image và thư viện Python.
3. Tạo `.env.example`, health check và lệnh khởi tạo schema/index.
4. Viết README cho các lệnh cài đặt, khởi động, reset dữ liệu demo và dừng dịch vụ.

Điều kiện hoàn thành: từ thư mục sạch, người đọc có thể khởi động toàn bộ hạ tầng và chạy health check bằng các lệnh đã ghi.

## 6. Giai đoạn C — triển khai pipeline tối thiểu

1. Chuẩn hóa Unicode NFC và khoảng trắng trước khi tính SHA-256.
2. Tạo định danh ổn định cho văn bản, phiên bản và semantic chunk.
3. Lưu manifest với unique constraint cho source event, content hash và version.
4. Ghi `document_version` và `outbox_event` trong cùng PostgreSQL transaction.
5. Outbox publisher dùng Publisher Confirm trước khi đánh dấu event đã gửi.
6. Consumer acknowledgement sau khi xử lý và chống redelivery bằng `event_id` cùng `operation_key`.
7. Chunk dữ liệu theo điều/khoản thay vì theo vị trí ký tự tùy ý.
8. Upsert chunk bằng ID xác định, kèm trạng thái phiên bản và khoảng hiệu lực.
9. Dùng staging và bước activation tách biệt; chỉ phiên bản active được truy vấn.
10. Thêm reconciliation giữa PostgreSQL và OpenSearch.

Điều kiện hoàn thành: sáu kịch bản bắt buộc chạy thành công và có assertion tự động.

## 7. Giai đoạn D — benchmark và bằng chứng

Định nghĩa trước khi chạy:

- `duplicate_document_count`: số document dư sau khi chạy lại cùng input.
- `duplicate_chunk_count`: số semantic chunk active bị trùng.
- `reembedded_chunk_count`: số chunk phải tạo lại embedding sau mỗi lần ingest.
- `stale_matching_leakage`: số chunk không hợp lệ tại thời điểm truy vấn chia cho tổng số chunk trả về; trường hợp không có kết quả được báo riêng.
- Thời gian ingest và retrieval chỉ dùng như số đo tham khảo của môi trường chạy.

Mỗi lần benchmark phải lưu:

- Cấu hình máy và phiên bản phần mềm.
- Git commit hoặc hash của mã demo.
- Dữ liệu đầu vào và tập truy vấn.
- Câu lệnh đã chạy.
- Output terminal thô.
- Báo cáo JSON và bảng Markdown được tạo từ cùng output.

Điều kiện hoàn thành: không nhập số liệu bằng tay vào bài; mọi con số đều lấy từ artifact do script tạo.

## 8. Giai đoạn E — cập nhật bài viết

1. Thay đoạn mô tả môi trường bằng cấu hình thực sự đã chạy.
2. Chèn đường dẫn hoặc hướng dẫn đến thư mục demo.
3. Thêm lệnh chạy tối thiểu và một output đại diện.
4. Ghi rõ dữ liệu thật, dữ liệu rút gọn và dữ liệu mô phỏng nếu có.
5. Thay câu “Kết quả chứng minh” bằng kết luận giới hạn trong tập kiểm thử.
6. Chỉ giữ `Stale matching leakage: 0%` nếu artifact thực tế cho kết quả đó.
7. Bổ sung link tài liệu chính thức cho PostgreSQL, RabbitMQ, OpenSearch, Unicode và hai nghị định.

## 9. Giai đoạn F — kiểm tra và đóng gói

1. Chạy unit test và toàn bộ kịch bản tích hợp từ trạng thái sạch.
2. Đối chiếu số liệu trong bài với `artifacts/benchmark.json`.
3. Build PDF hai lượt và kiểm tra link, bảng, caption, mục lục và font nhúng.
4. Lưu log build và checklist đối chiếu từng feedback.

## 10. Thứ tự triển khai

1. Kiểm chứng pháp luật và chốt dữ liệu mẫu.
2. Dựng Docker Compose và schema.
3. Viết ingest, deduplication và version activation.
4. Viết retrieval theo thời điểm.
5. Viết test tích hợp cho các kịch bản.
6. Chạy benchmark và xuất artifact.
7. Cập nhật nội dung bài.
8. Chuẩn hóa định dạng LaTeX và build PDF cuối.

## 11. Rủi ro cần kiểm soát

- Nguồn chính thức thay đổi URL: lưu metadata và ngày truy cập, không sao chép toàn bộ văn bản nếu không cần.
- OpenSearch nặng trên máy cá nhân: giữ index và dữ liệu nhỏ, có health check và giới hạn bộ nhớ.
- Embedding phụ thuộc dịch vụ ngoài: chọn mô hình local có phiên bản cố định hoặc tách adapter; benchmark phải ghi rõ adapter đã dùng.
- Khái niệm “hết hiệu lực” phức tạp hơn một cờ boolean: demo giới hạn ở metadata và mốc thời gian đã kiểm chứng, không suy rộng thành tư vấn pháp lý.
