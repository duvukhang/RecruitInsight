# Pipeline dữ liệu, analytics và Machine Learning

Tài liệu mô tả source hiện tại; bằng chứng runtime mới và phần BLOCKED nằm ở [báo cáo nâng cấp](reports/research-upgrade.md). Thiết kế ban đầu chưa triển khai không được coi là kết quả.

RecruitInsight 2.0 bổ sung [adapter/staged/provenance](real-data-import.md) và [báo cáo mới](reports/upgrade-results.md). Staged JSONL khóa manifest/checksum rồi dùng chính ingestion/attempt/quality gate dưới đây. posted_year nullable đi riêng posted_at; không sửa ngày của dataset đã công bố. Salary parser thêm `40tr`/`upto`; CSV export chặn công thức kể cả whitespace đứng trước. Tham chiếu 05/11 trong báo cáo nghiên cứu cũ là lịch sử.

## Ingestion và nguồn

Upload CSV/JSON/JSONL tối đa 50 MiB, streaming ghi file và SHA-256 trước enqueue. CSV giữ dòng dư cột thành parse error; JSONL giữ original_line hỏng; JSON array bị hỏng toàn file khiến run FAILED. Raw payload và file gốc giữ nguyên để đối soát. Mỗi raw có record_number, raw_record_ref, dataset_version, source và ingested_at. Dataset lưu source, is_demo, hash, original_filename, schema_version, file_ref, format và created_at.

Form upload có thêm `source_metadata` là JSON tùy chọn: source_type (upload/offline/api/synthetic), collected_at, observation_from, observation_to và license_permission. Các ngày dùng YYYY-MM-DD; kiểm tra thứ tự thời kỳ. Không có metadata thì lưu object rỗng, không tự suy ra giấy phép/ngày thu thập từ ngày upload. is_demo và tên nguồn do người nhập khai báo; hệ thống chưa xác minh độc lập quyền sử dụng. Không tự crawl nguồn bên ngoài. Metadata khác với cùng idempotency key trả 409; request cũ không gửi metadata vẫn hợp lệ.

## Spark ETL và quality gate

Luồng: Raw → Validation → Normalization → Deduplication → Clean → Quality Gate → Analytics-ready → Publish. Batch mặc định đọc canonical raw JSONL trên volume, repartition(4); Mongo connector là smoke experiment riêng, không phải nguồn đọc ETL mặc định.

Normalization dùng Unicode NFC, trim/collapse whitespace, lowercase company/title keys và unique lowercase skills. Chưa có taxonomy đáng tin cậy nên không tự map tỉnh/ngành/chức danh sang danh mục chuẩn. Title/company thiếu hoặc sai kiểu, parse lỗi, kinh nghiệm không phải số hữu hạn trong [0,60] là invalid. Kinh nghiệm không cung cấp giữ null, khác 0 năm. Ngày đăng không parse được giữ null; không lấy ngày import thay thế. Salary không có midpoint vẫn có thể là clean và tham gia thống kê tin.

Dedup chỉ theo `source:source_job_id` nếu có, nếu không là SHA-256 của raw JSON sort keys. Không fuzzy merge, không tự canonicalize URL hay suy business key. Trong các record hợp lệ, record_number nhỏ nhất (tie-break raw ref) là canonical. `_global_duplicate_ref` do streaming ledger tạo được đưa vào duplicate. Invalid được ưu tiên trước duplicate. Các tin giống nghĩa nhưng khác payload/source ID có thể vẫn còn; group theo company giảm leakage trong trường hợp cùng doanh nghiệp nhưng không bảo đảm xử lý mọi repost khác doanh nghiệp.

Mỗi attempt phải thỏa `raw = invalid + duplicate + clean`; sai thì raise lỗi trước công bố. Bulk upsert theo attempt/raw ref chịu được retry task; version đã PUBLISHED không ghi đè. Quality report lưu counts, thresholds và normalization config; salary coverage không chặn phân tích số tin. Gate mặc định validity ≥0,90 và clean >0; consistency được đo/báo cáo, hiện chưa phải một ngưỡng gate riêng.

