import pytest
from recruitment.domain.salary import salary
from bigdata.normalize import normalize
import json


@pytest.mark.parametrize('value,mid,status',[
    ('10–15 triệu VND/tháng',12500000,'VALID_RANGE'),
    ('20 triệu/tháng',20000000,'VALID_RANGE'),
    ('1.000 USD/tháng',None,'FX_REQUIRED'),
    ('15–20 USD/giờ',None,'FX_REQUIRED'),
    ('Up to 30 triệu',None,'ONE_SIDED'),
    ('From 15 triệu',None,'ONE_SIDED'),
    ('Negotiable',None,'UNDISCLOSED'),
    ('Competitive',None,'UNDISCLOSED'),
    ('30–10 triệu',None,'REVERSED_RANGE'),
    ('240 triệu VND/năm',20000000,'VALID_RANGE'),
    ('-10 triệu',None,'INVALID_VALUE'),
])
def test_salary(value,mid,status):
    parsed=salary(value)
    assert parsed['salary_mid_vnd']==mid
    assert parsed['salary_quality_status']==status


def test_normalization_preserves_key_and_unknown_salary():
    raw=json.dumps({'source_job_id':'a','job_title':'  Data   Engineer ','company_name':' A ','salary':'Negotiable'})
    first=normalize(raw,'r1',1,'TEST');second=normalize(raw,'r2',2,'TEST')
    assert first['source_job_key']==second['source_job_key']
    assert first['job_title']=='Data Engineer'
    assert first['salary_mid_vnd'] is None


def test_fx_and_hour_assumptions_have_provenance():
    config={'rates':{'USD':{'rate':25000,'source':'TEST_FIXTURE_NOT_MARKET_RATE','date':'2026-01-01'}},'hours_per_month':160}
    parsed=salary('15–20 USD/giờ',normalization=config)
    assert parsed['salary_mid_vnd']==70000000
    assert parsed['fx_rate_reference']=='TEST_FIXTURE_NOT_MARKET_RATE'
    assert parsed['salary_normalization_assumptions']==['160 hours/month (configured)']
    assert salary('1000 USD/tháng',normalization={'rates':{'USD':{'rate':25000}}})['salary_mid_vnd'] is None


def test_invalid_currency_type_is_quarantined_instead_of_crashing_spark():
    record=normalize(json.dumps({'job_title':'Engineer','company_name':'A','salary':'1000','salary_currency':{'unexpected':'object'}}),'raw-1',1,'TEST')
    assert record['error_code']=='INVALID_SALARY_FIELDS'
    assert record['salary_mid_vnd'] is None


@pytest.mark.parametrize('value', [None, '', '   '])
def test_missing_experience_remains_unknown(value):
    record=normalize(json.dumps({'job_title':'Engineer','company_name':'A','experience_years':value}),'r',1,'TEST')
    assert record['experience_years'] is None
    assert record['error_code'] is None


@pytest.mark.parametrize('value', [-1, 61, 'nan', 'infinity', 'not a number', True])
def test_invalid_experience_is_quarantined(value):
    record=normalize(json.dumps({'job_title':'Engineer','company_name':'A','experience_years':value}),'r',1,'TEST')
    assert record['experience_years'] is None
    assert record['error_code']=='INVALID_EXPERIENCE'


def test_zero_experience_and_unsupported_pay_period():
    record=normalize(json.dumps({'job_title':'Engineer','company_name':'A','experience_years':0}),'r',1,'TEST')
    assert record['experience_years']==0
    assert salary('10 triệu',period='WEEK')['salary_quality_status']=='UNSUPPORTED_PERIOD'
    assert salary('10 triệu',period='WEEK')['salary_mid_vnd'] is None
