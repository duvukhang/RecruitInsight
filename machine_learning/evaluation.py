"""Holdout diagnostics only; these groups must never be model inputs or selectors."""
import math
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, median_absolute_error


def metrics(actual, predicted):
    values={'mae':mean_absolute_error(actual,predicted),'rmse':math.sqrt(mean_squared_error(actual,predicted)),
            'r2':r2_score(actual,predicted) if len(actual)>1 and len(set(actual))>1 else None,
            'median_absolute_error':median_absolute_error(actual,predicted)}
    return {k:float(v) if v is not None and math.isfinite(v) else None for k,v in values.items()}


def experience_group(value):
    return 'Unknown' if value is None else '<1' if value < 1 else '1–<3' if value < 3 else '3–<5' if value < 5 else '5+'


def grouped_errors(records, actual, predicted, minimum=30):
    if not (len(records)==len(actual)==len(predicted)):
        raise ValueError('Holdout records and predictions must align')
    dimensions={
        'industry':lambda r:r.get('industry') or 'Unknown',
        'province':lambda r:r.get('province') or 'Unknown',
        'experience_group':lambda r:experience_group(r.get('experience_years')),
        'salary_band':lambda r:f"{int(r['salary_mid_vnd']//10_000_000)*10}–<{(int(r['salary_mid_vnd']//10_000_000)+1)*10} million VND/month",
        'title_group':lambda r:str(r.get('job_title_normalized') or r.get('job_title') or 'Unknown').strip().lower(),
    }
    rows=[];suppressed={}
    for dimension, key in dimensions.items():
        groups={}
        for i,record in enumerate(records):
            groups.setdefault(key(record),[]).append(i)
        suppressed[dimension]=sum(len(ids)<minimum for ids in groups.values())
        for group,ids in sorted(groups.items()):
            if len(ids)>=minimum:
                rows.append({'dimension':dimension,'group':group,'n':len(ids),
                    'metrics':metrics([actual[i] for i in ids],[predicted[i] for i in ids])})
    return rows, {'minimum_samples':minimum,'suppressed_group_counts':suppressed,
                  'population':'holdout test only','salary_band_width_vnd':10_000_000,
                  'title_group_rule':'exact normalized title; no occupation taxonomy inferred',
                  'interpretation':'Descriptive errors; group membership does not establish causation.'}
