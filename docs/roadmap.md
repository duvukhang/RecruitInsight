# Roadmap, kiểm thử và kịch bản bảo vệ

> Tài liệu này là kế hoạch và biên bản **Phase 1**, không phải trạng thái runtime hiện tại. Source đã được triển khai và chạy kiểm chứng trong các phase sau. Xem [kiểm chứng cuối](reports/phase-9.md), [bàn giao](reports/phase-10.md) và [README](../README.md). Các lệnh dự kiến dưới đây có thể đã được thay thế; dùng README cho vận hành.

## Phạm vi nghiệm thu

Triển khai từng phase; phase sau chỉ bắt đầu khi các kiểm tra bắt buộc của phase trước pass. Năm trụ cột là ưu tiên cốt lõi, không xóa yêu cầu streaming/MLOps của master prompt. Các đường dẫn source/test dưới đây là mục tiêu triển khai, chưa phải files đã tồn tại.

| Phase | Đầu ra source/tài liệu | Kiểm tra bắt buộc và điều kiện chuyển phase |
| --- | --- | --- |
| 1. Requirements & Architecture | README và docs architecture/database/pipelines/api-contract/roadmap | Đủ 12 nội dung thiết kế, mỗi trụ cột có evidence plan; phân biệt thiết kế và runtime |
| 2. Infrastructure | Compose core/profiles, Dockerfiles, `.env.example`, backend/frontend skeleton, scripts, locks | Build images; Mongo auth, init idempotent, API readiness, worker registration; frontend proxy API; ghi phiên bản/digest thực |
| 3. Ingestion & Storage | Mongo validators/indexes, repositories, ingestion service/worker, upload routes, fixtures DEMO | CSV/JSON/JSONL, malformed input, size/encoding, raw preservation, idempotency, index uniqueness; restart giữ dữ liệu |
| 4. ETL | Spark transforms/salary/dedup, quality, job handlers, publish/recovery | Counts reconcile, deterministic output, two workers execute tasks, quality failure giữ pointer cũ, retry/worker kill/cancel đúng |
| 5. Analytics | Spark SQL aggregates, snapshots, analytics API | Đối chiếu số liệu với fixture chuẩn, filter kết hợp không sai median, n/coverage/DEMO metadata; explain Mongo queries |
| 6. Machine Learning | Split/preprocessing/training/evaluation, registry, inference adapter | Baseline + ≥2 regressors; một pipeline MLlib; leakage checks, saved artifact parity, holdout metrics, active/rollback, không model → structured error |
| 7. Frontend | Chín trang, auth, query hooks, forms/charts, API integration | RTL/Vitest cho forms/errors/polling; Playwright gọi API thật, filters/pagination/history; responsive/keyboard; không nút chết |
| 8. Streaming | Kafka configs/producer, streaming driver/checkpoint/sink | Poison event, duplicate event, broker failure, restart query, checkpoint/replay không tăng trùng; publish window |
| 9. Integration & Testing | E2E, performance, fault injection, reports | A–E end-to-end, benchmark tăng quy mô, security/permissions; không lỗi blocker mở |
| 10. Deployment & Documentation | Hướng dẫn máy mới, backup/restore, demo script, acceptance matrix | Cold start từ volumes mới, restore riêng thành công, evidence đầy đủ, ghi rõ giới hạn và actual results |

Không dùng ngày hoàn thành cố định khi chưa đo tốc độ triển khai/tài nguyên. Đường găng: infrastructure → raw → ETL/publish → analytics/ML → UI → E2E. Streaming là nhánh sau luồng batch hoạt động; không lấy thời gian làm Kafka để bỏ kiểm thử luồng chính.

## Test strategy và traceability

