# Phase 5 — Analytics

18/10/2026: Spark tính overview, percentiles, phân nhóm industry/province/experience/company, skills, monthly trends và salary histogram; Mongo lưu snapshots theo attempt đã publish. API đọc snapshot mặc định, dùng Mongo aggregation có maxTimeMS cho filter chọn lọc. Không cộng median giữa các nhóm. Metadata gồm version, DEMO, sample/eligible counts, missing salary rate, đơn vị và phương pháp percentile approximate.

`docker compose run --rm test-backend`: **23 passed, 2 skipped**. Hai Spark integration tests đã chạy riêng ở Phase 4; test Mongo aggregation kiểm tra province+industry filter, coverage 50%, salary mean đúng, skill counts và empty result. Mã nguồn: application/analytics.py, api/analytics.py, tests/test_analytics.py; evidence artifacts/tests-phase5.log.

Giới hạn hiện tại: filters backend đang hỗ trợ version/province/industry/date; chưa có mọi tổ hợp UX trong master prompt. Snapshot group top 100, skills top 30, trends 120 tháng; giới hạn được công khai ở code. Mọi nhận xét về thị trường phải dựa nguồn thật; dataset synthetic luôn đánh dấu DEMO.
