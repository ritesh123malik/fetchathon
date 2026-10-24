from fastapi.testclient import TestClient
from app.api import create_app
from app.services.transactions import import_transactions
import pytest

def test_categories_review_and_plan(tmp_path,monkeypatch):
    monkeypatch.delenv('RUPEEPILOT_NETWORK',raising=False)
    with TestClient(create_app(tmp_path/'tx.db')) as c:
        result=c.post('/api/transactions/import',json={'csv_text':'date,description,amount\n2026-10-24,Groceries,3000\n2026-10-24,Restaurant,5000'})
        assert result.status_code==200
        transactions=result.json()['transactions']
        assert [t['category'] for t in transactions]==['essential','discretionary']
        data=c.get('/api/demo').json();data['transactions']=transactions
        result=c.post('/api/plans',json=data)
        assert result.status_code==200,result.text
        assert result.json()['analyses']['expense']['metrics']['categories']['essential']=='3000'
        data['profile']['max_spending_cut']='6000'
        assert c.post('/api/plans',json=data).status_code==422
        data['profile']['max_spending_cut']='4000'
        data['profile']['regular_spending']='9000'
        assert c.post('/api/plans',json=data).status_code==422
        data['profile']['regular_spending']='8000'
        data['transactions'][0]['date']='2026-09-24'
        assert c.post('/api/plans',json=data).status_code==422

@pytest.mark.parametrize('text',[
 'description,amount\nShop,20',
 'date,description,amount\n2026-10-24,Shop,-20',
 'date,description,amount\n2026-10-24,Shop,NaN',
 'date,description,amount\n2026-10-24,Shop,1.001',
 'date,description,amount\nnot-a-date,Shop,20',
 'date,description,amount\n2026-10-24,,20',
 'date,description,amount',
])
def test_invalid_import(text):
    with pytest.raises(ValueError): import_transactions(text)

def test_unknown_category_stays_unclassified():
    result=import_transactions('date,description,amount\n2026-10-24,Mystery merchant,20')
    assert result['transactions'][0]['category']=='other'
