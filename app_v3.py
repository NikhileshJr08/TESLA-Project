import os, json
from datetime import datetime
from flask import Flask, request, jsonify, render_template

from data import DEFAULT_INVENTORY, PARTS, WH_LABELS
from orders import ORDERS
from algorithm import run_constraint_algorithm, analyze, run_scenario
from llm import extract_intent, generate_response, generate_scenario_response

app = Flask(__name__)

@app.route('/')
def index():
    """
    Main Web Route: Pre-computes initial full-dataset analysis server-side
    using default inventory logic, and injects dashboard statistics straight to the UI.
    """
    # Pre-compute dashboard stats server-side and inject as JSON
    results  = run_constraint_algorithm(ORDERS, DEFAULT_INVENTORY)
    by_part  = {}
    by_wh    = {}
    for p in PARTS:
        orders_p = [o for o in ORDERS if o['part']==p]
        con_p    = [o for o in results if o['part']==p and o['constrained']]
        by_part[p] = {'total':len(orders_p),'constrained':len(con_p),
                      'total_qty':sum(o['qty'] for o in orders_p),
                      'con_qty':sum(o['qty'] for o in con_p)}
    for w in [1,2,3]:
        orders_w = [o for o in ORDERS if o['wh']==w]
        con_w    = [o for o in results if o['wh']==w and o['constrained']]
        by_wh[w] = {'total':len(orders_w),'constrained':len(con_w),
                    'total_qty':sum(o['qty'] for o in orders_w)}

    # Monthly order volume (group by year-month)
    from collections import Counter
    month_counts = Counter()
    for o in ORDERS:
        if o['date'] != datetime.min:
            ym = o['date'].strftime('%b %Y')
            month_counts[ym] += 1
    # Sort chronologically
    def ym_key(s):
        try: return datetime.strptime(s, '%b %Y')
        except: return datetime.min
    monthly = [{'month':m,'count':c} for m,c in
               sorted(month_counts.items(), key=lambda x: ym_key(x[0]))]

    # Top 10 highest-qty constrained orders
    con_orders = sorted([o for o in results if o['constrained']],
                        key=lambda x: x['qty'], reverse=True)[:10]
    top_con = [{'id':o['id'],'part':o['part'],'wh':o['wh'],
                'qty':o['qty'],'date':o['date_str']} for o in con_orders]

    total      = len(ORDERS)
    total_con  = sum(1 for o in results if o['constrained'])
    total_qty  = sum(o['qty'] for o in ORDERS)

    dashboard_data = {
        'total_orders': total,
        'total_constrained': total_con,
        'total_fulfilled': total-total_con,
        'constraint_rate': round(total_con/total*100,1) if total else 0,
        'total_qty': total_qty,
        'by_part': by_part,
        'by_wh': {str(k):v for k,v in by_wh.items()},
        'monthly': monthly,
        'top_constrained': top_con,
    }

    return render_template('index.html',
        dashboard_data=json.dumps(dashboard_data),
        default_inventory=json.dumps(DEFAULT_INVENTORY),
        parts=json.dumps(PARTS),
        wh_labels=json.dumps(WH_LABELS),
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Chat API Endpoint: Parses an incoming chatbot query, runs intent analysis to extract context,
    computes analysis impact based on intent, and builds an AI-assisted natural-language response.
    """
    body      = request.get_json()
    query     = body.get('query','').strip()
    inventory = body.get('inventory', DEFAULT_INVENTORY)
    if not query: return jsonify({'error':'Empty query'}),400
    try:
        parsed   = extract_intent(query)
        analysis = analyze(parsed, inventory)
        response = generate_response(query, analysis)
        return jsonify({'response':response,'analysis':analysis})
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/scenario', methods=['POST'])
def scenario():
    """
    Scenario API Endpoint: Collects manual user inventory adjustments, tests them against
    simulated future runs of constraints, and emits the computed net changes (along with an AI response text if specified).
    """
    body             = request.get_json()
    baseline_inv     = body.get('baseline_inventory', DEFAULT_INVENTORY)
    adjustments      = body.get('adjustments',[])
    generate_ai_text = body.get('generate_ai', True)
    if not adjustments: return jsonify({'error':'No adjustments'}),400
    try:
        result = run_scenario(baseline_inv, adjustments)
        if generate_ai_text: result['ai_summary'] = generate_scenario_response(result)
        else:                result['ai_summary'] = None
        result.pop('scenario_inventory',None)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error':str(e)}),500



if __name__ == '__main__':
    app.run(debug=True, port=7000)
