# Audit RecruitInsight 2.0 — 07/11/2026

Điểm bắt đầu: `main`, commit `3d2e8005e90f4617d0d309b43b8876cd22d2d5c2`.
Nhánh làm việc: `feat/recruitinsight-real-data-rbac-ui`. Giữ ba file giao diện đang sửa từ yêu cầu trước; không stash/reset, không sửa `.env`.

## Audit → thiết kế

| Phát hiện trước nâng cấp | Vị trí ở baseline | Quyết định |
| --- | --- | --- |
| JWT 15 phút, refresh rotation/CSRF, role lấy từ DB | `api/auth.py:21`, `application/auth.py:14`, `infrastructure/security.py:16` | Reuse; thêm auth_version để revoke cả access và refresh |
| users.role đã có ba giá trị, username unique | `infrastructure/init_db.py:47`, `:58` | Reuse migration; thêm indexes và quản lý users, không đổi role schema |
| CLI users create đã có | `cli.py:18` | Modify: dùng cùng service và kiểm tra password |
| Metadata published riêng với admin, raw/report chỉ admin | `api/data.py:76`, `:95` | Reuse dependencies; không mở quyền export |
| Menu lọc role, Routes chưa guard | `frontend/src/App.tsx:185`, `Workspace.tsx:1269` | Modify: permissions tập trung, guard trước mount component và 403 |
| Upload streaming SHA-256 và 50 MiB, idempotency | `application/datasets.py:14` | Reuse cho snapshot; thêm staged JSONL có checksum, seal rồi enqueue |
| SourceMetadata giới hạn năm trường, chưa có trạng thái quyền/revision | `api/data.py:33` | Additive; không phá requests cũ |
| normalize giữ missing experience, posted_at không tự điền; chưa có posted_year | `bigdata/normalize.py:17`, `:33` | Reuse; thêm năm và provenance vào Spark schema |
| Parser chưa nhận 40tr/upto | `domain/salary.py:47`, `:69` | Modify có regression test; không gán FX |
| DEMO seed 42, 5 titles, 40 companies, 3 tỉnh | `scripts/generate_demo.py:9` | Reuse; fixture mới cũng ghi synthetic, không tráo thành public |
| ML ≥200 labels, ≥10 companies, reservoir 10k, group split | `machine_learning/training.py:24`, `:41` | Reuse nguyên algorithm và gate |
| Attempt/fencing/reconcile/publish và worker queue | `bigdata/etl.py`, `application/pipeline.py`, `workers/runner.py:15` | Giữ, staged import chỉ đổi danh sách input trước ingestion |

Các đường dẫn backend trong bảng tính từ `backend/src/recruitment/`. Dòng tham chiếu là baseline trước thay đổi.

## Baseline thực chạy

- Docker daemon 29.4.1, stack hiện có healthy. Sandbox mặc định không truy cập Docker pipe; chạy cùng lệnh với quyền Docker được cấp đã thành công.
- `docker compose run --rm test-backend`: **54 passed, 3 skipped** (Spark cần RUN_SPARK_TESTS=1). Image đang chạy là baseline, chưa chứa thay đổi mới.
- Frontend `npm.cmd test -- --configLoader runner`: **2 passed**; `tsc --noEmit` và `vite build`: **PASS**. `tsc -b` không ghi được tsbuildinfo cũ trong sandbox, không coi lỗi môi trường này là lỗi TypeScript.
- Các số benchmark 18/10 là lịch sử, không dùng nghiệm thu code mới.
- Ảnh trước thay đổi: suite `playwright.research.config.ts` baseline **2 passed**, đã giữ `artifacts/upgrade-2-before-desktop.png` và `upgrade-2-before-mobile.png`. Đây là UI fixture, không phải bằng chứng pipeline.

## Nguồn public: NEEDS_REVIEW

Đã truy cập ngày 07/11/2026:

- [Tinix](https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions): card ghi 606.878 rows, 14 cột, năm 2022–2026, CC BY-NC 4.0; không có posted day. Card yêu cầu kiểm tra điều khoản nguồn liên quan, chưa chứng minh quyền tái phân phối toàn bộ văn bản bên thứ ba.
- [VietJobs](https://huggingface.co/datasets/dinhieufam/VietJobs): preview 48,1k, không company/day và không thấy license trên card. [Bài báo](https://aclanthology.org/2026.lrec-1.501/) mô tả 48.092 tin, 16 nhóm ngành; license bài báo không tự áp cho dataset.

Chưa tải corpus hoặc commit mẫu public. Chặn network import mặc định; adapter dùng local input do người có quyền cung cấp, ghi permission evidence riêng và không tự gán REAL_VERIFIED. Fixture test tự tạo và ghi synthetic. Public pilot/500k benchmark chỉ nghiệm thu khi quyền và tài nguyên được xác minh.

## Các phase

1. Data: adapter streaming JSONL/CSV, deterministic, manifest/checksum/byte cap; staged import và posted_year; kiểm thử mappings/ETL.
2. RBAC: admin users/audit strict schemas; khóa Mongo fail-closed tuần tự hóa mutations để giữ last-admin trên standalone Mongo; epoch session; frontend guard.
3. UI: CSS dark/elevation, components chung, source/role badges, admin screens; giữ ECharts 2D, không thêm dependency/WebGL.
4. Regression/P1: filters toàn dataset, comparison theo version, exports, browser ba role/ba viewport; cập nhật báo cáo bằng kết quả thật.

Chi tiết files changed/reuse/tests/limitations từng phase: `upgrade-results.md`.
