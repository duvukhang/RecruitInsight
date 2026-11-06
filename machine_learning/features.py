import math

CATEGORICAL=['job_title','industry','province','seniority_level','education_level','employment_type','remote_type']


def features(record):
    result={column:str(record.get(column) or 'Unknown').strip().lower() for column in CATEGORICAL}
    missing = record.get('experience_years') is None or record.get('experience_years') == ''
    experience=0.0 if missing else float(record['experience_years'])
    if not math.isfinite(experience) or not 0<=experience<=60:
        raise ValueError('Invalid experience')
    result['experience_years']=experience
    result['experience_missing']=float(missing)
    for skill in record.get('required_skills',record.get('skills',[])):
        result['skill='+str(skill).strip().lower()]=1.0
    return result
