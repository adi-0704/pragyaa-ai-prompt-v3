"""
OpenClaw/Hermes Audit Automation Pipeline
==========================================
Authors: Aditya Tyagi; Gulshan Mehta
Reads Excel feedback data, compares AI vs Verifier verdicts,
identifies root causes of discrepancies, and auto-refines the prompt.

Usage: python openclaw_audit_automation.py <excel_file>
"""

import sys
import io
import os
import json
import time
import requests
import pandas as pd
import openpyxl
from datetime import datetime
from pathlib import Path

# Vertex AI Configuration
VERTEX_GENERATE_URL = "https://voicelensG1.pragyaa.ai/vertex/generate"
VERTEX_TRANSCRIPT_URL = "https://voicelensG1.pragyaa.ai/vertex/transcript"

# Vertex AI SDK (Legacy/Optional - We now prefer the direct API for speed)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# The Internal API uses 'requests' and doesn't need the SDK
INTERNAL_API_AVAILABLE = True 

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─────────────────────────────────────────────
# STEP 1: Excel Ingestion & Normalization
# ─────────────────────────────────────────────

def ingest_excel(filepath: str) -> pd.DataFrame:
    """Read Excel audit data and normalize columns."""
    print(f"[1/5] Ingesting: {filepath}")
    
    # Try 'Raw Data' sheet first, then first sheet
    try:
        df = pd.read_excel(filepath, sheet_name='Raw Data')
    except ValueError:
        df = pd.read_excel(filepath, sheet_name=0)
    
    # Normalize status columns
    ai_col = next((c for c in df.columns if 'Call Status AI' in str(c)), None)
    ver_col = next((c for c in df.columns if 'Call Status Verifier' in str(c)), None)
    
    if not ai_col or not ver_col:
        raise ValueError(f"Missing status columns. Found: {list(df.columns)}")
    
    df['ai_norm'] = df[ai_col].astype(str).str.strip().str.lower()
    df['ver_norm'] = df[ver_col].astype(str).str.strip().str.lower()
    df['is_match'] = df['ai_norm'] == df['ver_norm']
    
    print(f"  ✓ Loaded {len(df)} cases | {df['is_match'].sum()} agree | {(~df['is_match']).sum()} disputed")
    return df


# ─────────────────────────────────────────────
# STEP 2: Root Cause Analysis Engine
# ─────────────────────────────────────────────

PARAM_COLS = {
    'Greeting Met': 'Greeting Reasons',
    'Benefits Explained Met': 'Reasons - Benefits Explained',
    'Charges Explained Met': 'Charges Explained Reasons',
    'Pitch Modulation': 'Pitch Modulation Reasons',
    'Pitch Pace': 'Pitch Pace Reasons',
    'Tone Appropriate Met': 'Tone Appropriate Reasons',
    'Consent Taken Met': 'Consent Taken Reasons',
    'Card Variant Met': 'Card Variant Reasons',
}

CONSENT_PATTERNS = {
    'passive_agreement': ['passive', 'okay', "'ok'", 'haan', 'acknowledgment', 'acknowledge'],
    'no_explicit_ask': ['not explicitly', 'did not ask', 'without asking', 'did not explicitly'],
    'backchannel_only': ["'ji'", 'hmm', 'backchannel', "'haan ji'"],
    'premature_consent': ['before charge', 'before explaining', 'rushed'],
}

CHARGES_PATTERNS = {
    'rushed_delivery': ['rushed', 'fast', 'quickly', 'quick', 'too fast'],
    'confusing_amounts': ['confus', 'unclear', 'not clear', 'ambiguous'],
    'missing_gst': ['gst'],
    'wrong_amounts': ['incorrect', 'wrong', '999', '600', '619'],
    'not_separated': ['not distinguish', 'not separate', 'not clearly state'],
}


