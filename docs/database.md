# Thiết kế MongoDB

Database nghiệp vụ: `recruitment_bigdata`. `_id` dùng UUID string để dễ serialize; timestamps BSON Date UTC, API ISO-8601 UTC. Lương chuẩn hóa là Decimal128 khi lưu, response số VND có quy tắc làm tròn đồng; cấm NaN/Infinity. Các business key/hash luôn có version thuật toán. Không nhúng toàn bộ records trong một document để tránh giới hạn kích thước BSON.

## Collections, quan hệ và indexing

Quy ước mẫu dưới đây mô tả shape; `id`, `date`, `object` là kiểu, không phải dữ liệu nghiệp vụ thực. Mỗi collection có validator `$jsonSchema`, required keys và enum cụ thể tại Phase 3. Bảng này là hợp đồng schema thiết kế, chưa phải migration đã chạy.

| Collection | Shape tối thiểu và quan hệ logic | Index dự kiến |
| --- | --- | --- |
| raw_jobs | `_id, dataset_version, ingestion_id, record_number, source, source_job_id?, source_url?, raw_payload:object, content_hash, ingested_at:date, schema_version` | Unique `(ingestion_id, record_number)`; `(dataset_version, _id)`; `(source, source_job_id)` không unique |
| cleaned_jobs | `_id, dataset_version, attempt_id, source_job_key, raw_record_ref, job_title, job_title_normalized, company_name, company_key, province?, city?, country?, location?, remote_type?, employment_type?, industry?, experience_years_min?, experience_years_max?, seniority_level?, education_level?, required_skills:array, job_description?, salary_*, posted_at?, collected_at, source, source_url?, data_quality_score, pipeline_version, created_at, updated_at` | Unique `(dataset_version, attempt_id, source_job_key)`; `(dataset_version, attempt_id, province, industry, posted_at)`; `(dataset_version, attempt_id, posted_at, _id)` |
| invalid_jobs | `_id, dataset_version, attempt_id, ingestion_id, raw_record_ref, validation_stage, error_code, error_message, field_errors:array, detected_at, retryable:bool` | Unique `(attempt_id, raw_record_ref)`; `(dataset_version, attempt_id, error_code)` |
| duplicate_jobs | `_id, dataset_version, attempt_id, raw_record_ref, canonical_raw_ref, match_strategy, reason, detected_at` | Unique `(attempt_id, raw_record_ref)`; `(dataset_version, attempt_id)` |
| datasets | `_id=version, dataset_id, parent_version?, source, source_license?, is_demo:bool, content_hash, schema_version, pipeline_config_hash, pipeline_version?, status, published_attempt_id?, row_counts:object, created_by, created_at, published_at?, deletion_requested_at?` | Unique `(dataset_id, content_hash, schema_version, pipeline_config_hash)`; `(dataset_id, created_at)` |
| ingestion_runs | `_id, dataset_version, requested_by, idempotency_key, input_hash, file_ref, format, source, is_demo, status, total_records, raw_records, parse_error_count, started_at?, finished_at?, error?` | Unique `(requested_by, idempotency_key)`; `(dataset_version, started_at)` |
| etl_jobs | `_id, job_type, input_dataset_id, dataset_version, status, progress, attempt_id?, total_records, processed_records, valid_records, invalid_records, duplicate_records, started_at?, finished_at?, error_message?, retry_count, worker_id?, lease_until?, heartbeat_at?, fencing_token:int, pipeline_version, metrics:object, cancel_requested:bool` | `(status, job_type, created_at)`; `(status, lease_until)`; `(dataset_version, created_at)` |
| data_quality_reports | `_id, dataset_version, attempt_id, pipeline_version, counts, completeness, validity, uniqueness, consistency, timeliness, salary_label_usability, thresholds, passed, reasons:array, generated_at` | Unique `(dataset_version, attempt_id)` |
| analytics_snapshots | `_id, dataset_version, attempt_id, metric_name, dimensions:object, dimension_key, time_bucket?, values:object, sample_size, eligible_count, reference_period, method_version, updated_at` | Unique `(dataset_version, attempt_id, metric_name, dimension_key)`; `(dataset_version, attempt_id, metric_name, time_bucket)` |
| salary_predictions | `_id, user_id, model_version, dataset_version, input_features:object, predicted_salary_vnd, prediction_interval_lower_vnd?, prediction_interval_upper_vnd?, reference_period, confidence_metadata?, warnings:array, created_at` | `(user_id, created_at, _id)`; `(model_version, created_at)` |
| ml_experiments | `_id, training_job_id, model_version, algorithm, dataset_version, attempt_id, dataset_hash, split_manifest_ref, seed, feature_schema_version, parameters:object, parameter_hash, validation_metrics:object, test_metrics?:object, slice_metrics:array, artifact_uri, artifact_sha256, mlflow_run_id?, code_version, environment_hash, created_at` | Unique `(training_job_id, algorithm, parameter_hash)`; `(dataset_version, created_at)` |
| model_registry | `_id=model_version, model_name, version, algorithm, dataset_version, feature_schema_version, training_parameters, metrics, mlflow_run_id?, artifact_uri, artifact_sha256, status, registered_at, activated_at?, evaluation_passed, previous_model_version?` | Unique `(model_name, version)`; `(status, registered_at)` |
| users | `_id, username_normalized, password_hash, role, enabled, refresh_token_hashes:array, created_at, updated_at` | Unique `(username_normalized)` |
| audit_logs | `_id, actor_id, action, resource_type, resource_id, request_id, outcome, safe_details:object, created_at` | `(resource_type, resource_id, created_at)`; `(actor_id, created_at)` |
| system_settings | `_id, revision:int, value:object, updated_by, updated_at` | `_id` implicit unique; singleton keys `active_dataset`, `active_model`, `pipeline_config`, `source_config` |