| Requirement | Component và implementation mục tiêu | Tests mục tiêu | Evidence mục tiêu |
| --- | --- | --- | --- |
| R01 ingestion | `bigdata/ingestion`, dataset services, raw repository | `tests/integration/test_ingestion.py`: formats, malformed rows, idempotency, upload limits | Input SHA-256, raw counts, failed-row references |
| R02 ETL/quality | Spark transforms + job worker | `tests/unit/test_salary.py`, `tests/integration/test_etl.py`: parser, dedup, gate, counts, retry | Spark app ID, quality JSON, invalid/duplicate exports |
| R03 versions | Dataset publish service + Mongo CAS | `tests/integration/test_publication.py`: stale attempt, crash points, rollback | Pointer before/after, manifest and audit |
| R04 analytics | Spark SQL snapshots + API + React charts | `tests/integration/test_analytics.py`, frontend filter tests | Expected fixture totals, API output, UI screenshot |
| R05 ML | Split/training/evaluation/registry | `tests/unit/test_features.py`, `tests/integration/test_ml.py`: leakage, serialization, metrics, activation | Dataset/split hash, validation table, holdout predictions |
| R06 prediction | Serving adapter + history API | `tests/integration/test_predictions.py`: validation, artifact failure, ownership, parity | Model hash/version, API response and Mongo history |
| R07 operations | Auth, monitoring, jobs/settings | API permission/state/lease tests; safe-log checks | Logs sanitized, job state history, actor audit |
| R08 streaming | Kafka + Structured Streaming | `tests/integration/test_streaming.py`: replay/restart/poison/broker failure | Topic offsets, checkpoint metadata, unique event counts |
| R09 performance | Benchmark runner + report | `tests/performance/`: forced Spark actions, output equivalence, repetitions | Raw observations CSV/JSON, environment manifest, plots |
| Full-stack containers | Compose + Nginx/API/workers/Mongo/Spark | `tests/e2e/`: workflows A–E | Container status, network calls, screenshots, persisted results |

Unit tests chạy không cần Docker cho business rules. DB/integration tests chạy database riêng có suffix test, từ chối cleanup nếu db không thuộc test namespace. Không thay Mongo/Spark bằng mocks rồi gọi đó là integration pass. Có thể mock lỗi network cho unit tests, nhưng recovery phải kiểm chứng thêm trên services thật.

Security verification: anonymous 401, wrong role 403, ownership 404, JWT expiry/refresh/reuse, CORS/CSRF, upload limits, injection payloads, source/path allowlist, model artifact integrity, không log secret. API tests gồm success/400/401/403/404/409/413/415/422/429/500/503 theo endpoint phù hợp. Backend route tĩnh không bị dynamic ID che khuất.

## Benchmark Spark có thể bảo vệ được

1. Sinh input DEMO bằng seed 42 ở 100, 10.000, 100.000 dòng; tùy RAM thử 1.000.000. Generator phải có job IDs khác nhau, lỗi/trùng có tỷ lệ cấu hình; không chỉ copy cùng một file nhiều lần rồi làm dedup biến hết quy mô.
2. Lưu CPU, RAM/giới hạn Docker, OS/WSL2, disk, Spark/Python/JVM/connector/image versions, Git commit hoặc source SHA-256, executor cores/memory, partitions/shuffle/AQE/cache config.
3. So sánh cùng transformation/input/output trong ba cấu hình: Spark local[1] làm mốc; Spark standalone 1 worker; standalone 2 workers. Nếu thêm pandas phải xác nhận output tương đương, ghi khác biệt engine và I/O.
4. Warm-up một lần không tính vào kết quả; đo ít nhất ba lần độc lập/mỗi cấu hình/quy mô. Phân biệt cold/warm cache, session startup, read/transform/write/end-to-end. Timer phải bao quanh action hoàn tất và durable writes, không chỉ tạo lazy DataFrame.
5. Ghi raw wall-clock, stage times, counts, checksum, throughput = N_raw / elapsed; median và range từ các lần đo. Speedup = median local[1] / median cluster cùng workload. Đo memory theo sampled peak hoặc metrics thực, ghi phương pháp/tần suất, không tự suy ra từ memory limit.
6. Event logs/physical plan chứng minh partitioned scan, shuffle, số tasks và ít nhất hai executor trên hai worker có task thực thi. Nếu một executor làm hết thì chưa đạt bằng chứng phân tán dù có hai container.
7. Chỉ so sánh khi terminal counts/checksum output bằng nhau. Bỏ timestamps kỹ thuật khi hash output canonical; sort bằng business key. Lưu lỗi/OOM/timeout vào report, không thay bằng số ước đoán. Dataset nhỏ có thể chậm hơn do Spark overhead; báo trung thực.

