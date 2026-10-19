# ETL, Spark và Machine Learning

## 1. Ingestion và dữ liệu

Upload giới hạn khởi điểm 50 MiB (cấu hình được), chấp nhận CSV UTF-8/UTF-8 BOM, JSON array và JSONL; mỗi record tối đa 1 MiB. Không tin MIME/extension đơn thuần. Stream file đến vùng staging, tính SHA-256, lưu manifest rồi enqueue ingestion; không parse file lớn trong HTTP request. File upload trả 202 chỉ sau khi durable file reference và job metadata được ghi. Nếu ghi Mongo thất bại, cleanup file orphan bằng reconciler, không trả thành công giả.

Nguồn API/offline dùng adapter riêng: URL/host và offline root được allowlist, timeout/rate limit; cấm đường dẫn ra ngoài root và SSRF. Lưu source, license/permission, thời kỳ, mapping schema và is_demo. Không triển khai crawler vượt CAPTCHA. Chưa có dataset thật được cung cấp; bộ test synthetic dùng seed 42, gắn DEMO trên dataset, dashboard, exports và báo cáo model.

Raw giữ toàn bộ input kể cả lỗi parse: với dòng hỏng lưu `raw_payload.original_line` và error metadata. JSON hỏng toàn bộ file tạo run FAILED và file reference, không báo tổng record giả định. CSV có record_number ổn định theo parser và giữ raw source file; không đánh số theo partition không ổn định.

Idempotency cùng user/key và payload hash trả run cũ; cùng key nhưng payload khác trả 409. Raw unique `(ingestion_id, record_number)` giữ cả những bản trùng nội dung để audit. Cùng dataset/content/schema/pipeline config hash được nhận diện trong datasets; thay cấu hình pipeline tạo version dẫn xuất dù input không đổi. Input file persisted vào volume, không chỉ tồn tại trong filesystem tạm container.

## 2. ETL trên Spark

| Bước | Xử lý | Output và kiểm tra |
| --- | --- | --- |
| Read | Mongo connector đọc đúng raw version bằng partitioned scan | Schema tường minh, partition count, input count |
| Validate | Required title/company/source; kiểu số/ngày/URL/enum | Fatal → invalid; recoverable → normalized kèm warning |
| Clean | Unicode NFC, trim whitespace, HTML stripping, map địa phương/ngành có version, skills canonical | Giá trị gốc vẫn ở raw; không tự suy diễn trình độ/kinh nghiệm |
| Salary | Parse, chuẩn hóa tiền và kỳ hạn theo provenance | Bounds/target nullable, parse status, assumptions |
| Dedup | Stable matching, chọn canonical deterministic | Một canonical + duplicate evidence |
| Quality | Tính counts, coverage và gates | Báo cáo bất biến theo attempt |
| Analytics | Spark SQL groupBy, explode skills, time buckets, percentiles | Snapshot rows theo dimensions và manifest |
| Publish | Xác minh manifest, fencing và CAS pointer | Version hoàn chỉnh; xem thiết kế MongoDB |

Ưu tiên DataFrame/Spark SQL built-ins; UDF chỉ cho parser/quy tắc không thể thể hiện rõ bằng expressions, có unit test. Không `toPandas()` hay `collect()` toàn bộ dataset. Chỉ collect metrics nhỏ có giới hạn. Join/dedup/window có shuffle; ghi physical plan và tasks để chứng minh compute thật. Mongo writes qua connector hoặc `foreachPartition` + bounded bulk upsert, chịu được task retry.

Dedup theo thứ tự source+source_job_id, canonical URL (bỏ tracking query có allowlist), content hash, rồi business key đủ thông tin. Không gộp chỉ vì cùng title/company. Business key phải có location, employment type và posted date khi sử dụng; thiếu khóa đủ tin cậy thì giữ record và cảnh báo. Fuzzy matching là bước tùy chọn, chưa tự động gộp trong phiên bản đầu. Trong nhóm, canonical là raw record có record_number nhỏ nhất (thêm _id để tie-break). Repost across versions không xóa lịch sử; group-aware ML split vẫn bảo vệ leakage.

