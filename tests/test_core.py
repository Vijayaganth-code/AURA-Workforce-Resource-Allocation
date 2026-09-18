"""Core integration checks; run with `python -m pytest` after dependencies install."""
from backend_database import initialise_database
from ml.model_runtime import ensure_models
from services import candidates_for, create_recommendation, simulate

def setup_module():
    initialise_database(); ensure_models()

def test_candidate_pool_is_qualified_and_model_backed():
    result=candidates_for('T-101')
    assert result['model_status']['available']
    assert result['candidate_count'] > 0
    assert all(row['prediction_mode']=='trained_random_forest' for row in result['candidates'])

def test_simulation_does_not_mutate_database_state():
    before=candidates_for('T-101')['candidate_count']
    simulation=simulate('unavailable','E002',{'task_id':'T-101'})
    assert simulation['simulation_only'] is True
    assert candidates_for('T-101')['candidate_count']==before

def test_recommendation_requires_manager_approval():
    result=create_recommendation('T-101')
    assert result['feasible'] is True
    assert result['status']=='PENDING'
