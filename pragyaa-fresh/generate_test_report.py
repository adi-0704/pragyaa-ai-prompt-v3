import pandas as pd
import requests
import json
import os

VERTEX_GENERATE_URL = "https://pragyaa-ai-prompt.vercel.app/api/vertex"

# Paths
EXCEL_PATH = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\AI vs Verifier audits DC.xlsx"
OLD_PROMPT_PATH = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\refined_audit_prompt_v2.txt"
NEW_PROMPT_PATH = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\refined_audit_prompt_v3_dc.txt"
TRANSCRIPT_PATH = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\DC_audios\Rework\transcript.txt"
OUTPUT_EXCEL = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\DC_audios\Rework\Rework_Variance_Report.xlsx"

print("Loading data...")
with open(OLD_PROMPT_PATH, "r", encoding="utf-8") as f: old_prompt = f.read()
with open(NEW_PROMPT_PATH, "r", encoding="utf-8") as f: new_prompt = f.read()
with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f: transcript = f.read()

def run_audit(prompt, transcript_text):
    full_prompt = f"{prompt}\n\n[TRANSCRIPT TO AUDIT]:\n{transcript_text}"
    try:
        resp = requests.post(VERTEX_GENERATE_URL, json={"prompt": full_prompt, "model": "gemini-2.5-flash-lite"}, timeout=55)
        resp.raise_for_status()
        data = resp.json()
        return data.get("text") or data.get("response") or str(data)
    except Exception as e:
        return f"API ERROR: {e}"

print("Auditing with Old Prompt...")
old_result = run_audit(old_prompt, transcript)

print("Auditing with New Prompt...")
new_result = run_audit(new_prompt, transcript)

print("Generating Excel Report...")
# Sheet 1: Variance Test
df_variance = pd.DataFrame([{
    "Call Filename": os.path.basename(TRANSCRIPT_PATH),
    "Test Scenario": "Rework Call Benchmarking",
    "Scenario Context": "Benchmarking newly transcribed Rework call to verify if old prompt fails and new prompt passes.",
    "Transcript Snippet": transcript[:200] + "...",
    "Old Prompt Text": old_prompt.strip(),
    "Old Prompt Verdict (Expected)": "Rework",
    "Old Prompt Verdict (Raw)": old_result.strip(),
    "New Prompt Text": new_prompt.strip(),
    "New Prompt Verdict (Expected)": "Approved",
    "New Prompt Verdict (Raw)": new_result.strip(),
    "Variance Resolved?": "Pending Manual Review"
}])

# Sheet 2: Discrepancy Overview from Original Excel
try:
    df_raw = pd.read_excel(EXCEL_PATH)
    ai_col = [c for c in df_raw.columns if 'Call Status AI' in c][0]
    ver_col = [c for c in df_raw.columns if 'Call Status Verifier' in c][0]
    
    total = len(df_raw)
    ai_app = (df_raw[ai_col].astype(str).str.lower().str.strip() == 'approved').sum()
    ver_app = (df_raw[ver_col].astype(str).str.lower().str.strip() == 'approved').sum()
    false_reworks = ((df_raw[ai_col].astype(str).str.lower().str.strip() == 'rework') & 
                     (df_raw[ver_col].astype(str).str.lower().str.strip() == 'approved')).sum()
                     
    df_stats = pd.DataFrame([{
        "Total Audits": total,
        "AI Approvals": ai_app,
        "Human Approvals": ver_app,
        "False Reworks Identified": false_reworks,
        "Action Taken": "Generated Prompt v3 to fix Hindi Passive Consent & Speed Thresholds"
    }])
except Exception as e:
    df_stats = pd.DataFrame([{"Error": f"Could not process AI vs Verifier Excel: {e}"}])

# Write to Excel
with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
    df_variance.to_excel(writer, sheet_name="Variance Test Results", index=False)
    df_stats.to_excel(writer, sheet_name="Audit Discrepancy Stats", index=False)

    # Sheet 3: Prompts Comparison
    df_prompts = pd.DataFrame({
        "Old Prompt (v2)": [old_prompt],
        "Optimized Prompt (v3)": [new_prompt]
    })
    df_prompts.to_excel(writer, sheet_name="Prompt Evolution", index=False)

print(f"Excel Report generated at: {OUTPUT_EXCEL}")