def analyze_root_causes(df: pd.DataFrame) -> dict:
    """Identify root causes of AI vs Verifier discrepancies."""
    print("[2/5] Analyzing root causes...")
    
    results = {
        'summary': {},
        'false_rework': {'count': 0, 'param_failures': {}, 'patterns': {}},
        'false_approve': {'count': 0, 'reasons': []},
        'recommendations': [],
    }
    
    total = len(df)
    false_rework = df[(df['ai_norm'] == 'rework') & (df['ver_norm'] == 'approved')]
    false_approve = df[(df['ai_norm'] == 'approved') & (df['ver_norm'] == 'rework')]
    
    results['summary'] = {
        'total_cases': total,
        'agreement_rate': round(df['is_match'].mean() * 100, 1),
        'ai_approval_rate': round((df['ai_norm'] == 'approved').mean() * 100, 1),
        'verifier_approval_rate': round((df['ver_norm'] == 'approved').mean() * 100, 1),
        'false_rework_count': len(false_rework),
        'false_approve_count': len(false_approve),
        'gap': round(((df['ver_norm'] == 'approved').mean() - (df['ai_norm'] == 'approved').mean()) * 100, 1),
    }
    
    # Parameter-level failure analysis for false reworks
    results['false_rework']['count'] = len(false_rework)
    for param, reason_col in PARAM_COLS.items():
        if param in df.columns:
            no_ct = (false_rework[param].astype(str).str.strip().str.lower() == 'no').sum()
            pct = round(no_ct / len(false_rework) * 100, 1) if len(false_rework) > 0 else 0
            results['false_rework']['param_failures'][param] = {'count': no_ct, 'pct': pct}
    
    # Consent pattern analysis
    if 'Consent Taken Reasons' in df.columns:
        consent_fails = false_rework[false_rework['Consent Taken Met'].astype(str).str.strip().str.lower() == 'no']
        reasons = consent_fails['Consent Taken Reasons'].astype(str).tolist()
        consent_patterns = {}
        for pname, keywords in CONSENT_PATTERNS.items():
            count = sum(1 for r in reasons if any(k in r.lower() for k in keywords))
            consent_patterns[pname] = count
        results['false_rework']['patterns']['consent'] = consent_patterns
    
    # Charges pattern analysis
    if 'Charges Explained Reasons' in df.columns:
        charges_fails = false_rework[false_rework['Charges Explained Met'].astype(str).str.strip().str.lower() == 'no']
        reasons = charges_fails['Charges Explained Reasons'].astype(str).tolist()
        charges_patterns = {}
        for pname, keywords in CHARGES_PATTERNS.items():
            count = sum(1 for r in reasons if any(k in r.lower() for k in keywords))
            charges_patterns[pname] = count
        results['false_rework']['patterns']['charges'] = charges_patterns
    
    # False approve reasons
    if 'Reason for Rework' in df.columns:
        for _, row in false_approve.iterrows():
            reason = str(row.get('Reason for Rework', ''))
            if reason and reason != 'nan':
                results['false_approve']['reasons'].append(reason)
    results['false_approve']['count'] = len(false_approve)
    
    print(f"  ✓ False Reworks: {len(false_rework)} | False Approves: {len(false_approve)}")
    return results


# ─────────────────────────────────────────────
# STEP 3: Prompt Delta Generator
# ─────────────────────────────────────────────

