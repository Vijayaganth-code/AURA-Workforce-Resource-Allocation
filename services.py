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
  c.execute("UPDATE assignments SET status='REASSIGNED' WHERE task_id=? AND status='ACTIVE'",(row['task_id'],));c.execute("INSERT INTO assignments(assignment_id,employee_id,task_id,allocated_hours,status) VALUES (?,?,?,?,?)",(f"A-{row['task_id']}-{row['employee_id']}",row['employee_id'],row['task_id'],4,'ACTIVE'));c.execute("UPDATE recommendations SET status='APPROVED' WHERE recommendation_id=?",(recommendation_id,));c.execute("INSERT INTO notifications(notification_id,message,severity,read_at) VALUES (?,?,?,?)",(f"N-{uuid.uuid4().hex[:10]}",f"Task {row['task_id']} assigned to {row['employee_id']} after manager approval.",'INFO',None))
 return {'approved':True,'recommendation_id':recommendation_id}
def answer_question(q):
 q=q.lower();d=dashboard_data()
 if 'risk' in q:return f"The live risk radar contains {d['metrics']['risk_count']} high or critical tasks. Figures are model-derived from the current database."
 if 'leave' in q:return "Use the leave analysis workflow to create a non-mutating simulation; it checks the employee's assigned work, eligible candidates, and model risk before any approval."
 return f"The live command center has {d['metrics']['total_employees']} employees, {d['metrics']['active_tasks']} active tasks and {d['metrics']['utilization']}% utilization."

def analyze_project(project):
 """Non-mutating project intake assessment using the real workforce and ML scores."""
 with connection() as c:
  employees=_rows(c,'SELECT * FROM employees'); skills={r['name']:r['skill_id'] for r in _rows(c,'SELECT * FROM skills')}
  qualified=[]; available=0
  for e in employees:
   free=max(0,e['daily_capacity_hours']-e['current_workload_hours'])
   if e['availability'] and e['status'] in ('AVAILABLE','BUSY'): available+=free
   es={r['name']:r['level'] for r in _rows(c,'SELECT s.name,es.level FROM employee_skills es JOIN skills s ON s.skill_id=es.skill_id WHERE es.employee_id=?',(e['employee_id'],))}
   matches=[x for x in project['required_skills'] if es.get(x['skill'],0)>=x['required_level']]
   if len(matches)==len(project['required_skills']) and e['availability'] and free>0:
    ratio=sum(es[x['skill']]/5 for x in matches)/len(matches)
    synthetic={'priority':project['priority'],'estimated_hours':project['estimated_hours'],'remaining_hours':project['estimated_hours'],'complexity':max(1,min(5,len(matches)+1))}
    pred=predict(e,synthetic,ratio,sum(es[x['skill']] for x in matches)/len(matches),len(matches),max(1,(project['deadline']-datetime.now(timezone.utc)).total_seconds()/3600))
    qualified.append({**e,'available_capacity_hours':round(free,1),'skill_match_score':round(ratio*100,1),'predicted_completion_hours':pred['completion_hours'],'sla_breach_probability':pred['sla_breach_probability']})
  qualified.sort(key=lambda x:(x['sla_breach_probability'] if x['sla_breach_probability'] is not None else 1,-x['skill_match_score'],-x['available_capacity_hours']))
  recommended=qualified[:project['required_employee_count']]
  qualified_capacity=sum(x['available_capacity_hours'] for x in qualified)
  deadline_hours=max(0,(project['deadline']-datetime.now(timezone.utc)).total_seconds()/3600)
  predicted=max((x['predicted_completion_hours'] or project['estimated_hours'] for x in recommended),default=project['estimated_hours'])
  feasible=len(recommended)>=project['required_employee_count'] and qualified_capacity>=project['estimated_hours'] and predicted<=deadline_hours and max((x['sla_breach_probability'] or 1 for x in recommended),default=1)<.6
  # Do not recursively evaluate the whole dashboard here: one project intake must stay responsive.
  at_risk=c.execute("SELECT COALESCE(SUM(revenue_inr),0) FROM tasks WHERE status='ACTIVE' AND priority IN ('Critical','High')").fetchone()[0]; gap=max(0,project['estimated_hours']-qualified_capacity)
  reasons=[f"{len(qualified)} available employees meet every required skill level.",f"{qualified_capacity:.1f}h qualified capacity is available against {project['estimated_hours']}h required.",f"Predicted completion is {predicted:.1f}h with {deadline_hours:.1f}h until deadline."]
  if gap: reasons.append(f"A qualified capacity gap of {gap:.1f}h makes the proposed staffing unsafe.")
  return {'feasible':feasible,'confidence':round(sum(x['skill_match_score'] for x in recommended)/max(1,len(recommended))/100,2),'project':project,'capacity':{'required_hours':project['estimated_hours'],'available_hours':round(qualified_capacity,1),'total_available_hours':round(available,1),'capacity_gap':round(gap,1)},'qualified_resources':len(qualified),'recommended_resources':[{k:x[k] for k in ('employee_id','name','skill_match_score','available_capacity_hours','current_workload_hours','predicted_completion_hours','sla_breach_probability')} for x in recommended],'predicted_completion_hours':predicted,'sla_breach_probability':max((x['sla_breach_probability'] or 1 for x in recommended),default=1),'revenue_inr':project['revenue_inr'],'existing_revenue_at_risk':at_risk,'opportunity_cost_inr':round(min(at_risk,project['estimated_hours']*750),2),'risk_level':'LOW' if feasible else 'HIGH','reasoning':reasons,'alternative_options':['Extend the deadline or reduce scope.','Use a contractor for the capacity gap.'] if not feasible else ['Reserve the recommended resources pending manager approval.'],'simulation_only':True}

