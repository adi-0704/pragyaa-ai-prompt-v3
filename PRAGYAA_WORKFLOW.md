# Pragyaa.AI Multi-Product Workflow Guide

This project supports automated audit analysis and prompt optimization for three core products:
1. **Amazon NCA**
2. **Insta NCA**
3. **CC/DC Upgrade**

## 🛠️ Components

### 1. Unified Backend (`api/index.py`)
The backend automatically detects the process type from the uploaded Excel file. It uses a `PROCESS_CONFIGS` dictionary to:
- Map parameter-level failures.
- Generate specific "Fix Instructions" for Vertex AI.
- Calculate product-specific agreement rates.
- **New**: Serves frontend static files and handles audio transcription/auditing via Vertex AI.

### 2. Intelligent Frontend (`app.js`)
The dashboard adapts to the detected process:
- Shows process-specific status badges.
- Renders failure heatmaps based on the canonical parameters of the product.
- Provides a "Changes Made" log that reflects the optimization logic applied.
- **New**: **Live Test Step** — Upload an MP3 to verify the optimized prompt in real-time.

## 🚀 How to Run Analysis

1. **Upload**: Drag and drop any "AI vs Verifier" Excel report into the dashboard.
2. **Review**: The system will identify the process (e.g., "Insta NCA") and show the "Approval Gap".
3. **Optimize**: Click "Generate Optimized Prompt". The system will:
   - Identify the top failing parameters.
   - Consult the internal "Fix Library" for that product.
   - Use Vertex AI to generate a new, more accurate prompt.
4. **Test**: Upload a sample audio file in Step 4 to see the new prompt in action.

## 📈 Deployment
The project is optimized for **Vercel**. 
- The `frontend/` directory has been unified into the root for simpler routing.
- `vercel.json` handles API routing to the Python backend.

---
*Created by Pragyaa.AI Automation Engine*

