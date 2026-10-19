# Phase 10 — Bàn giao và kịch bản bảo vệ

Hoàn thiện ngày 19/10/2026. Năm nội dung trọng tâm đã có source chạy thật và bằng chứng kiểm chứng. Phạm vi đã kiểm chứng được ghi ở [Phase 9](phase-9.md); không coi mọi đề xuất trong bản thiết kế Phase 1 là đã hoàn thành.

## Mở hệ thống

Giao diện: **http://localhost:8080**. Đăng nhập bằng `ADMIN_USERNAME` và `ADMIN_PASSWORD` trong `.env` cục bộ; không gửi hoặc commit file này. Swagger: http://localhost:8080/docs. Spark Master UI: http://localhost:8081. MLflow khi bật profile: http://localhost:5000.

Tại thời điểm bàn giao ngày 19/10/2026, core services, hai Spark workers và MLflow đã chạy healthy; streaming worker và Kafka đang dừng. Nếu Docker/máy vừa khởi động lại:

```powershell
docker compose -f docker-compose.yml -f docker-compose.mlops.yml --profile mlops up -d --scale spark-worker=2
```

Máy mới cần Docker Desktop Linux containers/WSL2 và Internet cho lần build đầu. Chạy từ thư mục dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Script tạo secrets ngẫu nhiên khi chưa có `.env`, build/start core stack và hai Spark workers. Không thay secrets của `.env` hiện có. Đây là hướng dẫn đã dùng để build trên máy phát triển, chưa phải chứng nhận cài thành công trên máy khác. Nếu import dữ liệu mới trên máy mới, cần upload/ETL/train trước khi dùng dự đoán.

## Kịch bản bảo vệ khoảng 12–15 phút

| Thời lượng | Thao tác | Điều cần chứng minh |
| --- | --- | --- |
| 2 phút | Mở Compose status, Swagger, Spark Master và sơ đồ `docs/architecture.md` | HTTP API, Mongo và compute workers chạy trong containers; Spark thực sự có hai executors. |
| 3 phút | Upload DEMO CSV mới, đợi RAW_READY, submit ETL; mở Job Monitor và Quality | Raw → Clean → Analytics; reconcile counts, lỗi và duplicate có bản ghi/CSV; dataset/attempt versions rõ ràng. |
| 2 phút | Dashboard đổi province/date/dataset; mở job detail và tải báo cáo | UI dùng API/published data thật, có sample size, thiếu nhãn lương và cảnh báo DEMO. |
| 3 phút | Model registry, validation/test metrics, diagnostics và prediction/history | Baseline + nhiều mô hình; chọn bằng validation; holdout không dùng chọn winner; prediction truy được model/data version. |
| 2 phút | Mở `benchmark_runs`, physical plans và `mongo-evidence.json` | So sánh ba quy mô, cùng output/checksum; index/aggregation có evidence. Nêu overhead dữ liệu nhỏ. |
| 1–3 phút | Mở recovery, persistence, backup/restore và MLflow evidence | Worker chết có retry/fencing; volumes giữ dữ liệu; restore isolated có prediction parity. |

Nên dùng dataset `cbc3ee9d-577b-4265-813f-d07cc78957de` làm ví dụ ổn định: 1.000 raw, 954 clean, 17 duplicate, 29 invalid, 867 nhãn lương. Active model Gradient Boosting `dfce50bf-e6c2-44b6-8cd4-9a76216073ac` là kết quả chọn bằng validation. Upload version mới có thể đổi active pointer sau quality gate; chọn lại version bằng UI khi đối chiếu evidence cũ.

Không cần chạy kill/restart/restore trực tiếp trong lúc trình bày. Các scripts đó thực sự làm gián đoạn compute và chỉ nên chạy lại khi queue trống, không có người khác sử dụng hệ thống. Giữ logs và giải thích attempt fencing/checkpoint thay vì chỉ trình chiếu ảnh.

## Source và tái lập

- [README](../../README.md): lệnh chạy, profiles, tests, vận hành và mô tả luồng.
- [OpenAPI xuất từ backend](../openapi.json): snapshot contract thực; Swagger hiện tại phản ánh mã đang chạy.
- [Benchmark](benchmark.md): timer boundary, môi trường, repetitions và giới hạn.
- `scripts/e2e.py`, `check_mlflow.py`, `failure_recovery.py`, `verify_runtime.py`: kiểm chứng từng luồng.
- `scripts/backup.ps1`, `restore.ps1`: snapshot và restore vào DB/files riêng; từ chối ghi đè DB đã có.
- `backend/requirements.lock`, `frontend/package-lock.json`: dependency locks. `artifacts/benchmark-source/` giữ snapshot source của lần benchmark.

Evidence thực nằm trong `artifacts/` và Docker volumes trên máy này; thư mục artifacts bị gitignore. Các báo cáo Markdown lưu các kết quả chính để người đọc vẫn hiểu nếu chưa có artifacts. Khi đóng gói nộp bài, sao lưu chọn lọc logs/JSON/CSV/ảnh cần thiết và backup theo quy định; kiểm tra dữ liệu nhạy cảm, không kèm `.env`, bearer tokens hoặc `node_modules`. Không xóa Docker volumes nếu muốn giữ dữ liệu hiện tại.

## Phần mở rộng chưa hoàn thành hoặc chưa được kiểm chứng

| Hạng mục | Trạng thái và hướng tiếp theo |
| --- | --- |
| Dữ liệu tuyển dụng thực, nhiều ngành | Chưa có nguồn được cấp quyền; tích hợp ingestion connector và provenance trước khi đánh giá giá trị thị trường. |
| ML nâng cao | Chưa có temporal experiments/interval hiệu chuẩn; local training bị chặn tối đa 10k labels. Spark numeric là baseline scale riêng, chưa thay thế toàn bộ feature pipeline local. |
| Streaming nâng cao | Checkpoint/replay đã kiểm chứng; chưa có DLQ topic routing và chưa bao phủ tất cả broker/network failure scenarios. |
| Quy mô vận hành | Chưa đo 1M rows, peak RAM/concurrent users hoặc nhiều máy vật lý; cần thiết kế lại tài nguyên và đo riêng trước khi kết luận khả năng phục vụ. |
| Quản trị vòng đời | Version pointers, retry, active/rollback đã có; xóa/retention tự động và giao diện quản trị nâng cao chưa triển khai đầy đủ. |
| Giao diện/phân tích nâng cao | Chín trang và các luồng chính đã có; các biến thể biểu đồ, export/analysis mở rộng trong thiết kế chưa bao phủ hết. Tối ưu chunk ECharts còn mở. |
| Triển khai production | Hiện dùng HTTP loopback local. TLS/reverse proxy công khai, HA, external secrets, monitoring/alerting và CI triển khai cần công việc riêng. |

Đồ án hiện đủ luồng thực để trình bày năm trọng tâm đã thống nhất. Khi bảo vệ, luôn gắn kết luận với dữ liệu DEMO, môi trường một máy và phạm vi đo đã ghi trong báo cáo.
