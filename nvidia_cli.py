import os
import sys
import requests
import json

def chat_with_nvidia(api_key, prompt, model="meta/llama-3.1-405b-instruct"):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "top_p": 0.7,
        "max_tokens": 1024,
        "stream": True
    }

    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith("data: "):
                    data_str = line_text[6:]
                    if data_str == "[DONE]":
                        break
                    data = json.loads(data_str)
                    content = data['choices'][0]['delta'].get('content', '')
                    print(content, end='', flush=True)
        print() # New line at the end
        return ""
    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    # Get API Key from environment or argument
    api_key = os.getenv("NVIDIA_API_KEY")
    
    if not api_key:
        if len(sys.argv) > 1 and sys.argv[1].startswith("nvapi-"):
            api_key = sys.argv[1]
            prompt_start_idx = 2
        else:
            print("Error: NVIDIA_API_KEY environment variable not set.")
            print("Usage: python nvidia_cli.py <your_api_key> \"your prompt\"")
            print("   or: $env:NVIDIA_API_KEY='your_key'; python nvidia_cli.py \"your prompt\"")
            sys.exit(1)
    else:
        prompt_start_idx = 1

    if len(sys.argv) <= prompt_start_idx:
        print("Error: No prompt provided.")
        print(f"Usage: python nvidia_cli.py \"your prompt\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[prompt_start_idx:])
    
    print(f"--- NVIDIA ({'meta/llama-3.1-405b-instruct'}) ---\n")
    chat_with_nvidia(api_key, prompt)