| Chỉ số | Tử số | Mẫu số |
| --- | --- | --- |
| Completeness | Ô title/company/source có giá trị sau normalization | 3 × raw |
| Validity | raw − invalid | raw |
| Uniqueness | clean | raw − invalid |
| Consistency | clean có title/company, experience null hoặc [0,60], midpoint null hoặc khớp bounds dương/sắp đúng (sai lệch <1 VND) | clean |
| Salary label usability | clean có midpoint >0, bao gồm NET | clean |
| Local training eligibility | clean có midpoint >0, basis khác NET | clean |
| Missing từng field | null/rỗng/Unknown sau normalization ở field đó | raw |
| Timeliness | clean có ngày đăng trong 180 ngày vừa qua, không ở tương lai | clean |

Mẫu số 0 trả null (NOT_COMPUTABLE). Đây là các quy tắc chất lượng có phạm vi cụ thể, không phải kiểm chứng tính đúng sự thật của nguồn. Raw values vẫn tồn tại để kiểm tra.

## Nhãn lương và giới hạn

Hai bounds hữu hạn, dương, đúng thứ tự → midpoint sau FX và quy đổi chu kỳ. Lương một giá trị được coi là hai bounds bằng nhau. Một phía (up to/from) → chỉ bound, midpoint null. Negotiable/competitive/thỏa thuận → undisclosed, không thay 0. Âm/đảo khoảng/không parse được → target null, giữ status. Kỳ hạn hỗ trợ MONTH/YEAR/HOUR/DAY; WEEK hoặc text weekly giữ target null với UNSUPPORTED_PERIOD.

Tiền tệ lấy từ trường currency hoặc tokens USD/$/VND/triệu trong text. Giá trị mơ hồ không tự gán FX; cần bảng rates có rate dương/source/date. Lương năm chia 12; giờ/ngày cần hours_per_month/days_per_month đã cấu hình. Assumptions và FX provenance lưu theo record, normalization config đóng băng theo version. Không tự dùng tỷ giá hiện tại hay chuyển NET sang GROSS. Có thể còn sai biệt locale/kỳ hạn diễn đạt không được parser hỗ trợ; giữ raw và kiểm tra theo nguồn trước dùng dữ liệu thật.

ML chỉ đọc published version/attempt, midpoint >0, salary_basis != NET. GROSS và UNKNOWN cùng vào mô hình; basis_counts được lưu, UNKNOWN làm giảm khả năng so sánh. Dữ liệu không có nhãn vẫn ở clean cho analytics; không loại khỏi mẫu số số tin.

## Analytics

Không filter: snapshot schema 2 từ Spark. Có province/industry/posted_from/posted_to hoặc snapshot lịch sử schema 1: Mongo aggregation live trên đúng published attempt. Không sửa snapshot cũ. Mọi response có version/attempt, số tin/nhãn, missing_salary_rate, reference_period, source và filters. Ngày kết thúc bao gồm cả ngày UTC bằng điều kiện nhỏ hơn ngày kế tiếp. Không có filter experience/remote ở API hiện tại.

Overview có số doanh nghiệp, ngành/tỉnh có thông tin (không đếm Unknown), nhãn lương, mean/median và percentiles. Group theo industry/province/số năm kinh nghiệm/company có số tin, số nhãn, mean, median, missing rate; p25/p75/p90 chỉ hiện khi có ≥30 nhãn. Nhóm nhỏ có warning; frontend không vẽ so sánh median ngành dưới ngưỡng. Threshold 30 là guardrail trình bày, không bảo đảm ý nghĩa thống kê. Median vẫn là mô tả mẫu nhỏ. Kỹ năng đếm mỗi tin một lần/skill; trends theo tháng đăng; histogram buckets 5 triệu VND/tháng. Group top 100, skills top 30, trends 120 tháng là giới hạn trả kết quả, không phải toàn bộ danh mục.

Spark percentile_approx accuracy=10000 và Mongo $percentile approximate là hai phương pháp xấp xỉ; không cộng median giữa các nhóm. Counts/mean phải thống nhất theo filter, percentile chỉ đối chiếu với sai số xấp xỉ phù hợp. Không tạo insight thị trường hardcode. Mỗi nhóm biểu đồ ghi câu hỏi, đơn vị, mẫu/bộ lọc/thời kỳ và giới hạn diễn giải.

