from recruitment.application.analytics import describe_groups


def test_group_statistics_small_samples_and_zero_labels():
    rows=describe_groups([
        {'jobs':4,'salary_sample_size':2,'percentiles':[10,15,20,25]},
        {'jobs':30,'salary_sample_size':30,'percentiles':[10,15,20,25]},
        {'jobs':2,'salary_sample_size':0,'percentiles':None},
    ])
    assert rows[0]['median_salary_vnd']==15
    assert rows[0]['p25'] is None
    assert rows[0]['warnings']==['SMALL_SALARY_SAMPLE']
    assert rows[0]['missing_salary_rate']==.5
    assert rows[1]['p25']==10 and rows[1]['warnings']==[]
    assert rows[2]['median_salary_vnd'] is None
    assert rows[2]['missing_salary_rate']==1
