# Phân tích dữ liệu tuyển dụng và dự đoán mức lương

Recruitment Data Analytics and Job Salary Prediction System. React/FastAPI/MongoDB, Spark ETL và ML chạy ở worker riêng, triển khai bằng Docker Compose.

## RecruitInsight 2.0

Nhánh `feat/recruitinsight-real-data-rbac-ui` bổ sung quản lý người dùng/audit, thu hồi phiên, route guards/403, giao diện dark có CSS depth và reduced motion, quality theo phiên bản, so sánh nguồn và staged JSONL. Luồng ETL/ML, upload 50 MiB và dữ liệu hiện có được giữ.

- [Audit/baseline](docs/reports/upgrade-audit.md), [test report và giới hạn](docs/reports/upgrade-results.md), [changelog](CHANGELOG.md).
- [Adapter, quyền nguồn, snapshot và staged import](docs/real-data-import.md).
- [Ma trận RBAC và vận hành quản trị](docs/admin-users.md).
- [Kịch bản demo 2.0 và lệnh kiểm chứng](docs/demo-2.md).

**Nguồn public hiện NEEDS_REVIEW**: đã kiểm dataset cards nhưng chưa xác minh đủ quyền với nội dung gốc. Không tự tải corpus hoặc ghi nhãn REAL_VERIFIED. Các demo/benchmark tạo trong phiên nâng cấp đều là dữ liệu tổng hợp, không phải quan sát thị trường hiện tại.

Sau build/start theo hướng dẫn bên dưới, ADMIN mở **Người dùng**, **Nhật ký quản trị**, **Nguồn dữ liệu**, **Chất lượng dữ liệu** từ sidebar. ANALYST xem mô hình/dự đoán; VIEWER chỉ xem analytics/jobs. Không tạo mật khẩu demo hardcode.

## Bài toán và phạm vi nghiên cứu

Hệ thống mô tả **các tin tuyển dụng trong tập dữ liệu quan sát**, ước lượng **midpoint lương công bố theo tháng VND** từ thông tin công việc và kiểm chứng workload Spark ở các quy mô xác định. Số tin không phải tổng nhu cầu lao động, lương công bố không phải bảo đảm lương thực nhận, và kết quả DEMO không đại diện cho Việt Nam.

[Phát biểu bài toán, input/output, giả thuyết và tham khảo](docs/architecture.md) · [Quy tắc dữ liệu/nhãn/split/metrics](docs/pipelines.md) · [Audit, thay đổi, PASS/BLOCKED và kịch bản bảo vệ](docs/reports/research-upgrade.md).

Lần rà soát 05/11/2026 giữ kiến trúc và API hiện có, bổ sung metadata nguồn tùy chọn, phân biệt missing experience với 0 năm, đo quality thay vì hardcode, group salary statistics và error slices. Các số đo ở phần bằng chứng lịch sử bên dưới thuộc source ngày 18/10; **chưa chạy lại Spark/Mongo E2E của source mới vì Docker daemon không khả dụng**. Không dùng số đo cũ để nghiệm thu hiệu năng code mới.

## Khởi động

Cần Docker Desktop chạy Linux containers/WSL2. Lần build đầu cần Internet. Trong thư mục dự án, chạy PowerShell:

```powershell
./scripts/setup.ps1
```

Nếu PowerShell chặn chạy script, dùng `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1` cho lần chạy này.

Script tạo `.env` với secrets ngẫu nhiên nếu chưa có, build và start core stack với hai Spark workers. Nếu tự tạo `.env` từ `.env.example`, điền đầy đủ các biến trống.

- **Giao diện: http://localhost:8080**
- Swagger: http://localhost:8080/docs
- Spark Master UI: http://localhost:8081
- Đăng nhập bằng `ADMIN_USERNAME` và `ADMIN_PASSWORD` trong `.env` cục bộ. Không có mật khẩu mặc định; không commit `.env`.

Dữ liệu mẫu là **DEMO tổng hợp**, không đại diện thị trường lao động thực. Generator cũ giữ seed 42; bộ DEMO mở rộng dùng seed 2026, 10 ngành, 240 doanh nghiệp giả lập và 8 địa phương. Hệ thống cho phép upload dataset thật khi có quyền sử dụng.

**Hồ sơ cá nhân:** bấm avatar góc phải trên hoặc mở http://localhost:8080/profile để sửa thông tin, đổi mật khẩu và quản lý các phiên đăng nhập. Xem [hướng dẫn hồ sơ](docs/profile.md).

**Giao diện sáng/tối:** bấm nút mặt trời/mặt trăng cạnh avatar (hoặc trên màn hình đăng nhập). Lựa chọn được lưu trên trình duyệt và đồng bộ giữa các tab; mặc định là chế độ tối.

