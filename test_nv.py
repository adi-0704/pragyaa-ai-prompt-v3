import requests
import json

url = "https://integrate.api.nvidia.com/v1/chat/completions"
api_key = "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"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "deepseek-ai/deepseek-v4-pro",
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 10
}

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
