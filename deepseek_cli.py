import os
import sys
from openai import OpenAI

# Default Configuration
DEFAULT_API_KEY = "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"
DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"
BASE_URL = "https://integrate.api.nvidia.com/v1"

def get_client():
    api_key = os.getenv("NVIDIA_API_KEY", DEFAULT_API_KEY)
    return OpenAI(base_url=BASE_URL, api_key=api_key)

def chat_stream(client, messages, model=DEFAULT_MODEL):
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            top_p=0.9,
            max_tokens=4096,
            stream=True,
            extra_body={"chat_template_kwargs": {"thinking": False}}
        )

        print("\nDeepSeek: ", end="", flush=True)
        full_response = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content
        print("\n")
        return full_response
    except Exception as e:
        print(f"\nError: {e}")
        return None

def main():
    client = get_client()
    
    # Check if a direct command was given
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        messages = [{"role": "user", "content": prompt}]
        chat_stream(client, messages)
        return

    # Interactive Mode
    print("=== DeepSeek NVIDIA CLI Chat ===")
    print("Type 'exit' or 'quit' to stop.")
    print("Type 'mode code' to switch to coding assistant.")
    print("Type 'mode chat' to switch to general chat.")
    print("-" * 30)

    mode = "chat"
    system_prompts = {
        "chat": "You are a helpful and concise AI assistant powered by DeepSeek.",
        "code": "You are an expert senior software engineer. Provide clean, efficient, and well-documented code. Always explain your logic."
    }
    
    history = [{"role": "system", "content": system_prompts[mode]}]

    while True:
        try:
            user_input = input(f"[{mode}] You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if user_input.lower() == 'mode code':
                mode = "code"
                history = [{"role": "system", "content": system_prompts[mode]}]
                print("--- Switched to CODE mode (History cleared) ---")
                continue
            
            if user_input.lower() == 'mode chat':
                mode = "chat"
                history = [{"role": "system", "content": system_prompts[mode]}]
                print("--- Switched to CHAT mode (History cleared) ---")
                continue

            history.append({"role": "user", "content": user_input})
            
            response = chat_stream(client, history)
            if response:
                history.append({"role": "assistant", "content": response})
            
            # Keep history manageable (last 10 messages)
            if len(history) > 11:
                history = [history[0]] + history[-10:]

        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()
