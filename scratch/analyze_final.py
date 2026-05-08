import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

# Read Raw Data sheet
df = pd.read_excel('AI vs Verifier audits DC.xlsx', sheet_name='Raw Data')
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

# Normalize status columns
df['ai_norm'] = df['Call Status AI'].astype(str).str.strip().str.lower()
df['ver_norm'] = df['Call Status Verifier'].astype(str).str.strip().str.lower()

# Cross-tab
print("\n=== CROSS-TABULATION ===")
ct = pd.crosstab(df['ai_norm'], df['ver_norm'], margins=True)
print(ct)

# Key stats
total = len(df)
agree = (df['ai_norm'] == df['ver_norm']).sum()
disputed = df[df['ai_norm'] != df['ver_norm']]
false_rework = disputed[(disputed['ai_norm'] == 'rework') & (disputed['ver_norm'] == 'approved')]
false_approve = disputed[(disputed['ai_norm'] == 'approved') & (disputed['ver_norm'] == 'rework')]

print(f"\n=== KEY STATS ===")
print(f"Total: {total}")
print(f"Agreement: {agree} ({agree/total*100:.1f}%)")
print(f"Disagreement: {len(disputed)} ({len(disputed)/total*100:.1f}%)")
print(f"AI Approved: {(df['ai_norm']=='approved').sum()} ({(df['ai_norm']=='approved').sum()/total*100:.1f}%)")
print(f"Verifier Approved: {(df['ver_norm']=='approved').sum()} ({(df['ver_norm']=='approved').sum()/total*100:.1f}%)")
print(f"False Rework (AI=Rework, Verifier=Approved): {len(false_rework)}")
print(f"False Approve (AI=Approved, Verifier=Rework): {len(false_approve)}")

# Parameter failure in FALSE REWORK
param_cols = ['Greeting Met', 'Benefits Explained Met', 'Charges Explained Met', 
              'Pitch Modulation', 'Pitch Pace', 'Tone Appropriate Met', 
              'Consent Taken Met', 'Card Variant Met']

print(f"\n=== PARAMETER FAILURES: FALSE REWORK ({len(false_rework)} cases) ===")
for p in param_cols:
    if p in df.columns:
        no_ct = (false_rework[p].astype(str).str.strip().str.lower() == 'no').sum()
        pct = no_ct/len(false_rework)*100
        print(f"  {p}: {no_ct}/{len(false_rework)} ({pct:.1f}%)")

# Consent patterns
print("\n=== CONSENT FAILURE PATTERNS (False Rework) ===")
consent_fails = false_rework[false_rework['Consent Taken Met'].astype(str).str.strip().str.lower() == 'no']
reasons = consent_fails['Consent Taken Reasons'].astype(str).tolist()
patterns = {'passive/okay/haan': 0, 'not explicitly asked': 0, 'ji/hmm backchannel': 0, 'rushed': 0}
for r in reasons:
    rl = r.lower()
    if any(w in rl for w in ['passive', 'okay', "'ok'", 'haan', 'acknowledgment']):
        patterns['passive/okay/haan'] += 1
    if any(w in rl for w in ['not explicitly', 'did not', 'without asking']):
        patterns['not explicitly asked'] += 1
    if any(w in rl for w in ["'ji'", 'hmm', 'backchannel']):
        patterns['ji/hmm backchannel'] += 1
    if 'rushed' in rl or 'before' in rl:
        patterns['rushed'] += 1
for p, c in sorted(patterns.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Charges patterns
print("\n=== CHARGES FAILURE PATTERNS (False Rework) ===")
charges_fails = false_rework[false_rework['Charges Explained Met'].astype(str).str.strip().str.lower() == 'no']
reasons = charges_fails['Charges Explained Reasons'].astype(str).tolist()
patterns = {'rushed': 0, 'confusing/unclear': 0, 'missing gst': 0, 'wrong amounts': 0, 'not separated': 0}
for r in reasons:
    rl = r.lower()
    if any(w in rl for w in ['rushed', 'fast', 'quickly', 'quick']):
        patterns['rushed'] += 1
    if any(w in rl for w in ['confus', 'unclear', 'not clear']):
        patterns['confusing/unclear'] += 1
    if 'gst' in rl and any(w in rl for w in ['not', 'missing', 'without']):
        patterns['missing gst'] += 1
    if any(w in rl for w in ['incorrect', 'wrong']):
        patterns['wrong amounts'] += 1
    if any(w in rl for w in ['not distinguish', 'not separate', 'not clearly state']):
        patterns['not separated'] += 1
for p, c in sorted(patterns.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Scenario-based analysis from email
print("\n=== DISPUTED APPROVED CASES (from email observations) ===")
# Charges not clear and approved
charges_no_approved = df[(df['Charges Explained Met'].astype(str).str.strip().str.lower() == 'no') & 
                          (df['ai_norm'] == 'approved')]
print(f"AI Approved but Charges=No: {len(charges_no_approved)}")

# Consent not clear and approved
consent_no_approved = df[(df['Consent Taken Met'].astype(str).str.strip().str.lower() == 'no') & 
                          (df['ai_norm'] == 'approved')]
print(f"AI Approved but Consent=No: {len(consent_no_approved)}")

# Reason for Rework column analysis
print("\n=== REASON FOR REWORK (Verifier-side) ===")
rework_reasons = df['Reason for Rework'].dropna()
print(f"Cases with Verifier Rework Reason: {len(rework_reasons)}")
for r in rework_reasons:
    print(f"  - {str(r)[:150]}")

# Drill down column
print("\n=== DRILL DOWN ===")
drill = df['Drill down'].dropna()
print(f"Cases with Drill down: {len(drill)}")
for d in drill:
    print(f"  - {str(d)[:150]}")
