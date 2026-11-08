"""Admin-only bounded JSONL chunks; sealed manifests enter the existing ingestion queue."""
import hashlib
import json
import os
from pathlib import Path
from pymongo.errors import DuplicateKeyError
from recruitment.application.datasets import DatasetService
from recruitment.domain.common import AppError, now, uid
from recruitment.infrastructure.config import settings


class StagedImport:
    def __init__(self, db):
        self.db = db

    def create(self, body, actor, key):
        if not key or len(key) > 128:
            raise AppError('VALIDATION_ERROR', 'Cần Idempotency-Key (1–128 ký tự).', 422)
        draft_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        previous = self.db.datasets.find_one({'created_by': actor, 'idempotency_key': key})
        if previous:
            if not previous.get('staged') or previous.get('draft_hash') != draft_hash:
                raise AppError('IDEMPOTENCY_CONFLICT', 'Key đã dùng cho manifest khác.', 409)
            return {'dataset_version': previous['_id'], 'chunk_count': len(previous['chunks'])}
        version = uid()
        record = {'_id': version, 'dataset_id': version, 'created_by': actor,
            'created_at': now(), 'status': 'IMPORTING', 'source': body.source,
            'is_demo': body.is_demo, 'source_metadata': body.source_metadata.model_dump(mode='json', exclude_none=True),
            'idempotency_key': key, 'draft_hash': draft_hash, 'format': 'jsonl', 'schema_version': 1,
            'row_counts': {}, 'staged': True, 'sealed': False,
            'chunks': [item.model_dump() for item in body.chunks]}
        try:
            self.db.datasets.insert_one(record)
        except DuplicateKeyError:
            return self.create(body, actor, key)
        return {'dataset_version': version, 'chunk_count': len(record['chunks'])}

    def require(self, version):
        record = self.db.datasets.find_one({'_id': version, 'staged': True})
        if not record:
            raise AppError('NOT_FOUND', 'Không tìm thấy staged import.', 404)
        return record

    async def chunk(self, version, index, file):
        record = self.require(version)
        if record.get('sealed'):
            raise AppError('INVALID_STATE', 'Manifest đã khóa.', 409)
        if index < 0 or index >= len(record['chunks']):
            raise AppError('NOT_FOUND', 'Không có chunk này.', 404)
        expected = record['chunks'][index]
        directory = settings().data_root / 'uploads' / version
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'{index:04}.jsonl'
        temporary = directory / (uid() + '.part')
        digest, total = hashlib.sha256(), 0
        try:
            with temporary.open('xb') as output:
                while block := await file.read(1024 * 1024):
                    total += len(block)
                    if total > min(expected['bytes'], settings().upload_limit):
                        raise AppError('UPLOAD_TOO_LARGE', 'Chunk vượt giới hạn byte.', 413)
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if total != expected['bytes'] or digest.hexdigest() != expected['sha256']:
                raise AppError('CHECKSUM_MISMATCH', 'Checksum hoặc kích thước chunk không khớp manifest.', 422)
            # All valid writes to the same index have the same declared bytes/hash.
            temporary.replace(path)
            return {'index': index, 'sha256': digest.hexdigest(), 'bytes': total}
        finally:
            temporary.unlink(missing_ok=True)

    def seal(self, version):
        record = self.require(version)
        if record.get('sealed'):
            return DatasetService(self.db).ensure_ingestion(record)
        directory = settings().data_root / 'uploads' / version
        for index, chunk in enumerate(record['chunks']):
            path = directory / f'{index:04}.jsonl'
            digest = hashlib.sha256()
            if not path.exists() or path.stat().st_size != chunk['bytes']:
                raise AppError('INCOMPLETE_IMPORT', f'Chưa nhận đủ chunk {index}.', 409)
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != chunk['sha256']:
                raise AppError('CHECKSUM_MISMATCH', 'Chunk đã thay đổi.', 409)
        manifest = json.dumps({'chunks': record['chunks']}, sort_keys=True, separators=(',', ':'))
        # No external path is accepted. ingestion reconstructs paths from version + index.
        self.db.datasets.update_one({'_id': version, 'sealed': False}, {'$set': {
            'sealed': True, 'file_ref': str(directory / 'staged.jsonl'),
            'content_hash': hashlib.sha256(manifest.encode()).hexdigest()}})
        return DatasetService(self.db).ensure_ingestion(self.require(version))


def staged_records(dataset):
    from bigdata.ingestion import input_records
    directory = Path(dataset['file_ref']).parent
    for index, chunk in enumerate(dataset['chunks']):
        path = directory / f'{index:04}.jsonl'
        digest, count = hashlib.sha256(), 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if path.stat().st_size != chunk['bytes'] or digest.hexdigest() != chunk['sha256']:
            raise AppError('CHECKSUM_MISMATCH', 'Chunk khác manifest trước ingestion.', 409)
        for record in input_records(path):
            count += 1
            yield record
        if count != chunk['row_count']:
            raise AppError('ROW_COUNT_MISMATCH', 'Số dòng chunk khác manifest.', 422)
