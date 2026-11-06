import pytest
from bigdata.quality import quality_metrics
from recruitment.api.data import SourceMetadata


def test_quality_denominators_reconciliation_and_missing():
    counts={'raw':10,'clean':6,'invalid':2,'duplicate':2}
    report=quality_metrics(counts,{'job_title':1,'company_name':2,'source':0,'experience_years':4},5,3,2,1)
    assert report['completeness']==pytest.approx(27/30)
    assert report['validity']==.8
    assert report['uniqueness']==.75
    assert report['consistency']==pytest.approx(5/6)
    assert report['training_eligible_rate']==pytest.approx(2/6)
    assert report['salary_label_usability']==.5
    assert report['missing_by_field']['experience_years']['rate']==.4
    assert report['reconciliation']['balanced']
    with pytest.raises(ValueError):
        quality_metrics({**counts,'raw':11},{},0,0,0,0)


def test_empty_quality_is_not_perfect_quality():
    report=quality_metrics(dict.fromkeys(['raw','clean','invalid','duplicate'],0),
                           dict.fromkeys(['job_title','company_name','source'],0),0,0,0,0)
    assert all(report[k] is None for k in ['completeness','validity','uniqueness','consistency','salary_label_usability'])


def test_provenance_does_not_invent_permission_or_observation_dates():
    assert SourceMetadata().model_dump(exclude_none=True)=={}
    metadata=SourceMetadata.model_validate_json('{"source_type":"synthetic","license_permission":"TEST ONLY","observation_from":"2026-01-01","observation_to":"2026-02-01"}')
    assert metadata.model_dump(mode='json')['observation_from']=='2026-01-01'
    with pytest.raises(ValueError):
        SourceMetadata(observation_from='2026-02-01',observation_to='2026-01-01')
