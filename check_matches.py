import pandas as pd
import os

# Load raw data
df = pd.read_excel('AI vs Verifier audits CC.xlsx', sheet_name='Raw Data')

# List available transcripts
transcript_dir = 'variance_cc_transcripts_8May/variance_cc_transcripts_8May'
available_transcripts = [f for f in os.listdir(transcript_dir) if f.endswith('.txt')]
available_bases = [f[:-4] for f in available_transcripts]

# Strip .mp3 from Filename
df['Base_Filename'] = df['Filename'].str.replace('.mp3', '', regex=False)

# Match filenames
df['Has_Transcript'] = df['Base_Filename'].isin(available_bases)

matched = df[df['Has_Transcript'] == True]
print(f"Total rows in Excel: {len(df)}")
print(f"Total transcripts in zip: {len(available_transcripts)}")
print(f"Total matches found: {len(matched)}")

variances = df[df['Lead Staus AI'] != df['Lead Staus Verifier']]
matched_variances = variances[variances['Base_Filename'].isin(available_bases)]
print(f"Total variances in Excel: {len(variances)}")
print(f"Variances with transcripts: {len(matched_variances)}")

if len(matched_variances) > 0:
    print("\nExample matched variances:")
    print(matched_variances[['Base_Filename', 'Lead Staus AI', 'Lead Staus Verifier']].head())
else:
    print("\nNo variances found in the transcript set provided.")
    print("Example transcript bases from zip:")
    print(available_bases[:5])
    print("Example base filenames from Excel:")
    print(df['Base_Filename'].head().tolist())
