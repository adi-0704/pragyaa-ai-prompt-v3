import pandas as pd
import os

# Load raw data
df = pd.read_excel('AI vs Verifier audits CC.xlsx', sheet_name='Raw Data')

# Define variance (usually Lead Staus AI != Lead Staus Verifier or Status == 'Variance')
# Let's check the unique values of 'Status' first
print("Unique Status values:", df['Status'].unique())

variances = df[df['Lead Staus AI'] != df['Lead Staus Verifier']]
print(f"Total variances found by comparing status: {len(variances)}")

# List available transcripts
transcript_dir = 'variance_cc_transcripts_8May/variance_cc_transcripts_8May'
available_transcripts = [f for f in os.listdir(transcript_dir) if f.endswith('.txt')]

# Match filenames
variances['Has_Transcript'] = variances['Filename'].apply(lambda x: f"{x}.txt" in available_transcripts)

matched = variances[variances['Has_Transcript'] == True]
missing = variances[variances['Has_Transcript'] == False]

print(f"Variances with transcripts: {len(matched)}")
print(f"Variances missing transcripts: {len(missing)}")

if len(missing) > 0:
    print("\nFirst 5 missing filenames:")
    print(missing['Filename'].head().tolist())

print("\nSummary of reasons for variance (where transcript is available):")
# Filter columns that start with 'Reasons -' and have non-null values for matched variances
reason_cols = [col for col in df.columns if col.startswith('Reasons -')]
for col in reason_cols:
    reasons = matched[matched[col].notnull()][col].unique()
    if len(reasons) > 0:
        print(f"\n{col}:")
        for r in reasons[:5]: # Show first 5 unique reasons
            print(f"  - {r}")
