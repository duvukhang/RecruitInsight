# Kịch bản demo RecruitInsight 2.0

Thời lượng gợi ý 12–15 phút. Tất cả fixture/generator trong repo là **DEMO tổng hợp**, không đại diện thị trường. Public pilot chỉ dùng khi có bằng chứng quyền hợp lệ; hiện còn NEEDS_REVIEW.

Bản đang chạy đã có [hồ sơ cá nhân](profile.md) ở avatar góc phải trên và DEMO đa ngành 50.000 raw / 49.046 clean / 10 ngành / 8 địa phương. Nếu chạy lại `e2e.py` bên dưới, active dataset/model sẽ chuyển sang fixture 1.000 dòng; chạy `python scripts/activate_expanded_demo.py` cuối cùng để trở về DEMO 50k. Không nhầm dataset active với benchmark 500k hoặc dữ liệu public.

1. Khởi động theo README, giữ `.env`/volumes. ADMIN đăng nhập `http://localhost:8080` bằng cấu hình cục bộ. Mở tổng quan: version/nguồn/giấy phép, N tin/nhãn, median, ngành/kỹ năng, mô hình active và ETL gần nhất (theo quyền). Không trình bày lịch sử là thị trường hiện tại.
2. Mở Quản lý dữ liệu. Để kiểm chứng adapter mà không dùng corpus public, dùng fixture `tests/fixtures/tinix-shape.synthetic.jsonl` và lệnh chuẩn bị trong [hướng dẫn import](real-data-import.md). Chọn JSONL chuẩn, nhập nguồn có nhãn SYNTHETIC/DEMO, xác nhận preview/quyền rồi upload. Có thể dùng các chunk 50k do `scripts.measure_adapter` tạo; chỉ chọn `chunk-*.jsonl`, không chọn input nguồn chưa map.
3. Đợi RAW_READY, chạy ETL, xem Giám sát ETL. Mở Chất lượng dữ liệu, chọn version: raw = invalid + duplicate + clean; missing fields, label coverage, parse statuses, độ phủ nguồn/năm. Giải thích tỷ lệ nhãn hợp lệ cho ML chưa thay điều kiện dataset/split. Version không đạt gate không đổi active pointer.
4. Chọn version đã publish, lọc địa phương/ngành/ngày; với nguồn chỉ có năm, xem biểu đồ năm và giải thích trends tháng rỗng. Jobs search title/company, salary/experience/employment/year/sort, mở detail. Phân trang dùng cursor được ký/bind scope; đổi filter về trang đầu. Truy cập Nguồn dữ liệu để so hai phiên bản riêng và tải JSON report.
5. Chọn version đủ ≥200 usable labels/≥10 companies, ADMIN train; xem validation selection, baseline, MAE/RMSE/R², N train/validation/test và nguồn/version. Active winner đủ điều kiện. Dự đoán một trường hợp, xem lịch sử cá nhân; MAE không phải confidence interval. Fixture 100 dòng không đủ gate, không thêm công ty giả để vượt gate.
6. Tạo ANALYST và VIEWER tại Người dùng bằng mật khẩu riêng đáp ứng policy. ANALYST xem registry/diagnostics/prediction, không upload/train/users. VIEWER chỉ analytics/jobs; mở trực tiếp `/users` hoặc `/predictions` phải ra 403; backend vẫn từ chối khi gọi API trực tiếp.
7. ADMIN đổi role, khóa tài khoản hoặc thu hồi phiên. Phiên cũ bị từ chối và phải đăng nhập lại; xem Nhật ký quản trị. Không tự khóa chính mình; admin cuối cùng không thể bị hạ quyền/khóa. Demo reset password dùng confirmation, không chiếu/ghi mật khẩu vào log/báo cáo.
8. Trình bày bảng benchmark snapshot mới trong [báo cáo](reports/upgrade-results.md): 36 observations, source/input hashes và counts/checksum. Phân biệt local/cluster overhead, containers cùng máy, cache không kiểm soát, workload không gồm Mongo write/ML và chưa đo peak RAM.

## Tái lập các kiểm chứng thực

```powershell
docker compose build backend frontend
docker compose up -d --scale spark-worker=2
docker compose run --rm test-backend
docker compose exec -T -e RUN_SPARK_TESTS=1 -e MONGO_DATABASE=recruitment_test etl-worker python -m pytest -q tests/test_etl.py
python scripts/e2e.py --rows 1000
python scripts/verify_upgrade.py
npm.cmd --prefix frontend test -- --configLoader runner
npm.cmd --prefix frontend run test:e2e
```

Hai script HTTP tạo dataset có nhãn synthetic, training artifacts và prediction để kiểm chứng; `e2e.py` có activate model/dataset mới, nên chạy trong phiên demo đã chọn. `verify_upgrade.py` phục hồi active dataset trước staged test và disable users test, không xóa audit. Không chạy đồng thời Spark integration/ETL/training với benchmark cần đủ executors. Các lần login dùng chung limiter; tách các suite nếu đã gần 10 lần/phút, không tắt limiter để test.

Browser fixture riêng: từ `frontend` chạy `npx.cmd playwright test --config playwright.research.config.ts`. Đây là UI fixture có nhãn TEST, không thay E2E Docker. Ảnh desktop/mobile ba role, source/quality/users nằm trong `artifacts/upgrade-2-live-*.png`; artifacts ignored cần lưu kèm khi bàn giao.