Mở rộng `etl_jobs.job_type`: INGESTION, ETL, TRAINING, REPORT_EXPORT, BENCHMARK, DATASET_DELETE. Tên collection kế thừa master prompt; không cần queue collection khác. Lỗi parse file lưu `invalid_jobs` với `validation_stage=INGESTION`, `attempt_id=ingestion_id`, `raw_record_ref` trỏ bản raw chứa dòng gốc. Lỗi nhiều trường gộp trong `field_errors`, mỗi raw input chỉ có một trạng thái cuối cho mỗi ETL attempt.

`salary_*` trong cleaned_jobs gồm: `salary_min`, `salary_max`, `salary_currency`, `salary_period`, `salary_min_vnd`, `salary_max_vnd`, `salary_mid_vnd`, `salary_is_disclosed`, `salary_quality_status`, `salary_original_text`, `salary_parse_method`, `salary_basis` (GROSS/NET/UNKNOWN), `fx_rate_reference`, `fx_rate_date`, `salary_normalization_assumptions`. Trường chưa biết để null, không ép về 0.

Không TTL trên raw/clean/datasets/models/audit để tránh mất bằng chứng. Refresh token hết hạn được cleanup bằng tác vụ định kỳ; nếu tách collection token sau này mới cân nhắc TTL. Artifact/prediction retention phải cấu hình và có audit trước xóa. Index bổ sung chỉ sau khi `explain('executionStats')` chứng minh truy vấn cần, tránh đánh index mọi tổ hợp bộ lọc.

## Schema mẫu cụ thể

Ví dụ minh họa **DEMO**, không phải dữ liệu đã import:

```json
{
  "_id": "demo-clean-001",
  "dataset_version": "demo-v1",
  "attempt_id": "demo-attempt-1",
  "source_job_key": "demo:job-001",
  "raw_record_ref": "demo-raw-001",
  "job_title": "Data Engineer",
  "job_title_normalized": "data engineer",
  "company_name": "DEMO Company",
  "company_key": "demo-company",
  "province": "Hồ Chí Minh",
  "country": "VN",
  "required_skills": ["python", "spark"],
  "salary_min_vnd": {"$numberDecimal": "10000000"},
  "salary_max_vnd": {"$numberDecimal": "15000000"},
  "salary_mid_vnd": {"$numberDecimal": "12500000"},
  "salary_is_disclosed": true,
  "salary_quality_status": "VALID_RANGE",
  "salary_original_text": "10–15 triệu VND/tháng",
  "salary_parse_method": "range_v1",
  "salary_currency": "VND",
  "salary_period": "MONTH",
  "salary_basis": "UNKNOWN",
  "fx_rate_reference": null,
  "fx_rate_date": null,
  "salary_normalization_assumptions": [],
  "source": "DEMO",
  "data_quality_score": 1.0,
  "pipeline_version": "etl-v1",
  "collected_at": {"$date": "2026-10-18T00:00:00Z"},
  "created_at": {"$date": "2026-10-18T00:00:00Z"},
  "updated_at": {"$date": "2026-10-18T00:00:00Z"}
}
```

Validator fragment dự kiến cho các bất biến cơ bản; application rule và integration tests kiểm tra thêm `min ≤ max` và salary eligibility:

```javascript
{
  $jsonSchema: {
    bsonType: "object",
    required: ["dataset_version", "attempt_id", "source_job_key", "job_title", "created_at"],
    properties: {
      dataset_version: {bsonType: "string"},
      attempt_id: {bsonType: "string"},
      source_job_key: {bsonType: "string"},
      job_title: {bsonType: "string", minLength: 1},
      salary_mid_vnd: {bsonType: ["decimal", "null"], minimum: 0},
      required_skills: {bsonType: "array", items: {bsonType: "string"}},
      created_at: {bsonType: "date"}
    }
  }
}
```

