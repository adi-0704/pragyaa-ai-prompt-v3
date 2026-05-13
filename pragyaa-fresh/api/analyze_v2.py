"""
/api/analyze_v2 — Multi-process Excel analysis + AI prompt evolution
Supports Amazon(NCA), Insta(NCA), and CC/DC processes.
"""
from flask import Flask, request, jsonify
import pandas as pd
import io, base64, json, requests
import os

app = Flask(__name__)

VERTEX_GENERATE_URL = "https://voicelensG1.pragyaa.ai/vertex/generate"
DEFAULT_MODEL       = "gemini-2.5-flash-lite"

# ─── Process Configs ──────────────────────────────────────────────────────────
PROCESS_CONFIGS = {
    "Amazon(NCA)": {
        "params": [
            "Greeting Score", "Self Brand Score", "Call Purpose Score", "Grammar Score", 
            "Hold Transfer Silence Score", "Active Listen Score", "Engagement Tone Score", 
            "Product Benefits Score", "Urgency/Objections Rebuttal Score", "Fees Charges Score", 
            "First Txn Amazon Score", "Appointment Score", "Referral Code Score", 
            "Track Application", "VKYC Biometric Score", "Subject to Approval Score", 
            "Closing Summary Score", "Accurate Disposition", "Junk Lead", 
            "Complete Information Provided", "Professional Behaviour", "No Disconnection Avoid"
        ],
        "fixes": {
            "Accurate Disposition": "Strictly follow agent disposition if scenario is Rejected/Busy/Callback/Already Applied.",
            "Greeting Score": "Pass if agent introduced ICICI brand and self; be lenient on minor opening variations.",
            "Closing Summary Score": "If call disconnected by customer or technical error, mark as NA/Met.",
            "Hold Transfer Silence Score": "Markdown ONLY if dead air exceeds 10 seconds without informing customer."
        }
    },
    "Insta(NCA)": {
        "params": [
            "Greeting Score", "Self Brand Score", "Call Purpose Score", "Grammar Score", 
            "Hold Transfer Silence Score", "Active Listen Score", "Engagement Tone Score", 
            "Product Benefits Score", "Urgency/Objections Rebuttal Score", "Login Offer Details Score", 
            "Customer Basic Information Score", "Link SMS Email Score", "Activate Auto Debit Score", 
            "Referral Code Score", "OTP Verification Consent Score", 
            "Success VOC Card Confirmation Reasons", "Closing Summary Score",
            "Accurate Disposition", "Junk Lead", "Complete Information Provided", 
            "Professional Behavior", "No Disconnection Avoid"
        ],
        "fixes": {
            "Greeting Score": "Pass if greeting intent is clear; introduce ICICI brand.",
            "Active Listen Score": "Be lenient on backchannels ('Hmm', 'Ok') and overlap speech.",
            "Accurate Disposition": "Ensure sub-disposition matches the conversation outcome (Junk, Lead, Rejected)."
        }
    },
    "CC/DC Upgrade": {
        "params": [
            'Greeting Met', 'Benefits Explained Met', 'Charges Explained Met',
            'Pitch Modulation', 'Pitch Pace', 'Tone Appropriate Met',
            'Consent Taken Met', 'Card Variant Met'
        ],
        "fixes": {
            'Consent Taken Met': '3-Tier Hindi consent (Tier1: explicit, Tier2: contextual, Tier3: refusal only).',
            'Charges Explained Met': 'Content-based (₹699+GST); pace irrelevant.',
            'Card Variant Met': 'Fuzzy match card variants (e.g., "Coral card" -> Coral Debit Card).'
        }
    }
}

# ─── Helper Functions ────────────────────────────────────────────────────────
def detect_process(df):
    cols = " ".join(df.columns.astype(str))
    if "Amazon" in cols or "VKYC" in cols:
        return "Amazon(NCA)"
    if "Insta" in cols or "VOC" in cols:
        return "Insta(NCA)"
    return "CC/DC Upgrade"

def preprocess_df(df):
    ai_col  = next((c for c in df.columns if 'AI' in str(c) and ('Status' in str(c) or 'Disposition' in str(c))), None)
    ver_col = next((c for c in df.columns if ('Verifier' in str(c) or 'Finmech' in str(c)) and ('Status' in str(c) or 'Disposition' in str(c))), None)
    
    if not ai_col or not ver_col:
        # Fallback for simpler sheets
        ai_col = df.columns[0]
        ver_col = df.columns[1]
        
    df['ai_norm']  = df[ai_col].astype(str).str.strip().str.lower()
    df['ver_norm'] = df[ver_col].astype(str).str.strip().str.lower()
    
    # Normalize 'rework' and 'approved' / 'yes' and 'no'
    def normalize_val(v):
        v = str(v).lower()
        if 'rework' in v or 'no' in v or 'incorrect' in v: return 'rework'
        if 'approve' in v or 'yes' in v or 'correct' in v: return 'approved'
        return v
        
    df['ai_norm'] = df['ai_norm'].apply(normalize_val)
    df['ver_norm'] = df['ver_norm'].apply(normalize_val)
    
    return df, ai_col, ver_col

