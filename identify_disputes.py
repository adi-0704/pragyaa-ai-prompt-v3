import pandas as pd

df = pd.read_excel('AI vs Verifier audits CC.xlsx', sheet_name='Raw Data')

# AI Approved, but Verifier Rejected
# We need to find the exact labels used in 'Lead Staus AI' and 'Lead Staus Verifier'
print("AI Status unique values:", df['Lead Staus AI'].unique())
print("Verifier Status unique values:", df['Lead Staus Verifier'].unique())

# Assuming 'Approved' and 'Rejected' or similar
# Based on summary, AI Approved = 867, Verifier Approved = 1114
# Disputes in approved cases = 33 (AI Approved, Verifier Rejected)

# Let's try to identify them
disputed_approved = df[(df['Lead Staus AI'] == 'Approved') & (df['Lead Staus Verifier'] == 'Rework')]
print(f"Found {len(disputed_approved)} cases where AI Approved and Verifier says Rework")

if len(disputed_approved) > 0:
    print("\nFilenames for Disputed Approved cases (first 10):")
    print(disputed_approved['Filename'].head(10).tolist())
    
    # Check if we have reasons
    reason_cols = [col for col in df.columns if col.startswith('Reasons -')]
    print("\nSummary of reasons for these cases:")
    for col in reason_cols:
        val_counts = disputed_approved[col].value_counts()
        if not val_counts.empty:
            print(f"\n{col}:")
            print(val_counts)