## 3. Chuẩn hóa lương

| Input | Quy tắc và target |
| --- | --- |
| 10–15 triệu VND/tháng | min 10m, max 15m, midpoint 12.5m |
| 20 triệu/tháng | Hai bounds 20m khi currency VND được nêu trong mapping có nguồn; nếu không xác định currency thì target null |
| 1.000 USD/tháng | Parser theo locale nguồn; FX có source/date, thiếu FX → giữ USD, target VND null |
| 15–20 USD/giờ | Nhân FX và hours_per_month đã cấu hình, ghi assumption; thiếu một trong hai → null |
| Lương năm/ngày | Chia 12 hoặc nhân days_per_month; công khai assumption |
| Up to 30 triệu | Chỉ upper bound, midpoint null |
| From 15 triệu | Chỉ lower bound, midpoint null |
| Negotiable/Competitive/không công khai | undisclosed; bounds/target null |
| Net hoặc gross | Giữ salary_basis; không tự đổi net thành gross |
| min > max, âm, số không hợp lệ | Salary invalid, không tự đảo bounds; record vẫn có thể dùng cho thống kê tin |

FX lấy từ bảng cấu hình có provenance được admin import; không mặc định tỷ giá giả. Fixture test dùng FX có nhãn TEST và ngày tham chiếu, không dùng làm tỷ giá thị trường. Không xóa silently outlier; gắn status và rule version. Trong ML ban đầu chỉ nhận GROSS hoặc UNKNOWN với thống kê tỷ lệ UNKNOWN và cảnh báo định nghĩa target; NET bị loại để không trộn basis đã biết. Nếu nghiệp vụ cần gross thuần, bật gate yêu cầu GROSS, chấp nhận giảm mẫu. Cấu hình này được lưu theo experiment.

## 4. Chất lượng và đối soát

Định nghĩa terminal outcome: invalid trước, rồi duplicate trong tập đủ điều kiện, còn lại clean. Các lỗi parser ingestion được tính vào raw và invalid của ETL. Mỗi attempt phải thỏa `N_raw = N_invalid + N_duplicate + N_clean`. Count lỗi theo field có thể lớn hơn số invalid, phải báo tách riêng. Retry không làm tăng count của attempt được công bố.

| Chỉ số | Công thức |
| --- | --- |
| Completeness | Số ô required có giá trị / (N_raw × số required fields); report thêm từng field |
| Validity | (N_raw − N_invalid) / N_raw |
| Uniqueness | N_clean / (N_raw − N_invalid) |
| Consistency | Số clean pass các quy tắc chéo / N_clean |
| Timeliness | Số clean có posted_at hợp lệ trong max_age_days / N_clean; ngày thiếu tính không đạt |
| Salary label usability | Số clean có target đủ điều kiện / N_clean |

Mẫu số 0 → null và ghi `NOT_COMPUTABLE`; không gán 100%. Gate khởi điểm đề xuất: validity ≥0.90, consistency=1, N_clean>0; salary coverage chỉ gate training, không chặn analytics về số tin. Threshold lưu theo report và có revision. Để demo lỗi gate, dùng dataset cố ý nhiều lỗi; output lưu để truy vết nhưng không đổi active pointer. Ngưỡng là quyết định cấu hình cần hiệu chỉnh theo dữ liệu thật, không phải kết quả đo.

Analytics đầu tiên hỗ trợ date range, province, industry, experience, remote type. Snapshot lưu các tổ hợp dimensions cần filter kết hợp, không cộng median từ các nhóm. Với tổ hợp filter không materialize, dùng query Mongo giới hạn version và giới hạn tài nguyên, hoặc enqueue snapshot job trả 202; không tự bỏ filter. Mean tính từ sum/count; kỹ năng đếm tin chứa skill unique; time trend theo posted_at, không dùng ngày import thay thế. Mỗi response có sample size, eligible count, missing salary rate, method và cập nhật.