Để tạo và công bố DEMO mở rộng qua upload → ingestion → Spark ETL → training/activation thật (cần Docker đã chạy và `.env` có tài khoản ADMIN), chạy `python scripts/activate_expanded_demo.py`. Lệnh này chuyển dataset/model đang active sang bản DEMO mới, không xóa bản cũ; file CSV nằm trong `data/` đã được gitignore. Bộ 50.000 dòng tạo ra 49.046 tin sạch, 438 trùng, 516 không hợp lệ với seed mặc định. Đây là dữ liệu mô phỏng, không phải corpus public.

## Môi trường Python venv và cài thư viện

Dùng **Python 3.11** để đồng nhất với backend/Spark trong Docker. Chạy các lệnh tại thư mục gốc `D:\HK7\BigData\RecruitInsight`. Windows Terminal và terminal trong VS Code có thể mở PowerShell, CMD hoặc Git Bash; chọn đúng nhóm lệnh theo shell đang sử dụng.

File cài đặt là [requirements.txt](requirements.txt), tham chiếu toàn bộ 46 thư viện đã khóa phiên bản trong [backend/requirements.lock](backend/requirements.lock). Các thư viện chính gồm FastAPI, Uvicorn, PyMongo, Pydantic, PyJWT, Argon2, PySpark, NumPy, SciPy, scikit-learn, XGBoost CPU, Matplotlib, HTTPX và pytest. Không cần cài từng thư viện bằng tay.

### PowerShell — Windows Terminal hoặc VS Code

```powershell
cd D:\HK7\BigData\RecruitInsight
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python --version
```

Nếu PowerShell báo không cho chạy `Activate.ps1`, có thể cài trực tiếp bằng Python của venv, không cần kích hoạt:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

### Git Bash trên Windows

```bash
cd /d/HK7/BigData/RecruitInsight
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python --version
```

### CMD — Command Prompt

```bat
cd /d D:\HK7\BigData\RecruitInsight
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python --version
```

Nếu `py -3.11` không tìm thấy interpreter, cài Python 3.11 trước; có thể thay bằng `python -m venv .venv` khi `python --version` đã là 3.11. Chỉ tạo venv một lần; mỗi terminal mới chỉ cần chạy lại lệnh kích hoạt tương ứng. Dùng `deactivate` để thoát. Thư mục `.venv/` đã được gitignore. Trong VS Code, chọn **Python: Select Interpreter → .venv\Scripts\python.exe**.

Các dependency pins đã được kiểm chứng trong container Linux Python 3.11; cài toàn bộ trên Windows là môi trường phát triển bổ sung. Spark chạy local cần Java 17 và `JAVA_HOME`; luồng phân tán của đồ án vẫn nên chạy bằng Docker Compose. Nếu chỉ chạy hệ thống qua Docker, không bắt buộc tạo venv trên host vì image đã cài thư viện.

### Thư viện frontend và chạy hệ thống

Frontend dùng Node.js/npm, cài riêng bằng `package-lock.json`, không cài bằng pip. Trên Git Bash hoặc CMD:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

Trên PowerShell dùng `npm.cmd --prefix frontend ci` và `npm.cmd --prefix frontend run build` nếu `npm.ps1` bị execution policy chặn. Chỉ cần cài Node.js khi build/test frontend trên host; Docker tự build frontend trong image.

Khởi động toàn bộ ứng dụng từ PowerShell/CMD:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Từ Git Bash:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Script tạo `.env` nếu chưa có và chạy Docker stack. Sau khi khởi động, mở http://localhost:8080. Không cần chạy thêm backend/frontend trên host để sử dụng giao diện này.

Khi sửa giao diện và muốn Vite tự cập nhật, giữ Docker stack đang chạy rồi mở terminal khác:

```bash
npm --prefix frontend run dev
```

