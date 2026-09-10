# Demo RAG pháp luật: chống dữ liệu trùng và truy xuất sai phiên bản

Repository nhỏ này tái tạo phần thực nghiệm của bài viết về Incremental RAG cho dữ liệu pháp luật. Demo tập trung vào vòng đời dữ liệu: nhận văn bản, tạo phiên bản, phát event bằng Transactional Outbox, lập chỉ mục, kích hoạt phiên bản và truy vấn theo thời điểm.

Demo dùng PostgreSQL, RabbitMQ, OpenSearch và embedding `BAAI/bge-m3` qua OpenRouter. Nó không gọi mô hình sinh câu trả lời; output là các chunk được truy xuất kèm nguồn và metadata hiệu lực.

> **Disclaimer:** Demo này chỉ phục vụ mục đích nghiên cứu và minh họa kỹ thuật. Nội dung trong fixture là bản diễn giải rút gọn, có thể không phản ánh đầy đủ ngữ cảnh, lịch sử sửa đổi, quy định chuyển tiếp hoặc trạng thái hiệu lực của văn bản pháp luật. Kết quả truy xuất không phải tư vấn pháp lý và không được dùng làm căn cứ duy nhất cho quyết định pháp lý, hành chính hoặc kinh doanh. Khi sử dụng thực tế, người đọc phải đối chiếu văn bản ký số từ nguồn chính thức và tham vấn người có chuyên môn phù hợp. Các số liệu benchmark chỉ áp dụng cho đúng mã nguồn, cấu hình, dữ liệu và lần chạy được ghi trong artifacts; chúng không chứng minh hiệu năng hay độ chính xác của một hệ thống production. Việc gọi OpenRouter chịu chính sách xử lý dữ liệu, giá và điều khoản dịch vụ của nhà cung cấp; không gửi tài liệu mật hoặc dữ liệu cá nhân nếu chưa có cơ sở và biện pháp bảo vệ phù hợp.

## Demo kiểm chứng điều gì?

Một lần chạy `run-all` kiểm tra các hành vi sau:

1. PostgreSQL ghi `document_version` và `outbox_event` trong cùng transaction.
2. Outbox publisher chỉ đánh dấu event đã gửi sau khi RabbitMQ xác nhận publish.
3. Cùng một event được publish hai lần để mô phỏng cơ chế at-least-once delivery.
4. Consumer dùng `event_id` và `operation_key` để bỏ qua lần giao lặp.
5. Nạp lại cùng nội dung trả về version cũ, không tạo thêm version, chunk hoặc outbox event.
6. Chunk được ghi vào OpenSearch bằng ID tất định trước khi version được kích hoạt.
7. PostgreSQL dùng Compare-And-Set khi chuyển con trỏ `active_version_id`.
8. Truy vấn trước ngày hiệu lực không lấy nội dung của Nghị định 309/2026/NĐ-CP.
9. Truy vấn sau ngày hiệu lực lấy được quy định về ki-ốt thông minh và xác thực VNeID.
10. `stale_matching_leakage` được tính từ chính các hit mà OpenSearch trả về.

## Kiến trúc chạy thử

```text
Legal document fixture
        |
        v
PostgreSQL transaction
document_version + chunks + outbox_event
        |
        v
Outbox publisher -- Publisher Confirm --> RabbitMQ
                                            |
                                            v
                                  Idempotent consumer
                                            |
                                            v
                                  OpenSearch candidate chunks
                                            |
                                            v
                                validate + PostgreSQL CAS
                                            |
                                            v
                              temporal-filtered retrieval
```

PostgreSQL là nguồn trạng thái chính. OpenSearch có thể chứa candidate chunk nhưng retriever chỉ tìm trong các version đang active và có hiệu lực tại thời điểm truy vấn.

## Dữ liệu pháp luật

Fixture gồm metadata đã kiểm tra và các đoạn diễn giải rút gọn từ:

- Nghị định 118/2025/NĐ-CP, ban hành ngày 09/06/2025 và có hiệu lực ngày 01/07/2025.
- Nghị định 309/2026/NĐ-CP, ban hành và có hiệu lực ngày 05/08/2026, sửa đổi và bổ sung Nghị định 118/2025/NĐ-CP.
- Điều 1 khoản 2 Nghị định 309 bổ sung khoản 9 Điều 3 về ki-ốt thông minh.
- Điều 8 khoản 2 Nghị định 309 bổ sung khoản 2a Điều 17 về xác thực qua VNeID hoặc thiết bị đọc thẻ Căn cước.

Nguồn và phạm vi kiểm chứng được ghi trong [`docs/legal-source-audit.md`](docs/legal-source-audit.md). Fixture phục vụ kiểm thử kỹ thuật, không thay thế văn bản chính thức hoặc tư vấn pháp luật.

## Yêu cầu

- Docker Engine có hỗ trợ Docker Compose.
- Khoảng 2 GB RAM trống cho OpenSearch và hai dịch vụ còn lại.
- OpenRouter API key có quyền gọi embeddings.
- Các cổng cục bộ chưa bị chiếm: `55432`, `5673`, `15673` và `9201`.

