"""Seven real uAgents on localhost; registration and publication are disabled."""
import asyncio
import json
import secrets
import os
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from uagents import Agent, Bureau, Context, Model, Protocol
from uagents_core.registration import BatchRegistrationPolicy
from uagents.resolver import Resolver
from uagents_core.contrib.protocols.chat import ChatMessage, ChatAcknowledgement, TextContent, EndSessionContent, chat_protocol_spec
import uagents.asgi
from app.agents.network_messages import AgentTask, AgentTaskResult
from app.services.planner import PlanningInput, execute_task, json_value, plan
from app.config import PROJECT_ROOT

class LocalResolver(Resolver):
    async def resolve(self, destination):
        return None, []  # In-bureau delivery needs no external resolution.


class LocalAgent(Agent):
    # uAgents 0.25.5 sends status updates even with no registration policy.
    async def _update_agent_status(self, active: bool):
        pass


class NoRegistration(BatchRegistrationPolicy):
    def add_agent(self, agent_info, identity): pass
    async def register(self): pass

class PlanRequest(Model):
    payload_json: str

class PlanResponse(Model):
    payload_json: str = '{}'
    error: str = ''


def prepare_chat_payload(draft):
    from decimal import Decimal
    profile = {}
    inc = Decimal(str(draft.get('monthly_income', '0.00') or '0.00'))
    spend = Decimal(str(draft.get('regular_spending', '0.00') or '0.00'))
    bills = Decimal(str(draft.get('fixed_bills', '0.00') or '0.00'))
    sav = Decimal(str(draft.get('planned_savings', '0.00') or '0.00'))
    shock = Decimal(str(draft.get('unexpected_expenses', '0.00') or '0.00'))
    opening = Decimal(str(draft.get('opening_balance', '0.00') or '0.00'))
    buffer = Decimal(str(draft.get('minimum_cash_buffer', '0.00') or '0.00'))

    if 'max_spending_cut' in draft and draft['max_spending_cut'] is not None:
        cut = min(Decimal(str(draft['max_spending_cut'])), spend)
    else:
        cut = min(spend * Decimal('0.5'), Decimal('4000.00'))

    profile['monthly_income'] = str(inc)
    profile['fixed_bills'] = str(bills)
    profile['regular_spending'] = str(spend)
    profile['planned_savings'] = str(sav)
    profile['unexpected_expenses'] = str(shock)
    profile['opening_balance'] = str(opening)
    profile['minimum_cash_buffer'] = str(buffer)
    profile['max_spending_cut'] = str(cut)

    clean_bills = []
    for b in draft.get('bills', []):
        b_amount = Decimal(str(b.get('amount', 0)))
        b_name = (b.get('name') or '').lower()
        if 'medical' in b_name or 'emergency' in b_name or 'unexpected' in b_name or (b_amount == shock and shock > 0):
            continue
        clean_bills.append(b)

    if bills > 0 and clean_bills:
        current_sum = sum(Decimal(str(b.get('amount', 0))) for b in clean_bills)
        if current_sum > bills:
            profile['fixed_bills'] = str(current_sum)
    else:
        clean_bills = []

    clean_goals = []
    if sav > 0:
        g_sum = Decimal(0)
        for g in draft.get('goals', []):
            contrib = Decimal(str(g.get('monthly_contribution', 0)))
            if g_sum + contrib <= sav:
                clean_goals.append(g)
                g_sum += contrib

    return {'profile': profile, 'bills': clean_bills, 'goals': clean_goals}


