import json
from recruitment.adapters.mongo import database
from recruitment.application.datasets import published
db=database();dataset,match=published(db)
query={**match,'province':'Hồ Chí Minh'}
index='dataset_version_1_attempt_id_1_province_1_industry_1_posted_at_1'
natural=db.cleaned_jobs.find(query).sort([('industry',1),('posted_at',1)]).hint([('$natural',1)]).explain()
indexed=db.cleaned_jobs.find(query).sort([('industry',1),('posted_at',1)]).hint(index).explain()
def summary(value):
    stats=value['executionStats']
    return {k:stats[k] for k in ['nReturned','totalDocsExamined','totalKeysExamined','executionTimeMillis']}
aggregation=list(db.cleaned_jobs.aggregate([{'$match':match},{'$group':{'_id':'$province','jobs':{'$sum':1},
    'salary_sample_size':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},'mean_salary_vnd':{'$avg':'$salary_mid_vnd'}}},{'$sort':{'jobs':-1}}]))
result={'dataset_version':dataset['_id'],'natural_scan':summary(natural),'indexed_scan':summary(indexed),'index':index,
    'aggregation':aggregation,'indexes':list(db.cleaned_jobs.index_information()),'method':'Same query with natural-scan and compound-index hints; no index dropped'}
assert result['natural_scan']['nReturned']==result['indexed_scan']['nReturned']
db.audit_logs.insert_one({'action':'MONGO_EVIDENCE','created_at':__import__('recruitment.domain.common',fromlist=['now']).now(),'details':result})
print(json.dumps(result,ensure_ascii=False))
