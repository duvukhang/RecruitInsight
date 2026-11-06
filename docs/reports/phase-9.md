# Phase 9 — Kiểm chứng hệ thống

> Bằng chứng lịch sử ngày 18–19/10/2026, không phải kết quả chạy lại source nâng cấp 05/11/2026. Xem [audit và trạng thái kiểm chứng mới](research-upgrade.md).

Các phép chạy dưới đây thực hiện ngày 18/10/2026; báo cáo được hoàn thiện ngày 19/10/2026. Đây là kết quả quan sát trên Docker Desktop của máy phát triển, dùng **dữ liệu DEMO tổng hợp seed 42**, không phải dữ liệu thị trường. Những báo cáo phase trước giữ nguyên bối cảnh của lần chạy lúc đó.

## Kết quả theo năm trọng tâm

| Nội dung | Bằng chứng đã chạy | Kết quả |
| --- | --- | --- |
| Big Data | Spark standalone, hai workers/executors; workload có UDF, window/shuffle và aggregate; benchmark ba quy mô | Counts/checksum khớp. 100k dòng: local[1] 4.086s; cluster hai executors 2.805s, khoảng 1.46×. [Phương pháp và giới hạn](benchmark.md). |
| ETL | Upload → ingestion → Raw → Spark → Clean/errors/duplicates → quality gate → Analytics | 1.000 raw = 954 clean + 17 duplicate + 29 invalid. Dataset có 867 nhãn lương hợp lệ. |
| Machine Learning | Company-group split, baseline và nhiều regressors, holdout predictions, artifacts, active model, API prediction | Sáu mô hình được lưu; sáu MLflow runs FINISHED và hash model artifacts đối chiếu thành công. |
| MongoDB | Validators, unique/compound/TTL indexes, aggregation, immutable versions và active pointers | Query có index kiểm tra 325 docs thay vì natural scan 1.948 docs, cùng trả 325 kết quả trong lần đo. Connector đọc 954 rows qua bốn partitions. |
| Full-stack & Docker | Giao diện React gọi API qua nginx, auth/roles, workers, volumes, Chrome E2E | Đăng nhập, dashboard/filter, jobs, prediction/history, datasets, model registry và responsive mobile chạy thành công. |

Dataset kiểm chứng chính: `cbc3ee9d-577b-4265-813f-d07cc78957de`. Spark ETL application `app-20261018145115-0002` ghi nhận hai executors, thời gian job 15.380s. Thời gian này thuộc ETL đầy đủ của fixture 1.000 dòng; không trộn với thời gian benchmark chỉ đo Spark action.

## Đánh giá mô hình

MAE/RMSE tính bằng VND/tháng, làm tròn đến đồng. Tập train/validation/test chia theo doanh nghiệp, không để doanh nghiệp xuất hiện ở nhiều tập. Preprocessing được fit trên train. Local models dùng reservoir sample tối đa 10k nhãn; fixture này nhỏ hơn giới hạn đó.

| Mô hình | Validation MAE | Test MAE | Test RMSE | Test R² |
| --- | ---: | ---: | ---: | ---: |
| Dummy median | 8.355.172 | 7.932.906 | 9.060.760 | -0.0004 |
| Ridge | 1.572.476 | 1.435.594 | 1.941.264 | 0.9541 |
| Random Forest | 1.664.051 | 1.645.848 | 2.159.969 | 0.9432 |
| Gradient Boosting | **1.536.390** | 1.465.503 | 1.971.769 | 0.9526 |
| XGBoost CPU | 1.613.366 | 1.530.135 | 2.066.048 | 0.9480 |
| Spark MLlib LinearRegression¹ | 1.736.559 | 1.835.838 | 2.410.353 | 0.9292 |

¹ Spark numeric là nhóm thí nghiệm riêng: chỉ feature experience, dùng toàn bộ rows thuộc doanh nghiệp train. Khác feature/training size với local models nên không quy chênh lệch metrics hoàn toàn cho thuật toán.

**Gradient Boosting được chọn bằng validation trước khi đánh giá test.** Ridge có test MAE tốt hơn nhưng không dùng holdout để chọn lại winner. Active model: `dfce50bf-e6c2-44b6-8cd4-9a76216073ac`. Fixture prediction Data Engineer, Hồ Chí Minh, 5 năm kinh nghiệm trả 20.544.291 VND/tháng; có model version, dataset version, cảnh báo DEMO và history trong MongoDB. Đây là kiểm chứng inference, không phải tư vấn mức lương thực tế.

## Kiểm thử và phục hồi

