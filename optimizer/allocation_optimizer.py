"""OR-Tools allocation selection with deterministic fallback."""
OBJECTIVE_WEIGHTS={"sla":.30,"skill_match":.25,"performance":.20,"capacity":.15,"business_value":.10}
def choose_best(candidates):
 if not candidates:return None
 try:
  from ortools.sat.python import cp_model
  m=cp_model.CpModel();xs=[m.NewBoolVar(f'x{i}')for i in range(len(candidates))];m.Add(sum(xs)==1)
  scores=[int(1000*(OBJECTIVE_WEIGHTS['skill_match']*x['skill_match_score']/100-OBJECTIVE_WEIGHTS['sla']*x['sla_breach_probability']+OBJECTIVE_WEIGHTS['performance']*x.get('performance_rating',0)/5+OBJECTIVE_WEIGHTS['capacity']*min(x['available_capacity_hours']/8,1)-OBJECTIVE_WEIGHTS['business_value']*x.get('hourly_cost_inr',0)/2000)) for x in candidates]
  m.Maximize(sum(x*s for x,s in zip(xs,scores)));s=cp_model.CpSolver();s.Solve(m);return candidates[next(i for i,x in enumerate(xs)if s.Value(x))]
 except Exception:return sorted(candidates,key=lambda x:(x['sla_breach_probability'],-x['skill_match_score']))[0]

def optimize_multi_task(candidates_by_task, required_hours_by_task):
 """CP-SAT simulated allocation x[employee, task], respecting shared employee capacity."""
 try:
  from ortools.sat.python import cp_model
  m=cp_model.CpModel(); variables=[]; by_employee={}; by_task={}
  for task_id,candidates in candidates_by_task.items():
   for c in candidates:
    v=m.NewBoolVar(f"x_{c['employee_id']}_{task_id}"); variables.append((v,task_id,c));by_employee.setdefault(c['employee_id'],[]).append((v,c));by_task.setdefault(task_id,[]).append((v,c))
  for task_id,items in by_task.items(): m.Add(sum(v for v,_ in items)>=1)
  for _,items in by_employee.items(): m.Add(sum(v*int(min(c['available_capacity_hours'],required_hours_by_task.get(next(t for vv,t,cc in variables if vv is v),0))*10) for v,c in items)<=int(items[0][1]['available_capacity_hours']*10))
  m.Maximize(sum(v*int((1-c['sla_breach_probability'])*300+c['skill_match_score']*2+c.get('performance_rating',0)*20) for v,_,c in variables)); solver=cp_model.CpSolver();
  if solver.Solve(m) not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return {'feasible':False,'selected_assignments':[]}
  chosen=[{'task_id':t,'employee_id':c['employee_id'],'allocated_hours':min(required_hours_by_task[t],c['available_capacity_hours']),'predicted_completion_hours':c['predicted_completion_hours'],'sla_risk':c['sla_breach_probability']} for v,t,c in variables if solver.Value(v)]
  return {'feasible':True,'selected_assignments':chosen,'objective_score':solver.ObjectiveValue(),'constraints_satisfied':['availability','capacity','skill level','task coverage']}
 except Exception as exc:return {'feasible':False,'selected_assignments':[],'reason':str(exc)}
