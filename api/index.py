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
        generate_prompt = data.get('generate_prompt', False)
        
        if not file_content_b64:
            return jsonify({"error": "No file content provided"}), 400
            
        # Decode Excel file
        file_bytes = base64.b64decode(file_content_b64)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
        
        # Step 2: Analyze
        analysis = analyze_root_causes(df)
        
        # Step 3: Generate deltas
        deltas = generate_prompt_deltas(analysis)
        
        # Step 4: Compare
        coverage = compare_prompt_with_data(current_prompt, deltas)
        
        # Step 5: Evolve Prompt (if requested)
        optimized_prompt = None
        vertex_status = "Using Internal Company API (Cloud ID not required)"
        
        if generate_prompt:
            try:
                # Call evolution logic from the automation script
                from openclaw_audit_automation import evolve_prompt_vertex
                optimized_prompt = evolve_prompt_vertex(analysis, deltas, current_prompt, "/tmp")
                if not optimized_prompt:
                    vertex_status = "API returned empty response or failed"
            except Exception as ai_err:
                vertex_status = f"API Error: {str(ai_err)}"

        return jsonify({
            "status": "success",
            "analysis": analysis,
            "deltas": deltas,
            "coverage": coverage,
            "vertex_available": VERTEX_AVAILABLE,
            "vertex_status": vertex_status,
            "optimized_prompt": optimized_prompt
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
