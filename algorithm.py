import copy
from collections import defaultdict
from data import WH_LABELS, PARTS
from orders import ORDERS

def build_inv_map(inventory):
    """
    Converts a flat list of inventory records into a nested dictionary map
    (part -> warehouse -> qty/transit) for quick O(1) lookups during analysis.
    """
    m = defaultdict(dict)
    for rec in inventory:
        m[rec['part']][rec['wh']] = {'qty':rec['qty'],'transit':rec['transit']}
    return m

def get_avail(inv_map, part, wh):
    """
    Retrieves the total available inventory (on-hand + in-transit) for a
    specific part and warehouse from the nested inventory map.
    """
    loc = inv_map.get(part,{}).get(wh)
    return (loc['qty']+loc['transit']) if loc else 0

def deduct(inv_map, part, wh, amount):
    """
    Deducts a specified inventory amount from a warehouse for a given part.
    Prioritizes deducting from on-hand quantity first before falling back
    to in-transit quantity.
    """
    loc = inv_map.get(part,{}).get(wh)
    if not loc or amount<=0: return
    fq = min(loc['qty'],amount); loc['qty']-=fq
    rem = amount-fq
    if rem>0: loc['transit']=max(0,loc['transit']-rem)


def run_constraint_algorithm(orders, inventory):
    """
    Core Engine Algorithm: Simulates order fulfillment sequentially against
    given inventory levels. Checks for constrained orders, identifies resolution paths
    (e.g. from parent warehouses or compatible parts), and logs the trace of availability.
    """
    inv = build_inv_map(copy.deepcopy(inventory))
    results = []
    for order in orders:
        chain = [order['part']]+[c for c in order['compatibles'] if c!=order['part']]
        isp = (order['wh']==order['parent'])
        constrained,resolved_by,resolved_at,trace = True,None,None,[]
        for part in chain:
            aw = get_avail(inv,part,order['wh'])
            ap = aw if isp else get_avail(inv,part,order['parent'])
            trace.append({'part':part,'at_wh':aw,'at_parent':None if isp else ap,
                          'wh_label':WH_LABELS.get(order['wh'],str(order['wh'])),
                          'parent_label':WH_LABELS.get(order['parent'],str(order['parent']))})
            if aw>=order['qty']:
                deduct(inv,part,order['wh'],order['qty']); constrained=False
                resolved_by=part; resolved_at=WH_LABELS.get(order['wh']); break
            if not isp and ap>=order['qty']:
                deduct(inv,part,order['parent'],order['qty']); constrained=False
                resolved_by=part; resolved_at=f"{WH_LABELS.get(order['parent'])} (Parent DC)"; break
        results.append({**order,'constrained':constrained,
                        'resolved_by':resolved_by,'resolved_at':resolved_at,'trace':trace})
    return results



def _summarise(results, part_filter, wh_filter):
    """
    Aggregates the algorithm output into high-level metrics.
    Filters the results by part/warehouse and calculates quantities, 
    totals, and constraints both globally and per-group.
    """
    def filt(lst):
        return [o for o in lst
                if (not part_filter or o['part']==part_filter)
                and (not wh_filter or o['wh']==wh_filter)]
    filtered    = filt(results)
    constrained = [o for o in filtered if o['constrained']]
    uncon       = [o for o in filtered if not o['constrained']]
    by_part = [{'part':p,'total':len([o for o in results if o['part']==p]),
                'constrained':sum(1 for o in results if o['part']==p and o['constrained']),
                'total_qty':sum(o['qty'] for o in results if o['part']==p)} for p in PARTS]
    by_wh = [{'wh':w,'label':WH_LABELS[w],
               'total':len([o for o in results if o['wh']==w]),
               'constrained':sum(1 for o in results if o['wh']==w and o['constrained'])}
             for w in [1,2,3]]
    def safe(o): return {'id':o['id'],'date_str':o['date_str'],'qty':o['qty'],
                          'wh':o['wh'],'part':o['part'],'trace':o.get('trace',[]),
                          'resolved_by':o.get('resolved_by'),'resolved_at':o.get('resolved_at')}
    return {'filtered':{'total':len(filtered),'constrained':len(constrained),'unconstrained':len(uncon)},
            'global':{'total':len(results),'constrained':sum(1 for o in results if o['constrained'])},
            'by_part':by_part,'by_wh':by_wh,
            'constrained_orders':[safe(o) for o in constrained[:20]],
            'unconstrained_sample':[safe(o) for o in uncon[:5]]}

