import os
import requests
import json
from flask import Flask, request, jsonify, Response
from functools import lru_cache
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ===== ENV CONFIG =====
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "stepfun/step-3.5-flash:free")
SITE_URL = os.getenv("SITE_URL", "https://github.com/00x0kafyy/worm-ai")
SITE_NAME = os.getenv("SITE_NAME", "WormGPT API")

if not API_KEY:
    raise RuntimeError("API_KEY not set")

def call_openrouter(prompt: str):
    """Call OpenRouter API with proper error handling"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}  # Removed system prompt for speed
        ],
        "temperature": 0.7,
        "max_tokens": 300,  # Reduced for faster response
        "top_p": 0.9
    }
    
    try:
        # Increased timeout and added retry
        r = requests.post(f"{BASE_URL}/chat/completions", 
                         headers=headers, 
                         json=data, 
                         timeout=45)
        
        # Log status for debugging
        app.logger.info(f"OpenRouter response status: {r.status_code}")
        
        if r.status_code != 200:
            app.logger.error(f"OpenRouter error: {r.text[:200]}")
            return {"error": f"API returned {r.status_code}"}
        
        # Parse JSON response
        response_data = r.json()
        return {"response": response_data["choices"][0]["message"]["content"]}
        
    except requests.exceptions.Timeout:
        app.logger.error("Request timeout")
        return {"error": "Request timeout - try again"}
    except json.JSONDecodeError as e:
        app.logger.error(f"JSON decode error: {e}, Response: {r.text[:200]}")
        return {"error": "Invalid API response"}
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return {"error": str(e)}

@app.route("/")
def home():
    return jsonify({"status": "running", "message": "WormGPT API is active"})

@app.route("/query", methods=["GET", "POST"])
def query():
    # Get prompt from GET or POST
    if request.method == "GET":
        prompt = request.args.get("q")
    else:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            prompt = data.get("prompt") or data.get("q")
        else:
            prompt = request.form.get("prompt") or request.form.get("q")
    
    if not prompt:
        return jsonify({"error": "No prompt provided. Use ?q=your_question"}), 400
    
    result = call_openrouter(prompt)
    
    # Always return valid JSON
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
    
    return jsonify(result)

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
