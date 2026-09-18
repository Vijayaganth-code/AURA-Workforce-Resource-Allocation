"""OR-Tools allocation selection with deterministic fallback."""
OBJECTIVE_WEIGHTS={"sla":.30,"skill_match":.25,"performance":.20,"capacity":.15,"business_value":.10}
def choose_best(candidates):
 if not candidates:return None
 try:
  from ortools.sat.python import cp_model
  m=cp_model.CpModel();xs=[m.NewBoolVar(f'x{i}')for i in range(len(candidates))];m.Add(sum(xs)<=1);scores=[int(1000*(.25*x['skill_match_score']-.3*x['sla_breach_probability']+.15*min(x['available_capacity_hours']/8,1)*100))for x in candidates];m.Maximize(sum(x*s for x,s in zip(xs,scores)));s=cp_model.CpSolver();s.Solve(m);return candidates[next(i for i,x in enumerate(xs)if s.Value(x))]
 except Exception:return sorted(candidates,key=lambda x:(x['sla_breach_probability'],-x['skill_match_score']))[0]
