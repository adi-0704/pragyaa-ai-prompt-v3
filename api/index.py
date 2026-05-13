"""
Pragyaa.AI — Serverless Backend v1.1.0 (Multi-Process Support)
Supports Amazon(NCA), Insta(NCA), and CC/DC Upgrade processes.
"""

from flask import Flask, request, jsonify
import pandas as pd
import os
import json
import io
import base64
import requests

app = Flask(__name__)

# ─── CORS ─────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/analyze', methods=['OPTIONS'])
@app.route('/api/vertex', methods=['OPTIONS'])
@app.route('/api/health', methods=['OPTIONS'])
def options_handler():
    return jsonify({}), 200

# ─── Internal Company AI API ───────────────────────────────────────────────────
VERTEX_GENERATE_URL = "https://voicelensG1.pragyaa.ai/vertex/generate"
VERTEX_TRANSCRIPT_URL = "https://voicelensG1.pragyaa.ai/vertex/transcribe"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

# ─── Process Configs ──────────────────────────────────────────────────────────
PROCESS_CONFIGS = {
    "Amazon(NCA)": {
        "params": [
            "Greeting Score", "Self Brand Score", "Call Purpose Score", "Grammar Score", 
            "Hold Transfer Silence Score", "Active Listen Score", "Engagement Tone Score", 
            "Product Benefits Score", "Urgency/Objections Rebuttal  Score", "Fees Charges Score", 
            "First Txn Amazon Score", "Appointment Score", "Referral Code Score", 
            "Track Application", "VKYC Biometric Score", "Subject to Approval Score", 
            "Closing Summary Score", "Accurate Disposition", "Junk Lead", 
            "Complete Information Provided", "Professional Behaviour", "No Disconnection Avoid"
        ],
        "fixes": {
            "Accurate Disposition": "Ensure disposition accurately reflects LEAD vs REJECTED based on final transcript sentiment.",
            "Greeting Score": "Be stricter on Right Party Verification (RPV) — only pass if customer identity is confirmed.",
            "Call Purpose Score": "AI is over-approving. Strictly mark as NO if the agent misses the 'Pre-approved Credit Card' context or interest check.",
            "Referral Code Score": "AI is currently missing mentions. Detect SOL ID (0000) and AIR code mentions even in fast speech.",
            "Grammar Score": "Stricter markdown for sentence construction and pronunciation errors of 'ICICI Bank'.",
            "Fees Charges Score": "Ensure ₹499/₹199 + GST is explicitly mentioned; AI is currently under-reporting.",
            "Closing Summary Score": "Increase detection of professional closing phrases and summary points."
        }
    },
    "Insta(NCA)": {
        "params": [
            "Greeting Score", "Self Brand Score", "Call Purpose Score", "Grammar Score", 
            "Hold Transfer Silence Score", "Active Listen Ack Score", "Engagement Tone Score", 
            "Product Benefits Score", "Urgency Score", "Login Offer Details Score", 
            "Customer Basic Information Score", "Link SMS Email Score", "Activate Auto Debit Score", 
            "Referral Code Score", "OTP Verification Consent Score", 
            "Success VOC Card Confirmation Score", "Closing Summary Score",
            "Accurate Disposition", "Junk Lead", "Complete Information Provided", 
            "Professional Behavior", "No Disconnection Avoid"
        ],
        "fixes": {
            "Greeting Score": "Verify Right Party Verification (RPV) is strictly met before passing.",
            "Call Purpose Score": "Stricter check for 'Pre-approved' and 'Interest' pitch context.",
            "Accurate Disposition": "Fix sub-disposition tagging (NOT_INTERESTED vs NOT_ELIGIBLE). Ensure LEAD is only tagged for successful generation.",
            "Grammar Score": "Markdown for significant grammatical errors or mispronunciations.",
            "Success VOC Card Confirmation Score": "Be more sensitive to card name and color confirmation mentions."
        }
    },
    "CC/DC Upgrade": {
        "params": [
            'Greeting Met', 'Benefits Explained Met', 'Charges Explained Met',
            'Pitch Modulation', 'Pitch Pace', 'Tone Appropriate Met',
            'Consent Taken Met', 'Card Variant Met'
        ],
        "fixes": {
            'Consent Taken Met': 'Implement 3-Tier Hindi consent: Tier1 (explicit), Tier2 (contextual), Tier3 (refusal only).',
            'Charges Explained Met': 'Switch to content-based evaluation (pass if ₹699+GST stated correctly regardless of pace).',
            'Card Variant Met': 'Add fuzzy mapping: "Coral card"/"Updated Coral" → Coral Debit Card.'
        }
    }
}

