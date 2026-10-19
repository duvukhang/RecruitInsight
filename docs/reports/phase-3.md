# Phase 3 — Ingestion & Storage

18/10/2026: đã triển khai upload có giới hạn kích thước, file extension allowlist, durable file, SHA-256 và idempotency key; worker nhập CSV/JSON/JSONL vào Mongo raw bằng bulk upsert, giữ cả dòng JSONL hỏng. Dataset và ingestion metadata độc lập với HTTP request. Raw JSONL chuẩn hóa phục vụ Spark được lưu volume shared, MongoDB vẫn là kho nghiệp vụ.

`docker compose build backend` PASS; `docker compose run --rm test-backend`: **10 passed**, 3 warnings đã ghi ở Phase 2. Tests chạy Mongo riêng `recruitment_test`, kiểm tra ba định dạng, giữ malformed row, cùng key trả cùng job, key đổi nội dung trả conflict, chạy lại ingestion không tăng raw count. Source: application/datasets.py, api/data.py, bigdata/ingestion.py, workers/runner.py, tests/test_ingestion.py.

Chưa có dữ liệu tuyển dụng thực được cung cấp. Test input ghi TEST/DEMO. Spark ETL và frontend upload chưa thuộc kết quả kiểm chứng phase này; tiếp tục Phase 4 và nối UI sau backend/analytics/ML.
