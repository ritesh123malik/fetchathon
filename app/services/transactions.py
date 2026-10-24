"""Local, transparent CSV classification; every suggestion remains editable."""
import csv
import io
from decimal import Decimal
from app.schemas.financial_models import Transaction

RULES={
    'essential': ('grocery','groceries','pharmacy','medicine','bus','metro','fuel','school'),
    'discretionary': ('restaurant','cafe','coffee','cinema','movie','netflix','spotify','shopping','dining','takeaway'),
}

def import_transactions(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if reader.fieldnames != ['date','description','amount']:
        raise ValueError('CSV header must be exactly: date,description,amount')
    rows=[]
    for index,row in enumerate(reader,start=2):
        if len(rows)>=1000: raise ValueError('Import at most 1000 transactions at a time.')
        if None in row or any(v is None for v in row.values()): raise ValueError(f'Row {index}: expected three columns.')
        description=row['description'].strip()
        if not description: raise ValueError(f'Row {index}: description is required.')
        category=next((key for key,words in RULES.items() if any(word in description.lower() for word in words)),'other')
        try:
            transaction=Transaction(date=row['date'].strip(), description=description,amount=row['amount'].strip().replace(',',''),category=category)
        except ValueError as exc: raise ValueError(f'Row {index}: invalid date or positive rupee amount (two decimal places maximum).') from exc
        rows.append(transaction)
    if not rows: raise ValueError('CSV contains no transactions.')
    return {'transactions':[t.model_dump(mode='json') for t in rows],
            'total':str(sum((t.amount for t in rows),Decimal(0))),
            'note':'Keyword-based category suggestions. Review them before applying. Import only regular spending; exclude income, transfers, fixed bills and savings.'}
