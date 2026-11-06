# MongoDB: mô hình lưu trữ hiện tại

Database nghiệp vụ `recruitment_bigdata`; tests tích hợp chỉ dùng database kết thúc bằng `_test`. Migration/validators/indexes thực tế ở `backend/src/recruitment/infrastructure/init_db.py`. Không đổi schema bắt buộc hoặc index trong lần nâng cấp nghiên cứu. Trường metadata mới là bổ sung tùy chọn; versions đã công bố và dữ liệu người dùng được giữ nguyên.

## Collections và quan hệ

| Collection | Vai trò / khóa truy vết | Index hiện có |
| --- | --- | --- |
| raw_jobs | Toàn bộ raw_payload, record_number, source, ingested_at; `_id=version:number` | Unique (dataset_version, record_number) |
| datasets | UUID version/id, source/is_demo/hash/file_ref, original_filename/schema_version/source_metadata, status/counts/normalization config, published_attempt_id | Unique (created_by, idempotency_key) |
| ingestion_runs | Trạng thái nhập, total_records, timestamps; ID theo version | _id |
| cleaned_jobs | Record normalized + salary fields; dataset_version/attempt_id/raw_record_ref | Unique (dataset_version, attempt_id, source_job_key); compound (dataset_version, attempt_id, province, industry, posted_at) |
| invalid_jobs | Fatal error code/stage/message/raw reference | Unique (attempt_id, raw_record_ref) |
| duplicate_jobs | Canonical raw ref, match strategy/reason | Unique (attempt_id, raw_record_ref) |
| data_quality_reports | Counts, ratios/definitions/missing/eligibility/reconciliation/thresholds | Unique (dataset_version, attempt_id) |
| analytics_snapshots | `data`, schema version, method/sample size, is_demo, version/attempt | Unique (dataset_version, attempt_id) |
| etl_jobs | Durable queue, payload/job_type/status, lease/fencing/retry/attempt | (status, job_type, created_at); (status, lease_until) |
| model_registry | Model/dataset IDs, metrics, feature schema, sample counts, artifact path/SHA, known categories, experience range | (dataset_version, created_at desc) |
| ml_experiments | Training job/algorithm/manifest, validation/test metrics, slice metrics/policy | _id |
| salary_predictions | User/model/dataset, input, VND prediction, warnings/reference period/test metrics | (user_id, created_at desc) |
| system_settings | Singleton active_dataset/active_model, revision and previous model; normalization config | _id |
| users, audit_logs | Roles/Argon2 hashes và thao tác quản trị | users.username unique |
| auth_sessions, auth_limits | Session/refresh và giới hạn thử đăng nhập | TTL expires_at |
| worker_heartbeats | Health theo worker/kind, updated_at | _id |
| benchmark_runs | Config/environment, measured observations/summary, artifact refs | _id |
| stream_seen | Event-ID ledger, first_raw_ref phục vụ replay dedup | _id (event_id) |

Catalog validators áp dụng cho các collections liệt kê trong COLLECTIONS; không khẳng định benchmark_runs/stream_seen đều có custom validator. `_id` thường là UUID/string; audit logs có thể ObjectId. Timestamp hệ thống BSON Date UTC; posted_at là ISO UTC string phục vụ filter hiện tại. Salary hiện lưu số Python/Spark double/int, không Decimal128; chưa có migration Decimal128. Kinh nghiệm thiếu là null. Không chuyển thành zero khi lưu.

Metadata nguồn nằm trên dataset, raw/clean tham chiếu bằng dataset_version. collected_at do người nhập khai báo, khác created_at/ingested_at. Khoảng ngày đăng quan sát tính từ clean theo filter; observation period trong source_metadata là provenance khai báo, không tự đồng nhất hai khái niệm.

## Publish, retry và đọc nhất quán

Ingestion tạo IMPORTING → RAW_READY; ETL PROCESSING → PUBLISHED hoặc FAILED. Claim job tạo attempt và fencing token. Bulk upsert `_id=attempt:raw_ref` bảo vệ retry task. Chỉ attempt đã đối soát và đạt quality gate được CAS vào published_attempt_id. Sau đó CAS active_dataset theo revision; version hoàn chỉnh vẫn có thể chưa active nếu người quản trị đã đổi pointer. Không có transaction đa collection và không hứa rollback toàn bộ staging khi worker chết.

Mỗi analytics request resolve một published version/attempt và đưa cả hai vào `$match` đầu tiên. Report/export dùng published attempt, hoặc attempt report gần nhất nếu chưa publish. Không cộng rows từ attempts cũ. Snapshot schema 1 không có group median được truy vấn live trên đúng immutable clean, không ghi đè snapshot cũ. Dataset/model activation chỉ đổi pointers; không xóa lịch sử. Chưa có API xóa/retention tự động trong phạm vi mô tả này.

## Aggregation, index và hiệu năng

Counts dùng toàn bộ clean; thống kê lương bỏ null midpoint. Group response luôn tách `jobs` và `salary_sample_size`, có mean/median/quantiles và small-sample warning. MongoDB 8 dùng `$percentile` approximate, Spark snapshot dùng percentile_approx accuracy=10000. Không cộng median nhóm để suy median toàn bộ.

Compound index hiện có ưu tiên version/attempt/province/industry/posted_at. Không mặc định mọi tổ hợp filter đều IXSCAN hiệu quả; đo explain executionStats trước/sau cùng query, dataset, cache và tải hệ thống rồi mới kết luận. Bằng chứng cũ natural 1.948 docs vs indexed 325 docs cùng 325 kết quả thuộc lần đo phase-9, không phải số đo mới hoặc bảo đảm latency. Chưa chạy lại Mongo explain trong lần nâng cấp vì Docker daemon không khả dụng.

Không log URI có password hay raw secrets. Export CSV scope version/attempt, có is_demo và chống formula injection; giữ nguyên cơ chế hiện có. Backup/restore chỉ vào DB/files riêng theo scripts hiện hữu, không tự chạy thao tác thay đổi dữ liệu trong audit.
