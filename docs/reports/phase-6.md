# Phase 6 — Machine Learning

18/10/2026: đã triển khai baseline median, Ridge, Random Forest (cùng reservoir sample seed 42, tối đa 10k labels) và Spark MLlib LinearRegression trên full dữ liệu thuộc nhóm doanh nghiệp train. Spark numeric chỉ dùng experience, được đánh dấu thí nghiệm scale riêng, không dùng để chọn winner từ bảng so sánh local. Split theo company group, manifest IDs/hash lưu artifact; preprocess fit train; winner local được freeze từ validation trước khi đo holdout.

Backend suite: **25 passed, 2 skipped** (hai Spark tests chạy riêng). E2E HTTP qua Nginx/FastAPI/workers/Mongo/Spark: **PASS** với 1.000 raw DEMO → **954 clean**, 4 models, activate model được chọn validation, prediction **21.125.662 VND/tháng** và history lưu Mongo. Đây là kết quả synthetic DEMO, không phải ước lượng thị trường thực. Dataset version `d9f91335-62eb-412b-b378-84622b661cb6`; Spark ETL job `4d242047-b74d-4f07-a60a-590d032ce229`; training job `bc5b0376-4af3-490f-8d35-a8da23ef4192`.

Evidence: artifacts/e2e-result.json có metrics validation/test và prediction thực; artifacts/e2e.log; artifacts/tests-phase6.log. Mongo model_registry/ml_experiments và artifact volume lưu models, split/holdout JSON. Load kiểm tra root allowlist và SHA-256; Spark numeric xuất coefficients JSON để serving không phải khởi động Spark trong HTTP request. Activation kiểm tra validation MAE không kém baseline. Chưa có confidence interval nên không hiển thị % độ tin cậy.

Giới hạn: hiện có 4 algorithms trên, chưa có XGBoost/GBT, MLflow profile và slice metrics/importance UI; bổ sung trong phase hoàn thiện. Chưa có temporal experiment vì sample generator phân phối cùng company trên nhiều ngày; company-group split được ghi rõ thay vì gọi đó là dự báo tương lai. Bắt đầu Phase 7 frontend.
