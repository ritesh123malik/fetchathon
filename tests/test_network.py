"""Integration proof: real uAgents transport, with all outbound internet blocked."""
import concurrent.futures
import json
import os
import socket
import subprocess
import time
from pathlib import Path
import sys
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api import create_app
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def network(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    tmp=tmp_path_factory.mktemp('network')
    code='''
import socket,sys
original=socket.socket.connect
def local_only(self,address):
    if isinstance(address,tuple) and address[0] not in ('127.0.0.1','localhost','::1'):
        raise RuntimeError('Outbound network blocked: '+str(address))
    return original(self,address)
socket.socket.connect=local_only
import uagents.asgi
uagents.asgi.HOST='127.0.0.1'
from run_network import build_network
build_network(int(sys.argv[1])).run()
'''
    log=(tmp/'network.log').open('w+')
    env={**os.environ,'PYTHONPATH':str(ROOT)}
    proc=subprocess.Popen([sys.executable,'-c',code,str(port)],cwd=tmp,env=env,stdout=log,stderr=log)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(600):
            if proc.poll() is not None:
                log.seek(0);pytest.fail(log.read())
            try:
                httpx.get(url,timeout=.2);break
            except httpx.TransportError: time.sleep(.05)
        else:
            log.seek(0);pytest.fail('Agent network did not start: '+log.read())
        yield port
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill();proc.wait()
        log.close()


def test_end_to_end_uagents_and_concurrent_requests(network,tmp_path,monkeypatch):
    monkeypatch.setenv('RUPEEPILOT_NETWORK','1')
    monkeypatch.setenv('RUPEEPILOT_AGENT_PORT',str(network))
    with TestClient(create_app(tmp_path/'network.db')) as c:
        demo=c.get('/api/demo').json()
        result=c.post('/api/plans',json=demo)
        assert result.status_code==200,result.text
        data=result.json()
        assert all(t['transport']=='uagents' for t in data['trace'])
        assert data['result']['status']=='verified'
        rid=data['result']['request_id']
        assert c.get('/api/plans/'+rid).json()['result']==data['result']
        assert c.post('/api/plans/'+rid+'/select',json={'scenario_id':data['result']['recommended_scenario']['scenario_id']}).status_code==200
    def request(amount):
        d=json.loads(json.dumps(demo));d['profile']['unexpected_expenses']=str(amount)
        r=httpx.post(f'http://127.0.0.1:{network}/plan',json={'payload_json':json.dumps(d)},timeout=30).json()
        assert not r['error'],r
        return json.loads(r['payload_json'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs=list(pool.map(request,[8000,9000,10000,11000]))
    assert len({o['result']['request_id'] for o in outputs})==4
    assert [o['input']['profile']['unexpected_expenses'] for o in outputs]==['8000','9000','10000','11000']
