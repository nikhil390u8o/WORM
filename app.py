import os
import requests
from flask import Flask, request, jsonify, Response
from functools import lru_cache
import time

app = Flask(__name__)

# ===== ENV CONFIG =====
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "stepfun/step-3.5-flash:free")
SITE_URL = os.getenv("SITE_URL", "https://github.com/your-repo")
SITE_NAME = os.getenv("SITE_NAME", "WormGPT API")
PROMPT_FILE = "system-prompt.txt"

if not API_KEY:
    raise RuntimeError("API_KEY not set in environment variables")

# Cache for system prompt
_prompt_cache = None
_prompt_cache_time = 0

def load_prompt():
    global _prompt_cache, _prompt_cache_time
    # Refresh cache every 60 seconds
    if not _prompt_cache or time.time() - _prompt_cache_time > 60:
        if not os.path.exists(PROMPT_FILE):
            _prompt_cache = "You are a helpful AI assistant."
        else:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                _prompt_cache = content if content else "You are a helpful AI assistant."
        _prompt_cache_time = time.time()
    return _prompt_cache

@lru_cache(maxsize=50)
def call_openrouter(prompt: str):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": load_prompt()},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500  # Reduced for speed
    }
    
    try:
        r = requests.post(f"{BASE_URL}/chat/completions", 
                         headers=headers, 
                         json=data, 
                         timeout=30)
        
        if r.status_code != 200:
            return {"error": r.text}
        
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}
    except Exception as e:
        return {"error": str(e)}

@app.route("/")
def home():
    return "WormGPT API Running - Use /query?q=your_question"

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "model": MODEL, "timestamp": time.time()})

@app.route("/query", methods=["GET", "POST"])
def query():
    if request.method == "GET":
        prompt = request.args.get("q")
    else:
        data = request.get_json(silent=True) or {}
        prompt = data.get("prompt")
    
    if not prompt:
        return jsonify({"error": "No prompt provided. Use ?q=your_question"}), 400
    
    result = call_openrouter(prompt)
    
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    
    return jsonify({"response": result, "cached": False})

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    call_openrouter.cache_clear()
    return jsonify({"message": "Cache cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
