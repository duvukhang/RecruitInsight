# API contract dự kiến — /api/v1

Đây là contract thiết kế ban đầu của Phase 1, giữ lại để tham khảo; một số quy ước dưới đây khác implementation hiện tại. API đã chạy được. Xem [OpenAPI thực](openapi.json), Swagger tại http://localhost:8080/docs và [báo cáo kiểm chứng](reports/phase-9.md) để biết trạng thái hiện hành. Chưa triển khai CI tự động kiểm tra contract drift.

## Quy ước chung

HTTPS ở môi trường triển khai có truy cập mạng; local demo có thể HTTP loopback. IDs là UUID/string version, timestamps ISO-8601 UTC, money là JSON number VND/tháng đã làm tròn theo rule version. JSON không chứa NaN/Infinity. Success object có `data` và `meta`; list thêm pagination. Fields chưa biết trả null theo schema; không thay missing salary bằng 0.

```json
{
  "data": [],
  "meta": {
    "request_id": "example-request",
    "page": 1,
    "page_size": 25,
    "total": 0,
    "dataset_version": null
  }
}
```

Query list: `page≥1`, `page_size=25` mặc định, tối đa 100; `sort` thuộc allowlist từng resource, `order=asc|desc`, tie-break `_id`. Dataset filter `dataset_version` explicit hoặc resolve pointer một lần; response luôn trả version thực tế. `/jobs` hỗ trợ `q` tối đa 200 ký tự, province, industry, remote_type, experience_min/max, posted_from/to. Ngày invalid/đảo khoảng → 422. Giới hạn offset sâu 10.000; trả 422 yêu cầu filter/cursor export job, không scan không giới hạn. Không nhận JSON Mongo operators hoặc regex người dùng; query builder allowlist fields, kiểu và operators.