# ─── Data Helpers ──────────────────────────────────────────────────────────────
def detect_process(df):
    cols = " ".join(df.columns.astype(str))
    if "Amazon" in cols or "VKYC" in cols or "Biometric" in cols:
        return "Amazon(NCA)"
    if "Insta" in cols or "VOC" in cols:
        return "Insta(NCA)"
    return "CC/DC Upgrade"

def preprocess_df(df):
    """Find and normalize the AI/Verifier status columns."""
    ai_col  = next((c for c in df.columns if 'AI' in str(c) and ('Status' in str(c) or 'Disposition' in str(c))), None)
    ver_col = next((c for c in df.columns if ('Verifier' in str(c) or 'Finmech' in str(c)) and ('Status' in str(c) or 'Disposition' in str(c))), None)
    
    if not ai_col or not ver_col:
        # Fallback if specific headers are missing
        ai_col = next((c for c in df.columns if 'Call Status AI' in str(c)), df.columns[0])
        ver_col = next((c for c in df.columns if 'Call Status Verifier' in str(c)), df.columns[1])
        
    df['ai_norm'] = df[ai_col].astype(str).str.strip().str.lower()
    df['ver_norm'] = df[ver_col].astype(str).str.strip().str.lower()
    
    def normalize_val(v):
        v = str(v).lower()
        if any(k in v for k in ['rework', 'no', 'incorrect', 'false', '0']): return 'rework'
        if any(k in v for k in ['approve', 'yes', 'correct', 'true', '1']): return 'approved'
        return v
        
    df['ai_norm'] = df['ai_norm'].apply(normalize_val)
    df['ver_norm'] = df['ver_norm'].apply(normalize_val)
    df['is_match'] = df['ai_norm'] == df['ver_norm']
    return df, ai_col, ver_col

def analyze_root_causes(df, ai_col, ver_col, process_name):
    """Full discrepancy analysis with process-specific parameters."""
    total = len(df)
    agree = int((df['ai_norm'] == df['ver_norm']).sum())

    false_rework = df[(df['ai_norm'] == 'rework') & (df['ver_norm'] == 'approved')]
    false_approve = df[(df['ai_norm'] == 'approved') & (df['ver_norm'] == 'rework')]

    config = PROCESS_CONFIGS.get(process_name, PROCESS_CONFIGS["CC/DC Upgrade"])
    params = config["params"]
    
    param_failures = {}
    fr_len = max(len(false_rework), 1)
    for p in params:
        col = next((c for c in df.columns if p in str(c)), None)
        if not col:
            continue
        # Count where AI said 'No/Rework' but verifier said 'Yes/Approved'
        fails = int((false_rework[col].astype(str).str.strip().str.lower().isin(['no', '0', 'incorrect', 'rework'])).sum())
        param_failures[p] = {'count': fails, 'pct': round(fails / fr_len * 100, 1)}

    rework_reason_col = next((c for c in df.columns if 'Reason' in str(c) or 'Finding' in str(c)), None)
    fa_reasons = list(false_approve[rework_reason_col].dropna().astype(str).values) if rework_reason_col else []

    ai_approved = int((df['ai_norm'] == 'approved').sum())
    ver_approved = int((df['ver_norm'] == 'approved').sum())

    return {
        'summary': {
            'total_cases': total,
            'agreement_rate': round(agree / total * 100, 1),
            'ai_approval_rate': round(ai_approved / total * 100, 1),
            'verifier_approval_rate': round(ver_approved / total * 100, 1),
            'false_rework_count': len(false_rework),
            'false_approve_count': len(false_approve),
            'gap': round((ver_approved - ai_approved) / total * 100, 1),
            'process': process_name
        },
        'false_rework': {
            'param_failures': param_failures,
            'patterns': {} # Pattern extraction can be expanded here
        },
        'false_approve': {'reasons': fa_reasons}
    }

def generate_prompt_deltas(analysis, process_name):
    """Build structured fix recommendations based on process config."""
    pf = analysis['false_rework']['param_failures']
    sorted_params = sorted(pf.items(), key=lambda x: x[1]['pct'], reverse=True)
    
    config = PROCESS_CONFIGS.get(process_name, PROCESS_CONFIGS["CC/DC Upgrade"])
    fixes = config["fixes"]
    
    deltas = []
    for param, info in sorted_params:
        if info['pct'] < 1: # Lower threshold to capture minor variances
            continue
        severity = 'CRITICAL' if info['pct'] > 40 else ('HIGH' if info['pct'] > 15 else 'MEDIUM')
        
        root_cause = f"AI too strict on {param} (incorrect markdown vs verifier)"
        fix = fixes.get(param, f"Align {param} threshold with human verifier judgment standards.")
        
        deltas.append({'param': param, **info, 'severity': severity, 'rootCause': root_cause, 'fix': fix})
    return deltas

