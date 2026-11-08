# RecruitInsight 2.0 — kết quả và bằng chứng

Bổ sung mới nhất: [hồ sơ cá nhân, dashboard và DEMO 50k](profile-upgrade.md). Dataset active hiện là `7aeabd85-8462-4ca0-af46-19cae61fa6be` (49.046 clean); các bảng kiểm chứng phía dưới ghi lại lần nghiệm thu trước khi bổ sung hồ sơ, không phải số liệu của dataset đang active.

Ngày thực hiện: 07–08/11/2026 (Asia/Saigon). Bắt đầu tại `main@3d2e8005e90f4617d0d309b43b8876cd22d2d5c2`, nhánh `feat/recruitinsight-real-data-rbac-ui`. Thay đổi đang ở working tree; không tự commit/push. Không sửa `.env`, không xóa dữ liệu/volumes ứng dụng. Test fixtures chỉ cleanup trong DB `_test`; các user tạo cho demo HTTP được disable mềm.

## Phase 0 — audit/baseline

- Files: [upgrade-audit.md](upgrade-audit.md); đọc README/architecture/pipelines/API/research report và các module API/services/ETL/ML/frontend/workers/tests liên quan.
- Reuse: auth/roles/CLI, DatasetService upload/idempotency, ingestion/attempt/fencing/recovery, quality/publish, registry/serving, ECharts/React Query.
- Tests thật: Docker baseline **54 passed, 3 Spark skipped**; frontend **2 passed**, TypeScript/Vite build đạt; browser baseline **2 passed**.
- Evidence: `artifacts/upgrade-2-before-{desktop,mobile}.png` (UI fixture); commit/branch và phát hiện file:line trong audit.
- Giới hạn: nguồn public chưa đủ quyền; số đo 18/10 không thay bằng chứng mới. Phase tiếp: adapter và staged import.

## Phase 1 — dữ liệu

- Files changed/new: `bigdata/sources.py`, `normalize.py`, `ingestion.py`, `etl.py`; `application/staged_import.py`, `api/data.py`, `api/analytics.py`, `application/analytics.py`, `domain/salary.py`, `infrastructure/init_db.py`; `scripts/prepare_real_dataset.py`, `measure_adapter.py`; `tests/test_real_sources.py`, `test_staged_import.py`, `test_upgrade_analytics.py`, `test_etl.py`, fixture 100 dòng và `docs/real-data-import.md`.
- Reuse: parser/normalization và gate cũ; raw/canonical/worker queue; version/attempt/fencing và CAS publish không đổi. Staged chỉ thay danh sách input trước ingestion, không bypass quality.
- Behavior: allowlist Tinix/VietJobs từ local export; không fetch URL; bounded batches/row/bytes; UTF-8, seed, SHA-256, dry-run; missing/interval experience giữ unknown, không tạo company/date/skills. CSV/JSONL giữ provenance qua normalize; salary 40tr/upto và FX/NET giữ quy tắc nhãn. Staged chunks có manifest, checksum, row count và idempotency; sealed bất biến, một version cho tất cả chunk.
- Tests: adapter/RBAC/staged sớm **20 passed**; tests sau mở rộng gồm CSV roundtrip/injection, Unicode, byte caps, negative row count, preserve temporary owner, dừng parse đúng limit dù dòng sau bị hỏng, year-only/salary/experience/company search, pagination và explain index đều nằm trong regression cuối. Spark ban đầu **3 passed / 52,91 s**; bản source cuối **3 passed / 73,18 s**, gồm metadata dict/string CSV, profile Unknown và year-only publish.
- Evidence adapter thực, fixture tổng hợp: 5.000 → **7.289.230 bytes**, 1 chunk, **0,285 s** converter; 50.000 → **72.992.280 bytes**, 5 chunk, chunk tối đa **14.602.900 bytes**, **2,569 s** converter. Scope gồm input hash/mapping/serialization/manifest, không gồm fixture generation/ETL/Mongo. Một lần đo, có workload nền; không suy rộng thành cam kết throughput. `artifacts/upgrade-2-adapter.json`; input/output lớn ở uploads/artifacts volume, không Git.
- HTTP live staged: **200 raw = 100 clean + 100 duplicate + 0 invalid**, year 2024/count 100, trends tháng rỗng, quality profile đúng. `artifacts/upgrade-2-live.json`. Đây là SYNTHETIC, không phải corpus public.
- Limitations: Tinix quyền nội dung gốc NEEDS_REVIEW, VietJobs chưa license/company/day. Public pilot **BLOCKED**, chưa tải/commit corpus. CSV bảo vệ công thức có thể thêm apostrophe; ưu tiên JSONL. UI preview 4 KiB là kiểm tra sơ bộ/canonical schema, không tự map arbitrary CSV. Staged chưa có GC tự động; quản lý disk và giữ export nguồn gốc ngoài Git.
- Next phase: user management, session revocation và frontend guards.

