# Phase 8 — Streaming

18/10/2026: Kafka 4.2.0 KRaft profile, Spark Structured Streaming Kafka connector 3.5.7, durable checkpoint volume và bounded microbatch ingestion (100 offsets/trigger). Mỗi microbatch có immutable dataset version theo partition/offset hash; event-ID ledger chống replay xuyên batch. ETL worker chạy pipeline Spark đã kiểm thử, quality gate và snapshot publication thông thường; dashboard thấy version mới sau publish.

Kết quả thực: 22 Kafka events → **20 clean + 1 duplicate + 1 invalid**; restart streaming driver, gửi batch mới: **PASS** với cùng counts; replay nguyên 22 event IDs: **0 clean + 21 duplicate + 1 invalid**, quality gate không công bố version rỗng và **active pointer giữ nguyên**. Evidence artifacts/streaming-result.json, stream-replay-result.json, streaming-e2e.log, streaming-restart.log, stream-replay.log; Kafka/checkpoint persistent volumes còn nguyên.

Lỗi phát hiện: Kafka non-root không ghi được volume mới; thêm one-shot init chỉ đổi owner volume, broker vẫn UID 1000. Nginx healthcheck localhost chọn IPv6 trong BusyBox nên dùng 127.0.0.1. Kafka connector jars resolve thực từ Maven thành công.

Giới hạn: microbatch ingestion materialize tối đa 100 Kafka records ở driver, không collect toàn bộ dataset; ETL cleaning/dedup/aggregation thực hiện phân tán tiếp ở Spark batch worker. At-least-once delivery + idempotent sink, không tuyên bố exactly-once xuyên Kafka/Mongo. Single broker phục vụ đồ án, không HA. Streaming snapshots có nhãn DEMO mặc định. MLflow profile đã start SQLite/artifact volume; tracking integration tiếp tục kiểm tra ở phase hoàn thiện.