def compare_prompt_with_data(current_prompt, deltas):
    """Check which deltas are already addressed in the current prompt."""
    prompt_lower = (current_prompt or '').lower()
    covered, gaps = [], []
    for d in deltas:
        keywords = d['param'].lower().split()
        if any(k in prompt_lower for k in keywords):
            covered.append(d['param'])
        else:
            gaps.append(d['param'])
    return {'covered': covered, 'gaps': gaps, 'coverage_pct': round(len(covered) / max(len(deltas), 1) * 100, 1)}

def call_vertex_api(prompt_text, model=DEFAULT_MODEL):
    """Call internal company Vertex AI API."""
    payload = {'prompt': prompt_text, 'model': model}
    resp = requests.post(VERTEX_GENERATE_URL, json=payload, timeout=55)
    resp.raise_for_status()
    data = resp.json()
    text = (
        data.get('text') or data.get('response') or data.get('content') or
        data.get('generated_text') or data.get('result') or data.get('output') or
        (data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')) or
        (data.get('candidates', [{}])[0].get('output')) or
        (data.get('candidates', [{}])[0].get('text'))
    )
    if isinstance(text, dict): text = json.dumps(text)
    return text

def evolve_prompt_vertex(analysis, deltas, current_prompt):
    """Generate an optimized audit prompt via Vertex AI."""
    s = analysis['summary']
    process = s['process']
    
    meta_prompt = f"""You are an expert prompt engineer specializing in compliance audit automation for Pragyaa.AI.
PROCESS TYPE: {process}

ANALYSIS SUMMARY:
- Total audits analyzed: {s['total_cases']}
- AI Approval Rate: {s['ai_approval_rate']}%
- Verifier Approval Rate: {s['verifier_approval_rate']}%
- Agreement Rate: {s['agreement_rate']}%
- False Rework Cases (AI too strict): {s['false_rework_count']}

TOP VARIANCE FINDINGS (AI vs Verifier):
{chr(10).join(f"- [{d['severity']}] {d['param']}: {d['pct']}% failure | Root Cause: {d['rootCause']} | FIX: {d['fix']}" for d in deltas)}

CURRENT PROMPT:
{current_prompt[:1500] if current_prompt else "(none provided)"}

TASK: Generate an improved audit prompt for {process} that:
1. Implements the FIXES listed above to align with human verifier judgment.
2. Corrects 'Accurate Disposition' logic for edge cases (Rejected, Busy, Callback, Pin code, etc.).
3. Adopts a more lenient/intent-based evaluation for Greeting and Tone.
4. Correctly handles 'NA' scenarios for Closing Summary (e.g., customer disconnects).
5. Ensures all critical compliance pillars are maintained while reducing false rework.

Output ONLY the final optimized audit prompt. No preamble, no explanations."""

    return call_vertex_api(meta_prompt)

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.1.0', 'engine': 'Vertex AI'})

@app.route('/api/analyze', methods=['POST'])
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True)
        file_content_b64 = data.get('file_content')
        current_prompt = data.get('current_prompt', '')
        generate_prompt_flag = data.get('generate_prompt', False)

        if not file_content_b64:
            return jsonify({'error': 'No file content provided'}), 400

        # Decode and parse Excel
        file_bytes = base64.b64decode(file_content_b64)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        process_name = detect_process(df)
        df, ai_col, ver_col = preprocess_df(df)

        # Full analysis
        analysis = analyze_root_causes(df, ai_col, ver_col, process_name)
        deltas = generate_prompt_deltas(analysis, process_name)
        coverage = compare_prompt_with_data(current_prompt, deltas)

        # Prompt evolution
        optimized_prompt = None
        vertex_status = 'Not requested'

        if generate_prompt_flag:
            try:
                optimized_prompt = evolve_prompt_vertex(analysis, deltas, current_prompt)
                vertex_status = 'Success' if optimized_prompt else 'Empty response from AI'
            except Exception as ai_err:
                vertex_status = f'AI Error: {str(ai_err)}'

        # Shape response for frontend
        formatted_analysis = {
            'summary': analysis['summary'],
            'paramFailures': analysis['false_rework']['param_failures'],
            'consentPatterns': {}, # Reserved for future expansion
            'chargesPatterns': {},
            'faReasons': analysis['false_approve']['reasons']
        }

        return jsonify({
            'status': 'success',
            'analysis': formatted_analysis,
            'deltas': deltas,
            'coverage': coverage,
            'vertex_status': vertex_status,
            'optimized_prompt': optimized_prompt
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/vertex', methods=['POST'])
@app.route('/vertex', methods=['POST'])
def vertex_proxy():
    try:
        data = request.get_json(force=True)
        is_transcript = 'audio' in data
        url = VERTEX_TRANSCRIPT_URL if is_transcript else VERTEX_GENERATE_URL
        response = requests.post(url, json=data, timeout=55)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