Output dự kiến: `artifacts/evidence/<run_id>/benchmark-observations.csv`, `benchmark-summary.json`, `environment.json`, Spark event logs và plot từ dữ liệu đo. Thư mục này chưa được tạo để tránh nhầm có kết quả thực.

## Kịch bản demo theo năm trụ cột

| Bước | Thao tác | Bằng chứng cần chỉ ra |
| --- | --- | --- |
| 1 | Start core stack, mở UI và health | Containers healthy, UI gọi `/api/v1`, authenticated session |
| 2 | Upload DEMO có lỗi và trùng; mở ingestion/raw | SHA-256/source/DEMO, raw không bị mất, job được lưu trước xử lý |
| 3 | Submit ETL, mở Spark UI và job monitor | Hai executors nhận tasks, partition/shuffle, counts và logs |
| 4 | Xem clean/invalid/duplicate/quality rồi dashboard | Đối soát counts; snapshot gắn version; salary thiếu vẫn null |
| 5 | Run benchmark và mở bảng/plot | Ba quy mô, raw repeated observations, tài nguyên và runtime thực |
| 6 | Mongo index/aggregation/explain, đổi dataset version | Index constraints, query output, publish pointer; version cũ còn truy xuất được |
| 7 | Train, mở baseline/model comparison/holdout | Split không giao record/group; validation chọn model; test actual/predicted |
| 8 | Active model, nhập form dự đoán, xem history | API response gắn model/version; record Mongo mới; không hard-code frontend |
| 9 | Inject quality failure, retry/kill worker, restart containers | Active snapshot giữ nguyên khi lỗi; không duplicates; dữ liệu và artifacts còn nguyên |
| 10 | Bật streaming và mlops profiles | Kafka event → Spark → Mongo → UI, checkpoint restart, MLflow run thật |

Luồng E2E A: upload → ingestion → ETL → snapshot → dashboard. B: published dataset → train → compare → activate → predict → history. C: Kafka → streaming → snapshot → UI. D: restart → persistence → no duplicates. E: pipeline failure → logged error → retry → recovery. Với E, lỗi transient có thể retry; lỗi dữ liệu cần sửa/version mới, không retry vô hạn.

## Lệnh vận hành mục tiêu

Các lệnh dưới đây **chỉ chạy sau khi files/scripts được triển khai trong phase tương ứng**. Hiện chưa thể chạy chúng trong workspace. Shell host là PowerShell; compute chạy trong container. Không có lệnh xóa volumes trong quy trình stop/restart.

| Mục đích | Lệnh mục tiêu | Expected outcome |
| --- | --- | --- |
| Cấu hình | `Copy-Item .env.example .env` rồi điền secrets | Env đủ biến, không dùng default password |
| Build | `docker compose build` | Images build với lock/digest, exit 0 |
| Start | `docker compose up -d --scale spark-worker=2` | Core services sẵn sàng; init exit 0 |
| Profiles | `docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile streaming --profile mlops up -d` | Kafka/streaming/MLflow có health và logs |
| Stop | `docker compose stop` | Containers dừng, volumes còn |
| Restart | `docker compose restart` | Health phục hồi, counts/history giữ nguyên |
| Logs | `docker compose logs --tail 200 backend etl-worker training-worker` | Log structured, không lộ secrets |
| Mongo shell | `docker compose exec mongodb mongosh --username <user> --authenticationDatabase recruitment_bigdata --password` | Password prompt, quyền tối thiểu |
| Submit ETL | `docker compose exec backend python -m recruitment.cli etl submit --dataset-version <version>` | CLI gọi application service, trả job_id |
| Train | `docker compose exec backend python -m recruitment.cli models train --dataset-version <version>` | Trả training job, worker xử lý |
| Backend/unit/integration | `docker compose run --rm test-backend` | Pytest pass, JUnit report thật; test service Phase 2/3 |
| Frontend | `npm --prefix frontend ci` rồi `npm --prefix frontend test -- --run` | Vitest/RTL pass; host chỉ chạy tool dev |
| E2E | `npm --prefix frontend run test:e2e` | Playwright gọi stack thật, report/screenshots |
| Benchmark | `docker compose exec etl-worker python -m bigdata.benchmark --sizes 100 10000 100000 --repeats 3` | Observations và environment manifest |
| Backup/restore | `./scripts/backup.ps1` và `./scripts/restore.ps1 -Manifest <path> -TargetProject recruitment-restore` | Dump + artifact manifest; restore isolated có checksum verification |

