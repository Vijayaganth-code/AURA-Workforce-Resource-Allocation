"""Shared, database-backed Random Forest training and inference for AURA."""
import json
from pathlib import Path
MODELS = Path(__file__).parent / 'models'
COMPLETION, SLA, METRICS = MODELS/'completion_model.joblib', MODELS/'sla_model.joblib', MODELS/'metrics.json'
FEATURES = ['skill_match','skill_level','experience','workload','capacity','historical_completion','sla_success','estimated_hours','remaining_hours','complexity','priority','requirements','hours_until_deadline','performance']
_completion = _sla = None

def feature_vector(employee, task, skill_match, skill_level, requirement_count, hours_until_deadline):
    priority = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}.get(str(task['priority']).upper(), 2)
    return [skill_match, skill_level, employee['years_experience'], employee['current_workload_hours'], employee['daily_capacity_hours'], employee['average_task_completion_hours'], employee['sla_success_rate'], task['estimated_hours'], task['remaining_hours'], task['complexity'], priority, requirement_count, max(0, hours_until_deadline), employee['performance_rating']]

def _dataset():
    from backend_database import connection
    with connection() as c:
        rows = c.execute('''SELECT p.completion_hours,p.sla_met,e.*,t.* FROM performance_history p
            JOIN employees e ON e.employee_id=p.employee_id JOIN tasks t ON t.task_id=p.task_id''').fetchall()
    x=[]; hours=[]; breach=[]
    for row in rows:
        r=dict(row); x.append(feature_vector(r,r,.75,3.5,2,24)); hours.append(float(r['completion_hours'])); breach.append(0 if int(r['sla_met']) else 1)
    return x,hours,breach

def ensure_models(force=False):
    global _completion, _sla
    try:
        import joblib
        if not force and COMPLETION.exists() and SLA.exists() and METRICS.exists() and json.loads(METRICS.read_text()).get('dataset') == 'performance_history':
            _completion, _sla = joblib.load(COMPLETION), joblib.load(SLA); return status()
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
        from sklearn.model_selection import train_test_split
        x,hours,breach=_dataset()
        if len(x)<20 or len(set(breach))<2: raise RuntimeError('performance_history has insufficient outcome variation for training')
        xt,xv,yht,yhv=train_test_split(x,hours,test_size=.2,random_state=42)
        _,_,ybt,ybv=train_test_split(x,breach,test_size=.2,random_state=42)
        _completion=RandomForestRegressor(n_estimators=180,min_samples_leaf=2,random_state=42,n_jobs=-1).fit(xt,yht)
        _sla=RandomForestClassifier(n_estimators=180,min_samples_leaf=2,random_state=42,class_weight='balanced',n_jobs=-1).fit(xt,ybt)
        cp=_completion.predict(xv); sp=_sla.predict(xv); prob=_sla.predict_proba(xv)[:,1]
        metrics={'dataset':'performance_history','feature_order':FEATURES,'records':len(x),'completion':{'mae':round(mean_absolute_error(yhv,cp),3),'rmse':round(mean_squared_error(yhv,cp)**.5,3),'r2':round(r2_score(yhv,cp),3)},'sla':{'accuracy':round(accuracy_score(ybv,sp),3),'precision':round(precision_score(ybv,sp,zero_division=0),3),'recall':round(recall_score(ybv,sp,zero_division=0),3),'f1':round(f1_score(ybv,sp,zero_division=0),3),'roc_auc':round(roc_auc_score(ybv,prob),3)}}
        MODELS.mkdir(exist_ok=True); joblib.dump(_completion,COMPLETION); joblib.dump(_sla,SLA); METRICS.write_text(json.dumps(metrics,indent=2)); return status()
    except Exception as exc: return {'available':False,'mode':'unavailable','reason':str(exc)}

def status():
    out={'available':_completion is not None and _sla is not None,'mode':'trained_random_forest' if _completion is not None else 'unavailable'}
    if METRICS.exists(): out['metrics']=json.loads(METRICS.read_text())
    return out

def predict(employee,task,skill_match,skill_level,requirements,hours_until_deadline):
    if not status()['available']: return {'completion_hours':None,'sla_breach_probability':None,'mode':'unavailable'}
    x=[feature_vector(employee,task,skill_match,skill_level,requirements,hours_until_deadline)]
    return {'completion_hours':round(float(_completion.predict(x)[0]),2),'sla_breach_probability':round(float(_sla.predict_proba(x)[0][1]),4),'mode':'trained_random_forest'}