def analyze_leave(employee_id,start_date,end_date):
 with connection() as c:
  employee=c.execute('SELECT * FROM employees WHERE employee_id=?',(employee_id,)).fetchone()
  if not employee: raise ValueError('Employee not found')
  employee=dict(employee); tasks=_rows(c,"SELECT t.* FROM tasks t JOIN assignments a ON a.task_id=t.task_id WHERE a.employee_id=? AND a.status='ACTIVE'",(employee_id,)); all_employees=_rows(c,'SELECT * FROM employees')
 affected=[]; plans=[]; exposure=0
 for task in tasks:
  before=recommend(task['task_id']); simulated={'employees':deepcopy(all_employees)}
  for e in simulated['employees']:
   if e['employee_id']==employee_id:e['availability']=0;e['status']='ON_LEAVE'
  after=recommend(task['task_id'],simulated); exposure+=task['revenue_inr'] if not after.get('feasible') else 0
  affected.append({'task_id':task['task_id'],'task_name':task['task_name'],'priority':task['priority'],'remaining_hours':task['remaining_hours'],'deadline':task['deadline'],'current_owner':employee['name'],'risk':after.get('after',{}).get('sla_risk',1)})
  if after.get('selected'): plans.append({'task_id':task['task_id'],'current_owner':employee['name'],'replacement':after['selected']['name'],'employee_id':after['selected']['employee_id'],'skill_match':after['selected']['skill_match_score'],'predicted_hours':after['selected']['predicted_completion_hours'],'sla_risk':after['selected']['sla_breach_probability']})
 return {'employee':employee,'leave_period':{'start_date':start_date.isoformat(),'end_date':end_date.isoformat()},'affected_tasks':affected,'affected_task_count':len(affected),'revenue_at_risk_inr':exposure,'sla_risk_before':max([recommend(t['task_id']).get('after',{}).get('sla_risk',1) for t in tasks] or [0]),'sla_risk_after':max([x['risk'] for x in affected] or [0]),'replacement_candidates':plans,'simulated_allocation':plans,'workload_impact':[],'recommendation':'Leave is operationally feasible with the simulated coverage plan.' if len(plans)==len(tasks) else 'Do not approve leave without external coverage for uncovered work.','risk_level':'LOW' if len(plans)==len(tasks) else 'HIGH','simulation_only':True}
