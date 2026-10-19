import socket
from datetime import timedelta
from recruitment.adapters.mongo import database
from recruitment.domain.common import now

if not database().worker_heartbeats.find_one({"_id": socket.gethostname(), "updated_at": {"$gt": now() - timedelta(seconds=45)}}):
    raise SystemExit(1)
