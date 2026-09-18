"""Runtime model loading/training. Values labelled ML are always model outputs."""
import json
from pathlib import Path
MODELS=Path(__file__).parent/'models'; COMPLETION=MODELS/'completion_model.joblib'; SLA=MODELS/'sla_model.joblib'; METRICS=MODELS/'metrics.json'
FEATURES=['skill_match','skill_level','experience','workload','capacity','historical_completion','sla_success','estimated_hours','remaining_hours','complexity','priority','requirements','hours_until_deadline','performance']
_completion=_sla=None
def feature_vector(employee,task,skill_match,skill_level,requirement_count,hours_until_deadline):
 priority={'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}.get(str(task['priority']).upper(),2)
 return [skill_match,skill_level,employee['years_experience'],employee['current_workload_hours'],employee['daily_capacity_hours'],employee['average_task_completion_hours'],employee['sla_success_rate'],task['estimated_hours'],task['remaining_hours'],task['complexity'],priority,requirement_count,max(0,hours_until_deadline),employee['performance_rating']]
def ensure_models():
 global _completion,_sla
 try:
  import joblib
  if COMPLETION.exists() and SLA.exists():_completion=joblib.load(COMPLETION);_sla=joblib.load(SLA);return status()
  from sklearn.ensemble import RandomForestClassifier,RandomForestRegressor
  from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score,accuracy_score,precision_score,recall_score,f1_score,roc_auc_score
  from sklearn.model_selection import train_test_split
  import random
  rng=random.Random(2026); x=[]; y_hours=[]; y_breach=[]
  for _ in range(2400):
   skill=rng.uniform(.45,1); level=rng.randint(2,5); exp=rng.randint(1,14); workload=rng.uniform(0,8); capacity=8; hist=rng.uniform(4,15); success=rng.uniform(.78,.99); estimated=rng.uniform(2,20); remaining=estimated*rng.uniform(.3,1); complexity=rng.randint(1,5); priority=rng.randint(1,4); req=rng.randint(1,4); deadline=rng.uniform(1,48); performance=rng.uniform(3,5)
   actual=max(.5,remaining*(.65+.11*complexity+.045*workload-.28*skill-.025*exp-.035*(performance-3)+rng.gauss(0,.10)))
   breach=int(actual>deadline*(.82+.06*priority) or rng.random()>(success+.08*skill-.03*workload))
   x.append([skill,level,exp,workload,capacity,hist,success*100,estimated,remaining,complexity,priority,req,deadline,performance]);y_hours.append(actual);y_breach.append(breach)
  xt,xv,yht,yhv=train_test_split(x,y_hours,test_size=.2,random_state=42);_,_,yst,ysv=train_test_split(x,y_breach,test_size=.2,random_state=42)
  _completion=RandomForestRegressor(n_estimators=180,min_samples_leaf=2,random_state=42,n_jobs=-1).fit(xt,yht);_sla=RandomForestClassifier(n_estimators=180,min_samples_leaf=2,random_state=42,class_weight='balanced',n_jobs=-1).fit(xt,yst)
  completion_pred=_completion.predict(xv);sla_pred=_sla.predict(xv);sla_prob=_sla.predict_proba(xv)[:,1]
  metrics={'dataset':'Synthetic historical workforce data — hackathon demonstration only','completion':{'mae':round(mean_absolute_error(yhv,completion_pred),3),'rmse':round(mean_squared_error(yhv,completion_pred)**.5,3),'r2':round(r2_score(yhv,completion_pred),3)},'sla':{'accuracy':round(accuracy_score(ysv,sla_pred),3),'precision':round(precision_score(ysv,sla_pred,zero_division=0),3),'recall':round(recall_score(ysv,sla_pred,zero_division=0),3),'f1':round(f1_score(ysv,sla_pred,zero_division=0),3),'roc_auc':round(roc_auc_score(ysv,sla_prob),3)}}
  MODELS.mkdir(exist_ok=True);joblib.dump(_completion,COMPLETION);joblib.dump(_sla,SLA);METRICS.write_text(json.dumps(metrics,indent=2));return status()
 except Exception as exc:return {'available':False,'mode':'unavailable','reason':str(exc)}
def status():
 data={'available':_completion is not None and _sla is not None,'mode':'trained_random_forest' if _completion is not None else 'unavailable'}
 if METRICS.exists():data['metrics']=json.loads(METRICS.read_text())
 return data
def predict(employee,task,skill_match,skill_level,requirements,hours_until_deadline):
 s=status()
 if not s['available']:return {'completion_hours':None,'sla_breach_probability':None,'mode':'unavailable'}
 x=[feature_vector(employee,task,skill_match,skill_level,requirements,hours_until_deadline)]
 return {'completion_hours':round(float(_completion.predict(x)[0]),2),'sla_breach_probability':round(float(_sla.predict_proba(x)[0][1]),4),'mode':'trained_random_forest'}
