"""AURA FastAPI application: every decision is database-backed and approval-gated."""
import json, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from backend_database import connection,initialise_database,reset_database
from ml.model_runtime import ensure_models,status,predict
from services import dashboard_data,candidates_for,recommend,simulate,create_recommendation,approve_reallocation,answer_question,analyze_project,analyze_leave
ROOT=Path(__file__).parent;app=FastAPI(title="AURA Workforce Decision API",version="2.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
class Pair(BaseModel):employee_id:str;task_id:str
class EventRequest(BaseModel):event_type:str;employee_id:str|None=None;task_id:str|None=None;payload:dict=Field(default_factory=dict)
class LeaveRequest(BaseModel):employee_id:str;start_date:datetime;end_date:datetime;reason:str|None=None
class BreakRequest(BaseModel):employee_id:str;break_type:str='SHORT_BREAK'
class TaskAnalysis(BaseModel):project_name:str;revenue_inr:float=Field(gt=0);deadline:datetime;estimated_hours:float=Field(gt=0);priority:str;required_skills:list[str]=Field(min_length=1)
class SkillRequirement(BaseModel):skill:str=Field(min_length=1);required_level:int=Field(ge=1,le=5)
class ProjectAnalysis(BaseModel):
 project_name:str=Field(min_length=2);description:str='';revenue_inr:float=Field(gt=0);estimated_hours:float=Field(gt=0);deadline:datetime;priority:str;required_skills:list[SkillRequirement]=Field(min_length=1);required_employee_count:int=Field(ge=1);location_requirement:str|None=None
@app.on_event('startup')
def startup():initialise_database();ensure_models()
def err(fn):
 try:return fn()
 except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/health')
def health():return {'status':'healthy','ml':status()}
@app.get('/api/dashboard')
def dashboard():return dashboard_data()
@app.get('/api/employees')
def employees():
 with connection()as c:return[dict(x)for x in c.execute('SELECT * FROM employees ORDER BY employee_id')]
@app.get('/api/employees/{employee_id}')
def employee(employee_id:str):
 with connection()as c:
  r=c.execute('SELECT * FROM employees WHERE employee_id=?',(employee_id,)).fetchone()
  if not r:raise HTTPException(404,'Employee not found')
  out=dict(r);out['skills']=[dict(x)for x in c.execute('SELECT s.name,es.level FROM employee_skills es JOIN skills s ON s.skill_id=es.skill_id WHERE es.employee_id=?',(employee_id,))];return out
@app.get('/api/tasks')
def tasks():return dashboard_data()['tasks']
@app.get('/api/tasks/{task_id}')
def task(task_id:str):
 with connection()as c:
  r=c.execute('SELECT * FROM tasks WHERE task_id=?',(task_id,)).fetchone()
  if not r:raise HTTPException(404,'Task not found')
  return dict(r)
@app.get('/api/assignments')
def assignments():
 with connection()as c:return[dict(x)for x in c.execute("SELECT * FROM assignments WHERE status='ACTIVE'")]
@app.get('/api/tasks/{task_id}/candidates')
def candidates(task_id:str):return err(lambda:candidates_for(task_id))
@app.get('/api/tasks/{task_id}/recommendation')
def recommendation(task_id:str):return err(lambda:recommend(task_id))
@app.get('/api/sla-risk')
def sla_risk():return dashboard_data()['sla_risk']
@app.get('/api/ml/status')
def ml_status():return status()
@app.get('/api/ml/metrics')
def ml_metrics():return status().get('metrics',{'message':'Model metrics unavailable'})
@app.post('/api/ml/predict-completion')
def completion(body:Pair):return _prediction(body)
@app.post('/api/ml/predict-sla-risk')
def sla_prediction(body:Pair):return _prediction(body)
def _prediction(body):
 pool=err(lambda:candidates_for(body.task_id));result=next((x for x in pool['candidates']if x['employee_id']==body.employee_id),None)
 if not result:raise HTTPException(422,'Employee is not eligible for this task')
 return {'employee_id':body.employee_id,'task_id':body.task_id,'predicted_completion_hours':result['predicted_completion_hours'],'sla_breach_probability':result['sla_breach_probability'],'model_mode':result['prediction_mode']}
@app.post('/api/reallocate')
def reallocate(body:EventRequest):
 if not body.task_id:raise HTTPException(422,'task_id is required')
 return err(lambda:create_recommendation(body.task_id))
@app.post('/api/recommendations/{recommendation_id}/approve')
def approve(recommendation_id:str):return err(lambda:approve_reallocation(recommendation_id))
@app.post('/api/recommendations/{recommendation_id}/reject')
def reject(recommendation_id:str):
 with connection()as c:
  if not c.execute("UPDATE recommendations SET status='REJECTED' WHERE recommendation_id=? AND status='PENDING'",(recommendation_id,)).rowcount:raise HTTPException(409,'Recommendation not pending')
 return {'rejected':True}
@app.post('/api/events')
def event(body:EventRequest):
 with connection()as c:c.execute('INSERT INTO events(event_id,event_type,employee_id,task_id,payload_json,created_at) VALUES (?,?,?,?,?,?)',(f'EV-{uuid.uuid4().hex[:10]}',body.event_type,body.employee_id,body.task_id,json.dumps(body.payload),datetime.now(timezone.utc).isoformat()))
 return {'accepted':True,'simulation':simulate(body.event_type,body.employee_id,body.payload) if body.task_id else None}
@app.post('/api/break/start')
def break_start(body:BreakRequest):
 with connection()as c:
  e=c.execute('SELECT status FROM employees WHERE employee_id=?',(body.employee_id,)).fetchone()
  if not e:raise HTTPException(404,'Employee not found')
  if e['status']=='ON_BREAK':raise HTTPException(409,'Employee already has an active break')
  c.execute("UPDATE employees SET status='ON_BREAK',availability=0 WHERE employee_id=?",(body.employee_id,));c.execute('INSERT INTO break_sessions(break_id,employee_id,break_type,status,started_at,ended_at) VALUES (?,?,?,?,?,?)',(f'B-{uuid.uuid4().hex[:10]}',body.employee_id,body.break_type,'ACTIVE',datetime.now(timezone.utc).isoformat(),None))
 return {'started':True,'reassessment':'Monitor; reallocation is required only for a long break or critical SLA task.'}
@app.post('/api/break/end')
def break_end(body:BreakRequest):
 with connection()as c:
  b=c.execute("SELECT * FROM break_sessions WHERE employee_id=? AND status='ACTIVE' ORDER BY started_at DESC LIMIT 1",(body.employee_id,)).fetchone()
  if not b:raise HTTPException(409,'No active break exists for this employee')
  c.execute("UPDATE break_sessions SET status='ENDED',ended_at=? WHERE break_id=?",(datetime.now(timezone.utc).isoformat(),b['break_id']));c.execute("UPDATE employees SET status='AVAILABLE',availability=1 WHERE employee_id=?",(body.employee_id,))
 return {'ended':True}
@app.post('/api/leave/analyze')
def leave_analyze(body:LeaveRequest):
 if body.end_date<body.start_date:raise HTTPException(422,'End date must not precede start date')
 return err(lambda:analyze_leave(body.employee_id,body.start_date,body.end_date))
@app.post('/api/projects/analyze')
def project_analyze(body:ProjectAnalysis):
 if body.deadline<=datetime.now(timezone.utc):raise HTTPException(422,'Deadline must be in the future')
 return err(lambda:analyze_project({**body.model_dump(),'required_skills':[x.model_dump() for x in body.required_skills]}))
@app.post('/api/leave/request')
def leave_request(body:LeaveRequest):
 if body.end_date<body.start_date:raise HTTPException(422,'End date must not precede start date')
 with connection()as c:c.execute('INSERT INTO leave_requests(leave_id,employee_id,start_date,end_date,status) VALUES (?,?,?,?,?)',(f'L-{uuid.uuid4().hex[:10]}',body.employee_id,body.start_date.isoformat(),body.end_date.isoformat(),'PENDING'))
 return {'created':True,'analysis':simulate('leave',body.employee_id)}
@app.post('/api/employee/unavailable')
def unavailable(body:EventRequest):return simulate('unavailable',body.employee_id,body.payload)
@app.post('/api/employee/available')
def available(body:EventRequest):
 with connection()as c:c.execute("UPDATE employees SET status='AVAILABLE',availability=1 WHERE employee_id=?",(body.employee_id,))
 return {'updated':True}
@app.post('/api/task/analyze')
def analyze_task(body:TaskAnalysis):return simulate('new_project',None,body.model_dump())
@app.get('/api/decisions')
def decisions():
 with connection() as c:return [dict(x) for x in c.execute("SELECT * FROM recommendations WHERE status='PENDING' ORDER BY created_at DESC")]
@app.post('/api/simulations/{scenario}')
def scenario_simulation(scenario:str,body:EventRequest|None=None):
 allowed={'single_employee_unavailable','two_employees_unavailable','critical_task_arrives','deadline_shortened','priority_escalation','workforce_capacity_drop','high_value_project_capacity_shortage','skill_bottleneck','workload_spike','multiple_critical_tasks'}
 if scenario not in allowed:raise HTTPException(404,'Unknown simulation scenario')
 payload=(body.payload if body else {})
 employee_id=body.employee_id if body else None
 kind='multiple_unavailable' if scenario=='two_employees_unavailable' else 'unavailable'
 result=simulate(kind,employee_id,payload)
 return {**result,'scenario':scenario,'simulation_only':True,'message':'Simulation Mode — No production changes made'}
@app.post('/api/allocate')
def allocate(body:EventRequest):
 if not body.task_id:raise HTTPException(422,'task_id is required')
 return err(lambda:create_recommendation(body.task_id))
@app.post('/api/incidents')
def incident(body:EventRequest):
 if not body.task_id:raise HTTPException(422,'task_id is required')
 return err(lambda:create_recommendation(body.task_id))
@app.post('/api/exit/request')
def exit_request(body:EventRequest):
 if not body.employee_id:raise HTTPException(422,'employee_id is required')
 with connection()as c:c.execute("UPDATE employees SET status='EXIT_PENDING',availability=0 WHERE employee_id=?",(body.employee_id,))
 return simulate('exit',body.employee_id,body.payload)
@app.post('/api/demo/reset')
def demo_reset():
 reset_database();ensure_models()
 return {'reset':True,'message':'The deterministic demo dataset was restored.'}
@app.post('/api/simulate')
def sim(body:EventRequest):return simulate(body.event_type,body.employee_id,body.payload)
@app.get('/api/notifications')
def notifications():
 with connection()as c:return[dict(x)for x in c.execute('SELECT * FROM notifications ORDER BY rowid DESC LIMIT 30')]
@app.post('/api/notifications/read')
def notifications_read():
 with connection() as c:
  c.execute('UPDATE notifications SET read_at=? WHERE read_at IS NULL',(datetime.now(timezone.utc).isoformat(),))
 return {'marked_read':True}
@app.post('/api/agent/chat')
def chat(question:str):return {'answer':answer_question(question),'mode':'local data-backed assistant; no external LLM configured'}
@app.post('/api/analyst')
def analyst(question:str):return chat(question)
app.mount('/',StaticFiles(directory=ROOT,html=True),name='frontend')
