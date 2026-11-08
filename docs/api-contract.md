# API contract hiện tại

Prefix `/api/v1`. [openapi.json](openapi.json) được xuất từ FastAPI source; Swagger `/docs` kiểm tra runtime. Tài liệu này thay thiết kế cũ có endpoints/filters chưa triển khai.

## Bổ sung RecruitInsight 2.0

Giữ nguyên endpoints cũ. [RBAC và vận hành](admin-users.md), [mapping/provenance và staged import](real-data-import.md). Request users/staged dùng Pydantic extra=forbid, kiểu strict; response users/audit/staged có models trong OpenAPI, chỉ trả fields được phép.

| Method | Route | Quyền / response |
| --- | --- | --- |
| GET | `/sources` | ADMIN; danh mục allowlist và NEEDS_REVIEW |
| POST | `/datasets/staged` | ADMIN; Idempotency-Key, manifest chunks; 201 version/chunk_count |
| PUT | `/datasets/staged/{version}/chunks/{index}` | ADMIN; multipart file ≤50 MiB; 200 hash/bytes |
| POST | `/datasets/staged/{version}/complete` | ADMIN; 202 ingestion/job/status URL |
| GET | `/users` | ADMIN; q prefix, role, enabled, page, page_size; không hash/token |
| POST | `/users` | ADMIN; username/password/role; 201 public user |
| PATCH | `/users/{id}` | ADMIN; role và/hoặc enabled; 200 public user |
| POST | `/users/{id}/reset-password` | ADMIN; password; 200 public user, revoke phiên |
| POST | `/users/{id}/revoke-sessions` | ADMIN; 200 public user, revoke access/refresh |
| GET | `/audit-logs` | ADMIN; action/actor_id/page/page_size, projection an toàn |
| GET | `/analytics/job-years` | Đã đăng nhập; cùng version/filter, năm/count; không dựng ngày |

Users và audit page_size 1–100, page tối đa 10.000; audit sort created_at/_id, users sort username. List theo offset có giới hạn, chưa phải keyset pagination. Non-admin nhận 403 trước lookup target; anonymous 401. Duplicate username/cùng key khác manifest/last admin/self-disable/concurrent writer trả 409. Schema/null/empty patch hoặc password yếu trả 422. Server error validation không echo input password.

Auth JWT/refresh bổ sung auth_version, default 0 cho users/tokens cũ. Khi reset/disable/đổi role/revoke, token cũ nhận 401 ngay; /auth/me vẫn đọc role hiện hành trong DB. Frontend phải đăng nhập lại khi phiên bị thu hồi.

`source_metadata` upload được mở rộng, vẫn tùy chọn: dataset_origin (synthetic/public_unverified/real/mixed/unknown), permission_status (NEEDS_REVIEW/DECLARED_PERMISSION/SYNTHETIC_FIXTURE), permission_evidence, adapter_version, source_revision, source_dataset_url, input_sha256 (64 hex), row_count, observation_year_from/to. Khoảng năm đảo bị từ chối; dữ liệu khai báo không phải xác minh pháp lý. Không nhận REAL_VERIFIED.

`GET /jobs` thêm salary_min/max (VND/tháng), experience_min/max (năm), employment_type exact, posted_year. Khoảng đảo/nonfinite trả 422; unknown không khớp range. q tìm title **hoặc company**, regex được escape. sort/order và phân trang vẫn ở server. Meta.job_filters lưu đầy đủ query, meta.sample_size vẫn là scope analytics trước các job-only filters; meta.total là số tin khớp toàn bộ job filters. Contains search có thể scan trong version/attempt, maxTimeMS=5000; không hứa text index tăng tốc contains.

posted_year nullable và provenance là additive trong normalized Spark/clean documents. job-years dùng snapshot years khi có, fallback live aggregation cho snapshot cũ; chỉ lấy năm từ posted_year hoặc ngày đã có. Quality report thêm profile parser/source/origin/companies/industries/provinces/years và source_metadata; report cũ thiếu profile vẫn hiển thị được.

`GET /models?active_only=true` (ANALYST+) giới hạn query vào active pointer toàn hệ thống, vẫn kết hợp dataset_version nếu gửi; không trả artifact_uri. `GET /etl/jobs?dataset_version=...&job_type=ETL` (ADMIN) lấy run theo version, hỗ trợ INGESTION/TRAINING; default vẫn list tất cả như cũ. Dashboard dùng hai query này theo role; VIEWER không gọi API mô hình/ETL. Quality profile schema_version=2 loại Unknown khỏi distinct ngành/tỉnh; báo cáo cũ chưa có version được ghi chú thay vì sửa ngầm dữ liệu đã công bố.

Jobs hỗ trợ keyset: gửi `cursor=` rỗng để bắt đầu; dùng `meta.next_cursor` cho trang sau, null là hết. Cursor có chữ ký HS256, audience riêng, hạn 24 giờ, bind version/attempt/filter/sort/order/page_size; giả mạo/khác scope/hết hạn trả 422 INVALID_CURSOR. Không dùng cursor làm access token được. Không kết hợp cursor với page khác 1. Sort cursor dùng `(field,_id)` cùng chiều và xử lý null/missing rõ ràng; legacy offset/page vẫn giữ giới hạn 400. UI jobs dùng cursor nên duyệt được qua giới hạn offset, có Trang đầu/Trước/Sau và không trộn scope khi đổi bộ lọc. Khi active pointer đổi giữa hai trang, chọn version cụ thể hoặc về trang đầu. Count total vẫn là toàn bộ scope, không chỉ phần sau cursor. Có compound indexes cho bốn trường sort; contains regex vẫn bị giới hạn timeout như trên.

Response thường `{data,meta}`; errors `{error:{code,message,details,request_id}}`. Meta tùy endpoint; không hứa pagination cursor hoặc expected_revision trong request khi source không nhận. Bearer access JWT và refresh cookie/CSRF theo cơ chế hiện có. VIEWER đọc analytics/jobs và metadata published; ANALYST thêm predictions/model metrics; ADMIN quản lý upload/ETL/training/activation/reports/settings. Prediction history/detail kiểm tra ownership. Quyền chính xác theo dependencies trong source.

## Hồ sơ cá nhân (mọi vai trò đã đăng nhập)

`GET /auth/profile` trả whitelist id/username/role/display_name/avatar_color/email/organization/bio và thời điểm tạo/cập nhật/đăng nhập. `PATCH /auth/profile` nhận ít nhất một trường display_name (1–80), email (0–254, dạng email hoặc rỗng), organization (0–120), bio (0–600), avatar_color (cyan/blue/violet/emerald/amber). Không nhận null, extra fields hoặc user ID; không thay auth_version khi sửa thông tin.

`POST /auth/password` nhận current_password và password mới theo chính sách ADMIN hiện hữu; trả 204, tăng auth_version và xóa các refresh sessions. Sai mật khẩu hiện tại trả 400; tối đa 5 lần/phút/user, quá trả 429. `POST /auth/revoke-sessions` trả 204 và thu hồi toàn bộ phiên của chính mình, gồm phiên hiện tại. Access cũ trả 401, refresh cũ không sử dụng được.

`GET /auth/sessions?page=1&page_size=10` (size tối đa 50) chỉ trả phiên còn hạn, đúng user và auth_version; whitelist created_at/last_seen_at/expires_at/user_agent. Không trả session ID/hash/token. last_seen_at là thời điểm đăng nhập hoặc refresh gần nhất. Profile và sessions hỗ trợ access-token renewal ở frontend giống các API đọc hiện hữu.

## Upload multipart

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
