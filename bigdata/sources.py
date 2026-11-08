"""Versioned, conservative mappings. No network access and no inferred dates/companies."""
import hashlib
import json
import re
import unicodedata

ADAPTER_VERSION = 'public-jobs-v1'
SOURCES = {
    'tinix': {'dataset': 'tinixai/vietnamese-job-descriptions', 'license': 'CC-BY-NC-4.0',
              'url': 'https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions', 'permission_status': 'NEEDS_REVIEW'},
    'vietjobs': {'dataset': 'dinhieufam/VietJobs', 'license': None,
                 'url': 'https://huggingface.co/datasets/dinhieufam/VietJobs', 'permission_status': 'NEEDS_REVIEW'},
}


def plain(value):
    return unicodedata.normalize('NFC', str(value)).strip() if value is not None else ''


def experience(value):
    raw = plain(value).lower()
    exact = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:năm|years?)', raw)
    interval = re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)\s*(?:năm|years?)', raw)
    if exact and 0 <= float(exact[1].replace(',', '.')) <= 60:
        years = float(exact[1].replace(',', '.'))
        return years, {'raw': value, 'status': 'EXACT', 'min': years, 'max': years}
    if interval and 0 <= int(interval[1]) <= int(interval[2]) <= 60:
        return None, {'raw': value, 'status': 'INTERVAL', 'min': int(interval[1]), 'max': int(interval[2])}
    if re.fullmatch(r'dưới\s+1\s+năm', raw):
        return None, {'raw': value, 'status': 'INTERVAL', 'min': 0, 'max_exclusive': 1}
    return None, {'raw': value, 'status': 'UNKNOWN'}


def map_record(raw, source, revision='', permission_evidence='', synthetic=False):
    provider = SOURCES[source]  # allowlist; never accepts arbitrary URLs
    encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    digest = hashlib.sha256(encoded).hexdigest()
    original_id = raw.get('id')
    identity = str(original_id) if original_id is not None else 'sha256:' + digest
    years, experience_metadata = experience(raw.get('experience_level' if source == 'tinix' else 'experience_required'))
    year = raw.get('year')
    year = int(year) if not isinstance(year, bool) and re.fullmatch(r'(?:19|20)\d{2}', str(year)) else None
    location = plain(raw.get('location'))
    provinces = {'hà nội': 'Hà Nội', 'hồ chí minh': 'Hồ Chí Minh', 'đà nẵng': 'Đà Nẵng'}
    description = plain(raw.get('job_description' if source == 'tinix' else 'description'))
    return {
        'source': provider['dataset'], 'source_job_id': identity, 'original_record_id': original_id,
        'dataset_origin': 'synthetic' if synthetic else 'public_unverified',
        'job_title': raw.get('job_title'), 'company_name': raw.get('company_name'),
        'salary': raw.get('salary'), 'salary_original_text': raw.get('salary'),
        'original_salary_text': raw.get('salary'), 'province': provinces.get(location.casefold(), 'Unknown'),
        'location_raw': raw.get('location'), 'industry': raw.get('job_industry' if source == 'tinix' else 'category'),
        'employment_type': raw.get('job_type' if source == 'tinix' else 'contract_type'),
        'remote_type': 'Unknown', 'experience_years': years,
        'experience_metadata': experience_metadata, 'education_level': raw.get('education_level'),
        'seniority_level': 'Unknown', 'seniority_raw': raw.get('job_position'),
        'required_skills': [], 'requirements_raw': raw.get('requirements' if source == 'tinix' else 'requirements_text'),
        'job_description': description[:30000], 'posted_at': None, 'posted_year': year,
        # Dataset URL belongs in provenance. It is not a job posting URL.
        'source_url': None,
        'source_metadata': {'adapter_version': ADAPTER_VERSION, 'source_revision': revision,
            'source_dataset_url': provider['url'], 'declared_license': provider['license'],
            'permission_status': 'SYNTHETIC_FIXTURE' if synthetic else 'NEEDS_REVIEW',
            'permission_evidence': permission_evidence, 'original_sha256': digest,
            'description_truncated': len(description) > 30000,
            'mapping': {'posted_year': 'year', 'posted_at': 'absent', 'skills': 'no validated extractor',
                        'company_name': 'original only', 'province': 'exact alias or Unknown'}},
    }