Mở URL Vite hiển thị (thường http://localhost:5173). Vite chuyển `/api` qua `http://127.0.0.1:8080` tới backend trong Docker; cần giữ service `frontend` của Docker chạy để làm API proxy. Backend cổng 8000 chỉ ở mạng nội bộ Docker. Nếu đăng nhập báo “Dịch vụ đang gián đoạn”, kiểm tra `docker compose ps` và thử http://localhost:8080 trước.

## Demo

```powershell
python scripts/generate_demo.py --rows 10000 --output data/DEMO-jobs.csv
```

1. **Quản lý dữ liệu**: upload CSV/JSON/JSONL, nhập nguồn; giữ nhãn DEMO cho dữ liệu tổng hợp.
2. Đợi `RAW_READY`, bấm **ETL**; theo dõi job ở **Giám sát ETL**.
3. Khi quality gate đạt, mở **Dashboard**, chọn dataset version và bộ lọc.
4. Xem quality report, bản ghi lỗi/trùng và tải CSV để đối soát.
5. **Machine Learning**: chọn published dataset, huấn luyện, so sánh validation/holdout và active model vượt baseline.
6. **Dự đoán mức lương**: gửi form; kết quả/model version/lịch sử được lấy từ API và lưu MongoDB.

Training cần ít nhất 200 nhãn hợp lệ và 10 doanh nghiệp độc lập. Các cột CSV chuẩn: `source_job_id,job_title,company_name,province,industry,experience_years,salary,salary_currency,posted_at,skills,remote_type`. JSON/JSONL dùng cùng tên trường; skills có thể là array. Salary thiếu không bị đổi thành 0. Ngoại tệ/giờ/ngày cần tỷ giá có nguồn/ngày và giả định thời gian trong **Hệ thống**; cấu hình đóng băng theo dataset version.

## Năm trọng tâm đã triển khai

| Nội dung | Triển khai và bằng chứng thực |
| --- | --- |
| Big Data | Spark standalone hai executor; normalize/window/shuffle. Benchmark 100/10k/100k, warm-up và 3 lần đo. 100k: local 4.086s, hai executors 2.805s; [báo cáo](docs/reports/benchmark.md). |
| ETL | Raw → validation/normalization/dedup → clean → quality gate → snapshots. 1.000 DEMO → 954 clean; lỗi/trùng có collections và CSV reports. Kill worker giữa job 10k → retry bằng attempt mới, không cộng trùng kết quả công bố. |
| ML | Dummy, Ridge, Random Forest, Gradient Boosting, XGBoost CPU và Spark MLlib LinearRegression. Group split theo doanh nghiệp, chọn bằng validation; holdout predictions/metrics, artifact hashes và 6 MLflow runs đã xác minh. |
| MongoDB | Validators, unique/compound/TTL indexes, bulk upsert, aggregation và version pointers. Cùng query: natural scan 1.948 docs vs index scan 325 docs, cùng 325 kết quả. Mongo Spark connector đọc 954 rows qua 4 partitions. |
| Full-stack & Docker | Chín trang React, JWT/roles/refresh, API thật, workers riêng, persistent volumes. E2E HTTP/Chrome, ảnh desktop/mobile và [báo cáo kiểm chứng](docs/reports/phase-9.md). |

Benchmark đo read/normalize/dedup/aggregate, chưa gồm Mongo write; chạy nhiều containers trên một máy, không phải nhiều máy vật lý. Dữ liệu nhỏ cluster chậm hơn do overhead. Giữ observations/checksum/physical plans, không tự điền số liệu.

Local models dùng reservoir sample seed 42, tối đa 10k labels, cùng company-group split. Spark numeric dùng full dữ liệu thuộc doanh nghiệp train, chỉ có feature experience; đây là thí nghiệm scale riêng. Không so khác features/training size rồi kết luận chỉ do thuật toán. Không hiển thị confidence % hoặc interval chưa hiệu chuẩn.

## Profiles

MLflow (SQLite chỉ giữ metadata MLOps, business registry ở MongoDB):

```powershell
docker compose -f docker-compose.yml -f docker-compose.mlops.yml --profile mlops up -d --scale spark-worker=2
```

Mở http://localhost:5000. Training worker ghi metrics/artifacts qua MLflow REST.

Kafka + Spark Structured Streaming:

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml --profile streaming up -d --scale spark-worker=2
python scripts/streaming_e2e.py
python scripts/stream_replay.py
```

Checkpoint ở volume; immutable microbatch version và event-ID ledger chống replay. Tối đa 100 events/trigger được materialize để ingestion có giới hạn; Spark batch worker xử lý cleaning/dedup/analytics tiếp theo. At-least-once + idempotent sink. Nếu bật cả hai profiles, truyền cả ba compose files cùng `--profile streaming --profile mlops`.

## Kiểm thử

```powershell
docker compose run --rm test-backend
docker compose exec -e RUN_SPARK_TESTS=1 -e MONGO_DATABASE=recruitment_test etl-worker python -m pytest -q tests/test_etl.py
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run test:e2e
```

Hai Spark tests chạy riêng trong etl-worker để executor phân giải đúng driver. Tests Mongo dùng `recruitment_test`, có chốt bảo vệ cleanup. Playwright dùng Chrome trên host; ứng dụng/compute vẫn trong containers. Browser fixture dùng dataset tạo bởi `python scripts/e2e.py --rows 1000`.

```powershell
python scripts/e2e.py --rows 1000
python scripts/check_mlflow.py
python scripts/failure_recovery.py
python scripts/verify_runtime.py
```

`failure_recovery.py` chủ động kill ETL worker của dự án; `verify_runtime.py` restart core/MLOps để kiểm tra persistence. Chạy khi không có tác vụ khác cần giữ. Kết quả thực được ghi trong `artifacts/` (ignored), không log tokens/mật khẩu.

Benchmark, sau khi dừng streaming/compute khác để đủ hai executors:

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml stop streaming-worker
docker compose exec etl-worker python -m bigdata.benchmark --sizes 100 10000 100000 --repeats 3
```

## Vận hành

### Xem database bằng MongoDB Compass

MongoDB của đồ án được mở ở **127.0.0.1:27018** trên host (cổng trong Docker vẫn là 27017), tránh trùng với MongoDB local thường dùng cổng 27017. Trong Compass, chọn **Add new connection**, nhập URI:

```text
mongodb://127.0.0.1:27018/recruitment_bigdata?authSource=recruitment_bigdata&directConnection=true
```

Ở **Authentication → Username / Password**, nhập username theo `MONGO_APP_USER` và password theo `MONGO_APP_PASSWORD` trong `.env`; Authentication Database là `recruitment_bigdata`. Chỉ lấy giá trị sau dấu `=`, không dùng mật khẩu đăng nhập web. Bấm **Connect**, mở database **recruitment_bigdata** để xem các collections như `raw_jobs`, `cleaned_jobs`, `datasets`, `model_registry`, `salary_predictions`.

Nếu chọn tài khoản root để quản trị, dùng `MONGO_ROOT_USER` / `MONGO_ROOT_PASSWORD` và đổi Authentication Database thành **admin**. Cổng chỉ bind localhost. Sau khi thay đổi mapping, áp dụng bằng `docker compose up -d mongodb`; volume dữ liệu được giữ nguyên.

```powershell
docker compose logs --tail 100 backend etl-worker training-worker
docker compose exec backend python -m recruitment.cli etl submit --dataset-version <version>
docker compose exec backend python -m recruitment.cli models train --dataset-version <version>
docker compose exec backend python -m recruitment.cli users create --username analyst --role ANALYST
```

Lệnh users hỏi mật khẩu qua prompt. Backup/restore vào database/files riêng, từ chối ghi đè database đã có:

```powershell
./scripts/backup.ps1
./scripts/restore.ps1 -Manifest artifacts/backups/<backup-id>/manifest.json -Database recruitment_verify_restore
```

Backup cần queue trống và không có yêu cầu ghi trong lúc chụp; script dừng compute tạm thời. Archive giữ Mongo BSON, validators/indexes và uploads/artifacts/events/checkpoints. Restore xác minh SHA-256, counts và prediction parity; không tự chuyển ứng dụng sang bản restore.

Dừng toàn bộ mà giữ volumes:

```powershell
docker compose -f docker-compose.yml -f docker-compose.streaming.yml -f docker-compose.mlops.yml --profile streaming --profile mlops stop
```

## Source và tài liệu

- `backend/src/recruitment`: API, application services, domain rules, ports, Mongo/security/config.
- `bigdata`, `machine_learning`, `workers`: ingestion/ETL/streaming/benchmark, train/evaluate/serve/track, queue/lease/fencing/recovery.
- `frontend`: React/TypeScript/Vite, Router, Query, RHF/Zod, ECharts, Tailwind và shadcn-style Radix/CVA Button.
- `infrastructure`, `scripts`, `tests`: images/init, vận hành và kiểm chứng.
- [Kiến trúc](docs/architecture.md), [MongoDB](docs/database.md), [ETL/ML](docs/pipelines.md), [API thiết kế](docs/api-contract.md), [roadmap](docs/roadmap.md).
- [Phase 2](docs/reports/phase-2.md), [3](docs/reports/phase-3.md), [4](docs/reports/phase-4.md), [5](docs/reports/phase-5.md), [6](docs/reports/phase-6.md), [7](docs/reports/phase-7.md), [8](docs/reports/phase-8.md), [kiểm chứng cuối](docs/reports/phase-9.md), [bàn giao](docs/reports/phase-10.md).

Phase 1 là thiết kế ban đầu; Swagger runtime là nguồn chính xác cho API hiện có. Báo cáo cuối phân biệt tính năng đã kiểm chứng và phần mở rộng. Spark chạy Python 3.11 trong container; Python 3.13 của host chỉ dùng cho các scripts thư viện chuẩn.
