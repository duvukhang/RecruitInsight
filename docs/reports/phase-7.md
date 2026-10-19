# Phase 7 — Frontend

18/10/2026: chín trang React/TypeScript đã nối API thật: dashboard, tuyển dụng, lương, jobs, prediction/history, upload datasets/quality, ETL polling/retry/cancel, models train/metrics/active và system status. TanStack Query, React Router, ECharts, RHF/Zod, Lucide; CSS responsive cục bộ. Không publish lên Sites vì kiến trúc chạy qua Docker Compose.

Kiểm tra: Vite/TypeScript production build PASS; Vitest/RTL test refresh thất bại → login → lỗi mật khẩu PASS; Playwright **1 passed (3.4s)** trên Chrome thật, xác minh dashboard 954 records, filter Hà Nội, job list, dự đoán API/history, dataset/model screens, desktop/mobile screenshots và không horizontal overflow ở viewport 390px. Đã xem ảnh `artifacts/dashboard.png`, `dashboard-mobile.png`, `dashboard-prediction.png`.

Lỗi thực: Playwright 1.52 treo ở Node 24; cập nhật/pin 1.64.1 rồi browser test pass. Một lỗi TypeScript trong test RTL đã sửa trước build cuối. Build còn warning chunk >500kB; tiếp tục chia bundle khi hoàn thiện. Test UI synthetic mock chỉ dùng cho trạng thái lỗi login; browser E2E dùng API/containers thực, không mock dữ liệu nghiệp vụ.

Giới hạn: CSS hiện dùng native CSS thay Tailwind/shadcn; chưa có toàn bộ tính năng export/settings nâng cao. Không coi sự có mặt của chín trang là bằng chứng mọi yêu cầu phụ đã hoàn tất. Bắt đầu bổ sung streaming/MLOps và performance evidence.