| Kiểm tra thực tế | Kết quả | Evidence trong thư mục `artifacts/` |
| --- | --- | --- |
| Backend suite | 31 passed, 2 Spark tests skipped để chạy riêng | `tests-accepted.log` |
| Spark tests trong worker, Mongo test DB riêng | 2 passed; kiểm tra counts/median/publication và quality failure giữ pointer cũ | `tests-spark-final.log` |
| Frontend unit | 2 passed; lỗi đăng nhập và refresh đồng thời | `frontend-unit-handover.log`; source `frontend/src` |
| Chrome E2E | 1 passed, 4.4s tổng; mobile width 390 không tràn ngang toàn trang | `browser-final.log`, `dashboard.png`, `dashboard-mobile.png`, `dashboard-prediction.png` |
| Upload/ETL/train/activate/predict qua HTTP | PASS, sáu mô hình | `e2e-final.log`, `e2e-result.json` |
| SIGKILL ETL worker giữa job 10k | PASS, lease hết hạn và retry một lần; published attempt mới có đúng 9.546 clean + 183 duplicate + 271 invalid | `recovery-result.json` |
| Restart core/MLOps | PASS, predictions giống trước restart và history còn nguyên | `persistence-result.json` |
| CSV exports | 954 clean, 17 duplicate, 29 invalid đúng dataset/attempt | `persistence-result.json` |
| MLflow artifact verification | PASS, sáu runs và model SHA-256 khớp | `mlflow-result.json` |
| Backup/isolated restore | PASS, 20 collections; file hashes/counts và prediction parity đúng | `backups/d60c41ee-a21e-4287-a360-a38a1446fd28/manifest.json`, `restore.log` |
| Kafka/Structured Streaming | 22 events → 20 clean + 1 duplicate + 1 invalid; checkpoint restart và event replay đã chạy | `streaming-result.json`, `stream-replay-result.json` |
| Mongo Spark connector 10.7.0 | PASS, phân vùng thực [238, 239, 239, 238] | `mongo-spark-connector.log` |
| Runtime dependency lock | PASS, 46 packages đúng lock, Python 3.11.11/Java 17 | `runtime-environment.json` |
| Kiểm tra Docker logs với credentials cấu hình/JWT pattern | PASS, không có matches trong phạm vi logs đã quét | `log-scan.json` |

Streaming dùng at-least-once delivery với checkpoint, immutable microbatch versions và event-ID ledger idempotent. Khi replay 22 IDs, batch sau có 0 clean + 21 duplicate + 1 invalid; active dataset cũ được giữ. Không tuyên bố exactly-once toàn hệ thống.

Backup khôi phục vào database `recruitment_verify_restore` và thư mục files riêng, không ghi đè production database. Job recovery dùng attempt fencing: các rows của attempt cũ không được cộng vào snapshot đã công bố.

## Môi trường và những sửa lỗi đã xác minh

Docker Engine 29.4.1, VM 16 CPU/khoảng 7.57 GiB RAM; Spark 3.5.7, Python 3.11.11, MongoDB 8.0.9. Hai Spark workers mỗi worker một core; executor memory 1 GiB. Python host 3.13 chỉ chạy các scripts thư viện chuẩn. Exact dependency versions nằm trong lock và runtime artifact.

Các lỗi đã sửa trong quá trình chạy gồm tải PySpark timeout (cache/retry), healthcheck nginx IPv6 localhost, DNS upstream sau backend restart, Mongo audit validator, schema/connection của Spark test executors, Unicode khi sinh tài liệu bằng PowerShell và refresh token đồng thời. Lần cuối bổ sung CSRF logout check, kiểm tra kiểu dữ liệu salary, metadata DEMO cho CSV downloads và tách bộ lọc dataset huấn luyện khỏi dashboard. Backend tests, frontend build và Chrome E2E sau cập nhật đều pass.

Giao diện có Tailwind, Radix/CVA Button, ECharts, trạng thái tải/lỗi và nhãn nguồn dữ liệu. Đã xem ảnh desktop/mobile sau build cuối. Vite vẫn cảnh báo ECharts chunk trên 500 kB; đây là mục tối ưu tải tiếp theo. Backend có một deprecation warning từ Starlette/AnyIO trong tests; không làm sai kết quả kiểm thử.

## Giới hạn bằng chứng

Chưa kiểm chứng cold-start trên một máy khác, tải đồng thời lớn, peak RAM toàn stack, benchmark một triệu dòng, cluster nhiều máy hoặc HA. Số đo index và benchmark là observations của lần chạy cụ thể; không bảo đảm lặp lại đúng latency trên mọi máy. Các kiểm tra phục hồi chưa bao phủ mọi tổ hợp lỗi broker/network/driver cùng lúc.

Dữ liệu hiện tại chỉ DEMO thuộc ngành IT; metrics cao không chứng minh khả năng tổng quát cho thị trường. Chưa có nguồn tuyển dụng thực được cấp quyền, temporal backtest hay prediction interval được hiệu chuẩn. [Bàn giao và phạm vi mở rộng](phase-10.md).

## Kiểm tra bàn giao ngày 19/10/2026

Các containers đã dừng qua đêm được khởi động lại bằng core + MLflow Compose, giữ nguyên volumes. MongoDB, backend, frontend, Spark master/hai workers, ETL/training workers và MLflow đều healthy. Frontend unit chạy lại 2 passed; Chrome E2E chạy lại 1 passed trong 4.9s. HTTP readiness trả ready; active model được giữ; CSV exports có đúng 954/17/29 rows, `dataset_version`, `is_demo=True` và tên file có tiền tố DEMO. Evidence mới: `start-handover.log`, `frontend-unit-handover.log`, `browser-handover.log`, `handover-result.json`. OpenAPI được xuất lại từ backend đang chạy.