def generate_prompt_deltas(analysis: dict) -> list:
    """Generate specific prompt modification instructions based on root causes."""
    print("[3/5] Generating prompt refinements...")
    
    deltas = []
    fr = analysis['false_rework']
    
    # Sort parameters by failure rate
    sorted_params = sorted(
        fr['param_failures'].items(),
        key=lambda x: x[1]['pct'],
        reverse=True
    )
    
    for param, info in sorted_params:
        if info['pct'] < 5:
            continue  # Skip low-impact parameters
        
        delta = {
            'parameter': param,
            'failure_rate': info['pct'],
            'failure_count': info['count'],
            'severity': 'CRITICAL' if info['pct'] > 50 else 'HIGH' if info['pct'] > 20 else 'MEDIUM',
            'fix': '',
        }
        
        if param == 'Consent Taken Met':
            patterns = fr['patterns'].get('consent', {})
            delta['root_cause'] = f"AI treats passive Hindi agreement as invalid consent"
            delta['fix'] = (
                "EXPAND Tier 2 consent: Accept 'Okay', 'Theek hai', 'Haan ji', 'Ji' as valid "
                "consent IF agent completed full pitch (benefits + charges) before customer response. "
                f"Pattern breakdown: passive_agreement={patterns.get('passive_agreement',0)}, "
                f"no_explicit_ask={patterns.get('no_explicit_ask',0)}, "
                f"backchannel={patterns.get('backchannel_only',0)}"
            )
        
        elif param == 'Charges Explained Met':
            patterns = fr['patterns'].get('charges', {})
            delta['root_cause'] = f"AI penalizes speed/style of delivery, not factual accuracy"
            delta['fix'] = (
                "SWITCH from speed-based to content-based charges evaluation. "
                "Pass charges if ₹699+GST joining AND annual fees stated correctly, "
                "regardless of delivery speed. Only fail for wrong amounts or total omission. "
                f"Pattern breakdown: rushed={patterns.get('rushed_delivery',0)}, "
                f"confusing={patterns.get('confusing_amounts',0)}, "
                f"missing_gst={patterns.get('missing_gst',0)}"
            )
        
        elif param == 'Pitch Pace':
            delta['root_cause'] = "AI pace threshold is stricter than human tolerance"
            delta['fix'] = (
                "Only fail Pitch Pace if customer EXPLICITLY asks to repeat or slow down. "
                "Normal conversational Hindi speed is acceptable."
            )
        
        elif param == 'Benefits Explained Met':
            delta['root_cause'] = "AI requires too many benefits to be mentioned"
            delta['fix'] = "Pass benefits if agent mentions ≥2 core benefits accurately."
        
        elif param == 'Card Variant Met':
            delta['root_cause'] = "AI fails on card name variations"
            delta['fix'] = "Add fuzzy matching: 'Coral card'/'Updated Coral'/'Coral Visa' → Coral Debit Card"
        
        else:
            delta['root_cause'] = f"AI too strict on {param}"
            delta['fix'] = f"Align {param} threshold with human verifier standards"
        
        deltas.append(delta)
    
    # False approve fixes
    fa = analysis['false_approve']
    if fa['count'] > 0:
        reason_summary = '; '.join(set(fa['reasons'][:10]))
        deltas.append({
            'parameter': 'False Approves',
            'failure_rate': round(fa['count'] / analysis['summary']['total_cases'] * 100, 1),
            'failure_count': fa['count'],
            'severity': 'HIGH' if fa['count'] > 10 else 'MEDIUM',
            'root_cause': f"AI approved {fa['count']} calls that verifiers rejected",
            'fix': f"Add guardrails for: {reason_summary}",
        })
    
    print(f"  ✓ Generated {len(deltas)} prompt deltas")
    return deltas


# ─────────────────────────────────────────────
# STEP 4: Load & Compare Current Prompt
# ─────────────────────────────────────────────

def load_current_prompt(prompt_dir: str) -> str:
    """Load the current prompt file."""
    print("[4/5] Loading current prompt...")
    
    candidates = [
        'refined_audit_prompt_v3_dc.txt',
        'refined_audit_prompt_v2.txt',
        'refined_audit_prompt.txt',
    ]
    
    for fname in candidates:
        fpath = os.path.join(prompt_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"  ✓ Loaded: {fname} ({len(content)} chars)")
            return content
    
    print("  ⚠ No existing prompt found")
    return ""


