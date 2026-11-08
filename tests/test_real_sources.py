import hashlib
import json
import pytest
from bigdata.sources import map_record, experience
from bigdata.normalize import normalize
from recruitment.domain.salary import salary
from scripts.prepare_real_dataset import prepare


@pytest.mark.parametrize('value,expected,status', [('2 năm', 2, 'EXACT'), ('2-3 năm', None, 'INTERVAL'),
    ('Dưới 1 năm', None, 'INTERVAL'), ('Không yêu cầu', None, 'UNKNOWN'), (None, None, 'UNKNOWN')])
def test_source_experience(value, expected, status):
    years, meta = experience(value)
    assert years == expected and meta['status'] == status


@pytest.mark.parametrize('value,mid,status', [('15 - 35 triệu', 25e6, 'VALID_RANGE'), ('26 triệu', 26e6, 'VALID_RANGE'),
    ('40tr', 40e6, 'VALID_RANGE'), ('1.000 USD', None, 'FX_REQUIRED'), ('thỏa thuận', None, 'UNDISCLOSED'),
    ('upto 40tr', None, 'ONE_SIDED'), ('26 triệu NET', 26e6, 'VALID_RANGE')])
def test_public_salary_forms(value, mid, status):
    parsed = salary(value)
    assert parsed['salary_original_text'] == value
    assert parsed['salary_mid_vnd'] == mid and parsed['salary_quality_status'] == status


def test_mapping_no_invented_company_dates_skills_or_urls():
    raw = {'id': 0, 'job_title': 'Kỹ sư', 'salary': '40tr', 'location': 'Nhiều nơi', 'experience_level': '2-3 năm', 'year': 2024}
    mapped = map_record(raw, 'tinix')
    assert mapped['source_job_id'] == '0'
    assert mapped['company_name'] is None and mapped['source_url'] is None
    assert mapped['posted_at'] is None and mapped['posted_year'] == 2024
    assert mapped['experience_years'] is None and mapped['required_skills'] == []
    assert mapped['province'] == 'Unknown' and mapped['source_metadata']['permission_status'] == 'NEEDS_REVIEW'
    result = normalize(json.dumps(mapped), 'raw', 1, 'tinix')
    assert result['posted_at'] is None and result['posted_year'] == 2024
    assert result['error_code'] == 'MISSING_COMPANY'
    assert map_record(raw, 'vietjobs')['company_name'] is None
    with pytest.raises(KeyError):
        map_record(raw, 'http://169.254.169.254')


def test_streaming_determinism_unicode_byte_cap_and_dry_run(tmp_path):
    # Original synthetic fixture: no third-party corpus copied into repository.
    path = tmp_path / 'fixture.jsonl'
    path.write_text('\n'.join(json.dumps({'id': i, 'job_title': 'Kỹ sư thử nghiệm', 'company_name': 'SYNTHETIC A',
        'salary': '26 triệu', 'year': 2023}) for i in range(1000)), encoding='utf-8')
    manifests = []
    for name in ['a.jsonl', 'b.jsonl']:
        manifests.append(prepare('tinix', path, tmp_path / name, limit=1000, batch_size=32, seed=42,
            max_output_bytes=100000, synthetic=True))
    assert (tmp_path / 'a.jsonl').read_bytes() == (tmp_path / 'b.jsonl').read_bytes()
    result = manifests[0]
    assert 0 < result['row_count'] < 1000 and result['bytes'] <= 100000 and result['byte_cap_reached']
    assert hashlib.sha256((tmp_path / 'a.jsonl').read_bytes()).hexdigest() == result['sha256']
    dry = prepare('tinix', path, tmp_path / 'dry.jsonl', limit=10, synthetic=True, dry_run=True)
    assert dry['row_count'] == 10 and not (tmp_path / 'dry.jsonl').exists()
    assert dry['permission_status'] == 'SYNTHETIC_FIXTURE'
    with pytest.raises(ValueError, match='NEEDS_REVIEW'):
        prepare('tinix', path, tmp_path / 'denied.jsonl')
    with pytest.raises(FileExistsError):
        prepare('tinix', path, tmp_path / 'a.jsonl', synthetic=True)
    reserved = tmp_path / 'reserved.jsonl.part'
    reserved.write_text('another process owns this file', encoding='utf-8')
    with pytest.raises(FileExistsError):
        prepare('tinix', path, tmp_path / 'reserved.jsonl', synthetic=True)
    assert reserved.read_text(encoding='utf-8') == 'another process owns this file'


def test_csv_formula_injection(tmp_path):
    path = tmp_path / 'input.jsonl'
    path.write_text(json.dumps({'id': 1, 'job_title': '=HYPERLINK("x")'}), encoding='utf-8')
    output = tmp_path / 'safe.csv'
    prepare('tinix', path, output, synthetic=True)
    import csv
    with output.open(encoding='utf-8') as stream:
        assert next(csv.DictReader(stream))['job_title'].startswith("'=")


def test_csv_roundtrip_preserves_provenance_and_no_fake_skill(tmp_path):
    from bigdata.ingestion import input_records
    source = tmp_path / 'input.jsonl'
    source.write_text(json.dumps({'id': 0, 'job_title': 'Kỹ sư', 'company_name': 'SYNTHETIC A', 'experience_level': '2-3 năm', 'year': 2024}), encoding='utf-8')
    output = tmp_path / 'output.csv'
    prepare('tinix', source, output, synthetic=True)
    row = next(input_records(output))
    cleaned = normalize(json.dumps(row), 'test', 1, 'tinix')
    assert cleaned['required_skills'] == [] and cleaned['experience_years'] is None
    assert cleaned['source_job_key'] == 'tinix:0' and cleaned['original_record_id'] == '0'
    assert cleaned['posted_year'] == 2024 and cleaned['posted_at'] is None
    assert json.loads(cleaned['provenance_json'])['permission_status'] == 'SYNTHETIC_FIXTURE'
    assert json.loads(cleaned['experience_metadata_json'])['status'] == 'INTERVAL'


def test_limit_does_not_parse_records_beyond_requested_prefix(tmp_path):
    source = tmp_path / 'limited.jsonl'
    source.write_text('\n'.join(json.dumps({'id': i, 'job_title': 'SYNTHETIC'}) for i in range(10)) + '\nnot JSON outside requested prefix\n', encoding='utf-8')
    result = prepare('tinix', source, tmp_path / 'output.jsonl', limit=10, synthetic=True)
    assert result['row_count'] == 10