## ML: local và Spark là hai nhóm thí nghiệm

Local models: Dummy median, Ridge(alpha=10), Random Forest, Gradient Boosting, XGBoost CPU. Reservoir tối đa 10.000 labels seed 42; 200 labels và 10 company groups tối thiểu; từng split ≥30. GroupShuffleSplit test 15% groups seed 42; validation tỷ lệ 0,15/0,85 groups seed 43. Tỷ lệ số rows không nhất thiết đúng 70/15/15. Manifest giữ record IDs, seeds, counts, dataset hash, target rule và basis counts. Nếu source_job_key xuất hiện qua nhiều split thì từ chối training.

Preprocessing DictVectorizer chỉ fit train; categorical Unknown-safe, skills indicators; features allowlist không có salary/parse status/FX. dict-v2 dùng experience=0 làm giá trị tính toán cùng indicator experience_missing=1 khi thiếu; clean vẫn null. Nhờ indicator, thiếu khác 0 năm quan sát. Pipeline lưu cùng artifact. Model dict-v1 cũ tiếp tục inference với các đặc trưng cũ; DictVectorizer bỏ qua key missing mới chưa có trong vocabulary.

Chốt winner bằng validation MAE, tie-break RMSE trước mở test. Sau đó đánh giá toàn bộ candidates đã đóng băng và median baseline trên cùng test IDs. MAE/RMSE/MedAE đơn vị VND/tháng; R² không có đơn vị, null nếu target hằng hoặc ít hơn hai mẫu. Không tuning hoặc chọn lại winner từ bảng test.

Holdout lưu actual/predicted/residual, scatter, residual histogram và weights/importance. Slice errors theo industry, province, experience (<1, 1–<3, 3–<5, 5+, Unknown), salary buckets 10 triệu và exact normalized title. Chỉ tính metrics cho nhóm ≥30; lưu số nhóm bị suppress. Salary band chỉ phục vụ chẩn đoán sau khi biết actual, tuyệt đối không đưa vào X. Importance/coefficient không phải quan hệ nhân quả.

Spark MLlib LinearRegression chỉ dùng observed experience, toàn bộ eligible clean thuộc train companies của manifest local; validation/test cũng loại missing experience. Cần train≥100 và validation/test≥30 sau loại missing. Lưu training companies/count, validation/test IDs, dataset/attempt và eligibility predicate. Vì khác feature và có thể khác sample/count nên không xếp cùng bảng để kết luận thuật toán tốt hơn. Numeric coefficient/intercept xuất JSON giúp inference không khởi động Spark trong request; artifact pipeline Spark vẫn được lưu.

Temporal holdout là đề xuất riêng khi có ngày đăng đáng tin cậy, chưa chạy và không thay group split hiện tại. Ablation đề xuất: experience → +title → +industry/province → +skills và categorical còn lại; dùng cùng IDs/seeds, fit lại preprocessing trên train, cùng validation MAE và holdout đóng băng; chưa chạy vì hiện chỉ có DEMO và chưa kiểm chứng nguồn thực. Không trình bày như kết quả đã đạt.

## Serving, job recovery và streaming

Serving validate → resolve active pointer → checksum/allowlisted artifact load → predict finite/positive → persist personal history. Fallback artifact trước đã xác minh phải trả đúng version và warning. Response giữ model/dataset version, reference period, test metrics, DEMO/OOD warnings; không confidence % hoặc interval chưa hiệu chuẩn. dict-v2 giữ categories train để cảnh báo unseen. MAE không phải sai số bảo đảm cho từng cá nhân.

Job queue Mongo claim/lease/fencing; output scope attempt; CAS PUBLISHED rồi CAS active pointer; retry tối đa 3 theo repository policy. Không chạy recovery phá phiên làm việc trong lần nâng cấp này. Kafka Structured Streaming profile là ingestion mở rộng: checkpoint volume, tối đa 100 offsets/trigger, event-ID ledger, immutable microbatch versions rồi batch ETL chuẩn. Delivery at-least-once với idempotent sink, không exactly-once xuyên hệ thống. MLflow tùy chọn, không ép bật. Xem reports phase-9 cho bằng chứng lịch sử, không coi là retest của source vừa sửa.