Lỗi thống nhất:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Kinh nghiệm phải là số từ 0 đến 60.",
    "details": {"fields": [{"field": "experience_years", "code": "OUT_OF_RANGE"}]},
    "request_id": "example-request"
  }
}
```

| HTTP | Mã lỗi tiêu biểu |
| --- | --- |
| 400 | INVALID_FILE_FORMAT, INVALID_QUERY |
| 401 / 403 | UNAUTHENTICATED / FORBIDDEN |
| 404 | DATASET_NOT_FOUND, JOB_NOT_FOUND, MODEL_NOT_FOUND |
| 409 | IDEMPOTENCY_CONFLICT, INVALID_STATE, VERSION_IN_USE, REVISION_CONFLICT |
| 413 / 415 | UPLOAD_TOO_LARGE / UNSUPPORTED_MEDIA_TYPE |
| 422 | VALIDATION_ERROR, INSUFFICIENT_TRAINING_DATA |
| 429 | RATE_LIMITED, có Retry-After |
| 500 / 503 | INTERNAL_ERROR / DEPENDENCY_UNAVAILABLE, MODEL_NOT_AVAILABLE |

Không đưa stack trace, secret hoặc connection string vào response. `X-Request-ID` được validate hoặc server sinh mới, trả header và log. Với long jobs, API chỉ validate điều kiện biết được tại thời điểm submit; điều kiện dữ liệu chưa tính được sẽ thành structured job error sau 202.

## Quyền và authentication

VIEWER đọc jobs/analytics, dataset metadata published. ANALYST thêm dự đoán/lịch sử cá nhân và đọc metrics published. ADMIN quản trị upload, ETL/training, model/dataset activation, reports, logs và settings. Raw/error records chỉ admin vì có thể chứa nội dung nhạy cảm. Tất cả endpoint nghiệp vụ cần Bearer access JWT; health live public chỉ trả trạng thái tối thiểu. System details admin. Ownership check cho prediction history/detail; không tin user_id từ request.

Access token ngắn hạn (đề xuất 15 phút), refresh token random opaque lưu hash, HttpOnly/SameSite cookie và rotation/reuse detection; frontend không lưu refresh token vào localStorage. Validate issuer/audience/expiry/algorithm allowlist. Argon2id password hash; bootstrap admin qua secret, không có password mặc định. Refresh/logout kiểm tra Origin và CSRF token khi dùng cookie. Login rate limit khởi điểm 5/phút/IP và account; prediction 30/phút/user, upload 5/phút/user; cấu hình lại bằng phép đo.

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| POST `/auth/login` | `{username,password}`; 1–128/1–256 ký tự | 200 `{access_token,token_type:"bearer",expires_in,user:{id,role}}`, set refresh cookie | Public, rate-limited |
| POST `/auth/refresh` | Refresh cookie + CSRF token | 200 access token mới, rotate cookie | Session |
| POST `/auth/logout` | Cookie + CSRF token | 204, revoke token | Session |
| GET `/auth/me` | — | 200 `{id,username,role}` | Mọi role |

## Datasets, ingestion và exports

`Idempotency-Key` bắt buộc cho upload/submit ETL/training/export, dài 1–128; scope theo actor+operation, lưu payload hash. Cùng key/payload trả lại status/resource cũ; khác payload trả 409. Version activation dùng expected_revision cho CAS. DELETE là asynchronous cleanup, không xóa ngay trong request.

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| POST `/datasets/upload` | multipart file + source, is_demo, source_license?, mapping_version?; ≤50 MiB | 202 `{dataset_version,ingestion_id,job_id,status:"QUEUED",status_url}` | ADMIN |
| POST `/datasets/import` | `{source_type:"OFFLINE"|"API",source_config_id}`; đường dẫn/URL lấy từ config allowlist | 202 ingestion/job reference | ADMIN |
| GET `/ingestion-runs/{id}` | ID | 200 `{id,status,counts,error,dataset_version,job_id}` | ADMIN |
| GET `/datasets` | page, page_size, source?, is_demo?, status? | 200 list DatasetSummary | Theo quyền published/admin |
| GET `/datasets/{id}` | Version ID | 200 DatasetDetail, lineage, counts, provenance | Theo quyền published/admin |
| GET `/datasets/{id}/quality` | attempt_id?; mặc định published/latest authorized | 200 report với thresholds, counts, reasons | ADMIN/ANALYST cho published |
| GET `/datasets/{id}/invalid` | page, page_size, error_code? | 200 list invalid records | ADMIN |
| GET `/datasets/{id}/duplicates` | page, page_size | 200 list canonical refs/reasons | ADMIN |
| POST `/datasets/{id}/reports` | `{kind:"ERRORS"|"QUALITY"|"CLEAN_EXPORT",format:"CSV"|"JSONL"}` | 202 export job | ADMIN |
| GET `/exports/{job_id}` | ID | 200 report metadata hoặc 409 nếu chưa hoàn tất | ADMIN |
| GET `/exports/{job_id}/download` | ID, ownership | 200 streamed file, Content-Disposition, checksum | ADMIN |
| POST `/datasets/{id}/activate` | `{expected_revision}` | 200 `{active_dataset_version,revision}` | ADMIN |
| DELETE `/datasets/{id}` | `{expected_revision}` | 202 cleanup job; 409 nếu active/in use | ADMIN |

DatasetSummary: `{id,dataset_id,parent_version,is_demo,status,source,created_at,row_counts,published_at}`. DatasetDetail thêm content_hash, schema/pipeline version, published_attempt_id và ingestion IDs. Chỉ admin xem file_ref nội bộ; không trả đường dẫn host. CSV export chống formula injection với ô bắt đầu `=`, `+`, `-`, `@` khi xuất text ra spreadsheet.

## ETL và job monitoring

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| POST `/etl/jobs` | `{dataset_version,pipeline_config_revision}` | 202 JobAccepted | ADMIN |
| GET `/etl/jobs` | page, status?, dataset_version? | 200 list JobSummary | ADMIN |
| GET `/etl/jobs/{job_id}` | — | 200 JobDetail | ADMIN |
| POST `/etl/jobs/{job_id}/retry` | `{expected_revision}` + Idempotency-Key | 202 job/attempt reference hoặc 409 | ADMIN |
| POST `/etl/jobs/{job_id}/cancel` | `{expected_revision}` | 202 CANCEL_REQUESTED khi đang chạy; 200 CANCELLED khi queued; 409 khi COMMITTING/terminal | ADMIN |
| GET `/etl/jobs/{job_id}/logs` | cursor?, limit≤200 | 200 sanitized logs + next_cursor | ADMIN |
| POST `/benchmarks` | `{sizes:[100,10000,100000],repeats:3,seed:42,worker_counts:[1,2]}`; size 1m cần budget config | 202 benchmark job | ADMIN |

JobAccepted: `{job_id,status,status_url}` + `Location` header. JobDetail: `{id,job_type,status,progress,stage,counts,attempt_id,retry_count,started_at,finished_at,duration_seconds,throughput,metrics,error,revision}`. Progress null nếu chưa xác định tổng, không tự động tăng bằng timer. Các report/benchmark/delete jobs dùng GET `/etl/jobs/{id}` chung theo job_type.

## Recruitment và analytics

Khai báo route tĩnh `/jobs/filters/options` trước `/jobs/{id}` trong FastAPI. Tương tự `/predictions/history` trước dynamic ID. Filter options có version và giới hạn trả về, không collect mọi giá trị trên request.

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| GET `/jobs/filters/options` | dataset_version? | 200 industries/provinces/skills/enum options | Mọi role |
| GET `/jobs` | Common list/job filters | 200 list JobSummary | Mọi role |
| GET `/jobs/{id}` | dataset_version? | 200 JobDetail, salary provenance, source URL | Mọi role |
| GET `/analytics/overview` | AnalyticsFilters | 200 totals, company/industry counts, salary median/coverage | Mọi role |
| GET `/analytics/salary-distribution` | AnalyticsFilters, bins≤50 | 200 bins, percentiles, box plot stats | Mọi role |
| GET `/analytics/salary-by-industry` | AnalyticsFilters | 200 group counts, salary summaries | Mọi role |
| GET `/analytics/salary-by-location` | AnalyticsFilters | 200 group counts, salary summaries | Mọi role |
| GET `/analytics/job-trends` | AnalyticsFilters, bucket=day/month/quarter | 200 buckets/counts | Mọi role |
| GET `/analytics/top-skills` | AnalyticsFilters, limit≤50 | 200 skills/count of jobs | Mọi role |
| GET `/analytics/experience` | AnalyticsFilters | 200 experience groups/counts | Mọi role |
| GET `/analytics/companies` | AnalyticsFilters, limit≤100 | 200 companies/counts | Mọi role |

AnalyticsFilters: dataset_version?, posted_from/to?, province?, industry?, experience_min/max?, remote_type?. Response meta: `{dataset_version,attempt_id,is_demo,sample_size,eligible_count,missing_salary_rate,reference_period,method_version,updated_at,warnings,filters}`. Không có active dataset → 409 `DATASET_NOT_AVAILABLE`, frontend hiển thị empty state. Version hoàn chỉnh có zero records cho filter → 200 empty data, sample_size=0 và salary summaries null.

Tổ hợp chưa có snapshot và vượt giới hạn query trực tiếp → 202 `{job_id,status_url}`; client polling rồi refetch, không bỏ qua filter. Export kết quả analytics dùng job report với filter/hash lưu trong manifest.

## ML và predictions

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| POST `/models/train` | `{dataset_version,algorithms,split_strategy,feature_schema_version,seed:42,training_config_revision}` | 202 `{job_id,status_url}` | ADMIN |
| GET `/training/jobs/{id}` | — | 200 JobDetail và experiment refs | ADMIN |
| GET `/models` | page, status?, dataset_version? | 200 list ModelSummary | ANALYST/ADMIN |
| GET `/models/{id}` | — | 200 metadata, artifact hash, lineage; không expose filesystem path | ANALYST/ADMIN |
| GET `/models/{id}/metrics` | — | 200 validation/test/slice metrics, split metadata | ANALYST/ADMIN |
| POST `/models/{id}/activate` | `{expected_revision}` | 200 `{active_model_version,revision}` | ADMIN |
| POST `/models/{id}/rollback` | `{target_model_version,expected_revision}`; id phải là active hiện tại | 200 pointer sau rollback | ADMIN |
| POST `/predictions/salary` | SalaryFeatures | 201 SalaryPrediction; history persisted | ANALYST/ADMIN |
| GET `/predictions/history` | page, page_size | 200 lịch sử của actor | ANALYST/ADMIN |
| GET `/predictions/{id}` | — | 200 prediction của actor; 404 nếu không có quyền sở hữu | ANALYST/ADMIN |

SalaryFeatures schema: required `job_title` (1–200), `industry` (1–100), `province` (1–100), `experience_years` (finite 0–60); optional city, seniority_level, education_level, employment_type, remote_type theo enum/filter options; `skills` tối đa 50 chuỗi, mỗi chuỗi 1–100. Reject extra fields, đặc biệt salary/target fields. Phân biệt nullable/unknown và chuỗi rỗng. Train algorithms thuộc allowlist baseline/linear/random_forest/spark_gbt/xgboost; không nhận đường dẫn module hoặc tham số thực thi tùy ý.

SalaryPrediction shape (placeholder chỉ minh họa cấu trúc, không phải prediction đã đo):

```text
data: {
  prediction_id: string,
  predicted_salary_vnd: finite positive number,
  currency: "VND", period: "MONTH",
  model_version: string, dataset_version: string,
  prediction_timestamp: UTC timestamp,
  reference_period: {from: date|null, to: date|null},
  model_metrics: {validation_mae_vnd: number|null, test_mae_vnd: number|null},
  warnings: string[],
  is_demo: boolean
}
```

Chỉ thêm `prediction_interval_*` và calibration metadata khi có phương pháp đã kiểm chứng. Không gắn “accuracy 95%” cho hồi quy. Prediction lưu thất bại → 503, không trả 201; request có Idempotency-Key tùy chọn để client retry an toàn sau timeout.

## Monitoring và settings

| Method / route | Request | Success response | Quyền |
| --- | --- | --- | --- |
| GET `/health/live` | — | 200 `{status:"alive"}` | Public |
| GET `/health/ready` | — | 200 hoặc 503, tối giản | Public nội bộ |
| GET `/system/status` | — | 200 component status/timeouts | ADMIN |
| GET `/system/pipeline-metrics` | time range tối đa 30 ngày | 200 throughput/duration/errors, sample counts | ADMIN |
| GET `/system/settings` | — | 200 safe config/revision | ADMIN |
| PATCH `/system/settings` | `{expected_revision,pipeline?,quality?,sources?}` allowlist | 200 revision mới; 409 nếu stale | ADMIN |

Secrets chỉ thiết lập qua môi trường/secret mount, không đọc ngược từ settings API. Backend ready phụ thuộc Mongo/schema; Spark down không làm mất API đọc dashboard nhưng job submit có thể trả 503 hoặc queued theo cấu hình được công khai.
