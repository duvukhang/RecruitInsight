import hashlib
import os
from pathlib import Path
from pymongo.errors import DuplicateKeyError
from recruitment.domain.common import AppError, now, uid
from recruitment.infrastructure.config import settings


class DatasetService:
    def __init__(self, db):
        self.db = db

    async def upload(self, file, source, is_demo, key, actor, source_metadata=None):
        source_metadata = source_metadata or {}
        if not key or len(key) > 128:
            raise AppError('VALIDATION_ERROR', 'Cần Idempotency-Key (1–128 ký tự).', 422)
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in {'.csv', '.json', '.jsonl'}:
            raise AppError('UNSUPPORTED_MEDIA_TYPE', 'Chỉ hỗ trợ CSV, JSON và JSONL.', 415)
        version = uid()
        directory = settings().data_root / 'uploads'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (version + suffix)
        total, digest = 0, hashlib.sha256()
        try:
            with path.open('wb') as target:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings().upload_limit:
                        raise AppError('UPLOAD_TOO_LARGE', 'File vượt quá 50 MiB.', 413)
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if not total:
                raise AppError('INVALID_FILE_FORMAT', 'File rỗng.', 400)
            sha = digest.hexdigest()
            previous = self.db.datasets.find_one({'created_by': actor, 'idempotency_key': key})
            if previous:
                path.unlink(missing_ok=True)
                if (previous['content_hash'], previous['source'], previous['is_demo'], previous.get('source_metadata', {})) != (sha, source, is_demo, source_metadata):
                    raise AppError('IDEMPOTENCY_CONFLICT', 'Key đã được dùng cho nội dung khác.', 409)
                return self.ensure_ingestion(previous)
            dataset = {'_id': version, 'dataset_id': version, 'created_by': actor,
                'idempotency_key': key, 'status': 'IMPORTING', 'source': source,
                'is_demo': is_demo, 'content_hash': sha, 'file_ref': str(path),
                'created_at': now(), 'format': suffix[1:], 'row_counts': {},
                'original_filename': Path(file.filename or '').name, 'schema_version': 1,
                'source_metadata': source_metadata}
            try:
                self.db.datasets.insert_one(dataset)
            except DuplicateKeyError:
                path.unlink(missing_ok=True)
                previous = self.db.datasets.find_one({'created_by': actor, 'idempotency_key': key})
                if (previous['content_hash'], previous['source'], previous['is_demo'], previous.get('source_metadata', {})) != (sha, source, is_demo, source_metadata):
                    raise AppError('IDEMPOTENCY_CONFLICT', 'Key đã được sử dụng.', 409)
                return self.ensure_ingestion(previous)
            return self.ensure_ingestion(dataset)
        except Exception:
            # Keep files referenced by persisted datasets, including recoverable enqueue failure.
            if not self.db.datasets.find_one({'_id': version}):
                path.unlink(missing_ok=True)
            raise

    def ensure_ingestion(self, dataset):
        version = dataset['_id']
        self.db.ingestion_runs.update_one({'_id': version}, {'$setOnInsert': {
            'dataset_version': version, 'status': 'QUEUED', 'created_at': now()}}, upsert=True)
        # Stable job id closes the crash/retry gap between metadata and queue writes.
        self.db.etl_jobs.update_one({'_id': 'ingest-' + version}, {'$setOnInsert': {
            'job_type': 'INGESTION', 'payload': {'dataset_version': version},
            'created_by': dataset['created_by'], 'created_at': now(), 'status': 'QUEUED',
            'fencing_token': 0, 'retry_count': 0, 'cancel_requested': False, 'progress': 0}}, upsert=True)
        return {'dataset_version': version, 'ingestion_id': version,
                'job_id': 'ingest-' + version, 'status_url': '/api/v1/etl/jobs/ingest-' + version}


def published(db, version=None):
    if not version:
        pointer = db.system_settings.find_one({'_id': 'active_dataset'})
        version = pointer['value'] if pointer else None
    dataset = db.datasets.find_one({'_id': version, 'status': 'PUBLISHED'})
    if not dataset:
        raise AppError('DATASET_NOT_AVAILABLE', 'Chưa có dataset đã công bố. Hãy nhập dữ liệu và chạy ETL.', 409)
    return dataset, {'dataset_version': version, 'attempt_id': dataset['published_attempt_id']}


def report_match(db,version):
    dataset=db.datasets.find_one({'_id':version})
    if not dataset:raise AppError('NOT_FOUND','Không tìm thấy dataset.',404)
    attempt=dataset.get('published_attempt_id')
    if not attempt:
        report=db.data_quality_reports.find_one({'dataset_version':version},sort=[('generated_at',-1)])
        attempt=report['attempt_id'] if report else dataset.get('active_attempt')
    return {'dataset_version':version,'attempt_id':attempt or '__NO_ATTEMPT__'}