## 5. Job ownership và failure recovery

State machine: PENDING → QUEUED → RUNNING → COMMITTING → COMPLETED; PENDING/QUEUED có thể CANCELLED; RUNNING → FAILED hoặc CANCEL_REQUESTED → CANCELLED; COMMITTING không hủy. FAILED tạo attempt mới qua retry → QUEUED tối đa 3 lần cho lỗi transient. Lỗi schema/quality không auto-retry; cần chỉnh input/config và tạo version mới. Checkpoints tiến trình không đồng nghĩa COMPLETED.

Lease khởi điểm 60 giây, heartbeat 15 giây. Claim và renew kiểm tra worker_id/fencing token. Recovery chỉ requeue khi lease hết và chưa COMMITTING; stale worker dừng khi renew thất bại. Các output được scope theo attempt nên ghi muộn không thay snapshot hiện hành. RUNNING cancel gọi Spark cancelJobGroup và đợi compute dừng; chỉ sau đó mark CANCELLED. Nếu không xác nhận dừng, giữ CANCEL_REQUESTED và thông báo, không tuyên bố đã hủy.

Log JSON có request_id, job_id, attempt_id, stage, counts, duration; sanitize exception trước lưu. Retry classification: network timeout/broker unavailable là transient; salary parse/schema input là lỗi dữ liệu. Reconciler xử lý orphan file, metadata publish dang dở và lease expiry có audit.

## 6. ML dataset, split và models

Chỉ đọc một published dataset version + attempt. Lưu ordered record IDs/hash, target rule, feature schema và split manifest. Features đầu tiên: title, industry, province/city, experience, seniority, education, employment/remote type, skills. Description chỉ thêm sau khi loại đoạn lương và kiểm tra leakage; không dùng salary_*, parse status, FX, quality score hoặc trường dẫn xuất target làm input.

Ưu tiên temporal split 70/15/15 theo posted_at hợp lệ, ngày cutoff được lưu. Các group cùng canonical job/repost không xuất hiện ở nhiều split: group cắt qua cutoff được quarantine khỏi experiment, báo số lượng bị loại. Nếu thiếu ngày đủ tin cậy, dùng group split seed 42 theo company/job group, đánh dấu không phải đánh giá tương lai. Tách thử nghiệm group theo company để đo khả năng tổng quát cho doanh nghiệp mới. Không shuffle rồi bỏ qua repost leakage.

Gate khởi điểm cho training: ≥200 labels, train ≥100, validation/test mỗi tập ≥30 và ít nhất 5 groups; nhỏ hơn thì trả `INSUFFICIENT_TRAINING_DATA`. Bộ 100 dòng dùng ETL smoke, không coi là benchmark ML đáng tin cậy. Minimums là guardrail vận hành, không đảm bảo chất lượng thống kê.

Preprocessing chỉ fit trên train: numeric imputation, categorical unknown-safe encoding, skills vectorization/TF-IDF. Các thống kê clipping/outlier và vocabulary fit train, áp dụng nguyên trạng cho validation/test. Lưu preprocessing cùng model artifact. Spark MLlib pipeline riêng có parity test cho feature mapping/inference; không giả định vector scikit-learn và MLlib tự tương thích.

| Model | Vai trò |
| --- | --- |
| DummyRegressor median | Baseline, dùng đúng train target |
| LinearRegression hoặc regularized linear | Mốc tuyến tính; pipeline scikit-learn |
| RandomForestRegressor | Mốc phi tuyến; sampling có giới hạn nếu local |
| Spark GBTRegressor | Pipeline MLlib phân tán trên dataset lớn |
| XGBRegressor | So sánh thêm trên sample có seed/manifest và memory cap |