## Phase 2 — RBAC và users/audit

- Files: `domain/permissions.py`, `api/users.py`, `application/users.py`, `api/auth.py`, `application/auth.py`, `infrastructure/security.py`, `init_db.py`, `cli.py`, `main.py`; frontend `permissions.tsx`, `App.tsx`, `AdminUsers.tsx`, `api.ts`; `tests/test_users_admin.py`, `test_admin_recovery.py`, `docs/admin-users.md`.
- Reuse: ba role, JWT/CSRF/refresh rotation, DB-authoritative current_user và prediction ownership. Không tạo auth mới hoặc password demo hardcode.
- Behavior: ADMIN list/create/update/disable/reset/revoke; strict schema/password/username policy và public projection. Last-admin check + write tuần tự bằng Mongo mutex không TTL, recheck actor trong critical section. Auth epoch chặn token cũ, gồm race refresh. Audit outbox atomic với user mutation, replay ID không trùng. UI 403 trước mount protected component kể cả URL case/encoding, role menu/shortcuts và cache/expired handling.
- Tests thật: role matrix anonymous/viewer/analyst/admin, DB role cũ trong JWT, disable/reset/revoke access+refresh, 2 concurrent demotions, self-disable, stale actor, brute force, password/extra-field/projection, mutex fail-closed và outbox replay. HTTP live RBAC/staged **47 kiểm tra đạt**; không lưu password/token vào evidence.
- Limitations: standalone Mongo không transaction đa document. Process chết khi giữ mutex cần runbook dừng writers và phục hồi lock thủ công; không tự TTL để owner cũ resume phá invariant. Audit delivery eventual từ outbox; list offset bounded, chưa keyset pagination. User cũ/CLI đã có hash tiếp tục đăng nhập, policy mạnh áp lúc tạo/reset.
- Next phase: UI và quality/source comparison.

## Phase 3 — UI

