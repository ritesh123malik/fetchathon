"""Conservative offline extraction. Unrecognized language stays unfilled."""
import re
from decimal import Decimal
from app.services.parsing_service import ParsedFinancialRequest, assess_completeness

LABELS = {
 'monthly_income': r'(?:monthly income|income|i earn|salary)',
 'fixed_bills': r'(?:fixed bills|fixed expenses|bills total)',
 'regular_spending': r'(?:regular spending|monthly spending|living expenses)',
 'planned_savings': r'(?:planned savings|monthly savings|save monthly|savings contribution)',
 'unexpected_expenses': r'(?:unexpected expenses?|emergency expense|medical expense)',
 'opening_balance': r'(?:opening balance|cash balance|available cash)',
 'max_spending_cut': r'(?:max(?:imum)? spending cut|cut limit|can cut|reduce spending by)',
 'minimum_cash_buffer': r'(?:minimum cash buffer|minimum buffer|cash buffer)',
}

def extract_local(text):
    values={}
    for field,label in LABELS.items():
        m=re.search(label+r'\s*(?:is|of|are|:|=)?\s*(?:₹|rs\.?|inr)?\s*(-?\d[\d,]*(?:\.\d+)?)\s*(k|lakh)?\b',text,re.I)
        if m:
            amount=Decimal(m[1].replace(',',''))
            if m[2]: amount*=Decimal(1000 if m[2].lower()=='k' else 100000)
            values[field]=str(amount)
    if re.search(r'no (?:unexpected|emergency) expense',text,re.I): values['unexpected_expenses']='0'
    if re.search(r'no (?:spending )?cuts',text,re.I): values['max_spending_cut']='0'
    return values


def merge_draft(previous, updates):
    base={k:v for k,v in previous.items() if k in ParsedFinancialRequest.model_fields and k not in {'missing_fields','assumptions','is_ready'}}
    base.update({k:v for k,v in updates.items() if v is not None and k not in {'missing_fields','assumptions','is_ready','notes'} and (v != [] or k not in base)})
    draft=assess_completeness(ParsedFinancialRequest.model_validate(base))
    if draft.currency != 'INR':
        raise ValueError('Only INR is supported; enter amounts in rupees.')
    for key in ['opening_balance','max_spending_cut','minimum_cash_buffer']:
        if getattr(draft,key) is None: draft.missing_fields.append(key.replace('_',' '))
    draft.is_ready=not draft.missing_fields
    return draft
