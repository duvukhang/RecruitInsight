import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from recruitment.domain.salary import salary


def text(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', str(value if value is not None else ''))).strip()


def metadata_object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def normalize(payload_json, raw_ref, record_number, source, normalization=None):
    raw = json.loads(payload_json)
    title = text(raw.get('job_title') or raw.get('title'))
    company = text(raw.get('company_name') or raw.get('company'))
    error = 'PARSE_ERROR' if raw.get('_parse_error') else 'MISSING_TITLE' if not title else 'MISSING_COMPANY' if not company else None
    if raw.get('job_title',raw.get('title')) is not None and not isinstance(raw.get('job_title',raw.get('title')),str):error=error or 'INVALID_TITLE_TYPE'
    if raw.get('company_name',raw.get('company')) is not None and not isinstance(raw.get('company_name',raw.get('company')),str):error=error or 'INVALID_COMPANY_TYPE'
    try:
        experience_raw = raw.get('experience_years', raw.get('experience_years_min'))
        experience = None if experience_raw is None or (isinstance(experience_raw, str) and not experience_raw.strip()) else float(experience_raw)
        if experience is not None and (isinstance(experience_raw, bool) or not math.isfinite(experience) or experience < 0 or experience > 60):
            error = error or 'INVALID_EXPERIENCE';experience = None
    except (ValueError, TypeError):
        error = error or 'INVALID_EXPERIENCE';experience = None
    skills = raw.get('required_skills', raw.get('skills', []))
    if isinstance(skills, str):
        skills = re.split('[,;|]', skills)
    if not isinstance(skills, list):
        skills = []
    skills = sorted({text(skill).lower() for skill in skills if text(skill)})[:100]
    posted = text(raw.get('posted_at'))
    try:
        parsed=datetime.fromisoformat(posted.replace('Z','+00:00')) if posted else None
        posted=(parsed.replace(tzinfo=timezone.utc) if parsed and not parsed.tzinfo else parsed.astimezone(timezone.utc)).isoformat() if parsed else None
    except ValueError:
        posted = None
    year_raw = raw.get('posted_year')
    posted_year = int(year_raw) if not isinstance(year_raw, bool) and re.fullmatch(r'(?:19|20)\d{2}', str(year_raw)) else None
    if posted_year is None and posted:
        posted_year = int(posted[:4])
    try:
        if any(value is not None and not isinstance(value,str) for value in [raw.get('salary_currency'),raw.get('salary_period')]):
            raise TypeError('Invalid salary metadata type')
        normalized_salary = salary(raw.get('salary_original_text') or raw.get('salary'), raw.get('salary_currency'), raw.get('salary_period'),normalization)
    except (TypeError,ValueError,AttributeError,OverflowError):
        error=error or 'INVALID_SALARY_FIELDS'
        normalized_salary=salary(None)
    stable_key = source + ':' + text(raw.get('source_job_id')) if raw.get('source_job_id') is not None and text(raw.get('source_job_id')) else hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'raw_record_ref': raw_ref, 'record_number': record_number, 'source_job_key': stable_key,
        'global_duplicate_ref':raw.get('_global_duplicate_ref'),
        'error_code': error, 'job_title': title, 'job_title_normalized': title.lower(),
        'company_name': company, 'company_key': company.lower(), 'source': source,
        'province': text(raw.get('province') or raw.get('location')) or 'Unknown',
        'industry': text(raw.get('industry')) or 'Unknown',
        'experience_years': experience, 'required_skills': skills,
        'seniority_level': text(raw.get('seniority_level')) or 'Unknown',
        'education_level': text(raw.get('education_level')) or 'Unknown',
        'remote_type': text(raw.get('remote_type')) or 'Unknown',
        'employment_type': text(raw.get('employment_type')) or 'Unknown',
        'job_description': re.sub('<[^>]*>', ' ', text(raw.get('job_description'))),
        'posted_at': posted, 'posted_year': posted_year,
        'source_job_id': text(raw.get('source_job_id')), 'original_record_id': text(raw.get('original_record_id')),
        'dataset_origin': text(raw.get('dataset_origin')) or 'unknown',
        'provenance_json': json.dumps(metadata_object(raw.get('source_metadata')), ensure_ascii=False),
        'experience_metadata_json': json.dumps(metadata_object(raw.get('experience_metadata')), ensure_ascii=False),
        'source_url': text(raw.get('source_url')), **normalized_salary}
