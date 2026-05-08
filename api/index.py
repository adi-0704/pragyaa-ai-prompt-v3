from flask import Flask, request, jsonify
import pandas as pd
import os
import json
from datetime import datetime
import io
import base64
import requests

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
        INTERNAL_API_AVAILABLE,
        SDK_AVAILABLE
    )
except ImportError:
    # Fallback if import fails in Vercel env
    INTERNAL_API_AVAILABLE = True
    SDK_AVAILABLE = False

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
        vertex_status = "Using Internal Company API"
        
        if generate_prompt:
            try:
                # Call evolution logic from the automation script
                from openclaw_audit_automation import evolve_prompt_vertex
                optimized_prompt = evolve_prompt_vertex(analysis, deltas, current_prompt, "/tmp")
                if not optimized_prompt:
                    vertex_status = "API returned empty response"
            except Exception as ai_err:
                vertex_status = f"API Error: {str(ai_err)}"

        # Convert snake_case to camelCase for frontend consistency
        formatted_analysis = {
            "summary": {
                "total": analysis['summary']['total_cases'],
                "agreementRate": analysis['summary']['agreement_rate'],
                "aiApprovalRate": analysis['summary']['ai_approval_rate'],
                "verApprovalRate": analysis['summary']['verifier_approval_rate'],
                "falseReworkCount": analysis['summary']['false_rework_count'],
                "falseApproveCount": analysis['summary']['false_approve_count'],
                "gap": analysis['summary']['gap']
            },
            "paramFailures": analysis['false_rework']['param_failures'],
            "consentPatterns": analysis['false_rework']['patterns'].get('consent', {}),
            "chargesPatterns": analysis['false_rework']['patterns'].get('charges', {}),
            "faReasons": analysis['false_approve']['reasons']
        }

        return jsonify({
            "status": "success",
            "analysis": formatted_analysis,
            "deltas": deltas,
            "coverage": coverage,
            "vertex_available": INTERNAL_API_AVAILABLE,
            "vertex_status": vertex_status,
            "optimized_prompt": optimized_prompt
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vertex', methods=['POST'])
def vertex_proxy():
    try:
        data = request.json
        from openclaw_audit_automation import VERTEX_GENERATE_URL, VERTEX_TRANSCRIPT_URL
        
        # Determine target URL based on request type
        is_transcript = 'audio' in data
        url = VERTEX_TRANSCRIPT_URL if is_transcript else VERTEX_GENERATE_URL
        
        # Forward request to Vertex API
        response = requests.post(url, json=data, timeout=60)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Vertex API Error ({response.status_code})", "details": response.text}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
