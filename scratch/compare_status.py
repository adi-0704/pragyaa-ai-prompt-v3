import pandas as pd
import os

def analyze_gap(csv_path, zip_contents_path, status_col):
    df = pd.read_csv(csv_path)
    with open(zip_contents_path, 'r', encoding='utf-16') as f:
        zip_lines = f.readlines()
    
    zip_data = {}
    for line in zip_lines:
        line = line.strip().replace('\\', '/')
        if line.endswith('.mp3'):
            parts = line.split('/')
            if len(parts) >= 3:
                # Format: CC_audios/Approved/filename.mp3
                folder = parts[-2]
                filename = parts[-1]
                zip_data[filename] = folder

    mismatches = []
    found_count = 0
    for idx, row in df.iterrows():
        fname = row['Filename']
        actual_status = row[status_col]
        if fname in zip_data:
            found_count += 1
            zip_status = zip_data[fname]
            if actual_status != zip_status:
                mismatches.append({
                    'Filename': fname,
                    'CSV_Status': actual_status,
                    'ZIP_Folder': zip_status
                })
    
    print(f"File: {csv_path}")
    print(f"Total rows in CSV: {len(df)}")
    print(f"Files found in ZIP: {found_count}")
    print(f"Mismatches: {len(mismatches)}")
    if mismatches:
        print("First 5 mismatches:")
        for m in mismatches[:5]:
            print(m)
    print("-" * 20)

# The zip_contents.txt might be UTF-16 from the powershell redirect? 
# Or maybe it's just standard. I'll check the encoding.
# Actually, I'll just run a bash command to check the first few lines.

if __name__ == "__main__":
    # Check CC
    try:
        analyze_gap('Verification Checklist - CC-formatted.csv', 'zip_contents.txt', 'Lead Staus 2')
    except Exception as e:
        print(f"Error CC: {e}")
        
    # Check DC
    try:
        analyze_gap('Verification Checklist - DC-formatted.csv', 'zip_contents.txt', 'Lead Status')
    except Exception as e:
        print(f"Error DC: {e}")
