"""Chuyển export CSV/JSONL cục bộ có quyền sử dụng; không tải URL tùy ý."""
import argparse
import csv
import hashlib
import io
import json
import random
from itertools import islice
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bigdata.ingestion import input_records
from bigdata.sources import ADAPTER_VERSION, SOURCES, map_record


def bounded_records(path):
    if path.suffix.lower() == '.jsonl':
        with path.open('rb') as stream:
            while line := stream.readline(1024 * 1024 + 1):
                if len(line) > 1024 * 1024:
                    raise ValueError('Bản ghi nguồn vượt 1 MiB.')
                if line.strip():
                    row = json.loads(line.decode('utf-8-sig'))
                    if not isinstance(row, dict):
                        raise ValueError('Bản ghi phải là object.')
                    yield row
    elif path.suffix.lower() == '.csv':
        previous = csv.field_size_limit()
        try:
            csv.field_size_limit(1024 * 1024)
            yield from input_records(path)
        finally:
            csv.field_size_limit(previous)
    else:
        raise ValueError('Input streaming chỉ hỗ trợ CSV hoặc JSONL.')


def prepare(source, input_path, output, limit=1000, seed=42, batch_size=100,
            max_output_bytes=50 * 1024 * 1024, dry_run=False, revision='', permission_evidence='', synthetic=False):
    if source not in SOURCES:
        raise ValueError('Nguồn không nằm trong allowlist.')
    if not (1 <= limit <= 500000 and 1 <= batch_size <= 1000 and 1 <= max_output_bytes <= 50 * 1024 * 1024):
        raise ValueError('Giới hạn rows/batch/bytes không hợp lệ; mỗi snapshot tối đa 50 MiB.')
    output, input_path = Path(output), Path(input_path)
    if output.resolve() == input_path.resolve() or output.suffix not in {'.jsonl', '.csv'}:
        raise ValueError('Output phải là file CSV/JSONL khác input.')
    if not synthetic and not permission_evidence.strip():
        raise ValueError('NEEDS_REVIEW: cần --permission-evidence mô tả quyền dùng input cục bộ; không phải chứng nhận pháp lý.')
    rng = random.Random(seed)
    counts = Counter()
    digest, input_digest, total, count = hashlib.sha256(), hashlib.sha256(), 0, 0
    with input_path.open('rb') as original:
        for chunk in iter(lambda: original.read(1024 * 1024), b''):
            input_digest.update(chunk)
    stream, owns_temporary = None, False
    temporary = output.with_suffix(output.suffix + '.part')
    try:
        if not dry_run:
            if output.exists() or output.with_suffix(output.suffix + '.manifest.json').exists():
                raise FileExistsError('Output/manifest đã tồn tại; chọn tên mới.')
            output.parent.mkdir(parents=True, exist_ok=True)
            stream = temporary.open('xb')
            owns_temporary = True
        batch, batch_bytes = [], 0
        exhausted = False
        def write_batch(rows):
            nonlocal total, count
            rng.shuffle(rows)
            for row in rows:
                mapped = map_record(row, source, revision, permission_evidence, synthetic)
                if output.suffix == '.csv':
                    buffer = io.StringIO(newline='')
                    values = {k: '|'.join(v) if k == 'required_skills' else json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in mapped.items()}
                    # CSV formula injection prevention; JSONL preserves exact raw text.
                    values = {k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in values.items()}
                    writer = csv.DictWriter(buffer, fieldnames=list(mapped), lineterminator='\n')
                    if count == 0:
                        writer.writeheader()
                    writer.writerow(values)
                    encoded = buffer.getvalue().encode('utf-8')
                else:
                    encoded = (json.dumps(mapped, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
                if total + len(encoded) > max_output_bytes:
                    return False
                if stream:
                    stream.write(encoded)
                digest.update(encoded)
                total += len(encoded)
                count += 1
                counts['missing_company'] += not bool(mapped['company_name'])
                counts['missing_experience'] += mapped['experience_years'] is None
                counts['missing_posted_day'] += mapped['posted_at'] is None
                from recruitment.domain.salary import salary
                counts['salary_' + salary(mapped['salary'])['salary_quality_status']] += 1
            return True
        for row in islice(bounded_records(input_path), limit):
            row_bytes = len(json.dumps(row, ensure_ascii=False).encode('utf-8'))
            if row_bytes > 1024 * 1024:
                raise ValueError('Bản ghi nguồn vượt 1 MiB.')
            batch.append(row)
            batch_bytes += row_bytes
            if len(batch) == batch_size or batch_bytes >= 4 * 1024 * 1024:
                if not write_batch(batch):
                    exhausted = True
                    break
                batch, batch_bytes = [], 0
        if batch and not exhausted:
            exhausted = not write_batch(batch)
        manifest = {'schema_version': 1, 'source': SOURCES[source]['dataset'], 'adapter_version': ADAPTER_VERSION,
            'source_revision': revision, 'source_url': SOURCES[source]['url'], 'license_permission': SOURCES[source]['license'],
            'permission_status': 'SYNTHETIC_FIXTURE' if synthetic else 'NEEDS_REVIEW',
            'permission_evidence': permission_evidence, 'dataset_origin': 'synthetic' if synthetic else 'public_unverified',
            'collected_at': None, 'prepared_at': datetime.now(timezone.utc).isoformat(),
            'input_sha256': input_digest.hexdigest(), 'sha256': digest.hexdigest(), 'row_count': count, 'bytes': total,
            'seed': seed, 'sampling_method': 'source prefix, bounded batch shuffle; NOT a random population sample',
            'limit': limit, 'batch_size': batch_size, 'byte_cap_reached': exhausted, 'counts': dict(counts)}
        if not dry_run:
            stream.close()
            stream = None
            if output.exists():
                raise FileExistsError('Output đã tồn tại; chọn tên mới.')
            temporary.replace(output)
            output.with_suffix(output.suffix + '.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return manifest
    finally:
        if stream:
            stream.close()
        if owns_temporary:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=SOURCES, required=True)
    parser.add_argument('--input', required=True, help='Export CSV/JSONL cục bộ đã có quyền sử dụng')
    parser.add_argument('--output', required=True)
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-output-bytes', type=int, default=50 * 1024 * 1024)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--revision', default='')
    parser.add_argument('--permission-evidence', default='')
    parser.add_argument('--synthetic', action='store_true', help='Input tự tạo để kiểm thử; không phải nguồn public')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.input, args.output, args.limit, args.seed, args.batch_size,
          args.max_output_bytes, args.dry_run, args.revision, args.permission_evidence, args.synthetic), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