def format_chat_plan(res, profile, is_demo=False):
    from decimal import Decimal
    result = res.get('result', {})
    rec = result.get('recommended_scenario')
    alts = result.get('alternatives', [])

    inc = Decimal(str(profile.get('monthly_income', '0')))
    bills = Decimal(str(profile.get('fixed_bills', '0')))
    spend = Decimal(str(profile.get('regular_spending', '0')))
    sav = Decimal(str(profile.get('planned_savings', '0')))
    shock = Decimal(str(profile.get('unexpected_expenses', '0')))
    opening = Decimal(str(profile.get('opening_balance', '0')))

    baseline = opening + inc - bills - spend - sav - shock

    title = "📊 **RupeePilot — ₹8,000 Emergency Demo**" if is_demo else "📊 **RupeePilot Financial Analysis**"

    lines = [
        title,
        "",
        f"• **Monthly Inflow**: ₹{inc:,.2f}",
        f"• **Essential Obligations (Bills)**: ₹{bills:,.2f} *(100% Protected)*",
        f"• **Regular Spending**: ₹{spend:,.2f}",
        f"• **Planned Savings**: ₹{sav:,.2f}",
        f"• **Unexpected Emergency**: ₹{shock:,.2f}",
        f"• **Baseline Closing Balance**: **₹{baseline:,.2f}**" + (" *(Shortfall)*" if baseline < 0 else ""),
        "",
        f"💡 **{result.get('summary', '')}**",
        "",
        "🛡️ **Verified Options (Independently checked by 6 Specialists):**",
    ]

    if rec:
        bal = Decimal(str(rec.get('projected_closing_balance', '0')))
        status = "✓ Balanced" if bal >= 0 else "⚠️ Partial recovery"
        lines.append(f"1. **Recommended Plan**: {rec.get('description', '')}")
        lines.append(f"   • Projected Closing Balance: **₹{bal:,.2f}** ({status})")
        if rec.get('tradeoffs'):
            lines.append(f"   • Trade-off: {rec['tradeoffs'][0]}")
        lines.append("")

    for idx, a in enumerate(alts[:2], start=2):
        bal = Decimal(str(a.get('projected_closing_balance', '0')))
        lines.append(f"{idx}. **Alternative**: {a.get('description', '')}")
        lines.append(f"   • Projected Closing Balance: **₹{bal:,.2f}**")
        if a.get('tradeoffs'):
            lines.append(f"   • Trade-off: {a['tradeoffs'][0]}")
        lines.append("")

    lines.extend([
        "🔒 **Safety & Verification:**",
        "• All calculations independently checked via Python Decimal arithmetic.",
        "• Verified across 6 specialists: Expense, Cashflow, Bills, Goal, Scenario, and Verification.",
        "• No automatic bank transactions are ever executed. You remain in control.",
    ])

    return "\n".join(lines)


