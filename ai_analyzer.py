import os
import json
import logging
import httpx
from typing import Any

logger = logging.getLogger(name)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Primary: Claude via OpenRouter | Fallback: Gemini via OpenRouter
PRIMARY_MODEL = "openai/gpt-oss-20b"
FALLBACK_MODEL = "google/gemini-2.0-flash-001"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a precise document analysis engine.
Your job is to analyze document text and return ONLY a valid JSON object — no markdown, no explanation, no preamble.

The JSON must follow this exact structure:
{
  "summary": "<2-3 sentence concise summary of the document>",
  "entities": {
    "names": ["<person name>", ...],
    "dates": ["<date string>", ...],
    "organizations": ["<org name>", ...],
    "amounts": ["<monetary amount>", ...]
  },
  "sentiment": "<Positive|Neutral|Negative>"
}

Rules:
- summary: 2–3 sentences only. Capture the document's main purpose.
- entities: Extract ALL that appear. Use empty arrays [] if none found.
- sentiment: Classify the OVERALL tone. Use exactly: Positive, Neutral, or Negative.
- Return ONLY the JSON. No extra text before or after."""


def _build_user_prompt(text: str) -> str:
    # Limit to ~3000 tokens worth of text to stay cost-efficient
    max_chars = 8000
    truncated = text[:max_chars]
    if len(text) > max_chars:
        truncated += "\n[Document truncated for analysis]"
    return f"Analyze this document:\n\n{truncated}"


async def analyze_document(text: str) -> dict[str, Any]:
    """
    Single LLM call to get summary, entities, and sentiment.
    Tries primary model (Claude), falls back to Gemini if unavailable.
    """
    if OPENROUTER_API_KEY:
        # Try primary model first
        try:
            result = await _call_openrouter(text, PRIMARY_MODEL)
            return result
        except Exception as e:
            logger.warning(f"Primary model ({PRIMARY_MODEL}) failed: {e}. Trying fallback...")

        # Fallback model
        try:
            result = await _call_openrouter(text, FALLBACK_MODEL)
            return result
        except Exception as e:
            logger.error(f"Fallback model also failed: {e}")
            raise RuntimeError("Both LLM models failed. Check OPENROUTER_API_KEY.")

    elif GEMINI_API_KEY:
        try:
            result = await _call_gemini_direct(text)
            return result
        except Exception as e:
            logger.error(f"Gemini direct call failed: {e}")
            raise RuntimeError(f"Gemini analysis failed: {e}")

    else:
        raise RuntimeError(
            "No LLM API key configured. Set OPENROUTER_API_KEY or GEMINI_API_KEY in environment."
        )


async def _call_openrouter(text: str, model: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://doc-analyzer.onrender.com",
        "X-Title": "Document Analysis API",
    }

    payload = {
        "model": model,
        "max_tokens": 800,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    raw_content = data["choices"][0]["message"]["content"].strip()
    logger.info(f"LLM response via {model}: {raw_content[:200]}...")
    return _parse_llm_response(raw_content)


async def _call_gemini_direct(text: str) -> dict[str, Any]:
    """Direct Gemini API call as alternative to OpenRouter."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    full_prompt = f"{SYSTEM_PROMPT}\n\n{_build_user_prompt(text)}"
payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    raw_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    logger.info(f"Gemini direct response: {raw_content[:200]}...")
    return _parse_llm_response(raw_content)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM JSON response."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last fence lines
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw response: {raw}")
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # Validate and set defaults for required fields
    result = {
        "summary": parsed.get("summary", "Summary not available."),
        "entities": {
            "names": parsed.get("entities", {}).get("names", []),
            "dates": parsed.get("entities", {}).get("dates", []),
            "organizations": parsed.get("entities", {}).get("organizations", []),
            "amounts": parsed.get("entities", {}).get("amounts", []),
        },
        "sentiment": parsed.get("sentiment", "Neutral"),
    }

    # Normalize sentiment to valid values
    sentiment = result["sentiment"].strip().capitalize()
    if sentiment not in {"Positive", "Neutral", "Negative"}:
        sentiment = "Neutral"
    result["sentiment"] = sentiment

    return result