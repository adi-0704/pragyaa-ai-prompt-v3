"""
Pragyaa.AI — Serverless Backend v1.0.9-routing-fix
Self-contained: No imports from root scripts.
Designed for Vercel Python Serverless Functions.
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

# ─── Data Helpers ──────────────────────────────────────────────────────────────
def preprocess_df(df):
    """Find and normalize the AI/Verifier status columns."""
    ai_col = next((c for c in df.columns if 'Call Status AI' in str(c)), None)
    ver_col = next((c for c in df.columns if 'Call Status Verifier' in str(c)), None)
    if not ai_col or not ver_col:
        raise ValueError(f"Missing status columns. Found columns: {list(df.columns)[:10]}")
    df['ai_norm'] = df[ai_col].astype(str).str.strip().str.lower()
    df['ver_norm'] = df[ver_col].astype(str).str.strip().str.lower()
    df['is_match'] = df['ai_norm'] == df['ver_norm']
    return df, ai_col, ver_col

def analyze_root_causes(df, ai_col, ver_col):
    """Full discrepancy analysis — same logic as frontend JS but authoritative."""
    norm = lambda v: str(v or '').strip().lower()
    total = len(df)
    agree = int((df['ai_norm'] == df['ver_norm']).sum())

    false_rework = df[(df['ai_norm'] == 'rework') & (df['ver_norm'] == 'approved')]
    false_approve = df[(df['ai_norm'] == 'approved') & (df['ver_norm'] == 'rework')]

    params = [
        'Greeting Met', 'Benefits Explained Met', 'Charges Explained Met',
        'Pitch Modulation', 'Pitch Pace', 'Tone Appropriate Met',
        'Consent Taken Met', 'Card Variant Met'
    ]
    param_failures = {}
    fr_len = max(len(false_rework), 1)
    for p in params:
        col = next((c for c in df.columns if p in str(c)), None)
        if not col:
            continue
        fails = int((false_rework[col].astype(str).str.strip().str.lower() == 'no').sum())
        param_failures[p] = {'count': fails, 'pct': round(fails / fr_len * 100, 1)}

    # Consent patterns
    consent_col = next((c for c in df.columns if 'Consent Taken Reasons' in str(c)), None)
    consent_met_col = next((c for c in df.columns if 'Consent Taken Met' in str(c)), None)
    consent_fails = false_rework[false_rework[consent_met_col].astype(str).str.strip().str.lower() == 'no'] if consent_met_col else pd.DataFrame()
    consent_patterns = {'Passive Okay/Haan': 0, 'No Explicit Ask': 0, 'Ji/Hmm Backchannel': 0, 'Premature/Rushed': 0}
    if consent_col and not consent_fails.empty:
        for _, row in consent_fails.iterrows():
            r = norm(row.get(consent_col, ''))
            if any(k in r for k in ['passive', 'okay', 'haan', 'acknowledgm']): consent_patterns['Passive Okay/Haan'] += 1
            if any(k in r for k in ['not explicitly', 'did not', 'without']): consent_patterns['No Explicit Ask'] += 1
            if any(k in r for k in ['ji', 'hmm', 'backchannel']): consent_patterns['Ji/Hmm Backchannel'] += 1
            if any(k in r for k in ['rushed', 'before']): consent_patterns['Premature/Rushed'] += 1

    # Charges patterns
    charges_col = next((c for c in df.columns if 'Charges Explained Reasons' in str(c)), None)
    charges_met_col = next((c for c in df.columns if 'Charges Explained Met' in str(c)), None)
    charges_fails = false_rework[false_rework[charges_met_col].astype(str).str.strip().str.lower() == 'no'] if charges_met_col else pd.DataFrame()
    charges_patterns = {'Rushed Delivery': 0, 'Confusing/Unclear': 0, 'Missing GST': 0, 'Wrong Amounts': 0}
    if charges_col and not charges_fails.empty:
        for _, row in charges_fails.iterrows():
            r = norm(row.get(charges_col, ''))
            if any(k in r for k in ['rushed', 'fast', 'quickly']): charges_patterns['Rushed Delivery'] += 1
            if any(k in r for k in ['confus', 'unclear', 'not clear']): charges_patterns['Confusing/Unclear'] += 1
            if 'gst' in r: charges_patterns['Missing GST'] += 1
            if any(k in r for k in ['incorrect', 'wrong']): charges_patterns['Wrong Amounts'] += 1

    rework_reason_col = next((c for c in df.columns if 'Reason for Rework' in str(c)), None)
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
            'gap': round((ver_approved - ai_approved) / total * 100, 1)
        },
        'false_rework': {
            'param_failures': param_failures,
            'patterns': {'consent': consent_patterns, 'charges': charges_patterns}
        },
        'false_approve': {'reasons': fa_reasons}
    }

def generate_prompt_deltas(analysis):
    """Build structured fix recommendations from the analysis."""
    pf = analysis['false_rework']['param_failures']
    sorted_params = sorted(pf.items(), key=lambda x: x[1]['pct'], reverse=True)
    deltas = []
    for param, info in sorted_params:
        if info['pct'] < 5:
            continue
        severity = 'CRITICAL' if info['pct'] > 50 else ('HIGH' if info['pct'] > 20 else 'MEDIUM')
        root_cause, fix = '', ''
        if param == 'Consent Taken Met':
            root_cause = 'AI rejects passive Hindi consent ("Okay", "Haan ji", "Theek hai")'
            fix = 'Implement 3-Tier consent: Tier1 explicit, Tier2 contextual (valid after full pitch), Tier3 refusal only'
        elif param == 'Charges Explained Met':
            root_cause = 'AI penalizes delivery speed instead of factual accuracy'
            fix = 'Switch to content-based evaluation — pass if ₹699+GST stated correctly regardless of pace'
        elif param == 'Pitch Pace':
            root_cause = 'AI pace threshold stricter than human verifier tolerance'
            fix = 'Only fail if customer explicitly asks to repeat or slow down'
        elif param == 'Benefits Explained Met':
            root_cause = 'AI requires too many benefits to be mentioned'
            fix = 'Pass if agent mentions ≥2 core benefits accurately'
        elif param == 'Card Variant Met':
            root_cause = 'AI fails on informal card name variations'
            fix = 'Add fuzzy mapping: "Coral card"/"Updated Coral" → Coral Debit Card'
        else:
            root_cause = f'AI too strict on {param}'
            fix = f'Align {param} threshold with human verifier standards'
        deltas.append({'param': param, **info, 'severity': severity, 'rootCause': root_cause, 'fix': fix})
    return deltas

def compare_prompt_with_data(current_prompt, deltas):
    """Check which deltas are already addressed in the current prompt."""
    prompt_lower = current_prompt.lower()
    covered, gaps = [], []
    for d in deltas:
        keywords = d['param'].lower().split()
        if any(k in prompt_lower for k in keywords):
            covered.append(d['param'])
        else:
            gaps.append(d['param'])
    return {'covered': covered, 'gaps': gaps, 'coverage_pct': round(len(covered) / max(len(deltas), 1) * 100, 1)}

def call_vertex_api(prompt_text, model=DEFAULT_MODEL):
    """Call internal company Vertex AI API and robustly extract text."""
    payload = {'prompt': prompt_text, 'model': model}
    resp = requests.post(VERTEX_GENERATE_URL, json=payload, timeout=55)
    resp.raise_for_status()
    data = resp.json()
    # Try every known field shape the internal API might return
    text = (
        data.get('text') or
        data.get('response') or
        data.get('content') or
        data.get('generated_text') or
        data.get('result') or
        data.get('output') or
        (data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')) or
        (data.get('candidates', [{}])[0].get('output')) or
        (data.get('candidates', [{}])[0].get('text'))
    )
    if isinstance(text, dict):
        text = json.dumps(text)
    return text

def evolve_prompt_vertex(analysis, deltas, current_prompt):
    """Generate an optimized audit prompt via the internal Vertex AI API."""
    s = analysis['summary']
    meta_prompt = f"""You are an expert prompt engineer specializing in compliance audit automation for ICICI Bank Debit Card upgrade calls.