Tuning theo validation MAE, tie-break RMSE; cùng split và sample khi so thuật toán trực tiếp. Nếu Spark dùng full data còn local models dùng sample, trình bày thành hai thí nghiệm riêng, không kết luận chênh lệch chỉ do model. Mọi candidate báo validation MAE/RMSE/R²/MedAE; baseline trên cùng test. Sau khi chốt winner, freeze config, đánh giá một lần holdout winner và baseline. Nếu cần test metrics của nhiều models cho báo cáo, freeze toàn bộ candidates trước mở test; không active model khác dựa trên bảng test.

Artifact kết quả gồm actual/predicted/residual theo test record ID, split metadata; biểu đồ scatter/residual, validation comparison và feature importance phù hợp model. Slice metrics theo industry/location/seniority/salary range, kèm n; nhóm nhỏ hiển thị thiếu mẫu thay vì kết luận. R² không xác định với target hằng/ít mẫu → null kèm reason, không JSON NaN. SMAPE tùy chọn, quy tắc mẫu số được ghi rõ.

Registry: TRAINING → EVALUATING → CANDIDATE → ACTIVE → ARCHIVED; lỗi → FAILED. Evaluation gate bao gồm artifact hash/load, finite predictions, feature schema và validation tốt hơn baseline theo margin cấu hình. ACTIVE dùng singleton pointer MongoDB; trạng thái trong registry là metadata do reconciler đồng bộ. Active/rollback phải kiểm tra artifact còn tồn tại và quyền admin.

MLflow profile bật thì ghi runs, parameters, metrics và artifacts; Mongo giữ experiment/business model metadata và artifact references. Khi profile tắt, artifact lưu volume nội bộ + manifest checksum, không hiển thị link MLflow giả. Artifact chỉ do training worker tin cậy tạo; không nhận pickle/joblib upload từ người dùng. Serving chỉ load allowlisted path có checksum và environment tương thích. Spark model serving dùng adapter/runtime Spark riêng hoặc session được quản lý ở serving process; tránh khởi động Spark cho từng request và không đưa training vào API. Chốt adapter qua latency test trước active model MLlib.

## 7. Inference và streaming

Inference: validate → canonical feature mapping → resolve active model một lần → verify/load cached immutable artifact → predict → finite/positive check → persist history → response. Không active model trả 503 `MODEL_NOT_AVAILABLE`. Artifact active lỗi có thể fallback về model trước đã xác minh; response ghi đúng model thực tế và warning, không âm thầm giả lập prediction. Nếu không có artifact dùng được, trả lỗi.

Không mặc định khoảng dự đoán. Nếu làm conformal interval, cần calibration subset riêng ngoài validation dùng để tuning và test cuối; báo empirical coverage và điều kiện exchangeability. Nếu chưa hiệu chuẩn, response không có interval/confidence phần trăm. OOD dựa trên category chưa thấy, numeric range train; là warning có căn cứ, không phải độ tin cậy xác suất.

Kafka topics: `recruitment.jobs.raw`, `.invalid`, `.processed`, `recruitment.pipeline.events`. Event có event_id, source key, schema_version, occurred_at, payload, is_demo. Spark Structured Streaming đọc raw topic với checkpoint volume và giới hạn offsets per trigger. `foreachBatch` ghi raw/clean/invalid idempotent theo event_id và business key; lưu batch manifest. Đây là at-least-once delivery với idempotent writes, không tuyên bố exactly-once xuyên Kafka/Mongo.

Streaming dùng dataset window/version riêng; không sửa published batch version. Microbatch tạo version hoàn chỉnh hoặc tích lũy staging theo window rồi publish; chỉ hiển thị sau quality gate. Restart sử dụng cùng checkpoint và query identity; checkpoint bị mất có thể replay, unique keys vẫn chống trùng. Test broker down/up, poison message, worker kill/restart và input rate/backpressure. Profile streaming chỉ được nghiệm thu sau khi toàn bộ kịch bản recovery chạy thật.