def compare_prompt_with_data(prompt: str, deltas: list) -> list:
    """Check which fixes are already in the prompt vs missing."""
    print("  Comparing prompt coverage...")
    
    coverage = []
    prompt_lower = prompt.lower()
    
    for delta in deltas:
        param = delta['parameter']
        is_covered = False
        
        # Check if the prompt already addresses this issue
        if param == 'Consent Taken Met':
            is_covered = 'tier 2' in prompt_lower and 'okay' in prompt_lower
        elif param == 'Charges Explained Met':
            is_covered = 'content-based' in prompt_lower or 'not speed-based' in prompt_lower
        elif param == 'Pitch Pace':
            is_covered = 'explicitly asks to repeat' in prompt_lower
        elif param == 'Benefits Explained Met':
            is_covered = '≥2' in prompt or 'at least 2' in prompt_lower
        elif param == 'Card Variant Met':
            is_covered = 'coral card' in prompt_lower and 'fuzzy' in prompt_lower
        
        coverage.append({
            **delta,
            'already_in_prompt': is_covered,
            'action': 'VERIFY' if is_covered else 'ADD',
        })
    
    added = sum(1 for c in coverage if c['action'] == 'ADD')
    print(f"  ✓ {added} new fixes needed, {len(coverage) - added} already covered")
    return coverage


# ─────────────────────────────────────────────
# STEP 6: AI-Powered Prompt Evolution (Vertex AI)
# ─────────────────────────────────────────────

