"""
Google Gemini API Client (Free Tier via Google AI Studio).
Supports direct REST API calling with gemini-2.5-flash / gemini-1.5-flash.
"""
import os
import json
import logging
import re
import requests

logger = logging.getLogger("smarthire.ai.gemini")


def call_gemini(system_prompt, user_prompt, api_key=None, model="gemini-2.5-flash"):
    """
    Call Google Gemini API using REST endpoint.
    Returns parsed JSON dictionary or None on failure/quota exceeded.
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            from dotenv import load_dotenv
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            load_dotenv(os.path.join(base_dir, ".env"), override=True)
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        return None

    # Endpoint URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_prompt}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            result = response.json()
            candidates = result.get("candidates", [])
            if candidates:
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                text_content = text_content.strip()
                # Clean code blocks if present
                if text_content.startswith("```"):
                    text_content = text_content.strip("`")
                    if text_content.startswith("json"):
                        text_content = text_content[4:].strip()
                return json.loads(text_content)
        else:
            clean_resp = re.sub(r"key=[^&\s'\"]+", "key=[REDACTED]", response.text[:200])
            logger.warning(f"[Gemini API] HTTP {response.status_code}: {clean_resp}")
            # Try gemini-1.5-flash as fallback model if 2.5-flash is not available on key
            if model != "gemini-1.5-flash":
                return call_gemini(system_prompt, user_prompt, api_key=api_key, model="gemini-1.5-flash")
    except Exception as e:
        clean_err = re.sub(r"key=[^&\s'\"]+", "key=[REDACTED]", str(e))
        logger.error(f"[Gemini API Error] {clean_err}")

    return None
