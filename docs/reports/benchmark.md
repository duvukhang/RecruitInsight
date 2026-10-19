# Spark benchmark — actual measurements

Run ID: `05c97cb6-a354-49db-86be-845bc490a5d3`, ngày 18/10/2026. DEMO seed 42, warm-up một lần không tính, ba lần đo mỗi cấu hình/quy mô. Counts và checksum output khớp giữa mọi cấu hình và lần lặp.

| Input rows | Spark local[1], median giây | Cluster 1 executor, median giây | Cluster 2 executors, median giây | Speedup cluster 2 / local[1] |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 0.644 | 0.738 | 0.772 | 0.83× |
| 10.000 | 0.999 | 1.022 | 1.172 | 0.85× |
| 100.000 | 4.086 | 4.492 | 2.805 | 1.46× |

Đây là phép đo **read JSONL + normalize UDF + dedup window + aggregate counts/checksum**, không phải toàn bộ upload/Mongo write/model training. Timer bao quanh Spark action hoàn tất. Session startup và tạo file không tính; không dùng Spark persist; OS cache không kiểm soát hoàn toàn. Các cấu hình chạy tuần tự trên cùng máy, không phải nhiều máy vật lý. Streaming đã dừng trong lúc benchmark để không chiếm executor.

Môi trường quan sát: Docker Desktop Linux engine 29.4.1, 16 CPU được cấp, khoảng 7.57 GiB RAM VM; Spark 3.5.7, Python 3.11.11, Java 17, Scala 2.12, hai worker mỗi worker một core, executor memory 1 GiB. Lưu exact runtime/source SHA trong environment artifact. Chưa đo peak memory toàn stack; không suy ra peak từ memory limit.

Dữ liệu nhỏ chịu overhead lập lịch/shuffle nên cluster chậm hơn local. Ở 100.000 dòng, hai executor nhanh hơn local trong thí nghiệm này; không suy rộng speedup sang workload khác hay khẳng định tăng tuyến tính. Range cluster 2 ở 100 dòng: 0.705–3.413 giây, cho thấy nhiễu đáng kể; vì vậy dùng median và giữ toàn bộ observations.

Evidence: MongoDB `benchmark_runs` có observations và summary; `/data/artifacts/evidence/<run_id>/` có observations.csv, summary.json, environment.json và physical plans; `/data/events/` có Spark event logs. Application cluster2 `app-20261018142719-0007` ghi nhận hai executors. Host bản sao metadata trong `artifacts/benchmark-*.json/csv`; logs đầy đủ `artifacts/benchmark.log`.

Tái lập sau khi build: dừng streaming nếu đang bật, rồi `docker compose exec etl-worker python -m bigdata.benchmark --sizes 100 10000 100000 --repeats 3`. Lần đo hiện tại chạy chính source benchmark qua stdin trong etl-worker để giữ các images/tài nguyên compute ổn định, không build image đồng thời với phép đo.
