import asyncio
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from app.api import create_app
from run_network import build_network
from uagents_core.contrib.protocols.chat import ChatMessage, ChatAcknowledgement, TextContent

class Storage:
    def __init__(self): self.values={}
    def get(self,key): return self.values.get(key)
    def set(self,key,value): self.values[key]=value

class Context:
    def __init__(self): self.storage=Storage(); self.session='session-1'; self.sent=[]
    async def send(self,recipient,message): self.sent.append(message)

def test_acp_demo_plan_missing_fields_and_isolation(tmp_path,monkeypatch):
    monkeypatch.delenv('RUPEEPILOT_NETWORK',raising=False)
    app=create_app(tmp_path/'chat.db')
    real_client=httpx.AsyncClient
    def client(**kwargs):
        return real_client(transport=httpx.ASGITransport(app=app),**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',client)
    async def exercise():
        bureau=build_network(18019)
        coordinator=bureau._agents[0]
        protocol=next(iter(coordinator.protocols.values()))
        handler=protocol.signed_message_handlers[ChatMessage.build_schema_digest(ChatMessage)]
        context=Context()
        async def send(text,sender='local-test-user'):
            context.sent=[]
            await handler(context,sender,ChatMessage(timestamp=datetime.now(timezone.utc),msg_id=uuid4(),content=[TextContent(type='text',text=text)]))
            assert isinstance(context.sent[0],ChatAcknowledgement)
            return context.sent[-1].content[0].text
        assert 'Please provide:' in await send('plan')
        assert 'Synthetic demo loaded' in await send('demo')
        reply=await send('plan')
        assert 'Saved locally:' in reply,reply
        assert '₹4000' in reply
        assert 'Please provide:' in await send('plan','different-user')
        context.session='session-2'
        assert 'Please provide:' in await send('plan')
        assert 'Draft cleared' in await send('reset')
    asyncio.run(exercise())
    with TestClient(app) as c: assert len(c.get('/api/plans').json())==1
