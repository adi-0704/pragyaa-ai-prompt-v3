import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, openpyxl

wb = openpyxl.load_workbook('AI vs Verifier audits DC.xlsx', data_only=True)
ws = wb[wb.sheetnames[0]]
headers = [cell.value for cell in ws[1]]

# Find column indices
ai_idx = None
ver_idx = None
for i, h in enumerate(headers):
    if h and 'Call Status AI' in str(h):
        ai_idx = i
    if h and 'Call Status Verifier' in str(h):
        ver_idx = i

print(f"AI col idx: {ai_idx}, Verifier col idx: {ver_idx}")

# Build DataFrame manually
data = []
for r in range(2, ws.max_row + 1):
    cells = [cell.value for cell in ws[r]]
    data.append(cells)

df = pd.DataFrame(data, columns=headers)

# Rename to clean column names
col_map = {headers[ai_idx]: 'AI_Status', headers[ver_idx]: 'Ver_Status'}
df = df.rename(columns=col_map)

df['ai_norm'] = df['AI_Status'].astype(str).str.strip().str.lower()
df['ver_norm'] = df['Ver_Status'].astype(str).str.strip().str.lower()

print("\n=== Cross-tabulation ===")
ct = pd.crosstab(df['ai_norm'], df['ver_norm'], margins=True)
print(ct)

disputed = df[df['ai_norm'] != df['ver_norm']]
false_rework = disputed[(disputed['ai_norm'] == 'rework') & (disputed['ver_norm'] == 'approved')]
false_approve = disputed[(disputed['ai_norm'] == 'approved') & (disputed['ver_norm'].isin(['rework']))]

print(f"\nTotal: {len(df)}, Disputed: {len(disputed)}")
print(f"False Rework (AI=Rework, Verifier=Approved): {len(false_rework)}")
print(f"False Approve (AI=Approved, Verifier=Rework): {len(false_approve)}")

# Find Met columns
met_cols = [(i, h) for i, h in enumerate(headers) if h and 'Met' in str(h)]
print(f"\nMet columns: {met_cols}")

print("\n=== Parameter Failures in FALSE REWORK Cases ===")
for col_idx, col_name in met_cols:
    vals = false_rework.iloc[:, col_idx].astype(str).str.strip().str.lower()
    no_count = (vals == 'no').sum()
    total = len(false_rework)
    pct = no_count/total*100 if total > 0 else 0
    print(f"  {col_name}: {no_count}/{total} ({pct:.1f}%)")

print("\n=== Parameter Failures in ALL AI-Rework Cases ===")
ai_rework = df[df['ai_norm'] == 'rework']
for col_idx, col_name in met_cols:
    vals = ai_rework.iloc[:, col_idx].astype(str).str.strip().str.lower()
    no_count = (vals == 'no').sum()
    total = len(ai_rework)
    pct = no_count/total*100 if total > 0 else 0
    print(f"  {col_name}: {no_count}/{total} ({pct:.1f}%)")

# Consent patterns in false rework
print("\n=== TOP CONSENT FAILURE PATTERNS (False Rework) ===")
consent_met_idx = [i for i, h in enumerate(headers) if h and 'Consent Taken Met' in str(h)]
consent_reason_idx = [i for i, h in enumerate(headers) if h and 'Consent Taken Reasons' in str(h)]
if consent_met_idx and consent_reason_idx:
    consent_failures = false_rework[false_rework.iloc[:, consent_met_idx[0]].astype(str).str.strip().str.lower() == 'no']
    print(f"Consent failures in false rework: {len(consent_failures)}")
    # Extract common patterns
    reasons = consent_failures.iloc[:, consent_reason_idx[0]].astype(str).tolist()
    # Count keyword patterns
    patterns = {
        'Passive/Okay/Haan': 0,
        'No explicit consent asked': 0,
        'Customer said Ji/Hmm': 0,
        'Backchannel only': 0,
        'Rushed consent': 0,
    }
    for r in reasons:
        rl = r.lower()
        if 'passive' in rl or 'okay' in rl or 'haan' in rl or "'ok'" in rl:
            patterns['Passive/Okay/Haan'] += 1
        if 'not explicitly' in rl or 'did not' in rl or 'without' in rl:
            patterns['No explicit consent asked'] += 1
        if "'ji'" in rl or 'hmm' in rl or "'haan ji'" in rl:
            patterns['Customer said Ji/Hmm'] += 1
        if 'backchannel' in rl or 'acknowledgment' in rl:
            patterns['Backchannel only'] += 1
        if 'rushed' in rl or 'before' in rl:
            patterns['Rushed consent'] += 1
    for p, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {p}: {count}")

# Charges patterns in false rework
print("\n=== TOP CHARGES FAILURE PATTERNS (False Rework) ===")
charges_met_idx = [i for i, h in enumerate(headers) if h and 'Charges Explained Met' in str(h)]
charges_reason_idx = [i for i, h in enumerate(headers) if h and 'Charges Explained Reasons' in str(h)]
if charges_met_idx and charges_reason_idx:
    charges_failures = false_rework[false_rework.iloc[:, charges_met_idx[0]].astype(str).str.strip().str.lower() == 'no']
    print(f"Charges failures in false rework: {len(charges_failures)}")
    reasons = charges_failures.iloc[:, charges_reason_idx[0]].astype(str).tolist()
    patterns = {
        'Rushed explanation': 0,
        'Confusing/unclear amounts': 0,
        'Missing GST': 0,
        'Wrong amounts': 0,
        'Not separated joining/annual': 0,
        'Charges after consent': 0,
    }
    for r in reasons:
        rl = r.lower()
        if 'rushed' in rl or 'fast' in rl or 'quickly' in rl:
            patterns['Rushed explanation'] += 1
        if 'confus' in rl or 'unclear' in rl or 'not clear' in rl:
            patterns['Confusing/unclear amounts'] += 1
        if 'gst' in rl and ('not' in rl or 'missing' in rl or 'without' in rl):
            patterns['Missing GST'] += 1
        if 'incorrect' in rl or 'wrong' in rl:
            patterns['Wrong amounts'] += 1
        if 'not' in rl and ('distinguish' in rl or 'separate' in rl or 'clearly state' in rl):
            patterns['Not separated joining/annual'] += 1
        if 'after' in rl and 'consent' in rl:
            patterns['Charges after consent'] += 1
    for p, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {p}: {count}")
