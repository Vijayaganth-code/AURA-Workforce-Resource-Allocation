"""Authoritative business services. ML predicts, OR-Tools chooses, manager approves."""
import json, uuid
from copy import deepcopy
from datetime import datetime, timezone
from backend_database import connection
from ml.model_runtime import predict,status
from optimizer.allocation_optimizer import choose_best

def _rows(c,sql,args=()):return [dict(x)for x in c.execute(sql,args)]
def _deadline(task):return max(0,(datetime.fromisoformat(task['deadline'])-datetime.now(timezone.utc)).total_seconds()/3600)
def _requirements(c,task_id):return _rows(c,"SELECT s.name,tr.required_level FROM task_requirements tr JOIN skills s ON s.skill_id=tr.skill_id WHERE tr.task_id=?",(task_id,))
def candidates_for(task_id,state=None):
 """Filters hard constraints then asks the trained models for eligible candidate outcomes."""
 with connection()as c:
  task=dict(c.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()or{})
  if not task:raise ValueError("Task not found")
  req=_requirements(c,task_id);employees=state['employees']if state else _rows(c,"SELECT * FROM employees")
  leave={r['employee_id']for r in _rows(c,"SELECT employee_id FROM leave_requests WHERE status='APPROVED'")};out=[]
  for e in employees:
   if not e['availability'] or e['status'] not in ('AVAILABLE','BUSY') or e['employee_id'] in leave:continue
   skills={x['name']:x['level']for x in _rows(c,"SELECT s.name,es.level FROM employee_skills es JOIN skills s ON s.skill_id=es.skill_id WHERE es.employee_id=?",(e['employee_id'],))}
   matched=[r for r in req if skills.get(r['name'],0)>=r['required_level']]
   if len(matched)!=len(req):continue
   free=max(0,e['daily_capacity_hours']-e['current_workload_hours'])
   if free<=0:continue
   skill_match=sum(min(1,skills[r['name']]/5)for r in req)/len(req);avg_level=sum(skills[r['name']]for r in req)/len(req)
   ml=predict(e,task,skill_match,avg_level,len(req),_deadline(task))
   out.append({'employee_id':e['employee_id'],'name':e['name'],'skill_match_score':round(skill_match*100,1),'employee_skill_level':round(avg_level,2),'available_capacity_hours':round(free,2),'current_workload_hours':e['current_workload_hours'],'hourly_cost_inr':e['hourly_cost_inr'],'performance_rating':e['performance_rating'],'predicted_completion_hours':ml['completion_hours'],'sla_breach_probability':ml['sla_breach_probability'],'prediction_mode':ml['mode']})
  # Do not disguise unavailable ML: optimizer reports an actionable failure instead.
  if status().get('available'):out.sort(key=lambda x:(x['sla_breach_probability'],-x['skill_match_score'],x['hourly_cost_inr']))
  return {'task_id':task_id,'candidate_count':len(out),'candidates':out,'model_status':status()}
def _risk_for(task,candidates):
 if not candidates:return 1.0
 return min(x['sla_breach_probability']for x in candidates if x['sla_breach_probability']is not None)
def recommend(task_id,state=None):
 pool=candidates_for(task_id,state); candidates=pool['candidates']
 if not candidates:return {'feasible':False,'reason':'No available employee meets all required skill levels and has positive capacity.','suggestions':['Extend deadline','Use external resource','Reprioritize lower-value work'],'candidates':[]}
 if not status().get('available'):return {'feasible':False,'reason':'ML models are unavailable; no allocation is presented as ML-optimized.','candidates':candidates}
 selected=choose_best(candidates)
 if not selected:return {'feasible':False,'reason':'OR-Tools did not find a feasible allocation.','candidates':candidates}
 with connection()as c: task=dict(c.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone())
 before=min(1.0,task['remaining_hours']/max(.1,_deadline(task)))
 return {'feasible':True,'task_id':task_id,'selected':selected,'alternatives':[x for x in candidates if x['employee_id']!=selected['employee_id']][:3],'before':{'sla_risk':round(before,4)},'after':{'sla_risk':selected['sla_breach_probability']},'explanation':[f"Required skills matched at {selected['skill_match_score']}%.",f"Model predicts {selected['predicted_completion_hours']} hours completion.",f"Model predicts {selected['sla_breach_probability']:.1%} SLA breach probability.",f"{selected['available_capacity_hours']} hours daily capacity remain."],'optimizer':'OR-Tools CP-SAT'}