## Cấu hình

Tạo file `.env` từ mẫu:

```bash
cp .env.example .env
```

Điền khóa vào `.env`:

```dotenv
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_API_KEY=<your-openrouter-key>
```

`.env` đã được loại khỏi Git và Docker build context. Không đưa khóa thật vào README, log hoặc artifact benchmark.

## Chạy demo từ đầu đến cuối

Tại thư mục này, chạy:

```bash
docker compose build demo
docker compose up -d postgres rabbitmq opensearch
docker compose run --rm demo python -m app.cli run-all
```

Hoặc dùng Makefile:

```bash
make up
make run
```

Một lần chạy sẽ reset schema và index của riêng project Compose này, nạp hai fixture, cố ý publish mỗi event hai lần, chạy hai truy vấn theo thời điểm và xuất báo cáo.

## Chạy test

```bash
docker compose run --rm demo pytest -q
```

Bộ test gồm hai nhóm:

- Unit test kiểm tra Unicode NFC, content hash và validation vector 1024 chiều của OpenRouter adapter mà không gọi mạng.
- Integration test chạy pipeline thật một lần với PostgreSQL, RabbitMQ, OpenSearch và OpenRouter, sau đó kiểm tra riêng từng cam kết idempotency, redelivery, temporal retrieval và leakage.

Kết quả gần nhất được lưu tại [`artifacts/test-output.txt`](artifacts/test-output.txt).

## Artifact được tạo

| File | Nội dung |
|---|---|
| `artifacts/benchmark.json` | Output đầy đủ ở dạng máy đọc được |
| `artifacts/benchmark.md` | Tóm tắt metric và assertion |
| `artifacts/terminal-output.txt` | Output nguyên trạng của lệnh `run-all` |
| `artifacts/test-output.txt` | Kết quả pytest |

Không nhập số liệu thủ công vào bài viết. Các con số trong bài cần được lấy từ `benchmark.json` của cùng lần chạy.

## Định nghĩa metric

`duplicate_deliveries` là số message hợp lệ nhưng đã có `event_id` trong bảng `processed_event`, nên consumer xác nhận mà không lập chỉ mục lại.

`stale_matching_leakage` được tính như sau:

```text
số chunk không có hiệu lực tại thời điểm truy vấn
-------------------------------------------------
       tổng số chunk được trả về trong top-k
```

Nếu truy vấn không trả về chunk nào, metric có giá trị `null`, không được tự động coi là `0%`.

`elapsed_ms` là thời gian của fixture nhỏ trên đúng lần chạy đó. Nó không đại diện cho benchmark 1.200 văn bản, OCR hoặc tải production.

## Cấu trúc chính

```text
app/
├── broker.py              # outbox publisher và idempotent consumer
├── config.py              # cấu hình từ biến môi trường
├── demo.py                # orchestration và báo cáo benchmark
├── embedding.py           # OpenRouter BGE-M3 adapter
├── fixtures.py            # đọc dữ liệu kiểm thử
├── interfaces.py          # protocol cho các ranh giới hệ thống
├── normalization.py       # Unicode NFC và SHA-256
├── opensearch_store.py    # staging và temporal retrieval
└── postgres.py            # manifest, version và outbox transaction
data/verified/             # fixture pháp luật rút gọn
docs/                      # kiểm chứng nguồn
sql/schema.sql             # schema PostgreSQL
tests/                     # unit và integration tests
artifacts/                 # output sinh tự động
```

## Dừng và dọn môi trường

Dừng container nhưng giữ dữ liệu:

```bash
docker compose down
```

Xóa cả volume của riêng demo:

```bash
docker compose down -v --remove-orphans
```

## Giới hạn hiện tại

- Fixture chỉ có 2 văn bản và 4 chunk.
- Dữ liệu là bản diễn giải rút gọn, chưa chạy parser DOCX hoặc OCR PDF.
- Demo chưa có MinIO, Redis, FastAPI, ACL hoặc hybrid keyword-vector search.
- Chưa đo throughput, tải đồng thời hoặc chất lượng retrieval trên tập câu hỏi lớn.
- `0.0` stale leakage chỉ có ý nghĩa trong fixture và top-k của lần chạy được lưu trong artifact.

Những thành phần chưa chạy trong demo cần được mô tả là hướng mở rộng trong bài, không được trình bày như kết quả thực nghiệm.

## Xử lý lỗi thường gặp

Kiểm tra trạng thái dịch vụ:

```bash
docker compose ps
docker compose logs opensearch
docker compose logs rabbitmq
docker compose logs postgres
```

Nếu cổng bị chiếm, đổi port phía host trong `docker-compose.yml`. Nếu OpenRouter trả về `401`, kiểm tra lại `EMBEDDING_API_KEY`; nếu trả về `402`, kiểm tra số dư tài khoản. Không in giá trị khóa ra terminal khi chẩn đoán.

