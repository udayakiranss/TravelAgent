# planner.py
# A simple planner that converts a high-level user goal into ordered sub-tasks.
def plan_trip(intent: dict):
    # intent example: {'from':'NYC','to':'LON','date':'2025-08-12','needs':['flight','hotel','car']}
    tasks = []
    needs = intent.get('needs', [])
    if 'flight' in needs:
        tasks.append({'task':'search_flights','params':{'from':intent.get('from'),'to':intent.get('to'),'date':intent.get('date')}})
    if 'hotel' in needs:
        tasks.append({'task':'search_hotels','params':{'city':intent.get('to')}})
    if 'car' in needs:
        tasks.append({'task':'search_cars','params':{'city':intent.get('to')}})
    # finally build itinerary and optionally payment
    tasks.append({'task':'build_itinerary','params':{}})
    if intent.get('auto_pay'):
        tasks.append({'task':'process_payment','params':{'amount':intent.get('budget',0),'method':intent.get('payment_method','card')}})
    return tasks
