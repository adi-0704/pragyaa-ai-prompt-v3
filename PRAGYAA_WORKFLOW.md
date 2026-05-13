# Pragyaa.AI Multi-Product Workflow Guide

This project now supports automated audit analysis and prompt optimization for three core products:
1. **Amazon NCA**
2. **Insta NCA**
3. **CC/DC Upgrade**

## 🛠️ Components

### 1. Unified Backend (`api/index.py`)
The backend automatically detects the process type from the uploaded Excel file. It uses a `PROCESS_CONFIGS` dictionary to:
- Map parameter-level failures.
- Generate specific "Fix Instructions" for Vertex AI.
- Calculate product-specific agreement rates.

### 2. Intelligent Frontend (`app.js`)
The dashboard adapts to the detected process:
- Shows process-specific status badges.
- Renders failure heatmaps based on the canonical parameters of the product.
- Provides a "Changes Made" log that reflects the optimization logic applied.

## 🚀 How to Run Analysis

1. **Upload**: Drag and drop any "AI vs Verifier" Excel report into the dashboard.
2. **Review**: The system will identify the process (e.g., "Insta NCA") and show the "Approval Gap".
3. **Optimize**: Click "Generate Optimized Prompt". The system will:
   - Identify the top failing parameters (e.g., "Referral Code", "Greeting").
   - Consult the internal "Fix Library" for that product.
   - Use Vertex AI to generate a new, more accurate prompt.

## 📈 Optimization Rules (Implemented)

### Amazon NCA
- **RPV Sensitivity**: High. (Greeting must confirm customer identity).
- **Referral Code Recovery**: Specifically looks for SOL ID / AIR codes.
- **Tone/Grammar**: Stricter alignment with Finmech standards.

### Insta NCA
- **Sub-Disposition Logic**: Distinguishes between `NOT_INTERESTED` and `NOT_ELIGIBLE`.
- **LEAD Recognition**: Only tags success if card generation is confirmed.

### CC/DC Upgrade
- **Passive Consent**: Handles Hindi affirmative phrases (e.g., "Theek hai").
- **Phonetic Mapping**: Maps "Updated Coral" to "Coral Card".

---
*Created by Pragyaa.AI Automation Engine*
