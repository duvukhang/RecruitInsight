"""Ratios with explicit populations; counts come from Spark actions, never defaults."""


def quality_metrics(counts, missing, consistent, salary_labels, training_eligible, recent):
    raw, clean = counts['raw'], counts['clean']
    if raw != clean + counts['invalid'] + counts['duplicate']:
        raise ValueError('ETL reconciliation failed')
    def ratio(numerator, denominator):
        return numerator / denominator if denominator else None
    required = ['job_title', 'company_name', 'source']
    return {
        'reconciliation': {'raw': raw, 'classified': clean + counts['invalid'] + counts['duplicate'], 'balanced': True},
        'completeness': ratio(sum(raw - missing[field] for field in required), raw * len(required)),
        'validity': ratio(raw - counts['invalid'], raw),
        'uniqueness': ratio(clean, raw - counts['invalid']),
        'consistency': ratio(consistent, clean),
        'salary_label_usability': ratio(salary_labels, clean),
        'training_eligible_rate': ratio(training_eligible, clean),
        'timeliness': ratio(recent, clean),
        'missing_by_field': {field: {'missing': count, 'denominator': raw, 'rate': ratio(count, raw)} for field, count in missing.items()},
        'metric_counts': {'raw': raw, 'clean': clean, 'consistent': consistent,
                          'salary_labels': salary_labels, 'training_eligible': training_eligible, 'recent': recent},
        'definitions': {
            'completeness': 'present title/company/source cells / (3 * raw)',
            'validity': '(raw - invalid) / raw', 'uniqueness': 'clean / (raw - invalid)',
            'consistency': 'clean passing title/company, experience bounds and salary midpoint rules / clean',
            'salary_label_usability': 'clean with positive normalized midpoint / clean (includes NET)',
            'training_eligible_rate': 'clean with positive midpoint and basis != NET / clean (local ML)',
            'missing_by_field': 'null, blank or Unknown after normalization / raw',
            'timeliness': 'clean posted within past 180 days, excluding future dates / clean',
            'zero_denominator': 'null = NOT_COMPUTABLE',
        },
    }
