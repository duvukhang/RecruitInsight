"""Đo adapter bằng fixture tự tạo; xuất các chunk JSONL dưới 50 MiB, không truy cập Mongo."""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4
from scripts.prepare_real_dataset import prepare


def run(root, sizes=(5000, 50000), chunk_rows=10000):
    root = Path(root) / uuid4().hex
    root.mkdir(parents=True)
    fixture = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures' / 'tinix-shape.synthetic.jsonl'
    templates = [json.loads(line) for line in fixture.read_text(encoding='utf-8').splitlines()]
    observations = []
    for size in sizes:
        directory = root / str(size)
        directory.mkdir()
        manifests, seconds = [], 0
        for start in range(0, size, chunk_rows):
            count = min(chunk_rows, size - start)
            source = directory / f'synthetic-input-{start}.jsonl'
            with source.open('w', encoding='utf-8') as stream:
                for index in range(start, start + count):
                    row = {**templates[index % len(templates)], 'id': 'SYNTHETIC-' + str(index)}
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            output = directory / f'chunk-{start}.jsonl'
            started = time.perf_counter()
            manifest = prepare('tinix', source, output, limit=count, batch_size=100, synthetic=True)
            seconds += time.perf_counter() - started
            assert manifest['row_count'] == count and not manifest['byte_cap_reached']
            manifests.append({'file': output.name, **manifest})
        observed = {'source': 'SYNTHETIC FIXTURE; not public corpus', 'input_rows': size,
            'output_rows': sum(m['row_count'] for m in manifests), 'chunk_count': len(manifests),
            'bytes': sum(m['bytes'] for m in manifests), 'max_chunk_bytes': max(m['bytes'] for m in manifests),
            'adapter_seconds': seconds, 'rows_per_second': size / seconds,
            'timing_scope': 'input SHA-256, mapping, serialization and manifest write; excludes fixture generation',
            'chunks': [{k: m[k] for k in ['file', 'row_count', 'bytes', 'sha256']} for m in manifests]}
        (directory / 'staged-manifest.json').write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding='utf-8')
        observations.append(observed)
    report = {'result': 'PASS', 'observations': observations, 'directory': str(root)}
    (root / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data/artifacts/adapter-evidence')
    parser.add_argument('--sizes', nargs='+', type=int, default=[5000, 50000])
    parser.add_argument('--chunk-rows', type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.chunk_rows <= 10000 or any(not 1 <= size <= 500000 for size in args.sizes):
        parser.error('Giới hạn chunk 1–10000 và quy mô 1–500000.')
    run(args.root, args.sizes, args.chunk_rows)