ANALYSIS SUMMARY:
- Total audits analyzed: {s['total_cases']}
- AI Approval Rate: {s['ai_approval_rate']}%
- Human Verifier Approval Rate: {s['verifier_approval_rate']}%
- Agreement Rate: {s['agreement_rate']}%
- False Rework Cases (AI too strict): {s['false_rework_count']}

TOP DISCREPANCY CAUSES:
{chr(10).join(f"- [{d['severity']}] {d['param']}: {d['pct']}% failure rate | Root Cause: {d['rootCause']} | Fix: {d['fix']}" for d in deltas)}

CONSENT PATTERNS: {json.dumps(analysis['false_rework']['patterns']['consent'], ensure_ascii=False)}
CHARGES PATTERNS: {json.dumps(analysis['false_rework']['patterns']['charges'], ensure_ascii=False)}

CURRENT PROMPT (to be improved):
{current_prompt[:2000] if current_prompt else "(none provided)"}

TASK: Generate an optimized, production-ready compliance audit prompt that:
1. Implements 3-Tier Hindi consent validation (Tier1: explicit "haan", Tier2: contextual after full pitch, Tier3: refusal only)
2. Uses content-based charges evaluation (pass if ₹699+GST stated correctly regardless of pace)
3. Uses fuzzy card variant matching for "Coral card", "Updated Coral", "Coral Visa"
4. Only fails Pitch Pace if customer explicitly asks for clarification
5. Aligns ALL thresholds with human verifier standards from the data above

Output ONLY the final audit prompt text. No explanations, no preamble."""

    return call_vertex_api(meta_prompt)

# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.9-routing-fix'})

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
        df, ai_col, ver_col = preprocess_df(df)

        # Full analysis
        analysis = analyze_root_causes(df, ai_col, ver_col)
        deltas = generate_prompt_deltas(analysis)
        coverage = compare_prompt_with_data(current_prompt, deltas)

        # Prompt evolution
        optimized_prompt = None
        vertex_status = 'Not requested'

        if generate_prompt_flag:
            try:
                vertex_status = 'Calling Internal API...'
                optimized_prompt = evolve_prompt_vertex(analysis, deltas, current_prompt)
                vertex_status = 'Success' if optimized_prompt else 'Empty response from API'
            except Exception as ai_err:
                vertex_status = f'API Error: {str(ai_err)}'

        # Shape response for frontend camelCase expectations
        formatted_analysis = {
            'summary': {
                'total': analysis['summary']['total_cases'],
                'agreementRate': analysis['summary']['agreement_rate'],
                'aiApprovalRate': analysis['summary']['ai_approval_rate'],
                'verApprovalRate': analysis['summary']['verifier_approval_rate'],
                'falseReworkCount': analysis['summary']['false_rework_count'],
                'falseApproveCount': analysis['summary']['false_approve_count'],
                'gap': analysis['summary']['gap']
            },
            'paramFailures': analysis['false_rework']['param_failures'],
            'consentPatterns': analysis['false_rework']['patterns']['consent'],
            'chargesPatterns': analysis['false_rework']['patterns']['charges'],
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

# Vercel calls this module and expects the `app` object directly.
# The if-block below is only for local development.
if __name__ == '__main__':
    app.run(debug=True, port=5000)