Ở Phase 3, migration sinh validator đầy đủ từ schema catalog, có fixture hợp lệ/không hợp lệ cho từng collection. Migration idempotent dùng create hoặc `collMod`, kiểm tra trùng trước tạo unique index; không tự xóa dữ liệu để migration pass.

## Version, publish và consistency

Dataset version là immutable sau khi PUBLISHED; dữ liệu mới hoặc cấu hình pipeline mới tạo version dẫn xuất. Dataset status: IMPORTING → RAW_READY → PROCESSING → VALIDATED → PUBLISHED; lỗi chuyển FAILED, xóa chuyển DELETING → DELETED. Retry có attempt mới, không ghi đè output đã publish. Dataset ID gom các versions cùng nguồn.

1. Worker claim job bằng `findOneAndUpdate` atomic, tăng fencing token và cấp attempt_id. Mọi output nằm trong `(dataset_version, attempt_id)`.
2. Spark write deterministic upserts theo partition, bulk operations có batch size; không collect toàn bộ records về driver. Lưu counts, quality report và snapshot manifest.
3. Chuyển job sang COMMITTING nội bộ bằng CAS kiểm tra lease, token và không có cancel request. Trong giai đoạn này không nhận cancel mới.
4. Xác minh attempt đầy đủ và đạt gate. Mark dataset PUBLISHED với `published_attempt_id` bằng CAS, rồi cập nhật singleton `system_settings.active_dataset` bằng revision CAS.
5. API đọc pointer một lần ở đầu request và gắn version/attempt vào mọi query. Chỉ phục vụ attempt đã publish. Job được đánh COMPLETED sau khi commit; reconciler sửa metadata nếu process chết giữa các bước.

COMMITTING là trạng thái bổ sung kỹ thuật cho job state machine, cần hiển thị là “Đang công bố”. Không cho recovery lấy lại job COMMITTING rồi ghi đè publication: reconciler hoàn tất hoặc đánh lỗi từ manifest. Nếu job hết lease trước bước 3, stale worker không thể CAS vào COMMITTING; output cũ không có pointer nên không lộ ra dashboard. Nếu dataset đã PUBLISHED nhưng chưa được active do process chết, đây là version hoàn chỉnh, chưa là active; reconciler đối chiếu revision để không ghi đè lựa chọn mới của admin.

Đổi active dataset/model bằng một singleton pointer document là atomic ở mức ứng dụng, không tuyên bố transaction đa collection. Phát triển dùng Mongo standalone; nếu sau này cần transaction nhiều documents phải cấu hình replica set và kiểm thử riêng. Admin rollback dataset chỉ đổi pointer về một version PUBLISHED tồn tại; không sửa dữ liệu. API nhận version rõ ràng để màn hình nhiều request không trộn versions.

Xóa version từ chối 409 nếu đang active, có job chạy hoặc model/prediction tham chiếu cần giữ. Khi được phép, tạo job cleanup có audit và manifest; không xóa raw trước khi kiểm tra retention.

## Aggregation và bằng chứng truy vấn

Spark là nơi tính precomputed analytics lớn. MongoDB aggregation dùng cho truy vấn vận hành hoặc phân tích có filter chọn lọc, luôn giới hạn version/attempt trước `$group`. Kết quả lương kèm `salary_sample_size` và tổng số records; không lấy số tin làm số mẫu lương.

Ví dụ truy vấn dùng ở demo, thay hai biến bằng version đã publish:

```javascript
db.cleaned_jobs.aggregate([
  {$match: {dataset_version: version, attempt_id: attempt}},
  {$group: {
    _id: "$province",
    jobs: {$sum: 1},
    salary_sample_size: {$sum: {$cond: [{$gt: ["$salary_mid_vnd", 0]}, 1, 0]}},
    mean_salary_vnd: {$avg: "$salary_mid_vnd"}
  }},
  {$sort: {jobs: -1}}
]);
db.cleaned_jobs.explain("executionStats").find({
  dataset_version: version, attempt_id: attempt, province: "Hồ Chí Minh"
}).sort({industry: 1, posted_at: 1});
```

Mean bỏ qua null; median/percentiles do Spark tính bằng phương pháp được ghi trong snapshot. Nếu dùng `percentile_approx`, công khai accuracy parameter; không trình bày là median exact. Thu output explain trước/sau index trên cùng query, cùng dữ liệu; báo keys/docs examined và latency, không cam kết mọi query luôn IXSCAN.