Tên test service, CLI và scripts phải được triển khai đúng hoặc cập nhật tài liệu trước khi đánh dấu pass. Không copy credentials lên command line; dùng prompt hoặc secret mount.

## Mẫu báo cáo sau mỗi phase

Mỗi phase ghi `docs/reports/phase-N.md`: mục tiêu; files tạo/sửa; architecture/design decisions; luồng đã triển khai; unit/integration tests; lệnh đã chạy; actual results kèm timestamp/environment/exit code/log path; lỗi; cách sửa; phần chưa hoàn thành; điều kiện chuyển phase. Evidence dùng input hash, code hash/commit và command để tái lập, không chỉ screenshot.

Trạng thái mỗi yêu cầu: PLANNED → IMPLEMENTED → VERIFIED hoặc BLOCKED với lý do. IMPLEMENTED chưa đồng nghĩa VERIFIED. Expected outcome đặt riêng actual result. Không điền metrics, benchmark hay log giả vào báo cáo.

## Báo cáo Phase 1 tại thời điểm thiết kế

- Mục tiêu: thiết kế đủ yêu cầu, ưu tiên năm trụ cột có bằng chứng bảo vệ.
- Files thực tế: `README.md` và năm tài liệu trong `docs/`.
- Decisions/luồng: modular monolith + worker riêng, Mongo queue, Spark standalone, attempt-scoped outputs, publication CAS; split/validation/holdout và registry có provenance.
- Kiểm tra thực tế: đọc master prompt UTF-8, kiểm tra workspace, đối chiếu tài liệu chính thức Spark/connector/MLflow; kiểm tra liên kết nội bộ và độ bao phủ 12 đầu ra thiết kế bằng script đọc files.
- Môi trường quan sát: Python 3.13.0, Node 24.16.0 trên host. Docker CLI có mặt nhưng Docker Engine chưa truy cập được: config access denied và Docker pipe permission denied.
- Lỗi/khắc phục: file đính kèm ban đầu hiển thị sai encoding, đọc lại với UTF-8; tài liệu dự án ghi UTF-8. Không sửa Docker settings hoặc yêu cầu quyền ngoài workspace.
- Chưa hoàn thành: toàn bộ source runtime, lockfiles, images, datasets thật, unit/integration/E2E/performance runs. Không có kết quả latency/metrics/benchmark.
- Điều kiện Phase 2: thiết kế đã kiểm tra nhất quán; triển khai hạ tầng, chọn/pin patch cụ thể và smoke tests. Docker cần chạy được để xác minh Phase 2; hiện chưa thể tuyên bố đạt runtime gate.

## Acceptance cuối cùng

Chỉ đánh dấu hoàn tất đồ án khi cold-start Docker thành công; Mongo auth/persistence/indexes/versions được test; upload và Spark ETL thật có counts/errors/dedup/quality; analytics từ published data; baseline và nhiều regressors được kiểm thử holdout; registry/inference/history hoạt động; UI gọi API thật; A–E pass; streaming profile restart được; benchmark có observations thật; backup/restore và tài liệu máy mới được chạy thử. Mọi giới hạn tài nguyên và thiếu nguồn dữ liệu thật phải được trình bày rõ trong báo cáo bảo vệ.