def dashboard_data():
 with connection()as c:
  tasks=_rows(c,"SELECT t.*,COALESCE(group_concat(e.name,', '),'Unassigned') owner FROM tasks t LEFT JOIN assignments a ON a.task_id=t.task_id AND a.status='ACTIVE' LEFT JOIN employees e ON e.employee_id=a.employee_id WHERE t.status NOT IN ('COMPLETED','CANCELLED') GROUP BY t.task_id ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END")
  employees=_rows(c,"SELECT * FROM employees");radar=[]
  for task in tasks:
   rec=recommend(task['task_id']);prob=rec.get('after',{}).get('sla_risk');task['sla_breach_probability']=prob
   task['risk']='CRITICAL' if prob is None or prob>=.7 else 'HIGH' if prob>=.45 else 'MEDIUM' if prob>=.2 else 'LOW';radar.append({'task_id':task['task_id'],'risk':task['risk'],'probability':prob,'time_remaining_hours':round(_deadline(task),2),'remaining_hours':task['remaining_hours']})
  at_risk=[x for x in radar if x['risk']in('HIGH','CRITICAL')];capacity=sum(e['daily_capacity_hours']for e in employees);work=sum(e['current_workload_hours']for e in employees)
  return {'tasks':tasks,'metrics':{'total_employees':len(employees),'active_employees':sum(e['status']in('AVAILABLE','BUSY')for e in employees),'active_tasks':len(tasks),'utilization':round(work/capacity*100,1),'risk_count':len(at_risk),'critical_tasks':sum(t['priority']=='Critical'for t in tasks),'revenue_at_risk':sum(t['revenue_inr']for t in tasks if t['task_id']in{x['task_id']for x in at_risk}),'available_capacity_hours':round(capacity-work,1)},'sla_risk':radar,'ml':status()}
def simulate(kind,employee_id=None,payload=None):
 """Clone employee state in memory; no mutation or database writes occur."""
 with connection()as c: employees=_rows(c,"SELECT * FROM employees")
 simulated={'employees':deepcopy(employees)}
 targets=[employee_id]if employee_id else []
 if kind=='multiple_unavailable':targets=(payload or{}).get('employee_ids',[])
 for e in simulated['employees']:
  if e['employee_id']in targets:e['availability']=0;e['status']='UNAVAILABLE'
 task_id=(payload or{}).get('task_id','T-101'if kind in('incident','critical_incident')else'T-104');before=recommend(task_id);after=recommend(task_id,simulated)
 return {'scenario':kind,'simulation_only':True,'base_recommendation':before,'simulated_recommendation':after,'before':{'candidate_count':len(before.get('candidates',[])),'sla_risk':before.get('after',{}).get('sla_risk')},'after':{'candidate_count':len(after.get('candidates',[])),'sla_risk':after.get('after',{}).get('sla_risk')},'results':[["Candidates",str(len(after.get('candidates',[]))),"Calculated on a cloned workforce state"],["SLA exposure",f"{(after.get('after',{}).get('sla_risk')or 1):.1%}","Model prediction"],["Decision",'Approval required',after.get('reason','OR-Tools recommendation ready')]]}
def create_recommendation(task_id):
 rec=recommend(task_id)
 if not rec.get('feasible'):return rec
 rid=f"REC-{uuid.uuid4().hex[:10]}"
 with connection()as c:c.execute("INSERT INTO recommendations(recommendation_id,task_id,employee_id,before_risk,after_risk,explanation_json) VALUES (?,?,?,?,?,?)",(rid,task_id,rec['selected']['employee_id'],rec['before']['sla_risk'],rec['after']['sla_risk'],json.dumps(rec)))
 return {**rec,'recommendation_id':rid,'status':'PENDING'}
def approve_reallocation(recommendation_id):
 with connection()as c:
  row=c.execute("SELECT * FROM recommendations WHERE recommendation_id=?",(recommendation_id,)).fetchone()
  if not row:raise ValueError('Recommendation not found')
  if row['status']!='PENDING':raise ValueError('Recommendation is no longer pending')
  c.execute("UPDATE assignments SET status='REASSIGNED' WHERE task_id=? AND status='ACTIVE'",(row['task_id'],));c.execute("INSERT INTO assignments(assignment_id,employee_id,task_id,allocated_hours,status) VALUES (?,?,?,?,?)",(f"A-{row['task_id']}-{row['employee_id']}",row['employee_id'],row['task_id'],4,'ACTIVE'));c.execute("UPDATE recommendations SET status='APPROVED' WHERE recommendation_id=?",(recommendation_id,));c.execute("INSERT INTO notifications VALUES (?,?,?,?)",(f"N-{uuid.uuid4().hex[:10]}",f"Task {row['task_id']} assigned to {row['employee_id']} after manager approval.",'INFO',None))
 return {'approved':True,'recommendation_id':recommendation_id}
def answer_question(q):
 q=q.lower();d=dashboard_data()
 if 'risk' in q:return f"The live risk radar contains {d['metrics']['risk_count']} high or critical tasks. Figures are model-derived from the current database."
 if 'leave' in q:return "Use the leave analysis workflow to create a non-mutating simulation; it checks the employee's assigned work, eligible candidates, and model risk before any approval."
 return f"The live command center has {d['metrics']['total_employees']} employees, {d['metrics']['active_tasks']} active tasks and {d['metrics']['utilization']}% utilization."
