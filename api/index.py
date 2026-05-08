from flask import Flask, request, jsonify
import pandas as pd
import os
import json
from datetime import datetime
import io
import base64

# Import logic from the root script
# Since Vercel puts the api/ folder in a specific environment, we might need to adjust imports
# Or just copy the necessary functions here for reliability in a serverless env
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openclaw_audit_automation import (
        analyze_root_causes, 
        generate_prompt_deltas, 
        compare_prompt_with_data,
        VERTEX_AVAILABLE
    )
except ImportError:
    # Fallback if import fails in Vercel env
    VERTEX_AVAILABLE = False

app = Flask(__name__)

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        file_content_b64 = data.get('file_content')
        current_prompt = data.get('current_prompt', '')
        
        if not file_content_b64:
            return jsonify({"error": "No file content provided"}), 400
            
        # Decode Excel file
        file_bytes = base64.b64decode(file_content_b64)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0) # Simple ingestion
        
        # Basic normalization (replicating ingest_excel logic)
        ai_col = next((c for c in df.columns if 'Call Status AI' in str(c)), None)
        ver_col = next((c for c in df.columns if 'Call Status Verifier' in str(c)), None)
        
        if not ai_col or not ver_col:
            return jsonify({"error": "Missing status columns in Excel"}), 400
            
        df['ai_norm'] = df[ai_col].astype(str).str.strip().str.lower()
        df['ver_norm'] = df[ver_col].astype(str).str.strip().str.lower()
        df['is_match'] = df['ai_norm'] == df['ver_norm']
        
        # Step 2: Analyze
        analysis = analyze_root_causes(df)
        
        # Step 3: Generate deltas
        deltas = generate_prompt_deltas(analysis)
        
        # Step 4: Compare
        coverage = compare_prompt_with_data(current_prompt, deltas)
        
        return jsonify({
            "status": "success",
            "analysis": analysis,
            "deltas": deltas,
            "coverage": coverage,
            "vertex_available": VERTEX_AVAILABLE
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
