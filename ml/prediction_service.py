"""Explicit fallback predictions used until separately trained sklearn artifacts exist."""
def predict_completion_time(employee,task):return round(task['remaining_hours']*(1.3-employee['performance_rating']/10-employee['years_experience']/100),1)
def predict_sla_risk(employee,task,skill_match_score):return min(.99,max(.01,predict_completion_time(employee,task)/max(.1,employee['daily_capacity_hours']-employee['current_workload_hours'])/8*(1-skill_match_score/250)))
