"""Đối soát observations, checksum, source/input hashes và summary của benchmark đã chạy."""
import argparse
import ast
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


def verify(root, archive):
    root, archive = Path(root), Path(archive)
    environment = json.loads((root / 'environment.json').read_text(encoding='utf-8'))
    summary = json.loads((root / 'summary.json').read_text(encoding='utf-8'))
    with (root / 'observations.csv').open(encoding='utf-8', newline='') as stream:
        observations = list(csv.DictReader(stream))
    sizes = sorted(map(int, environment['input_hashes']))
    expected = {(size, config) for size in sizes for config in ['local1', 'cluster1', 'cluster2']}
    grouped, fingerprints = {}, {}
    for row in observations:
        size, config = int(row['rows']), row['configuration']
        elapsed = float(row['elapsed_seconds'])
        assert elapsed > 0 and math.isclose(float(row['rows_per_second']), size / elapsed, rel_tol=1e-9)
        fingerprint = sorted(ast.literal_eval(row['fingerprint']))
        assert sum(item[1] for item in fingerprint) == size
        assert all(item[0] in ['clean', 'invalid', 'duplicate'] for item in fingerprint)
        if size in fingerprints:
            assert fingerprints[size] == fingerprint, 'Checksum khác giữa repetition/configuration'
        fingerprints[size] = fingerprint
        assert int(row['executors']) == {'local1': 0, 'cluster1': 1, 'cluster2': 2}[config]
        assert int(row['output_partitions']) > 0
        assert int(row['scheduled_tasks']) == sum(stage['tasks'] for stage in ast.literal_eval(row['stages']))
        grouped.setdefault((size, config), []).append(row)
    assert set(grouped) == expected
    for rows in grouped.values():
        assert sorted(int(row['repetition']) for row in rows) == [1, 2, 3]
    assert len(summary) == len(expected) and {(row['rows'], row['configuration']) for row in summary} == expected
    for row in summary:
        values = [float(item['elapsed_seconds']) for item in grouped[(row['rows'], row['configuration'])]]
        baseline = statistics.median(float(item['elapsed_seconds']) for item in grouped[(row['rows'], 'local1')])
        for key, value in [('median_seconds', statistics.median(values)), ('min_seconds', min(values)),
                           ('max_seconds', max(values)), ('speedup_vs_local1', baseline / statistics.median(values))]:
            assert math.isclose(row[key], value, rel_tol=1e-9), key
    for name, expected_hash in environment['source_hashes'].items():
        path = archive / 'bigdata' / name if name != 'salary.py' else archive / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, name
    combined = b''.join((archive / 'bigdata' / name).read_bytes() for name in ['benchmark.py', 'etl.py', 'normalize.py'])
    assert hashlib.sha256(combined).hexdigest() == environment['source_sha256']
    for size, expected_hash in environment['input_hashes'].items():
        with (root / f'DEMO-{size}.raw.jsonl').open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected_hash, size
    return {'result': 'PASS', 'observations': len(observations), 'groups': len(expected), 'sizes': sizes,
        'source_hashes_verified': len(environment['source_hashes']), 'input_hashes_verified': len(sizes),
        'counts': {str(size): {kind: count for kind, count, checksum in fingerprint} for size, fingerprint in fingerprints.items()},
        'scope': 'Frozen source snapshot; timings exclude Mongo writes/startup and do not measure final-source latency.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = verify(args.root, args.archive)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
