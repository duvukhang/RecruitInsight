import re
from datetime import date,timedelta
from recruitment.application.datasets import published
from recruitment.domain.common import AppError


class AnalyticsService:
    def __init__(self, db, version=None, province=None, industry=None, posted_from=None, posted_to=None):
        self.db=db
        self.dataset,self.match=published(db,version)
        if province:self.match['province']=province
        if industry:self.match['industry']=industry
        if posted_from or posted_to:
            self.match['posted_at']={}
            if posted_from:self.match['posted_at']['$gte']=posted_from
            if posted_to:self.match['posted_at']['$lt']=(date.fromisoformat(posted_to)+timedelta(days=1)).isoformat()
        self.filtered=bool(province or industry or posted_from or posted_to)

    def metadata(self):
        if not self.filtered:
            snapshot=self.db.analytics_snapshots.find_one({'dataset_version':self.dataset['_id'],'attempt_id':self.dataset['published_attempt_id']})
            total=snapshot['data']['overview']['total_jobs'];eligible=snapshot['data']['overview']['salary_sample_size']
        else:
            total=self.db.cleaned_jobs.count_documents(self.match,maxTimeMS=5000)
            eligible=self.db.cleaned_jobs.count_documents({**self.match,'salary_mid_vnd':{'$gt':0}},maxTimeMS=5000)
        warnings=['DEMO_DATA'] if self.dataset['is_demo'] else []
        if 0<total<30:warnings.append('SMALL_SAMPLE')
        if total and eligible/total<.5:warnings.append('HIGH_MISSING_SALARY_LABEL_RATE')
        return {'dataset_version':self.dataset['_id'],'attempt_id':self.dataset['published_attempt_id'],
                'is_demo':self.dataset['is_demo'],'updated_at':self.dataset.get('published_at'),
                'sample_size':total,'eligible_count':eligible,'missing_salary_rate':1-eligible/total if total else None,
                'currency':'VND','period':'MONTH','warnings':warnings,
                'filters':self.match,'method':'spark-sql-v1; percentile_approx accuracy=10000' if not self.filtered else 'mongodb-filtered-v1; approximate percentile'}

    def query(self,pipeline):
        return list(self.db.cleaned_jobs.aggregate([{'$match':self.match},*pipeline],maxTimeMS=5000))

    def metric(self,name):
        mapping={'overview':'overview','salary-by-industry':'industries','salary-by-location':'locations',
                 'top-skills':'skills','job-trends':'trends','experience':'experience','companies':'companies','salary-distribution':'histogram'}
        if not self.filtered:
            snapshot=self.db.analytics_snapshots.find_one({'dataset_version':self.dataset['_id'],'attempt_id':self.dataset['published_attempt_id']})
            return {'data':snapshot['data'][mapping[name]],'meta':self.metadata()}
        if name=='overview':
            records=self.query([{'$group':{'_id':None,'total_jobs':{'$sum':1},
                'total_companies':{'$addToSet':'$company_key'},'total_industries':{'$addToSet':'$industry'},
                'salary_sample_size':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},
                'mean_salary_vnd':{'$avg':'$salary_mid_vnd'},
                'percentiles':{'$percentile':{'input':'$salary_mid_vnd','p':[.25,.5,.75,.9],'method':'approximate'}}}}])
            if records:
                data=records[0];data.pop('_id',None)
                data['total_companies']=len(data['total_companies']);data['total_industries']=len(data['total_industries'])
                values=data.pop('percentiles')
                data.update(dict(zip(['p25','median_salary_vnd','p75','p90'],values)))
            else:data={'total_jobs':0,'total_companies':0,'total_industries':0,'salary_sample_size':0,'median_salary_vnd':None}
        elif name in ['salary-by-industry','salary-by-location','experience','companies']:
            field={'salary-by-industry':'industry','salary-by-location':'province','experience':'experience_years','companies':'company_name'}[name]
            data=self.query([{'$group':{'_id':'$'+field,'jobs':{'$sum':1},'salary_sample_size':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},'mean_salary_vnd':{'$avg':'$salary_mid_vnd'}}},{'$sort':{'jobs':-1}},{'$limit':100}])
            for row in data:row[field]=row.pop('_id')
        elif name=='top-skills':
            data=self.query([{'$unwind':'$required_skills'},{'$group':{'_id':'$required_skills','count':{'$sum':1}}},{'$sort':{'count':-1}},{'$limit':30}])
            for row in data:row['skill']=row.pop('_id')
        elif name=='job-trends':
            data=self.query([{'$match':{'posted_at':{'$ne':None}}},{'$group':{'_id':{'$substrCP':['$posted_at',0,7]},'count':{'$sum':1}}},{'$sort':{'_id':1}},{'$limit':120}])
            for row in data:row['month']=row.pop('_id')
        else:
            data=self.query([{'$match':{'salary_mid_vnd':{'$gt':0}}},{'$group':{'_id':{'$multiply':[{'$floor':{'$divide':['$salary_mid_vnd',5000000]}},5000000]},'count':{'$sum':1}}},{'$sort':{'_id':1}},{'$limit':100}])
            for row in data:row['lower_vnd']=row.pop('_id')
        return {'data':data,'meta':self.metadata()}
