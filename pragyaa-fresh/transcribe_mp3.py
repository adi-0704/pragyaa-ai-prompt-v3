import base64
import requests
import json
import sys

AUDIO_PATH = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\DC_audios\Rework\DC_upgrade_New_FNM5333_20234_8884138075_1777723115246_20260502_180032_AD050220261800271845_8884138075.mp3"
URL = "https://voicelensG1.pragyaa.ai/vertex/transcript"

def transcribe_audio():
    print("Reading audio file...")
    with open(AUDIO_PATH, "rb") as f:
        audio_data = f.read()
    
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")
    
    payload = {
        "prompt": "Transcribe this ICICI Bank sales call precisely. Include agent and customer labels.",
        "audio": audio_b64,
        "mime": "audio/mpeg"
    }
    
    print("Sending to transcription API...")
    try:
        resp = requests.post(URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        
        # Extract transcript text
        transcript = data.get("text") or data.get("response") or data.get("content") or "No transcript generated"
        
        output_path = r"c:\Users\aditya tyagi\OneDrive\Desktop\antigravity\pragyaa.ai\DC_audios\Rework\transcript.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        
        print(f"Transcription successful. Saved to {output_path}")
        print("\n--- TRANSCRIPT PEEK ---")
        print(transcript[:500] + "...")
        
    except Exception as e:
        print(f"Error: {e}")
        if 'resp' in locals():
            print(resp.text)

if __name__ == "__main__":
    transcribe_audio()
