# Changelog

## RecruitInsight 2.0 — 07–08/11/2026

- Nút chuyển sáng/tối ở thanh trên và màn hình đăng nhập, lưu lựa chọn trong trình duyệt và đồng bộ giữa các tab. Chế độ sáng áp dụng cho dashboard, bảng, biểu đồ, profile và hộp thoại; hỗ trợ điện thoại và bàn phím.
- Tinh gọn giao diện: bỏ mô tả/lưu ý dài, phụ đề giải thích thừa trên dashboard, phân tích, nguồn, chất lượng, cấu hình và hồ sơ; bỏ footer kỹ thuật và các dòng nguồn/giấy phép/trạng thái/version quanh bộ lọc, hero và chân dashboard. Giữ dữ liệu quản trị nguồn, lỗi và xác nhận thao tác.
- Hồ sơ cá nhân cho ba vai trò: tên hiển thị, email liên hệ, tổ chức, giới thiệu, màu avatar, đổi mật khẩu và thu hồi mọi phiên; API strict schema, audit không chứa thông tin hồ sơ/mật khẩu, kiểm tra mật khẩu hiện tại và rate limit.
- Dashboard mới với hero dữ liệu, hiệu ứng lớp CSS, 5 biểu đồ từ API và avatar truy cập hồ sơ; kiểm tra desktop/mobile và lưu hồ sơ qua API thật.
- DEMO đa ngành seed 2026: 50.000 raw → 49.046 clean / 438 duplicate / 516 invalid, 240 doanh nghiệp giả lập, 10 ngành, 8 địa phương; công bố và huấn luyện qua pipeline hiện hữu, có nhãn SYNTHETIC_FIXTURE.
- Adapter Tinix/VietJobs từ export CSV/JSONL cục bộ, manifest/checksum, byte caps, seed và dry-run; trạng thái nguồn NEEDS_REVIEW, không tải corpus chưa xác minh quyền.
- Staged JSONL ADMIN: chunk checksum/row count, seal, idempotency, background ingestion cùng version; giữ upload 50 MiB cũ.
- posted_year/provenance qua normalization, Spark schema, clean storage và analytics năm; hỗ trợ snapshot cũ bằng live aggregation.
- Quản trị users/audit, password policy, session epoch, last-admin mutex fail-closed và audit outbox bền vững.
- Frontend route guards/403, role-aware navigation, users/audit/source/quality screens; dark layout, CSS depth nhẹ, reduced motion, menu mobile và dialog native.
- Job company search, salary/experience/year/employment filters, sort và keyset cursor có chữ ký; comparison hai phiên bản và JSON export, scope filters trong URL. Dashboard active model/latest ETL theo role.
- Salary 40tr/upto, CSV injection guard cho whitespace, tests Mongo/Spark/API/browser và tài liệu vận hành.

Xem [audit](docs/reports/upgrade-audit.md) và [kết quả kiểm chứng](docs/reports/upgrade-results.md) để phân biệt PASS/BLOCKED; corpus public chưa đủ quyền không thuộc nghiệm thu PASS.