- Files: `App.tsx`, `Workspace.tsx`, `Chart.tsx`, `AdminUsers.tsx`, `Sources.tsx`, `QualityDashboard.tsx`, `components/insights.tsx`, `permissions.tsx`, `dark.css`, `main.tsx`, legacy CSS; Playwright configs và `e2e/{research,upgrade,upgrade.live}.spec.ts`.
- Reuse: React 19/TS/Vite, React Query, Router, RHF/Zod, Lucide, ECharts canvas. **Không thêm dependency/Three.js/WebGL.**
- Behavior: dark navy/cyan, layer/shadow, CSS hover depth nhỏ 200 ms trên cards, không bóp méo trục chart. Reduced motion tắt transform/transition/animation chart; mobile tắt depth, menu có aria-expanded. Common StatCard/PageHeader/InsightPanel/badges/filter/error/empty/dialog. Native dialogs có vòng Tab/Escape và trả focus. Top context, version/filter trong URL, registry/admin navigation theo role; quality báo counts/coverage/parser/missing; comparison giữ hai populations riêng, JSON export. Job filters/pagination/sort ở server, drawer gọi API detail đầy đủ.
- Tests thật UI fixture: **16 passed / 20,1 s** gồm ba role × 390/768/1366, overflow, reduced motion, guards case/encoding, error/retry, year fallback, dialog keyboard, role update/session revoke và scope filters qua navigation/reload/back-forward. `artifacts/upgrade-2-browser.xml`, screenshots `upgrade-2-{admin,analyst,viewer}-{390,768,1366}.png`; đã xem desktop/mobile. Screenshots fixture không thay live API evidence.
- Vòng sửa có chẩn đoán: (1) legacy CSS nav `display:flex!important` gây tràn 390, xóa rule đã thay; (2) vòng Tab native có thể chuyển focus ra browser chrome, thêm wrapping focus; (3) giữ scroll vị trí cũ khi đổi route, reset về đầu trang. Ảnh live cuối dùng reduced motion và chờ đủ canvas để không chụp giữa animation. Suite đạt; không quá ba vòng sửa source UI.
- Limitations: ECharts chunk còn 506,59 kB (gzip 169,32 kB), chưa đo Core Web Vitals. Chart và APIs dùng cùng giới hạn top groups cũ. Không có thông tin GPU hoặc market realtime; không thêm nội dung giả để lấp biểu đồ.
- Next phase: regression final, Docker E2E và benchmark snapshot.

## Phase 4 — regression/P1/P2

| Kiểm chứng | Kết quả đã quan sát | Evidence |
| --- | --- | --- |
| Backend regression source cuối | **81 passed, 3 Spark skipped** | upgrade-2-backend-final.xml; Spark chạy riêng |
| Frontend unit | **2 passed / 2,02 s** | upgrade-2-frontend-unit.log (stdout cuối) |
| Build production trong Docker | **PASS**, TypeScript + Vite | image build; ECharts warning như trên |
| Spark/Mongo source cuối | **3 passed / 73,18 s** | upgrade-2-spark-final.xml; không skip |
| HTTP pipeline cũ | **PASS**: 1.000 DEMO → 954 clean, 6 models, prediction/history | artifacts/e2e-result.json |
| HTTP RBAC + staged | **PASS**, 47 checks, 200/100/100/0 | artifacts/upgrade-2-live.json |
| UI fixture | **16 passed** | upgrade-2-browser.xml và 9 screenshots |
| Live browser roles + users/quality/comparison/export | **2 passed / 8,8 s** | upgrade-2-live-browser.xml; screenshots cuối dùng reduced motion, data/profile mới, ba role desktop/mobile và users/quality/sources |
| Benchmark snapshot 100/10k/100k/500k | **PASS**, 36 observations / 12 groups, 3 repeats + warm-up | upgrade-2-benchmark-{observations.csv,summary.json,environment.json,verification.json} |
| Public pilot / experiments synthetic vs real | **BLOCKED** vì quyền nguồn | dataset cards, audit, real-data-import.md |

Benchmark đã hoàn tất trên frozen image `sha256:6a332aa7c1294c99b48e330c9cbebb994bccc7c5210560307521380c7a6ad794`. Source archive `artifacts/upgrade-2-benchmark-source/bigdata/` và `salary.py`, normalize SHA-256 `278f7e954a1e5e49ed54993579ca7f850459e9ce7549c24660d53970d50856f9`. Snapshot trước sửa CSV metadata_object và định nghĩa profile Unknown; số đo chỉ mô tả snapshot đã lưu, không tuyên bố là latency chính xác của final source. `scripts/verify_upgrade_benchmark.py` xác minh đủ 36 observations, raw=classified, checksum giữa configurations/repetitions, 5 source hashes, 4 input hashes, median/min/max/speedup và executors/partitions/tasks. Fixtures benchmark là DEMO seed 42. Timing read/normalize/classify/dedup/checksum, không gồm Mongo writes/ML/startup/generation/metadata inspection. OS cache không kiểm soát; có dịch vụ nền và một số kiểm thử/build cục bộ trong phiên, không coi là thí nghiệm cô lập. Không đo peak memory toàn workload; `upgrade-2-resource-snapshot.json` chỉ là Docker stats tại một thời điểm.

