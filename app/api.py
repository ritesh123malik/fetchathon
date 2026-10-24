import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from app.config import PROJECT_ROOT, ASI_ONE_API_KEY
from app.schemas.financial_models import StrictModel
from app.services.planner import PlanningInput, plan
from app.services.local_chat import extract_local, merge_draft
from app.storage.repository import PlanningRepository

class ChatInput(StrictModel):
    message: str = Field(min_length=1,max_length=20000)
    draft: dict = Field(default_factory=dict)
    use_asi: bool = False

class TransactionImport(StrictModel):
    csv_text: str = Field(min_length=1,max_length=200000)

class Selection(StrictModel):
    scenario_id: str


def create_app(database_path=None):
    app=FastAPI(title='RupeePilot', docs_url='/api/docs')
    repo=PlanningRepository(database_path)
    with repo._connection() as con:
        con.execute('CREATE TABLE IF NOT EXISTS plan_details (request_id TEXT PRIMARY KEY, payload TEXT NOT NULL, selected TEXT)')

    @app.middleware('http')
    async def local_only(request:Request, call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in {'127.0.0.1','localhost','testserver'}:
            return JSONResponse({'detail':'Local access only'},status_code=403)
        origin=request.headers.get('origin')
        if request.method not in {'GET','HEAD','OPTIONS'} and origin and origin not in {f'http://{request.headers.get("host")}', 'http://127.0.0.1:5173', 'http://localhost:5173'}:
            return JSONResponse({'detail':'Origin not allowed'},status_code=403)
        if int(request.headers.get('content-length','0'))>1_000_000:
            return JSONResponse({'detail':'Request too large'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store'
        return response

    @app.get('/api/health')
    def health():
        return {'status':'ok','asi_configured':bool(ASI_ONE_API_KEY),'agent_transport':'uagents' if os.getenv('RUPEEPILOT_NETWORK')=='1' else 'local','local_only':True}

    @app.get('/api/demo')
    def demo():
        data=json.loads((PROJECT_ROOT/'data/demo_profile.json').read_text())
        data['profile']['max_spending_cut']='4000.00'
        return data

    @app.post('/api/transactions/import')
    def transactions(body:TransactionImport):
        from app.services.transactions import import_transactions
        try: return import_transactions(body.csv_text)
        except ValueError as exc: raise HTTPException(422,str(exc))

    @app.post('/api/chat')
    async def chat(body:ChatInput):
        if body.use_asi:
            from app.services.parsing_service import parse_financial_request
            import asyncio
            try:
                parsed=await asyncio.to_thread(parse_financial_request,body.message)
                updates=parsed.model_dump(mode='json',exclude_none=True)
            except (RuntimeError,ValueError) as e: raise HTTPException(502,str(e))
        else: updates=extract_local(body.message)
        try: draft=merge_draft(body.draft, updates)
        except ValueError as e: raise HTTPException(422,str(e))
        message=('Your numbers are ready to review. Check the form, then generate a verified plan.' if draft.is_ready else 'Please provide: '+', '.join(draft.missing_fields)+'.')
        if not updates: message='I could not safely extract those numbers. Use labels such as “income 28000, fixed bills 10000, regular spending 8000”, or complete the form. '+message
        return {'draft':draft.model_dump(mode='json'),'message':message,'parser':'ASI:One' if body.use_asi else 'Offline field extraction'}

    @app.post('/api/plans')
    async def make_plan(body:PlanningInput):
        if os.getenv('RUPEEPILOT_NETWORK')=='1':
            import httpx
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    r=await client.post(f'http://127.0.0.1:{int(os.getenv("RUPEEPILOT_AGENT_PORT","8010"))}/plan',json={'payload_json':body.model_dump_json()})
                    r.raise_for_status()
                    envelope=r.json()
                    if envelope.get('error'): raise ValueError(envelope['error'])
                    output=json.loads(envelope['payload_json'])
            except Exception as exc: raise HTTPException(503,'Local agent network unavailable; start python run_network.py. No plan was saved.') from exc
        else: output=await plan(body)
        from app.schemas.financial_models import PlanningResult
        result=PlanningResult.model_validate(output['result'])
        output['created_at']=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()
        repo.save_result(result)
        with repo._connection() as con: con.execute('INSERT INTO plan_details(request_id,payload) VALUES (?,?)',(result.request_id,json.dumps(output)))
        return output

    @app.get('/api/plans')
    def history():
        with repo._connection() as con:
            rows=con.execute('SELECT payload,selected FROM plan_details ORDER BY rowid DESC LIMIT 100').fetchall()
        return [{'request_id':(d:=json.loads(r['payload']))['result']['request_id'],'summary':d['result']['summary'],'status':d['result']['status'],'created_at':d['created_at'],'selected':r['selected']} for r in rows]

    def get_record(request_id):
        with repo._connection() as con: row=con.execute('SELECT payload,selected FROM plan_details WHERE request_id=?',(request_id,)).fetchone()
        if not row: raise HTTPException(404,'Plan not found')
        return {**json.loads(row['payload']),'selected':row['selected']}

    @app.get('/api/plans/{request_id}')
    def get_plan(request_id:str): return get_record(request_id)

    @app.post('/api/plans/{request_id}/select')
    def select_plan(request_id:str,body:Selection):
        record=get_record(request_id)
        result=record['result']
        options=[result['recommended_scenario'],*result['alternatives']]
        candidate=next((s for s in options if s and s['scenario_id']==body.scenario_id),None)
        if not candidate: raise HTTPException(404,'Scenario not found')
        if float(candidate['projected_closing_balance'])<0: raise HTTPException(409,'This scenario still has a shortfall. Update your inputs before choosing a plan.')
        if not record['verification_reports'][body.scenario_id]['approved']: raise HTTPException(409,'Unverified plan')
        with repo._connection() as con: con.execute('UPDATE plan_details SET selected=? WHERE request_id=?',(body.scenario_id,request_id))
        return {'selected':body.scenario_id,'message':'Planning choice saved locally. No payment or money transfer has been made.'}

    dist=PROJECT_ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
        @app.get('/')
        def index(): return FileResponse(dist/'index.html')
    return app

app=create_app(os.getenv('RUPEEPILOT_DB'))
