import csv
import json
from pathlib import Path
from pymongo import UpdateOne
from recruitment.domain.common import now, AppError


def input_records(path):
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as source:
        if path.suffix == '.csv':
            for record in csv.DictReader(source):
                if None in record:
                    record['_extra_columns']=record.pop(None)
                    record['_parse_error']='CSV_COLUMN_COUNT_MISMATCH'
                yield record
        elif path.suffix == '.jsonl':
            for line in source:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    yield value if isinstance(value, dict) else {'_parse_error': 'Record must be an object', 'original_line': line}
                except json.JSONDecodeError:
                    yield {'_parse_error': 'Malformed JSONL', 'original_line': line}
        else:
            # Upload capped at 50 MiB; JSONL is preferred for large datasets.
            values = json.load(source)
            if not isinstance(values, list):
                raise AppError('INVALID_FILE_FORMAT', 'JSON phải là một array chứa các object.')
            for value in values:
                yield value if isinstance(value, dict) else {'_parse_error': 'Record must be an object', 'original_value': value}


def ingest(db, job, guard):
    version = job['payload']['dataset_version']
    dataset = db.datasets.find_one({'_id': version})
    batch, count = [], 0
    canonical = Path(dataset['file_ref']).with_suffix('.raw.jsonl')
    temporary = canonical.with_name(job['attempt_id'] + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as output:
            for number, raw in enumerate(input_records(dataset['file_ref']), 1):
                if len(json.dumps(raw, ensure_ascii=False).encode()) > 1024 * 1024:
                    raise AppError('RECORD_TOO_LARGE', f'Record {number} vượt 1 MiB.')
                record = {'_id': f'{version}:{number}', 'dataset_version': version,
                    'record_number': number, 'raw_payload': raw, 'source': dataset['source'],
                    'ingested_at': now(), 'schema_version': 1}
                batch.append(UpdateOne({'_id': record['_id']}, {'$setOnInsert': record}, upsert=True))
                output.write(json.dumps({'record_number': number, 'raw_record_ref': record['_id'],
                    'payload_json': json.dumps(raw, ensure_ascii=False)}, ensure_ascii=False) + '\n')
                count += 1
                if len(batch) >= 500:
                    guard()
                    db.raw_jobs.bulk_write(batch, ordered=False)
                    batch.clear()
            if batch:
                guard()
                db.raw_jobs.bulk_write(batch, ordered=False)
        if not count:
            raise AppError('EMPTY_DATASET', 'Dataset không có record.')
        guard()
        temporary.replace(canonical)
        db.datasets.update_one({'_id': version, 'status': 'IMPORTING'}, {'$set': {
            'status': 'RAW_READY', 'raw_file_ref': str(canonical), 'row_counts.raw': count}})
        db.ingestion_runs.update_one({'_id': version}, {'$set': {'status': 'COMPLETED', 'total_records': count, 'finished_at': now()}})
        return {'raw_records': count}
    finally:
        temporary.unlink(missing_ok=True)
