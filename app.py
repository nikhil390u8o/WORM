
import os
import threading
import requests
from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# ===== ENV CONFIG =====
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "google/gemini-flash-1.5:free")  # ✅ Faster model
SITE_URL = os.getenv("SITE_URL", "https://github.com/your-repo")
SITE_NAME = os.getenv("SITE_NAME", "WormGPT API")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # ✅ Add this in Render env vars
PROMPT_FILE = "system-prompt.txt"

if not API_KEY:
    raise RuntimeError("API_KEY not set in environment variables")

# ===== SYSTEM PROMPT LOADER =====
_prompt_cache = None
_prompt_cache_time = 0

def load_prompt():
    global _prompt_cache, _prompt_cache_time
    if not _prompt_cache or time.time() - _prompt_cache_time > 60:
        if not os.path.exists(PROMPT_FILE):
            _prompt_cache = "You are a helpful AI assistant."
        else:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                _prompt_cache = content if content else "You are a helpful AI assistant."
        _prompt_cache_time = time.time()
    return _prompt_cache

# ===== MANUAL CACHE (fixes lru_cache bug) =====
_response_cache = {}

def call_openrouter(prompt: str):
    # ✅ Use prompt as cache key
    if prompt in _response_cache:
        return _response_cache[prompt], True  # (result, cached)

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
        "max_tokens": 500
    }

    try:
        r = requests.post(f"{BASE_URL}/chat/completions",
                          headers=headers,
                          json=data,
                          timeout=30)

        if r.status_code != 200:
            return {"error": r.text}, False

        result = r.json()["choices"][0]["message"]["content"]
        _response_cache[prompt] = result  # ✅ Save to cache
        return result, False

    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}, False
    except Exception as e:
        return {"error": str(e)}, False

# ===== KEEP ALIVE (fixes Render cold starts) =====
def keep_alive():
    while True:
        time.sleep(600)  # every 10 minutes
        if RENDER_URL:
            try:
                requests.get(f"{RENDER_URL}/health", timeout=10)
                print("[KeepAlive] Pinged successfully")
            except Exception as e:
                print(f"[KeepAlive] Failed: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# ===== ROUTES =====
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

    result, cached = call_openrouter(prompt)

    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500

    return jsonify({"response": result, "cached": cached})

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    _response_cache.clear()
    return jsonify({"message": "Cache cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
