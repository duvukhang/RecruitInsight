# Bổ sung hồ sơ và dashboard — 08/11/2026

Đã triển khai bản mới tại `http://localhost:8080`; hồ sơ tại `/profile`. Không sửa `.env`, không xóa dataset cũ hoặc volumes, không commit/push.

## Thay đổi

- Hồ sơ cá nhân cho ADMIN/ANALYST/VIEWER: tên hiển thị, email liên hệ, tổ chức, giới thiệu, màu avatar; tên/avatar đồng bộ topbar và sidebar sau lưu. Username và role không sửa qua API này.
- Bảo mật: xác thực mật khẩu hiện tại khi đổi, policy dùng chung với quản trị users, giới hạn 5 lần thử/phút/user, thu hồi access/refresh qua auth_version. Danh sách phiên chỉ của chính tài khoản, phân trang và whitelist; thu hồi toàn bộ gồm phiên hiện tại. Audit không chứa thông tin hồ sơ hoặc mật khẩu/token.
- Dashboard có hero với số liệu thực từ API, lớp CSS nhẹ, bố cục mới và 5 biểu đồ: thời gian, ngành, kỹ năng, địa phương, phân bố lương. Avatar ở góc phải trên dẫn tới hồ sơ trên cả desktop/mobile; không thêm thư viện.
- Frontend gia hạn token cho `/auth/profile` và các API xác thực cần bearer tương tự API dữ liệu. Chart tránh khởi tạo lại khi dữ liệu không đổi.

## Dataset đang active

`7aeabd85-8462-4ca0-af46-19cae61fa6be` — nguồn **DEMO-MULTI-50K / SYNTHETIC_FIXTURE**. Toàn bộ doanh nghiệp, lương và ngày đăng do generator tạo, không phải dữ liệu thị trường. Các nguồn public vẫn NEEDS_REVIEW.

| Chỉ số | Quan sát qua pipeline/API thật |
| --- | --- |
| Raw | 50.000 |
| Clean | 49.046 |
| Duplicate | 438 |
| Invalid | 516 |
| Doanh nghiệp giả lập | 240 |
| Ngành / địa phương | 10 / 8 |
| Tin đủ nhãn lương | 40.871 |
| Median lương công bố mô phỏng | 23.100.000 VND/tháng |
| Thời kỳ ngày đăng mô phỏng | 01/01–27/09/2026 |

Đối soát `50.000 = 49.046 + 438 + 516`. Pipeline thực chạy upload → ingestion → Spark ETL/publish → training 6 candidates → activation. ETL ghi nhận 2 executors, auto_activated=true. SHA-256 CSV: `7843e2d9f3ea3ad77f95129ba539d832676a01bf5b7af372d9dba170a7274d3c`.

Mô hình active `4a9826b5-4059-4c3f-b80d-0935dec5014c`, thuật toán `linear`, chọn bằng validation; local models dùng reservoir tối đa 10.000 nhãn như thiết kế cũ. Không gọi toàn bộ 50k là training sample của local model. Một request prediction thật trả số dương, đúng model/version và cảnh báo DEMO; chỉ là kiểm chứng serving, không xác thực giá trị dự báo thị trường.

Tái lập: `python scripts/activate_expanded_demo.py`. Lệnh này chủ động công bố và chuyển dataset/model active; không dùng khi muốn giữ nguyên active pointer. Generator cũ seed 42 và benchmark snapshot trước đây được giữ nguyên.

## Kiểm chứng đã chạy

- Backend regression: **87 passed, 3 skipped** (Spark tests yêu cầu RUN_SPARK_TESTS=1); stdout Docker pytest. Sáu ca mới kiểm tra hồ sơ ba vai trò, strict schema, ownership/projection, đổi mật khẩu/epoch, refresh rotation và rate limit. Spark ETL/training 50k chạy thật riêng như phần trên; không tính ba skipped thành PASS.
- Frontend unit: **2 passed**, gồm concurrent refresh cho API hồ sơ; TypeScript và production Docker build đạt.
- Browser fixture: **16 passed**, ba vai trò ở 390/768/1366px, route guards và scope filters.
- Live browser hồ sơ ba vai trò: **PASS**, lưu/tải lại thông tin cho tài khoản test ANALYST/VIEWER, chỉ đọc hồ sơ ADMIN; ảnh desktop/mobile/security trong `artifacts/profile-*.png`.
- Live browser bảo mật: **PASS**, sai mật khẩu bị từ chối, đổi mật khẩu cần đăng nhập lại, đăng nhập bằng mật khẩu mới, xác nhận thu hồi mọi thiết bị và đăng nhập lại.
- Bộ live cuối chạy liền trong phút mới: **3 passed / 13,5 s**, gồm luồng cũ (filters/jobs/registry/prediction), bảo mật hồ sơ và hồ sơ ba vai trò. Evidence `artifacts/profile-final-live-browser.xml`.

Lỗi kiểm thử đã chẩn đoán: selector hồ sơ trùng menu/topbar được đổi sang `.account-chip`; sau đổi mật khẩu ứng dụng giữ URL `/profile`, test đã sửa kỳ vọng. Chạy lặp các suite trong cùng phút từng chạm login limiter 10/phút; giữ nguyên limiter, tách thời điểm chạy. Đây không phải lỗi lưu hồ sơ hay đổi mật khẩu. Các tài khoản test được disable mềm trong cleanup.

Evidence: `artifacts/profile-upgrade-data.json`, `profile-live-browser.xml`, `profile-security-browser.xml`, `upgrade-2-browser.xml`; artifacts/data ignored, không commit CSV lớn hoặc thông tin đăng nhập. OpenAPI đã tái sinh từ backend: 49 paths. Email chưa có xác minh, avatar hiện dùng chữ đầu/màu và chưa hỗ trợ tải ảnh; phiên dùng User-Agent do thiết bị khai báo, cập nhật khi login/refresh.
