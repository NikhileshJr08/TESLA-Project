from datetime import datetime
from data import RAW_ROWS

def parse_date(s):
    """
    Tries multiple supported date formats to safely parse a date string.
    Returns datetime.min if none match as a safety fallback.
    """
    for fmt in ('%m/%d/%Y','%Y-%m-%d'):
        try: return datetime.strptime(s,fmt)
        except: pass
    return datetime.min

def parse_orders():
    """
    Reads raw row data, maps orders by ID/warehouse/part to eliminate redundancies,
    sets up hierarchical and compatibility structures, and returns chronologically sorted orders.
    """
    order_map = {}
    for row_id,date,qty,wh,part,parent,compat in RAW_ROWS:
        key = (row_id,wh,part)
        if key not in order_map:
            order_map[key] = {'id':row_id,'date_str':date,'date':parse_date(date),
                              'qty':qty,'wh':wh,'part':part,'parent':parent,'compatibles':[]}
        o = order_map[key]
        d = parse_date(date)
        if d < o['date']: o['date']=d; o['date_str']=date
        if compat and compat!=part and compat not in o['compatibles']:
            o['compatibles'].append(compat)
    return sorted(order_map.values(), key=lambda x: x['date'])

ORDERS = parse_orders()


