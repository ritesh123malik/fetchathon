"""One validated planning pipeline for the browser, chat and local agents."""
from datetime import date
from decimal import Decimal
from uuid import uuid4
from pydantic import Field, model_validator
from app.schemas.financial_models import StrictModel, FinancialProfile, Transaction, Bill, SavingsGoal, PlanningScenario, VerificationReport
from app.agents.coordinator import assemble_result
from app.agents.expense_agent import analyze_expenses
from app.agents.cashflow_agent import analyze_cashflow
from app.agents.bills_agent import analyze_bills
from app.agents.goal_agent import analyze_goals
from app.agents.scenario_agent import generate_scenarios
from app.agents.verification_agent import verify_scenario

class PlanningInput(StrictModel):
    profile: FinancialProfile
    bills: list[Bill] = Field(default_factory=list, max_length=100)
    goals: list[SavingsGoal] = Field(default_factory=list, max_length=100)
    transactions: list[Transaction] = Field(default_factory=list, max_length=1000)
    reference_date: date = Field(default_factory=date.today)

    @model_validator(mode='after')
    def consistent_totals(self):
        if sum((b.amount for b in self.bills if not b.paid), Decimal(0)) > self.profile.fixed_bills:
            raise ValueError('Unpaid itemized bills exceed fixed bills. Include them in the fixed-bill total; they are not added twice.')
        if sum((g.monthly_contribution for g in self.goals), Decimal(0)) > self.profile.planned_savings:
            raise ValueError('Goal contributions exceed planned savings. Update the total or the goals.')
        if self.transactions:
            if sum((t.amount for t in self.transactions), Decimal(0)) != self.profile.regular_spending:
                raise ValueError('Reviewed transaction total must equal regular spending. Reapply the import or clear transactions.')
            flexible = sum((t.amount for t in self.transactions if t.category == 'discretionary'), Decimal(0))
            if self.profile.max_spending_cut > flexible:
                raise ValueError('Spending-cut limit exceeds the transactions reviewed as discretionary.')
            if any((t.date.year,t.date.month)!=(self.reference_date.year,self.reference_date.month) for t in self.transactions):
                raise ValueError('Transactions must belong to the planning reference month.')
        if len({g.name for g in self.goals}) != len(self.goals):
            raise ValueError('Savings goal names must be unique.')
        return self


def execute_task(name, payload):
    """Shared specialist dispatch, also used by actual uAgents handlers."""
    if name == 'bills':
        return analyze_bills([Bill.model_validate(b) for b in payload.get('bills', [])], date.fromisoformat(payload['reference_date']))
    if name == 'goal':
        return analyze_goals([SavingsGoal.model_validate(g) for g in payload.get('goals', [])], reference_date=date.fromisoformat(payload['reference_date']))
    profile = FinancialProfile.model_validate(payload['profile'])
    if name == 'verification':
        return verify_scenario(profile, PlanningScenario.model_validate(payload['candidate']))
    if name == 'expense':
        return analyze_expenses(profile, [Transaction.model_validate(t) for t in payload.get('transactions',[])])
    return {'expense': analyze_expenses, 'cashflow': analyze_cashflow, 'scenario': generate_scenarios}[name](profile)


def json_value(value):
    if hasattr(value, 'model_dump'): return value.model_dump(mode='json')
    if isinstance(value, (Decimal, date)): return str(value)
    raise TypeError(type(value).__name__)


async def plan(data: PlanningInput, dispatch=None):
    import asyncio
    import json
    trace = []
    async def call(name, payload):
        result = await dispatch(name, payload) if dispatch else execute_task(name, payload)
        trace.append({'agent': name, 'status': 'completed', 'transport': 'uagents' if dispatch else 'local', 'sequence': len(trace)+1})
        return result
    payload = data.model_dump(mode='json')
    expense, cashflow, bills, goals = await asyncio.gather(*(call(n, payload) for n in ['expense','cashflow','bills','goal']))
    scenarios = await call('scenario', payload)
    candidates = [PlanningScenario.model_validate(c) for c in scenarios['scenarios']]
    checked = []
    for c in candidates:
        verification = await call('verification', {**payload, 'candidate': c.model_dump(mode='json')})
        verification['report'] = VerificationReport.model_validate(verification['report'])
        checked.append((c, verification))
    result = assemble_result(data.profile, data.bills, data.goals, str(uuid4()), expense, cashflow, bills, goals, scenarios, checked)
    p = data.profile
    # Monthly projections explicitly use recurring totals; the shock and cuts apply only in month one.
    recurring = p.monthly_income-p.fixed_bills-p.regular_spending-p.planned_savings
    chosen = result.recommended_scenario
    recovery = chosen.adjustment.spending_reduction+chosen.adjustment.savings_reduction if chosen else Decimal(0)
    forecast = [{'month': i, 'baseline': p.opening_balance+recurring*i,
                 'with_emergency': p.opening_balance+recurring*i-p.unexpected_expenses,
                 'with_plan': p.opening_balance+recurring*i-p.unexpected_expenses+recovery} for i in range(1,4)]
    # One-month reduction allocated proportionally, with exact remainder to the last goal.
    impacts=[]
    remaining_cut = chosen.adjustment.savings_reduction if chosen else Decimal(0)
    assigned_total = sum((g.monthly_contribution for g in data.goals), Decimal(0))
    # Unassigned savings is reduced first; do not invent goal money.
    remaining_cut = max(Decimal(0), remaining_cut-(p.planned_savings-assigned_total))
    total_cut=remaining_cut
    for i,g in enumerate(data.goals):
        cut = (total_cut*g.monthly_contribution/assigned_total).quantize(Decimal('.01')) if assigned_total else Decimal(0)
        cut = min(g.monthly_contribution, remaining_cut if i==len(data.goals)-1 else cut, remaining_cut)
        remaining_cut-=cut
        impacts.append({'name':g.name,'original_contribution':g.monthly_contribution,'this_month':g.monthly_contribution-cut,'one_month_reduction':cut})
    output={'input':payload,'result':result,'analyses':{'expense':expense,'cashflow':cashflow,'bills':bills,'goal':goals},'forecast':forecast,'goal_impacts':impacts,'trace':trace,'verification_reports':{c.scenario_id:v['report'] for c,v in checked},'forecast_assumption':'Income, bills, spending and savings repeat monthly. The unexpected expense and proposed cuts occur only in month 1. Bill payment timing is not guaranteed.'}
    return json.loads(json.dumps(output, default=json_value))
