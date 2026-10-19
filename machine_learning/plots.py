import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def diagnostics(directory,pipeline,predictions):
    actual=np.array([p['actual'] for p in predictions])/1e6
    predicted=np.array([p['predicted'] for p in predictions])/1e6
    fig,ax=plt.subplots(figsize=(6,4),layout='constrained')
    ax.scatter(actual,predicted,s=14,alpha=.6,color='#2563eb')
    lower,upper=min(actual.min(),predicted.min()),max(actual.max(),predicted.max())
    ax.plot([lower,upper],[lower,upper],'--',color='#94a3b8')
    ax.set(xlabel='Actual (million VND/month)',ylabel='Predicted (million VND/month)',title='Holdout: actual vs predicted')
    fig.savefig(directory/'actual-vs-predicted.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,4),layout='constrained');ax.hist(actual-predicted,bins=25,color='#2563eb',alpha=.8)
    ax.set(xlabel='Actual - predicted (million VND/month)',ylabel='Records',title='Holdout residual distribution')
    fig.savefig(directory/'residuals.png',dpi=160);plt.close(fig)
    model=pipeline['model'];weights=getattr(model,'feature_importances_',getattr(model,'coef_',None))
    importance=[]
    if weights is not None:
        names=pipeline['features'].get_feature_names_out();indices=np.argsort(np.abs(weights))[-15:]
        importance=[{'feature':str(names[i]),'value':float(weights[i])} for i in indices[::-1]]
        fig,ax=plt.subplots(figsize=(8,5),layout='constrained');ax.barh([names[i] for i in indices],[abs(float(weights[i])) for i in indices],color='#73a6b7')
        ax.set(title='Feature importance / absolute coefficient',xlabel='Importance (model dependent)')
        fig.savefig(directory/'importance.png',dpi=160);plt.close(fig)
    (directory/'importance.json').write_text(json.dumps(importance),encoding='utf-8')
    return importance
