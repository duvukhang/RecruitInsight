"""Verify saved observations without running Spark or inventing new measurements."""
import argparse
import ast
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


def verify(root):
    root=Path(root)
    observations=list(csv.DictReader((root/'benchmark-observations.csv').open(encoding='utf-8')))
    summary=json.loads((root/'benchmark-summary.json').read_text(encoding='utf-8'))
    expected={(size,config) for size in [100,10000,100000] for config in ['local1','cluster1','cluster2']}
    if {(int(r['rows']),r['configuration']) for r in observations} != expected:
        raise ValueError('Missing or unexpected benchmark configuration/scale')
    fingerprints={}
    for row in observations:
        size=int(row['rows']);elapsed=float(row['elapsed_seconds'])
        if elapsed<=0 or not math.isclose(float(row['rows_per_second']),size/elapsed,rel_tol=1e-9):
            raise ValueError('Invalid elapsed time or throughput')
        fingerprint=ast.literal_eval(row['fingerprint'])
        if sum(n for _,n,_ in fingerprint)!=size:
            raise ValueError('Output count mismatch')
        if size in fingerprints and fingerprint!=fingerprints[size]:
            raise ValueError('Checksums differ across repetitions/configurations')
        fingerprints[size]=fingerprint
    if {(r['rows'],r['configuration']) for r in summary} != expected or len(summary)!=9:
        raise ValueError('Summary coverage mismatch')
    for entry in summary:
        subset=[r for r in observations if int(r['rows'])==entry['rows'] and r['configuration']==entry['configuration']]
        if sorted(int(r['repetition']) for r in subset)!=[1,2,3]:
            raise ValueError('Expected exactly three measured repetitions')
        values=[float(r['elapsed_seconds']) for r in subset]
        local=statistics.median(float(r['elapsed_seconds']) for r in observations if int(r['rows'])==entry['rows'] and r['configuration']=='local1')
        for field,value in [('median_seconds',statistics.median(values)),('min_seconds',min(values)),('max_seconds',max(values)),('speedup_vs_local1',local/statistics.median(values))]:
            if not math.isclose(entry[field],value,rel_tol=1e-9):
                raise ValueError('Summary arithmetic mismatch: '+field)
    environment=json.loads((root/'benchmark-environment.json').read_text(encoding='utf-8'))
    archive=root/'benchmark-source'/'bigdata'
    source_hash=hashlib.sha256((archive/'etl.py').read_bytes()+(archive/'normalize.py').read_bytes()).hexdigest()
    if source_hash != environment['source_sha256']:
        raise ValueError('Archived workload source does not match historical environment hash')
    return {'status':'PASS','scope':'historical saved evidence consistency; not a new Spark run',
        'observations':len(observations),'configurations_and_scales':len(expected),
        'historical_source_hash_matches_archive':source_hash==environment['source_sha256'],
        'input_hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['benchmark-observations.csv','benchmark-summary.json','benchmark-environment.json']},
        'summary':summary}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('artifacts'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/upgrade-benchmark-verification.json'))
    args=parser.parse_args()
    result=verify(args.root)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['summary','input_hashes']}))
