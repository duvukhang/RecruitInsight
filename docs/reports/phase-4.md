# Phase 4 — Spark ETL

18/10/2026: pipeline thực thi DataFrame UDF normalization, window dedup deterministic, partitioned Mongo bulk upserts, invalid/duplicate records, quality gate và immutable snapshot publication.

Kiểm tra thực tế: backend suite **21 passed, 1 skipped** (Spark test được tách chạy trên driver có DNS hợp lệ); `RUN_SPARK_TESTS=1 MONGO_DATABASE=recruitment_test` trong etl-worker: **2 passed in 41.14s**. Test kiểm chứng 4 raw → 2 clean + 1 duplicate + 1 invalid, canonical ref deterministic, median/coverage đúng; test publish thực qua Spark executor vào Mongo test, rồi quality failure không đổi active pointer. Không dùng mock Mongo/Spark cho hai integration tests này.

Nguồn: domain/salary.py, bigdata/normalize.py, bigdata/etl.py, tests/test_salary.py, tests/test_etl.py, worker dispatch. Evidence: artifacts/tests-phase4.log, tests-spark-etl.log, tests-publication.log và Spark event volume.

Giới hạn: phiên bản đầu dùng double finite cho số lương VND thay vì Decimal128 trong bản thiết kế; ngày đăng chuẩn hóa ISO UTC string để dùng chung DataFrame/Mongo. FX và quy đổi giờ/ngày chưa có cấu hình provenance nên giữ target null thay vì tự đặt tỷ giá/giờ làm. Không trình bày các record đó như labels huấn luyện hợp lệ. Phải mở rộng cấu hình ở phase hoàn thiện. Có pipeline thực và publication gate đã kiểm chứng, bắt đầu nối analytics API.
