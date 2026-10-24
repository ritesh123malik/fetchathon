import asyncio
import json
from decimal import Decimal
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.api import create_app
from app.schemas.financial_models import FinancialProfile, BudgetAdjustment
from app.services.planner import PlanningInput, plan
from app.services.local_chat import extract_local, merge_draft

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('RUPEEPILOT_NETWORK',raising=False)
    with TestClient(create_app(tmp_path/'plans.db')) as c: yield c

@pytest.fixture
def demo(client): return client.get('/api/demo').json()

def test_full_plan_choice_history_restart(client,demo,tmp_path):
    made=client.post('/api/plans',json=demo)
    assert made.status_code==200, made.text
    data=made.json();result=data['result'];rid=result['request_id']
    assert result['status']=='verified'
    assert Decimal(result['recommended_scenario']['projected_closing_balance'])==0
    assert {t['agent'] for t in data['trace']}=={'expense','cashflow','bills','goal','scenario','verification'}
    assert len(data['verification_reports'])==len(result['alternatives'])+1
    assert Decimal(data['forecast'][0]['with_emergency'])==-4000
    assert Decimal(data['forecast'][2]['with_plan'])==8000
    selected=client.post(f'/api/plans/{rid}/select',json={'scenario_id':result['recommended_scenario']['scenario_id']})
    assert selected.status_code==200
    assert client.get('/api/plans').json()[0]['selected']==selected.json()['selected']
    with TestClient(create_app(tmp_path/'plans.db')) as restarted:
        assert restarted.get(f'/api/plans/{rid}').json()['selected']==selected.json()['selected']
    assert client.post(f'/api/plans/{rid}/select',json={'scenario_id':'invented'}).status_code==404

def test_chat_multiturn_and_explicit_limits(client):
    first=client.post('/api/chat',json={'message':'I earn 28000, fixed bills 10000, regular spending 8000.'}).json()
    assert not first['draft']['is_ready']
    second=client.post('/api/chat',json={'message':'Planned savings 6000, unexpected expense 8000, opening balance 0, max spending cut 4000, minimum buffer 0','draft':first['draft']}).json()
    assert second['draft']['is_ready']
    assert second['draft']['monthly_income']=='28000'
    assert second['draft']['max_spending_cut']=='4000'
    assert client.get('/api/plans').json()==[] # Parsing alone never saves or chooses a plan.
    third=client.post('/api/chat',json={'message':'no cuts','draft':second['draft']}).json()
    assert third['draft']['max_spending_cut']=='0'

def test_missing_opening_balance_is_not_ready():
    d=merge_draft({},extract_local('income 10k, fixed bills 0, regular spending 0, planned savings 0, no unexpected expense'))
    assert not d.is_ready
    assert 'opening balance' in d.missing_fields

def test_reject_negative_chat(client):
    assert client.post('/api/chat',json={'message':'income -200'}).status_code==422

@pytest.mark.parametrize('field,value',[('monthly_income','NaN'),('fixed_bills','Infinity'),('monthly_income','0.001'),('monthly_income','-1'),('monthly_income','1000000000001'),('currency','USD')])
def test_bad_money(client,demo,field,value):
    demo['profile'][field]=value
    assert client.post('/api/plans',json=demo).status_code==422
    assert not client.get('/api/plans').json()

def test_itemized_bills_and_goals_reconciled(client,demo):
    demo['profile']['fixed_bills']='1'
    assert client.post('/api/plans',json=demo).status_code==422
    demo['profile']['fixed_bills']='10000';demo['profile']['planned_savings']='1'
    assert client.post('/api/plans',json=demo).status_code==422

def test_duplicate_goal_names(client,demo):
    demo['goals'].append(demo['goals'][0].copy())
    demo['profile']['planned_savings']='12000'
    assert client.post('/api/plans',json=demo).status_code==422

def test_shortfall_cannot_be_selected(client,demo):
    demo['profile']['unexpected_expenses']='100000'
    data=client.post('/api/plans',json=demo).json()
    assert data['result']['status']=='verified_with_shortfall'
    rid=data['result']['request_id']
    s=data['result']['recommended_scenario']['scenario_id']
    assert client.post(f'/api/plans/{rid}/select',json={'scenario_id':s}).status_code==409

def test_origins_and_host(client,demo):
    assert client.post('/api/plans',json=demo,headers={'origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/health',headers={'host':'untrusted.example'}).status_code==403
    assert client.post('/api/plans',json=demo,headers={'origin':'http://testserver'}).status_code==200

def test_unknown_record(client):
    assert client.get('/api/plans/absent').status_code==404

def test_unavailable_network_does_not_save(client,demo,monkeypatch):
    monkeypatch.setenv('RUPEEPILOT_NETWORK','1')
    import httpx
    async def fail(*args,**kwargs): raise httpx.ConnectError('unreachable')
    monkeypatch.setattr(httpx.AsyncClient,'post',fail)
    assert client.post('/api/plans',json=demo).status_code==503
    assert not client.get('/api/plans').json()

def test_tampered_verification_blocks_recommendation(demo):
    from app.services.planner import execute_task
    async def dispatch(name,payload):
        output=execute_task(name,payload)
        if name=='scenario':
            for c in output['scenarios']: c.projected_closing_balance+=Decimal('1')
        return output
    output=asyncio.run(plan(PlanningInput.model_validate(demo),dispatch))
    assert output['result']['status']=='verification_failed'
    assert output['result']['recommended_scenario'] is None

def test_goal_cut_allocation(client,demo):
    demo['profile']['max_spending_cut']='0'
    output=client.post('/api/plans',json=demo).json()
    assert Decimal(output['goal_impacts'][0]['this_month'])==2000

def test_external_parser_failure_preserves_local_path(client,monkeypatch):
    import app.services.parsing_service as parsing
    def fail(_): raise RuntimeError('ASI:One unavailable')
    monkeypatch.setattr(parsing,'parse_financial_request',fail)
    assert client.post('/api/chat',json={'message':'income 28000','use_asi':True}).status_code==502
    assert client.post('/api/chat',json={'message':'income 28000'}).status_code==200
