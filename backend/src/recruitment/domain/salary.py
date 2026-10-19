import math
import re
import unicodedata


def number(value):
    value = value.strip()
    if re.fullmatch(r'\d{1,3}([.,]\d{3})+', value):
        value = re.sub('[.,]', '', value)
    else:
        value = value.replace(',', '.')
    result = float(value)
    return result if math.isfinite(result) else None


def salary(text, currency=None, period=None, normalization=None):
    normalization=normalization or {}
    if isinstance(currency,str):currency=currency.strip().upper()
    if isinstance(period,str):period=period.strip().upper()
    original = str(text or '')
    value = unicodedata.normalize('NFC', original).lower().strip()
    result = {'salary_original_text': original, 'salary_min_vnd': None,
        'salary_max_vnd': None, 'salary_mid_vnd': None, 'salary_is_disclosed': False,
        'salary_quality_status': 'UNDISCLOSED', 'salary_currency': currency,
        'salary_period': period or 'MONTH', 'salary_basis': 'NET' if 'net' in value else 'GROSS' if 'gross' in value else 'UNKNOWN',
        'salary_parse_method': 'salary-v1', 'fx_rate_reference': None, 'fx_rate_date': None,
        'salary_normalization_assumptions': []}
    if not value or any(x in value for x in ['negotiable', 'competitive', 'thỏa thuận', 'thoả thuận', 'không công khai']):
        return result
    if re.match(r'^-\s*\d', value):
        result['salary_quality_status']='INVALID_VALUE';return result
    currency = (currency or ('USD' if 'usd' in value or '$' in value else 'VND' if re.search(r'vnd|triệu|trieu|\bđ\b', value) else '')).upper()
    result['salary_currency'] = currency or None
    result['salary_is_disclosed'] = True
    values = re.findall(r'\d+(?:[.,]\d+)*', value)
    if not values or len(values) > 2:
        result['salary_quality_status'] = 'UNPARSEABLE';return result
    parsed = [number(x) for x in values]
    if any(x is None for x in parsed):
        result['salary_quality_status']='INVALID_VALUE';return result
    scale = 1_000_000 if 'triệu' in value or 'trieu' in value else 1
    parsed = [x * scale for x in parsed]
    if any(x <= 0 or x > 1e12 for x in parsed):
        result['salary_quality_status'] = 'INVALID_VALUE';return result
    lower = upper = None
    if len(parsed) == 2:
        lower, upper = parsed
    elif any(x in value for x in ['up to', 'tối đa', 'đến ', 'dưới']):
        upper = parsed[0]
    elif any(x in value for x in ['from ', 'từ ', 'trên', 'at least']):
        lower = parsed[0]
    else:
        lower = upper = parsed[0]
    if lower is not None and upper is not None and lower > upper:
        result['salary_quality_status'] = 'REVERSED_RANGE';return result
    result['salary_min']=lower;result['salary_max']=upper
    fx=1
    if currency != 'VND':
        rate=normalization.get('rates',{}).get(currency,{})
        if not rate.get('rate') or not rate.get('source') or not rate.get('date'):
            result['salary_quality_status'] = 'FX_REQUIRED';return result
        fx=float(rate['rate'])
        if not math.isfinite(fx) or fx<=0:
            result['salary_quality_status']='FX_REQUIRED';return result
        result['fx_rate_reference']=rate['source'];result['fx_rate_date']=rate['date']
    factor = 1
    if period == 'YEAR' or re.search(r'/năm|/year|annum|annual', value):
        factor = 1/12;result['salary_period'] = 'YEAR'
        result['salary_normalization_assumptions'] = ['12 months/year']
    elif period=='HOUR' or re.search(r'/giờ|/hour',value):
        hours=normalization.get('hours_per_month')
        if not hours:
            result['salary_quality_status']='WORK_TIME_ASSUMPTION_REQUIRED';return result
        factor=hours;result['salary_period']='HOUR';result['salary_normalization_assumptions']=[f'{hours} hours/month (configured)']
    elif period=='DAY' or re.search(r'/ngày|/day',value):
        days=normalization.get('days_per_month')
        if not days:
            result['salary_quality_status']='WORK_TIME_ASSUMPTION_REQUIRED';return result
        factor=days;result['salary_period']='DAY';result['salary_normalization_assumptions']=[f'{days} days/month (configured)']
    result['salary_min_vnd'] = lower*factor*fx if lower is not None else None
    result['salary_max_vnd'] = upper*factor*fx if upper is not None else None
    if lower is not None and upper is not None:
        result['salary_mid_vnd'] = (lower+upper)*factor*fx/2
        result['salary_quality_status'] = 'VALID_RANGE'
    else:
        result['salary_quality_status'] = 'ONE_SIDED'
    return result