def analyze(parsed_intent, inventory):
    """
    Executes the constraint algorithm after applying conditional inventory overrides
    based on the AI-parsed intent, and then summarizes the results for the response.
    """
    intent = parsed_intent.get('intent','GENERAL')
    pf     = parsed_intent.get('part')
    wf     = parsed_intent.get('warehouse')
    oh     = parsed_intent.get('onHandQty')
    tr     = parsed_intent.get('transitQty',0) or 0
    active_inv = inventory
    if intent=='INVENTORY_IMPACT' and pf and wf:
        active_inv = [{**i,'qty':oh if oh is not None else i['qty'],'transit':tr}
                      if (i['part']==pf and i['wh']==wf) else i for i in inventory]
    results = run_constraint_algorithm(ORDERS, active_inv)
    summary = _summarise(results, pf, wf)
    return {'intent':intent,'part':pf,'warehouse':wf,
            'inv_override':{'part':pf,'warehouse':wf,'onHandQty':oh,'transitQty':tr}
                            if intent=='INVENTORY_IMPACT' else None, **summary}



def run_scenario(baseline_inventory, adjustments):
    """
    Simulates a "what-if" inventory modification.
    Applies quantity changes to baseline inventory, then evaluates both baseline 
    and scenario constraints to calculate the net-delta impact directly resulting from the modification.
    """
    scenario_inv = copy.deepcopy(baseline_inventory)
    applied = []
    for adj in adjustments:
        part,wh = adj.get('part'), adj.get('wh')
        qd,td   = int(adj.get('qty_delta',0)), int(adj.get('transit_delta',0))
        if not part or not wh: continue
        rec = next((i for i in scenario_inv if i['part']==part and i['wh']==wh), None)
        if rec:
            rec['qty']     = max(0,rec['qty']+qd)
            rec['transit'] = max(0,rec['transit']+td)
            applied.append({'part':part,'wh':wh,'wh_label':WH_LABELS.get(wh,f'WH-{wh}'),
                            'qty_delta':qd,'transit_delta':td,
                            'new_qty':rec['qty'],'new_transit':rec['transit']})
    br = run_constraint_algorithm(ORDERS, baseline_inventory)
    sr = run_constraint_algorithm(ORDERS, scenario_inv)
    bs = _summarise(br,None,None); ss = _summarise(sr,None,None)
    bids = {o['id'] for o in br if o['constrained']}
    sids = {o['id'] for o in sr if o['constrained']}
    res_ids = bids-sids; brk_ids = sids-bids
    def safe(o): return {'id':o['id'],'date_str':o['date_str'],'qty':o['qty'],
                          'wh':o['wh'],'part':o['part'],
                          'resolved_by':o.get('resolved_by'),'resolved_at':o.get('resolved_at')}
    nr = [safe(o) for o in sr if o['id'] in res_ids and not o['constrained']]
    nb = [safe(o) for o in sr if o['id'] in brk_ids and o['constrained']]
    part_delta = []
    for p in PARTS:
        b = next((x for x in bs['by_part'] if x['part']==p),{})
        s = next((x for x in ss['by_part'] if x['part']==p),{})
        part_delta.append({'part':p,'total':b.get('total',0),
                           'base_constrained':b.get('constrained',0),
                           'scen_constrained':s.get('constrained',0),
                           'delta':s.get('constrained',0)-b.get('constrained',0)})
    wh_delta = []
    for w in [1,2,3]:
        b = next((x for x in bs['by_wh'] if x['wh']==w),{})
        s = next((x for x in ss['by_wh'] if x['wh']==w),{})
        wh_delta.append({'wh':w,'label':WH_LABELS[w],
                         'base_constrained':b.get('constrained',0),
                         'scen_constrained':s.get('constrained',0),
                         'delta':s.get('constrained',0)-b.get('constrained',0)})
    bc,sc = bs['global']['constrained'],ss['global']['constrained']
    return {'adjustments':applied,
            'baseline':{'constrained':bc,'unconstrained':bs['global']['total']-bc,'total':bs['global']['total']},
            'scenario':{'constrained':sc,'unconstrained':ss['global']['total']-sc,'total':ss['global']['total']},
            'delta':{'constrained':sc-bc,'resolved':len(res_ids),'broken':len(brk_ids)},
            'part_delta':part_delta,'wh_delta':wh_delta,
            'newly_resolved':nr[:30],'newly_broken':nb[:30],'scenario_inventory':scenario_inv}


