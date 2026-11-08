"""
Groq API Client (Free Tier fallback).
Supports direct OpenAI-compatible chat completions endpoint with llama-3.3-70b-versatile.
"""
import os
import json
import logging
import re
import requests

logger = logging.getLogger("smarthire.ai.groq")


def call_groq(system_prompt, user_prompt, api_key=None, model="llama-3.3-70b-versatile"):
    """
    Call Groq API using REST endpoint.
    Returns parsed JSON dictionary or None on failure/quota exceeded.
    """
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            from dotenv import load_dotenv
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            load_dotenv(os.path.join(base_dir, ".env"), override=True)
            api_key = os.environ.get("GROQ_API_KEY", "").strip()

    if not api_key:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            result = response.json()
            choices = result.get("choices", [])
            if choices:
                text_content = choices[0].get("message", {}).get("content", "").strip()
                if text_content.startswith("```"):
                    text_content = text_content.strip("`")
                    if text_content.startswith("json"):
                        text_content = text_content[4:].strip()
                return json.loads(text_content)
        else:
            clean_resp = re.sub(r"Bearer\s+[\w\.-]+", "Bearer [REDACTED]", response.text[:200])
            logger.warning(f"[Groq API] HTTP {response.status_code}: {clean_resp}")
            # Try llama-3.1-8b-instant as fallback
            if model != "llama-3.1-8b-instant":
                return call_groq(system_prompt, user_prompt, api_key=api_key, model="llama-3.1-8b-instant")
    except Exception as e:
        clean_err = re.sub(r"Bearer\s+[\w\.-]+", "Bearer [REDACTED]", str(e))
        logger.error(f"[Groq API Error] {clean_err}")

    return None
