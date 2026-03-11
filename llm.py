import os, json, re
import requests as req

def call_claude(system, user_msg, max_tokens=400):
    """
    Sends a request to the Anthropic Claude API to generate a chat response
    using a predefined system prompt and the user's message.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY','')
    headers = {'x-api-key':api_key,'anthropic-version':'2023-06-01','content-type':'application/json'}
    payload = {'model':'claude-sonnet-4-20250514','max_tokens':max_tokens,
               'system':system,'messages':[{'role':'user','content':user_msg}]}
    resp = req.post('https://api.anthropic.com/v1/messages',headers=headers,json=payload,timeout=30)
    resp.raise_for_status()
    return ''.join(b.get('text','') for b in resp.json().get('content',[]))

NLU_SYSTEM = """You are a supply chain query parser. Extract the user's intent and parameters.
Return ONLY valid JSON — no markdown, no extra text.

JSON schema:
{
  "intent": "CONSTRAINED_COUNT" | "INVENTORY_IMPACT" | "ORDER_COUNT" | "SUMMARY" | "GENERAL",
  "part": "Part A" | "Part B" | "Part C" | "Part D" | null,
  "warehouse": 1 | 2 | 3 | null,
  "onHandQty": number | null,
  "transitQty": number | null
}

Intent rules:
- CONSTRAINED_COUNT → "how many constrained VINs/orders for Part X at Warehouse Y"
- INVENTORY_IMPACT  → "I have N units of Part X at Warehouse Y, why still constrained?"
- ORDER_COUNT       → "how many total orders for Part X"
- SUMMARY           → general summary / overview
- GENERAL           → anything else

Warehouse mapping: "Warehouse A"/"WH-1"/"Warehouse 1" → 1; "B"/"2" → 2; "C"/"3" → 3
Part mapping: "Part_A"/"PartA"/"part a" → "Part A"  etc.
If onHandQty mentioned ("I have 5 pcs"), capture as onHandQty."""

RESPONSE_SYSTEM = """You are a senior supply chain analytics expert. Answer the user's question
using the analysis data provided. Be direct and specific — use real numbers from the data.
When explaining constraints, reference the FIFO allocation logic and compatibility chain concisely.
Keep answers under 200 words. Plain text only — no markdown headers."""

SCENARIO_SYSTEM = """You are a senior supply chain analytics expert interpreting a what-if
scenario simulation. Summarise the impact clearly: how many constraints were resolved, which
parts/warehouses benefited most, and whether the adjustments were efficient. Be specific with
numbers. Under 200 words. Plain text only."""

def extract_intent(query):
    """
    Uses Claude to parse the user's natural language query and maps it into a
    structured JSON object representing analytical intent, part, and warehouse.
    """
    raw = call_claude(NLU_SYSTEM, query, 250)
    raw = re.sub(r'```.*?```','',raw,flags=re.DOTALL).strip()
    try:    return json.loads(raw)
    except: return {'intent':'GENERAL','part':None,'warehouse':None}

def generate_response(query, analysis):
    """
    Generates a natural language textual summary of the constraint analysis
    for conversational engagement with the user.
    """
    s = {k:analysis[k] for k in ('intent','filtered','global','by_part','by_wh','inv_override') if k in analysis}
    s['sample_constrained'] = analysis.get('constrained_orders',[])[:5]
    return call_claude(RESPONSE_SYSTEM, f'User asked: "{query}"\n\nAnalysis:\n{json.dumps(s,indent=2)}', 500)

def generate_scenario_response(result):
    """
    Takes the mathematical delta output of a what-if scenario and generates
    a brief explanation summarizing the true impact for the user.
    """
    payload = {k:result[k] for k in ('adjustments','baseline','scenario','delta','part_delta','wh_delta')}
    payload['sample_resolved'] = result['newly_resolved'][:5]
    return call_claude(SCENARIO_SYSTEM, f'What-if scenario:\n{json.dumps(payload,indent=2)}', 500)