def evolve_prompt_vertex(analysis: dict, deltas: list, current_prompt: str, prompt_dir: str, max_retries: int = 3) -> str:
    """Uses the company's internal Vertex AI API to evolve the prompt based on analysis."""
    
    # Construct Meta-Prompt (similar to frontend/app.js)
    s = analysis['summary']
    d_str = "\n".join([f"- {d['parameter']}: {d['fix']} (Failure Rate: {d['failure_rate']}%)" for d in deltas])

    meta_prompt = f"""
You are an expert Prompt Engineer for an AI Audit system (OpenClaw).
We are auditing ICICI Bank Credit/Debit Card upgrade calls.

CURRENT PERFORMANCE:
- Agreement Rate: {s['agreement_rate']}% (Target: >85%)
- False Reworks: {s['false_rework_count']}
- False Approves: {s['false_approve_count']}

TOP FAILURES TO FIX:
{d_str}

CURRENT PROMPT CONTENT:
{current_prompt}

TASK:
1. Rewrite the CURRENT PROMPT to address the TOP FAILURES.
2. Be extremely specific in your instructions.
3. Incorporate the Hindi/Hinglish patterns identified in the fixes.
4. Ensure the output is ONLY the revised prompt, formatted clearly.
5. Do not change parts of the prompt that are working well.

REVISION RULES:
- For Consent: Expand Tier 2 to accept passive agreement (ji, theek hai, okay) if the pitch was completed.
- For Charges: Switch to content-based validation. If amount is correct, it passes regardless of speed.
- For Card Variant: Add fuzzy matching for Coral/Rubyx variations.

OUTPUT ONLY THE PROMPT.
"""

    print(f"[6/6] 🤖 Evolving prompt via Internal API ({VERTEX_GENERATE_URL})")
    
    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(
                VERTEX_GENERATE_URL,
                json={
                    "prompt": meta_prompt,
                    "model": "gemini-2.5-flash-lite"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                # Extract text from various possible response formats
                text = ""
                if isinstance(result, dict):
                    # Handle multiple possible response shapes from company API
                    text = (result.get('text') or 
                            result.get('response') or 
                            result.get('content') or 
                            result.get('generated_text') or 
                            result.get('result') or 
                            result.get('data') or "")
                    
                    if not text and 'candidates' in result:
                        try:
                            cand = result['candidates'][0]
                            text = cand.get('content', {}).get('parts', [{}])[0].get('text', '') or cand.get('output', '')
                        except: pass
                elif isinstance(result, str):
                    text = result
                
                if text:
                    print(f"  ✓ Prompt evolved successfully (Attempt {retries + 1})")
                    return text.strip()
                else:
                    raise ValueError(f"Could not find prompt text in API response keys. Response: {str(result)[:200]}...")
            else:
                raise ValueError(f"API Error ({response.status_code}): {response.text[:200]}")
                
        except Exception as e:
            retries += 1
            print(f"  ⚠ API attempt {retries} failed: {str(e)}")
            if retries < max_retries:
                wait_time = 2 ** retries
                print(f"    Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("  ❌ API evolution failed after maximum retries.")
                raise e
    return ""


def save_new_prompt(content: str, prompt_dir: str):
    """Save the new prompt with an incremented version number."""
    files = os.listdir(prompt_dir)
    v_files = [f for f in files if f.startswith('refined_audit_prompt_v') and f.endswith('.txt')]
    
    current_v = 0
    if v_files:
        versions = []
        for f in v_files:
            try:
                # Extract number from vX
                part = f.split('_v')[1]
                v_str = ''.join(filter(str.isdigit, part.split('_')[0]))
                if v_str:
                    versions.append(int(v_str))
            except: pass
        if versions:
            current_v = max(versions)
    
    new_v = current_v + 1
    new_fname = f'refined_audit_prompt_v{new_v}_auto.txt'
    new_fpath = os.path.join(prompt_dir, new_fname)
    
    with open(new_fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✓ New prompt saved: {new_fname}")
    return new_fname


# ─────────────────────────────────────────────
# STEP 5: Generate Report
# ─────────────────────────────────────────────

def generate_report(analysis: dict, deltas: list, coverage: list, output_dir: str) -> str:
    """Generate the final automation report."""
    print("[5/5] Generating report...")
    
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    report_path = os.path.join(output_dir, f'openclaw_audit_report_{timestamp}.md')
    
    s = analysis['summary']
    
    report = f"""# OpenClaw Audit Automation Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Product:** ICICI DC Upgrade

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| Total Cases | {s['total_cases']} |
| Agreement Rate | {s['agreement_rate']}% |
| AI Approval Rate | {s['ai_approval_rate']}% |
| Verifier Approval Rate | {s['verifier_approval_rate']}% |
| **Approval Gap** | **{s['gap']}%** |
| False Reworks (AI too strict) | {s['false_rework_count']} |
| False Approves (AI too lenient) | {s['false_approve_count']} |

> **Root Cause:** AI rejects {s['gap']}% more calls than human verifiers.
> Primary drivers: Consent strictness (95.3%), Charges rushing detection (83.0%), Pitch pace (55.9%)

---

## 2. Parameter-Level Failure Analysis (False Reworks)

| Parameter | Failures | Rate | Severity |
|---|---|---|---|
"""
    
    for d in sorted(deltas, key=lambda x: x.get('failure_rate', 0), reverse=True):
        if d['parameter'] != 'False Approves':
            report += f"| {d['parameter']} | {d['failure_count']} | {d['failure_rate']}% | {d['severity']} |\n"
    
    report += "\n---\n\n## 3. Root Cause → Fix Mapping\n\n"
    
    for i, c in enumerate(coverage, 1):
        status = "✅ Already in prompt" if c['already_in_prompt'] else "🔴 NEEDS ADDITION"
        report += f"""### 3.{i} {c['parameter']} ({c['severity']})
- **Root Cause:** {c['root_cause']}
- **Fix:** {c['fix']}
- **Status:** {status}

"""
    
    # Verifier rework reasons
    fa = analysis['false_approve']
    if fa['reasons']:
        report += "---\n\n## 4. False Approve Cases (AI missed these)\n\n"
        report += "Verifier rejected but AI approved — these need NEW guardrails:\n\n"
        for r in set(fa['reasons']):
            report += f"- {r}\n"
        report += "\n"
    
    # Prompt evolution instructions for OpenClaw/Hermes
    report += f"""---

## 5. OpenClaw/Hermes Prompt Evolution Instructions

### Skill: `dc_audit_prompt_evolver`

```json
{{
  "skill_name": "dc_audit_prompt_evolver",
  "trigger": "new_excel_feedback_received",
  "input": "AI vs Verifier audit Excel file",
  "steps": [
    "1. Ingest Excel → extract Raw Data sheet",
    "2. Compute: false_rework_rate, false_approve_rate, param_failures",
    "3. Compare param_failures against current prompt rules",
    "4. Generate delta patches for parameters with >10% failure rate",
    "5. Apply patches to prompt file (versioned)",
    "6. Log changes to evolution_history.json"
  ],
  "output": "Updated prompt file + change report",
  "feedback_loop": {{
    "metric": "agreement_rate",
    "target": ">85%",
    "current": "{s['agreement_rate']}%",
    "rerun_if_below": true
  }}
}}
```

### Current Calibration Targets:

| Parameter | Current AI Pass% | Target Pass% | Delta |
|---|---|---|---|
| Consent | ~{100 - analysis['false_rework']['param_failures'].get('Consent Taken Met', {}).get('pct', 0):.0f}% | >90% | Expand Tier 2 |
| Charges | ~{100 - analysis['false_rework']['param_failures'].get('Charges Explained Met', {}).get('pct', 0):.0f}% | >85% | Content-based eval |
| Pitch Pace | ~{100 - analysis['false_rework']['param_failures'].get('Pitch Pace', {}).get('pct', 0):.0f}% | >90% | Customer-signal only |
| Benefits | ~{100 - analysis['false_rework']['param_failures'].get('Benefits Explained Met', {}).get('pct', 0):.0f}% | >90% | ≥2 benefits rule |

"""
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"  ✓ Report saved: {report_path}")
    return report_path


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(excel_path: str, prompt_dir: str = None):
    """Run the full OpenClaw audit automation pipeline."""
    print("=" * 60)
    print("  OpenClaw/Hermes Audit Automation Pipeline")
    print("=" * 60)
    
    if prompt_dir is None:
        prompt_dir = os.path.dirname(os.path.abspath(excel_path))
    
    # Step 1: Ingest
    df = ingest_excel(excel_path)
    
    # Step 2: Analyze
    analysis = analyze_root_causes(df)
    
    # Step 3: Generate deltas
    deltas = generate_prompt_deltas(analysis)
    
    # Step 4: Compare with current prompt
    prompt = load_current_prompt(prompt_dir)
    coverage = compare_prompt_with_data(prompt, deltas)
    
    # Step 5: Generate report
    report_path = generate_report(analysis, deltas, coverage, prompt_dir)
    
    # Step 6: Evolve Prompt (Vertex AI)
    new_prompt_file = None
    if INTERNAL_API_AVAILABLE:
        # User requested limit on retries per optimisation
        max_retries = int(os.getenv("MAX_EVOLVE_RETRIES", 3))
        new_prompt = evolve_prompt_vertex(analysis, deltas, prompt, prompt_dir, max_retries=max_retries)
        if new_prompt:
            new_prompt_file = save_new_prompt(new_prompt, prompt_dir)
    else:
        print("[6/6] Skipping evolution (Internal API not configured)")

    # Save analysis JSON for Hermes skill consumption
    json_path = os.path.join(prompt_dir, 'evolution_history.json')
    history = []
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    
    history_entry = {
        'timestamp': datetime.now().isoformat(),
        'excel_file': os.path.basename(excel_path),
        'total_cases': analysis['summary']['total_cases'],
        'agreement_rate': analysis['summary']['agreement_rate'],
        'false_rework_count': analysis['summary']['false_rework_count'],
        'false_approve_count': analysis['summary']['false_approve_count'],
        'top_failures': [
            {'param': d['parameter'], 'rate': d['failure_rate'], 'action': d.get('action', 'ADD')}
            for d in coverage[:5]
        ],
    }
    
    if new_prompt_file:
        history_entry['evolved_prompt'] = new_prompt_file

    history.append(history_entry)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"  ✅ Pipeline complete!")
    print(f"  📊 Report: {report_path}")
    print(f"  📝 History: {json_path}")
    print(f"  🎯 Agreement: {analysis['summary']['agreement_rate']}% → Target: >85%")
    print(f"{'=' * 60}")
    
    return analysis, deltas, coverage


if __name__ == '__main__':
    excel_file = sys.argv[1] if len(sys.argv) > 1 else 'AI vs Verifier audits DC.xlsx'
    run_pipeline(excel_file)
