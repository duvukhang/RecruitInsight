# API contract hiện tại

Prefix `/api/v1`. [openapi.json](openapi.json) được xuất từ FastAPI source; Swagger `/docs` kiểm tra runtime. Tài liệu này thay thiết kế cũ có endpoints/filters chưa triển khai.

Response thường `{data,meta}`; errors `{error:{code,message,details,request_id}}`. Meta tùy endpoint; không hứa pagination cursor hoặc expected_revision trong request khi source không nhận. Bearer access JWT và refresh cookie/CSRF theo cơ chế hiện có. VIEWER đọc analytics/jobs và metadata published; ANALYST thêm predictions/model metrics; ADMIN quản lý upload/ETL/training/activation/reports/settings. Prediction history/detail kiểm tra ownership. Quyền chính xác theo dependencies trong source.

## Upload

`POST /datasets/upload`: multipart file, source, is_demo (default true), header Idempotency-Key (1–128). source_metadata là JSON string tùy chọn (default `{}`, max 8000): source_type (upload/offline/api/synthetic), collected_at, observation_from, observation_to (YYYY-MM-DD), license_permission (max 1000). Request cũ không metadata vẫn hợp lệ. JSON/ngày/thời kỳ đảo sai trả 422 trước ingestion. File CSV/JSON/JSONL tối đa 50 MiB; 202 có version/ingestion/job/status URL.

Idempotency chỉ áp dụng upload theo hợp đồng hiện có: cùng actor/key/content/source/is_demo/metadata trả resource cũ, khác trả 409. Không khẳng định submit ETL/training/export nhận cùng header. Activation CAS revision ở server, không nhận expected_revision từ client. Chưa có delete dataset API. HTTP không chạy Spark đồng bộ.

## Analytics và predictions

`GET /analytics/{metric}` nhận dataset_version, province, industry, posted_from, posted_to. Metrics: overview, salary-distribution, salary-by-industry, salary-by-location, job-trends, top-skills, experience, companies. Không có experience/remote filters. Scope published version+attempt; posted_to bao gồm cả ngày UTC.

Response bổ sung group median/p25/p75/p90/warnings/missing_salary_rate; meta thêm reference_period/source/source_metadata/interpretation/minimum_group_salary_samples. Group quantiles chỉ hiện khi >=30 nhãn; median vẫn là mô tả mẫu. Snapshot schema 1 fallback live query, không sửa snapshot bất biến.

`POST /predictions/salary` chỉ nhận allowlisted job features; extra salary/target fields bị từ chối. Kết quả có predicted_salary_vnd, currency/period, model_version, dataset_version, reference_period, model_metrics, warnings, timestamps/history ID/is_demo. OOD không phải xác suất; không confidence/interval chưa hiệu chuẩn. Diagnostics thêm slice_metrics/slice_policy đủ mẫu; preview holdout tối đa 1000 rows, artifact tải đầy đủ.

## Routes trong source snapshot

| Method | Route | Nhóm |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | Authentication |
| POST | `/api/v1/auth/refresh` | Authentication |
| POST | `/api/v1/auth/logout` | Authentication |
| GET | `/api/v1/auth/me` | Authentication |
| GET | `/api/v1/system/status` | System |
| GET | `/api/v1/system/settings` | System |
| PATCH | `/api/v1/system/settings` | System |
| POST | `/api/v1/datasets/upload` | Data |
| GET | `/api/v1/datasets` | Data |
| GET | `/api/v1/datasets/{version}` | Data |
| GET | `/api/v1/datasets/{version}/quality` | Data |
| GET | `/api/v1/datasets/{version}/invalid` | Data |
| GET | `/api/v1/datasets/{version}/duplicates` | Data |
| POST | `/api/v1/etl/jobs` | Data |
| GET | `/api/v1/etl/jobs` | Data |
| GET | `/api/v1/etl/jobs/{identifier}` | Data |
| POST | `/api/v1/etl/jobs/{identifier}/retry` | Data |
| POST | `/api/v1/etl/jobs/{identifier}/cancel` | Data |
| POST | `/api/v1/datasets/{version}/activate` | Data |
| GET | `/api/v1/analytics/{metric}` | Analytics |
| GET | `/api/v1/jobs/filters/options` | Analytics |
| GET | `/api/v1/jobs` | Analytics |
| GET | `/api/v1/jobs/{identifier}` | Analytics |
| POST | `/api/v1/models/train` | Machine Learning |
| GET | `/api/v1/models` | Machine Learning |
| GET | `/api/v1/models/{identifier}/metrics` | Machine Learning |
| POST | `/api/v1/models/{identifier}/activate` | Machine Learning |
| POST | `/api/v1/predictions/salary` | Machine Learning |
| GET | `/api/v1/predictions/history` | Machine Learning |
| GET | `/api/v1/predictions/{identifier}` | Machine Learning |
| GET | `/api/v1/models/{identifier}` | Machine Learning |
| POST | `/api/v1/models/{identifier}/rollback` | Machine Learning |
| GET | `/api/v1/datasets/{version}/export/{kind}` | Reports |
| GET | `/api/v1/models/{identifier}/diagnostics` | Reports |
| GET | `/api/v1/models/{identifier}/artifacts/{kind}` | Reports |
| GET | `/api/v1/benchmarks` | Reports |
| GET | `/api/v1/health/live` |  |
| GET | `/api/v1/health/ready` |  |

Mongo/Spark integration chưa chạy lại do Docker daemon không khả dụng. HTTP validation và additive schema checks PASS với TestClient/test doubles; xem [báo cáo](reports/research-upgrade.md).
