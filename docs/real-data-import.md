# Nguồn ngoài, snapshot và staged import

## Trạng thái quyền

Ngày xác minh: **07/11/2026**. [Tinix](https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions) công bố CC BY-NC 4.0, 606.878 tin, 14 cột và năm 2022–2026. Chưa xác minh đầy đủ quyền đối với văn bản đăng tuyển gốc. [VietJobs](https://huggingface.co/datasets/dinhieufam/VietJobs) không có license trên card đã xem, company_name và ngày đăng không có trong preview; [bài LREC](https://aclanthology.org/2026.lrec-1.501/) mô tả 48.092 tin và 16 ngành. License bài báo không thay license dữ liệu.

**Public pilot: NEEDS_REVIEW/BLOCKED**. Không tải corpus, không commit mẫu public và không gắn REAL_VERIFIED. Danh mục `/sources` phản ánh đúng trạng thái này. Cần chủ nguồn cung cấp quyền dùng/phân phối nội dung và revision trước khi thí điểm public. Việc người dùng khai báo permission evidence không phải chứng nhận của hệ thống.

## Adapter có thể dùng ngay với export cục bộ được phép

Tại root, với Python/dependencies đã cài và `PYTHONPATH=backend/src` (Docker image đã cấu hình):

```powershell
$env:PYTHONPATH = 'backend/src;.'
python -m scripts.prepare_real_dataset --source tinix --input data/source-export.jsonl --output data/tinix-pilot.jsonl --limit 1000 --seed 42 --batch-size 100 --max-output-bytes 52428800 --revision '<source-commit>' --permission-evidence '<văn bản/quyền dùng export cục bộ>' --dry-run
```

Bỏ `--dry-run` để ghi snapshot cùng `.manifest.json`. Output đã tồn tại bị từ chối; chọn tên mới. Input CSV/JSONL UTF-8, bản ghi tối đa 1 MiB, batch tối đa 1.000 dòng và khoảng 4 MiB raw. Không nhận URL tùy ý, không tự tải Internet và không ghi Mongo. `--source` chỉ nhận `tinix` hoặc `vietjobs`. Chỉ dùng `--synthetic` nếu input tự tạo để test; output và manifest được ghi rõ SYNTHETIC_FIXTURE.

Một snapshot tối đa 50 MiB, có thể ít dòng hơn `--limit`; đọc `row_count`, `bytes`, `byte_cap_reached` thay vì giả định đủ dòng. Method là **prefix nguồn + shuffle trong batch bằng seed**, không phải mẫu ngẫu nhiên đại diện quần thể. Không chọn công ty để vượt gate ML. JSONL giữ nguyên giá trị text; CSV thêm dấu nháy trước chuỗi có thể thành công thức, nên ưu tiên JSONL để nhập ETL. Manifest giữ SHA-256 input/output, revision do người cung cấp, thời điểm chuẩn bị, adapter version, quyền và số dòng; `prepared_at` khác ngày thu thập, `collected_at` không tự điền.

Mapping: id giữ thành ID nguồn (0 cũng hợp lệ), missing id dùng hash nội dung; company chỉ từ raw; location chỉ map alias chính xác Hà Nội/Hồ Chí Minh/Đà Nẵng, còn lại Unknown và giữ location_raw. Lương giữ raw; 40tr được nhận là triệu VND, upto chỉ một phía, USD không FX giữ label null, NET không đưa vào training hiện hữu. Kinh nghiệm chính xác `2 năm` → 2; `2-3 năm`/`Dưới 1 năm` giữ interval và giá trị điểm null; missing/Không yêu cầu không thành 0. Không có extractor skills đã xác thực thì `[]`, giữ requirements_raw. Không tự map chức vụ sang cấp bậc. Description giới hạn 30.000 ký tự, có cờ truncated và original row hash; lưu trữ export input gốc bên ngoài Git để kiểm chứng đầy đủ.

Tinix year → posted_year, posted_at null. VietJobs không company nên các dòng thiếu company sẽ vào invalid theo gate hiện hành; không đưa vào company-group training bằng công ty giả. Cần luồng nghiên cứu độc lập nếu muốn phân tích nguồn này mà không dùng schema doanh nghiệp của ứng dụng.

## Luồng giao diện

ADMIN → Quản lý dữ liệu: chọn file → kiểm tra preview 4 KiB đầu và schema chuẩn → điền provenance/quyền, nhãn DEMO/nguồn ngoài → xác nhận → Upload. Preview không phải parser/validator của toàn file; ingestion và Spark quyết định tính hợp lệ. Nguồn Tinix/VietJobs phải qua adapter trước; UI không tự đoán schema.

Một file CSV/JSON/JSONL dùng upload 50 MiB cũ. Nhiều file chỉ nhận JSONL, **mỗi chunk ≤50 MiB**, tối đa 128 chunk. UI tính hash/row count từng chunk có giới hạn; không tải toàn bộ 500k tin vào bảng hay API. Khi lỗi, gửi lại cùng file/form giữ key trong phiên component; với client tự động cần lưu key và version để resume. Staged version chưa seal không enqueue worker. Các chunk trùng nội dung được ETL dedup bình thường.

## Hợp đồng staged cho client dữ liệu lớn

1. `POST /api/v1/datasets/staged`, Bearer ADMIN, header `Idempotency-Key`. JSON `{source,is_demo,source_metadata,chunks:[{sha256,bytes,row_count},...]}`. Thứ tự array là thứ tự chunk, chỉ JSONL. Cùng actor/key/manifest trả version cũ, khác trả 409.
2. `PUT /api/v1/datasets/staged/{version}/chunks/{index}`, multipart `file`. Kiểm tra byte cap và SHA-256 streaming, không nhận đường dẫn file server hoặc URL. Thất bại 413/422 không tạo chunk hợp lệ. Có thể gửi lại trước seal.
3. `POST /api/v1/datasets/staged/{version}/complete`: kiểm lại tất cả checksum, khóa manifest rồi enqueue job INGESTION ID ổn định. Gọi lại trả cùng job, không tạo version mới. Chunk đã seal bị từ chối sửa.
4. Worker kiểm lại chunk hash/row count rồi đi qua raw → canonical JSONL → Spark → quality gate → publish. Một version/attempt phủ toàn bộ các chunk. Sai count/hash giữ FAILED, không publish; raw chưa hoàn tất không được đọc vào analytics. File/chunk gốc giữ trên uploads volume.

Không tăng upload_limit, không bypass ACL, queue, retry hoặc fencing. Import đang bỏ dở chưa có TTL/GC tự động; admin cần theo dõi dung lượng uploads. Giới hạn 128 chunk là giới hạn kỹ thuật, không bảo đảm máy có đủ disk. Không thử corpus lớn khi quyền hoặc tài nguyên chưa đủ.

## Năm và phiên bản cũ

`GET /analytics/job-years` trả posted_year/count, `time_resolution=YEAR`; snapshot có years dùng trực tiếp, snapshot cũ fallback Mongo (năm có sẵn hoặc năm từ ngày thật). Không tạo ngày từ năm, không viết lại snapshots đã publish. Xu hướng tháng chỉ dùng posted_at thật; dataset year-only không xuất hiện trong kết quả filter theo ngày.

Chất lượng theo phiên bản ghi raw/invalid/duplicate/clean, missing theo trường, nhãn/ML eligibility, parser statuses, độ phủ nguồn, số công ty/ngành/tỉnh và năm. Hai dataset được so riêng tại Nguồn dữ liệu; báo cáo JSON gồm metadata và số mẫu, không cộng hai median.

## Demo adapter không cần quyền corpus public

Fixture 100 dòng tại `tests/fixtures/tinix-shape.synthetic.jsonl` là dữ liệu tự tạo, đã ghi rõ điều kiện dùng trong README cùng thư mục. Với Docker stack và dependencies đã có:

```powershell
docker compose run --rm --no-deps test-backend python -m scripts.prepare_real_dataset --source tinix --input tests/fixtures/tinix-shape.synthetic.jsonl --output /data/uploads/SYNTHETIC-pilot-v1.jsonl --limit 100 --synthetic
docker compose run --rm --no-deps test-backend python -m scripts.measure_adapter --sizes 5000 50000
```

Chọn tên output mới nếu đã có. `measure_adapter` chỉ đo converter và ghi chunks/manifest; không chạy ETL, không ghi Mongo, không gọi đó là dữ liệu thực. Quan sát ngày 07/11: 5k → 7.289.230 bytes; 50k → 72.992.280 bytes chia thành 5 chunk, chunk lớn nhất 14.602.900 bytes. Một upload 50k duy nhất sẽ vượt 50 MiB; staged import xử lý các chunk của cùng version. Timing là quan sát trên máy hiện tại, không là cam kết throughput. Xem evidence tại báo cáo nâng cấp.