def build_network(port=8010):
    coordinator_seed = os.getenv("COORDINATOR_SEED")
    use_mailbox = os.getenv("AGENT_MAILBOX", "false").lower() in ("true", "1")

    # Ephemeral test identities: no private keys from the supplied .env are used unless mailbox is enabled.
    seed = secrets.token_hex(32)
    def agent(name):
        return LocalAgent(name='rupeepilot-'+name,seed=seed+name,enable_agent_inspector=False,
                     publish_agent_details=False,mark_inactive_on_shutdown=False,
                     handle_messages_concurrently=True, network='testnet', resolve=LocalResolver())

    if use_mailbox and coordinator_seed:
        coordinator = Agent(
            name='RupeePilot Financial Planner',
            seed=coordinator_seed,
            mailbox=True,
            enable_agent_inspector=False,
            publish_agent_details=False,
            mark_inactive_on_shutdown=False,
            handle_messages_concurrently=True,
            network='mainnet'
        )
    else:
        coordinator = agent('coordinator')

    specialists={}
    for name in ['expense','cashflow','bills','goal','scenario','verification']:
        specialist=agent(name)
        def attach(target, role):
            @target.on_message(model=AgentTask, replies=AgentTaskResult)
            async def task(ctx:Context,sender:str,msg:AgentTask):
                try:
                    if sender!=coordinator.address: raise ValueError('Unknown coordinator')
                    if msg.task_type!=role: raise ValueError('Incorrect task type')
                    response=execute_task(role,json.loads(msg.payload_json))
                    reply=AgentTaskResult(request_id=msg.request_id,agent_name=role,success=True,
                                          result_json=json.dumps(response,default=json_value))
                except Exception as exc:
                    reply=AgentTaskResult(request_id=msg.request_id,agent_name=role,success=False,error=str(exc))
                await ctx.send(sender,reply)
        attach(specialist,name)
        specialists[name]=specialist

    @coordinator.on_rest_post('/plan',PlanRequest,PlanResponse)
    async def planning(ctx:Context,request:PlanRequest):
        try:
            data=PlanningInput.model_validate_json(request.payload_json)
            async def dispatch(name,payload):
                request_id=str(uuid4())
                response,status=await ctx.send_and_receive(specialists[name].address,
                    AgentTask(request_id=request_id,task_type=name,payload_json=json.dumps(payload)),
                    response_type=AgentTaskResult,timeout=10)
                if not response or not response.success: raise RuntimeError(f'{name} did not complete: '+(response.error if response else 'timeout'))
                if response.request_id!=request_id or response.agent_name!=name: raise RuntimeError('Mismatched agent response')
                return json.loads(response.result_json)
            result=await plan(data,dispatch)
            return PlanResponse(payload_json=json.dumps(result))
        except Exception as exc: return PlanResponse(error=str(exc))

    # ACP adapter is installed locally but is not published or registered.
    protocol=Protocol(spec=chat_protocol_spec)
    @protocol.on_message(ChatMessage)
    async def chat(ctx:Context,sender:str,msg:ChatMessage):
        await ctx.send(sender,ChatAcknowledgement(timestamp=datetime.now(timezone.utc),acknowledged_msg_id=msg.msg_id))
        text='\n'.join(c.text for c in msg.content if isinstance(c,TextContent)).strip()
        key=f'draft:{sender}:{ctx.session}'
        draft=ctx.storage.get(key) or {}
        api_port=int(os.getenv("RUPEEPILOT_API_PORT","8080"))

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                lowered = text.lower().strip()
                if lowered in ('demo', 'load demo', 'example'):
                    demo=(await client.get(f'http://127.0.0.1:{api_port}/api/demo')).json()
                    draft={**demo['profile'],'bills':demo.get('bills',[]),'goals':demo.get('goals',[])}
                    ctx.storage.set(key,draft)
                    answer="Synthetic demo loaded: income ₹28,000, fixed bills ₹10,000, spending ₹8,000, savings ₹6,000, emergency ₹8,000, opening balance ₹0, allowed cut ₹4,000, buffer ₹0. Send plan to compare verified options."

                elif lowered in ('reset', 'clear', 'start over', 'restart'):
                    ctx.storage.set(key,{})
                    answer="Draft cleared. Provide income, fixed bills, regular spending, planned savings, unexpected expense, opening balance, max spending cut, and minimum buffer. Or send 'demo' to test the ₹8,000 emergency example."

                elif lowered in ('plan', 'generate plan', 'calculate'):
                    from app.services.local_chat import merge_draft
                    checked=merge_draft(draft,{})
                    if not checked.is_ready:
                        answer='Please provide: '+', '.join(checked.missing_fields)
                    else:
                        payload=prepare_chat_payload(draft)
                        r=await client.post(f'http://127.0.0.1:{api_port}/api/plans',json=payload)
                        r.raise_for_status()
                        result=r.json()['result']
                        rich_plan=format_chat_plan(r.json(), payload['profile'])
                        answer=f"{result['summary']}\n\n" + '\n'.join(s['description']+' Closing balance ₹'+s['projected_closing_balance'] for s in result['alternatives'][:2]) + f"\n\nSaved locally: {result['request_id']}. Review and choose in the local dashboard. No transaction is executed.\n\n{rich_plan}"

                else:
                    # Natural language financial query — parse via ASI:One
                    r=await client.post(f'http://127.0.0.1:{api_port}/api/chat',json={'message':text,'draft':draft,'use_asi':True})
                    r.raise_for_status()
                    data=r.json()
                    draft=data.get('draft', draft)
                    ctx.storage.set(key,draft)

                    # If income was identified, immediately compute and present the verified plan!
                    if draft.get('monthly_income') and (draft.get('unexpected_expenses') or draft.get('regular_spending') or draft.get('fixed_bills')):
                        payload=prepare_chat_payload(draft)
                        r_plan=await client.post(f'http://127.0.0.1:{api_port}/api/plans',json=payload)
                        r_plan.raise_for_status()
                        answer=format_chat_plan(r_plan.json(), payload['profile'])
                    else:
                        answer=(
                            f"{data.get('message', 'Processing your request...')}\n\n"
                            "💡 Tip: Send **demo** to immediately explore an ₹8,000 emergency walkthrough."
                        )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            answer=f"RupeePilot encountered an issue processing your request: {exc}. Please verify your input or try sending 'demo'."

        # Dispatch chat response with retry
        for attempt in range(2):
            try:
                await ctx.send(sender,ChatMessage(timestamp=datetime.now(timezone.utc),msg_id=uuid4(),content=[TextContent(type='text',text=answer)]))
                break
            except Exception as send_err:
                if attempt == 0:
                    await asyncio.sleep(1)

    @protocol.on_message(ChatAcknowledgement)
    async def ack(ctx:Context,sender:str,msg:ChatAcknowledgement): pass
    coordinator.include(protocol,publish_manifest=False)
    bureau=Bureau(agents=[coordinator,*specialists.values()],port=port,
                  endpoint=f'http://127.0.0.1:{port}/submit',registration_policy=NoRegistration())
    return bureau

if __name__=='__main__':
    # uAgents defaults to all interfaces; enforce loopback for this local build.
    uagents.asgi.HOST='127.0.0.1'
    build_network(int(os.getenv("RUPEEPILOT_AGENT_PORT", "8010"))).run()
