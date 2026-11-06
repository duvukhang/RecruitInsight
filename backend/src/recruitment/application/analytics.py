import re
from datetime import date,timedelta
from recruitment.application.datasets import published
from recruitment.domain.common import AppError


MIN_GROUP_SALARY_SAMPLES = 30


def describe_groups(rows):
    """Same presentation rules for Spark snapshots and filtered Mongo results."""
    for row in rows:
        values = row.pop('percentiles', None) or [None] * 4
        row['median_salary_vnd'] = values[1]
        enough = row['salary_sample_size'] >= MIN_GROUP_SALARY_SAMPLES
        row.update({key: values[i] if enough else None for key, i in [('p25', 0), ('p75', 2), ('p90', 3)]})
        row['warnings'] = [] if enough else ['SMALL_SALARY_SAMPLE']
        row['missing_salary_rate'] = 1-row['salary_sample_size']/row['jobs'] if row['jobs'] else None
    return rows


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
        self.snapshot = None if self.filtered else self.db.analytics_snapshots.find_one({
            'dataset_version': self.dataset['_id'], 'attempt_id': self.dataset['published_attempt_id']})
        # Old immutable snapshots remain usable through live version-scoped queries.
        self.use_snapshot = bool(self.snapshot and self.snapshot.get('analytics_schema_version', 1) >= 2)

    def metadata(self):
        if self.use_snapshot:
            summary=self.snapshot['data']['overview']
            total=summary['total_jobs'];eligible=summary['salary_sample_size']
            period={'from':summary.get('posted_from'),'to':summary.get('posted_to')}
        else:
            rows=self.query([{'$group':{'_id':None,'total':{'$sum':1},
                'eligible':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},
                'from':{'$min':'$posted_at'},'to':{'$max':'$posted_at'}}}])
            summary=rows[0] if rows else {}
            total=summary.get('total',0);eligible=summary.get('eligible',0)
            period={'from':summary.get('from'),'to':summary.get('to')}
        warnings=['DEMO_DATA'] if self.dataset['is_demo'] else []
        if 0<total<30:warnings.append('SMALL_SAMPLE')
        if total and eligible/total<.5:warnings.append('HIGH_MISSING_SALARY_LABEL_RATE')
        return {'dataset_version':self.dataset['_id'],'attempt_id':self.dataset['published_attempt_id'],
                'is_demo':self.dataset['is_demo'],'updated_at':self.dataset.get('published_at'),
                'sample_size':total,'eligible_count':eligible,'missing_salary_rate':1-eligible/total if total else None,
                'currency':'VND','period':'MONTH','warnings':warnings,
                'reference_period':period,'source':self.dataset.get('source'),
                'source_metadata':self.dataset.get('source_metadata',{}),
                'minimum_group_salary_samples':MIN_GROUP_SALARY_SAMPLES,
                'interpretation':'Observed job postings and advertised monthly salaries; not national labour demand or take-home pay. Association is not causation.',
                'filters':self.match,'method':'spark-sql-v2; percentile_approx accuracy=10000' if self.use_snapshot else 'mongodb-filtered-v2; approximate percentile'}

    def query(self,pipeline):
        return list(self.db.cleaned_jobs.aggregate([{'$match':self.match},*pipeline],maxTimeMS=5000))

    def metric(self,name):
        mapping={'overview':'overview','salary-by-industry':'industries','salary-by-location':'locations',
                 'top-skills':'skills','job-trends':'trends','experience':'experience','companies':'companies','salary-distribution':'histogram'}
        if self.use_snapshot:
            return {'data':self.snapshot['data'][mapping[name]],'meta':self.metadata()}
        if name=='overview':
            records=self.query([{'$group':{'_id':None,'total_jobs':{'$sum':1},
                'total_companies':{'$addToSet':'$company_key'},'total_industries':{'$addToSet':'$industry'},
                'total_provinces':{'$addToSet':'$province'},'posted_from':{'$min':'$posted_at'},'posted_to':{'$max':'$posted_at'},
                'salary_sample_size':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},
                'mean_salary_vnd':{'$avg':'$salary_mid_vnd'},
                'percentiles':{'$percentile':{'input':'$salary_mid_vnd','p':[.25,.5,.75,.9],'method':'approximate'}}}}])
            if records:
                data=records[0];data.pop('_id',None)
                data['total_companies']=len(data['total_companies'])
                data['total_industries']=len([v for v in data['total_industries'] if v and v!='Unknown'])
                data['total_provinces']=len([v for v in data['total_provinces'] if v and v!='Unknown'])
                values=data.pop('percentiles')
                data.update(dict(zip(['p25','median_salary_vnd','p75','p90'],values)))
            else:data={'total_jobs':0,'total_companies':0,'total_industries':0,'total_provinces':0,
                       'salary_sample_size':0,'mean_salary_vnd':None,'median_salary_vnd':None,
                       'p25':None,'p75':None,'p90':None,'posted_from':None,'posted_to':None}
        elif name in ['salary-by-industry','salary-by-location','experience','companies']:
            field={'salary-by-industry':'industry','salary-by-location':'province','experience':'experience_years','companies':'company_name'}[name]
            data=self.query([{'$group':{'_id':'$'+field,'jobs':{'$sum':1},'salary_sample_size':{'$sum':{'$cond':[{'$gt':['$salary_mid_vnd',0]},1,0]}},'mean_salary_vnd':{'$avg':'$salary_mid_vnd'},
                'percentiles':{'$percentile':{'input':'$salary_mid_vnd','p':[.25,.5,.75,.9],'method':'approximate'}}}},
                {'$sort':{'jobs':-1,'_id':1}},{'$limit':100}])
            for row in data:row[field]=row.pop('_id')
            data=describe_groups(data)
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
