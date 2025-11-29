# main.py - demo runner
from agents.orchestrator import Orchestrator
from agents.memory import create_memory

def interpret_nl(text: str):
    # very small rule-based NL parser for demo
    text = text.lower()
    intent = {'needs':[]}
    if 'flight' in text or 'fly' in text:
        intent['needs'].append('flight')
    if 'hotel' in text or 'stay' in text:
        intent['needs'].append('hotel')
    if 'car' in text or 'rental' in text:
        intent['needs'].append('car')
    import re
    m = re.search(r'from ([a-z]{3}) to ([a-z]{3})', text)
    if m:
        intent['from']=m.group(1).upper()
        intent['to']=m.group(2).upper()
    d = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if d:
        intent['date']=d.group(1)
    if 'pay' in text or 'charge' in text:
        intent['auto_pay'] = True
    return intent

if __name__ == '__main__':
    memory = create_memory()
    orch = Orchestrator(memory=memory)
    examples = [
        'Find me a flight from NYC to LON on 2025-08-12 and book a hotel'
        # 'I need a rental car in LON for my trip',
        # 'Charge my Visa to pay the total'
    ]
    for ex in examples:
        print('\nUSER:', ex)
        intent = interpret_nl(ex)
        print('PARSED INTENT:', intent)
        out = orch.run_intent(intent)
        print('RESULTS:', out)