def analyze_root_causes(df, process_name):
    config = PROCESS_CONFIGS.get(process_name, PROCESS_CONFIGS["CC/DC Upgrade"])
    params = config["params"]
    
    total  = len(df)
    agree  = int((df['ai_norm'] == df['ver_norm']).sum())
    fr     = df[(df['ai_norm'] == 'rework')   & (df['ver_norm'] == 'approved')]
    fa     = df[(df['ai_norm'] == 'approved') & (df['ver_norm'] == 'rework')]
    fr_len = max(len(fr), 1)

    param_failures = {}
    for p in params:
        col = next((c for c in df.columns if p in str(c)), None)
        if not col: continue
        
        # Count where AI said 'No' (or equivalent) but Verifier said 'Yes' (or equivalent)
        # In variance sheets, this is usually where Gap is negative or Variance is high
        fails = int((fr[col].astype(str).str.strip().str.lower().isin(['no', '0', 'incorrect'])).sum())
        param_failures[p] = {'count': fails, 'pct': round(fails / fr_len * 100, 1)}

    rw_col  = next((c for c in df.columns if 'Reason' in str(c) or 'Finding' in str(c)), None)
    fa_reasons = list(fa[rw_col].dropna().astype(str).values) if rw_col else []
    
    ai_app  = int((df['ai_norm']  == 'approved').sum())
    ver_app = int((df['ver_norm'] == 'approved').sum())

    return {
        'summary': {
            'total_cases': total,
            'agreement_rate': round(agree / total * 100, 1),
            'ai_approval_rate': round(ai_app / total * 100, 1),
            'verifier_approval_rate': round(ver_app / total * 100, 1),
            'false_rework_count': len(fr),
            'false_approve_count': len(fa),
            'gap': round((ver_app - ai_app) / total * 100, 1),
            'process': process_name
        },
        'false_rework': {
            'param_failures': param_failures,
            'patterns': {} # Could add more complex regex patterns here later
        },
        'false_approve': {'reasons': fa_reasons}
    }

def generate_prompt_deltas(analysis, process_name):
    config = PROCESS_CONFIGS.get(process_name, PROCESS_CONFIGS["CC/DC Upgrade"])
    pf = analysis['false_rework']['param_failures']
    fixes = config["fixes"]
    
    deltas = []
    for param, info in sorted(pf.items(), key=lambda x: x[1]['pct'], reverse=True):
        if info['pct'] < 1: continue # Lower threshold to capture more details
        severity = 'CRITICAL' if info['pct'] > 40 else ('HIGH' if info['pct'] > 15 else 'MEDIUM')
        
        rc = f"AI too strict on {param} (marks as NO when verifier says YES)"
        fix = fixes.get(param, f"Align {param} with verifier judgment standards.")
        
        deltas.append({'param': param, **info, 'severity': severity, 'rootCause': rc, 'fix': fix})
    return deltas

def call_vertex_api(prompt_text):
    try:
        resp = requests.post(VERTEX_GENERATE_URL,
                             json={'prompt': prompt_text, 'model': DEFAULT_MODEL},
                             timeout=55)
        resp.raise_for_status()
        d    = resp.json()
        text = (d.get('text') or d.get('response') or d.get('content') or
                d.get('generated_text') or d.get('result') or d.get('output') or
                (d.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')) or
                (d.get('candidates', [{}])[0].get('output')) or
                (d.get('candidates', [{}])[0].get('text')))
        if isinstance(text, dict): text = json.dumps(text)
        return text
    except Exception as e:
        print(f"Vertex API Error: {e}")
        return None

def evolve_prompt_vertex(analysis, deltas, current_prompt):
    s    = analysis['summary']
    process = s['process']
    
    meta = f"""You are an expert prompt engineer for Pragyaa.AI compliance auditing.
PROCESS: {process}

ANALYSIS ({s['total_cases']} audits):
- AI Approval: {s['ai_approval_rate']}%  |  Verifier Approval: {s['verifier_approval_rate']}%
- Agreement Rate: {s['agreement_rate']}%  |  False Reworks (AI too strict): {s['false_rework_count']}

TOP FAILURE CAUSES (AI vs Verifier Variance):
{chr(10).join(f"  [{d['severity']}] {d['param']}: {d['pct']}% failure | {d['rootCause']} → FIX: {d['fix']}" for d in deltas)}

CURRENT PROMPT SNIPPET:
{current_prompt[:1500] if current_prompt else '(none provided)'}

TASK: Update the compliance audit prompt to reduce variance.
Key Objectives for {process}:
1. Reduce False Reworks by implementing the FIXES listed above.
2. Ensure Accurate Disposition mapping (handle Rejected, Busy, Callback correctly).
3. Be lenient on Greeting and tone if brand intent is clear.
4. Handle call disconnects and technical errors gracefully (Mark as NA/Met).

Output ONLY the improved prompt text. No preamble, no explanations."""
    
    return call_vertex_api(meta)

# ─── Route ────────────────────────────────────────────────────────────────────
@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True)
        b64  = data.get('file_content')
        if not b64:
            return jsonify({'error': 'No file content provided'}), 400

        df = pd.read_excel(io.BytesIO(base64.b64decode(b64)), sheet_name=0)
        
        process_name = detect_process(df)
        df, ai_col, ver_col = preprocess_df(df)

        analysis = analyze_root_causes(df, process_name)
        deltas   = generate_prompt_deltas(analysis, process_name)
        
        optimized_prompt = None
        vertex_status    = 'Not requested'
        if data.get('generate_prompt'):
            optimized_prompt = evolve_prompt_vertex(analysis, deltas, data.get('current_prompt', ''))
            vertex_status    = 'success' if optimized_prompt else 'Error calling Vertex API'

        return jsonify({
            'status': 'success',
            'analysis': {
                'summary': analysis['summary'],
                'paramFailures': analysis['false_rework']['param_failures'],
                'faReasons': analysis['false_approve']['reasons'],
            },
            'deltas': deltas,
            'vertex_status': vertex_status,
            'optimized_prompt': optimized_prompt,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5002)