| Rows | Local 1 luồng (median s) | Cluster 1 executor (s) | Cluster 2 executors (s) | Tỷ lệ local/cluster2 |
| --- | --- | --- | --- | --- |
| 100 | 1,553 | 1,416 | 1,456 | 1,07× |
| 10.000 | 4,354 | 4,928 | 3,040 | 1,43× |
| 100.000 | 25,860 | 25,128 | 13,845 | 1,87× |
| 500.000 | 116,690 | 124,699 | 68,744 | 1,70× |

Counts snapshot: 100 → 96 clean/1 duplicate/3 invalid; 10k → 9.546/183/271; 100k → 95.461/1.835/2.704; 500k → 477.307/9.178/13.515. Mỗi size đối soát đủ raw và fingerprint giống nhau. Python 3.11.11, Spark 3.5.7, WSL2 cùng máy, 16 CPUs nhìn thấy và ~7,57 GiB Docker RAM. Cluster một executor không nhất quán nhanh hơn local; không kết luận phân tán luôn nhanh hơn hoặc số đo này bao gồm Mongo/ML.

P1: company/salary/experience/employment/year filtering, source comparison/JSON export, quality profiles, role-aware active model/latest ETL summary và URL scope filters đã triển khai. `application/pagination.py` thêm jobs keyset cursor HS256 bind version/attempt/filter/sort/size; tests Mongo duyệt đủ 31 rows, không lặp/mất với null/ties và 4 sort fields × 2 chiều, chặn forged/scope-changed cursor và không dùng làm access JWT. Legacy offset/page giữ nguyên; UI cursor có Trang đầu/Trước/Sau. Query explain xác nhận exact company query dùng compound index, 1 returned / ≤1 document examined; contains search có thể scan scope version và timeout 5 s. Không áp fixture 31 rows thành latency của 500k. Scope filters version/tỉnh/ngành/ngày lưu URL; search/job-only form state chưa lưu qua reload.

P2: diagnostics theo nhóm có sẵn được reuse; chưa chạy independent real-vs-synthetic model experiments/drift vì chưa có corpus được phép. Không trình bày như tính năng nghiên cứu đã được nghiệm thu.

## Acceptance

**Chưa ACCEPT toàn bộ** vì public pilot còn BLOCKED bởi quyền nguồn. Code và các kiểm chứng đã chạy có kết quả ở bảng trên; không dùng PASS của fixture tổng hợp để thay dữ liệu public được phép. Independent real-vs-synthetic experiments/drift và peak-memory profiling chưa chạy. Benchmark chỉ nghiệm thu frozen snapshot đã lưu, không là final-source latency. Không coi dữ liệu tổng hợp/lịch sử là thị trường lao động hiện tại; không thay group split/feature allowlist/holdout hoặc tắt security/quality gate để đạt số liệu.

Chạy lại theo README, `docs/real-data-import.md`, `docs/admin-users.md`, `scripts/e2e.py`, `scripts/verify_upgrade.py`; benchmark mới dùng command trong README với sizes đã chọn. Source fixtures/tests/scripts/docs được giữ trong Git working tree; artifacts/datasets ignored cần lưu riêng khi bàn giao.

Hướng dẫn trình bày: [demo-2.md](../demo-2.md). Inventory/hash của evidence nhỏ và kết quả kiểm tra: `artifacts/upgrade-2-delivery.json`. Docker core với hai Spark workers đã đồng bộ và chạy; không tự bật/tắt các profile Kafka/MLflow ngoài stack có sẵn. OpenAPI snapshot cuối có 45 route paths, giữ các API cũ và bổ sung các routes/filters đã mô tả.
