# Phase 2 — Infrastructure

Ngày kiểm tra: 18/10/2026 (Asia/Saigon).

Đã tạo Docker Compose, Dockerfiles non-root, Mongo init/indexes, API health/auth, worker heartbeat, job claim/lease/fencing, frontend login và system status, scripts setup/check, manifest và dependency locks.

Kiến trúc thực tế: Python 3.11.11 + Java 17 + PySpark 3.5.7, MongoDB 8.0.9; driver client mode trong etl-worker, hai standalone workers. Node 24.1.0 build, Nginx unprivileged phục vụ web/proxy cùng origin.

Kết quả thực tế:

- `npm.cmd --prefix frontend run build`: PASS.
- `docker compose build backend frontend`: PASS.
- `docker compose up -d --scale spark-worker=2`: PASS sau khi sửa lỗi runtime.
- `docker compose run --rm test-backend`: **7 passed**, 3 warnings (Starlette deprecation, pytest cache permissions).
- `docker compose exec etl-worker python scripts/smoke_spark.py`: **PASS**, application `app-20261018135354-0001`, 10.000 rows, **2 executors**.
- Init chạy lại thành công; test kiểm tra refresh rotation/logout, Mongo unique index, lease expiry và stale fencing.

Lỗi phát hiện và sửa: migration `collMod` cần admin nên dùng root connection trong init và chỉ đổi validator khi khác; Spark worker mặc định ghi vào site-packages bị từ chối nên đổi work-dir `/tmp/spark-work`; Nginx dùng resolver Docker DNS để backend đổi IP sau recreate vẫn truy cập được.

Logs đầy đủ ở `artifacts/` (ignored): build.log, build-current.log, tests-phase2.log, spark-smoke.log. Không chứa mật khẩu quản trị. `.env` sinh secrets ngẫu nhiên và không commit.

Giới hạn: chưa có nghiệp vụ ingestion/ETL/ML và streaming/MLOps profiles ở thời điểm phase này. Runtime smoke chỉ chứng minh hạ tầng Spark, chưa phải benchmark ETL. Các warnings được ghi nhận, không coi là failed tests. Đủ điều kiện bắt đầu Phase 3.
