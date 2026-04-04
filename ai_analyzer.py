import os
import json
import logging
import httpx
from typing import Any

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model fallback chain — tried in order until one succeeds
OPENROUTER_MODELS = [
    "openai/gpt-oss-20b",              # Primary: free tier, works well
    "google/gemini-2.0-flash-001",      # Fallback 1: fast, reliable
    "anthropic/claude-3.5-sonnet",      # Fallback 2: best quality (paid)
]

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
- summary: 2-3 sentences. Capture the document's main purpose.
- entities: Extract ALL that appear. Use empty arrays [] if none found.
- sentiment: Overall tone — exactly one of: Positive, Neutral, Negative.
- Return ONLY the JSON object. Absolutely nothing else."""


def _build_user_prompt(text: str) -> str:
    max_chars = 8000
    truncated = text[:max_chars]
    if len(text) > max_chars:
        truncated += "\n[Document truncated]"
    return f"Analyze this document:\n\n{truncated}"


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Parse and validate LLM JSON response. Returns safe defaults on failure."""
    default = {
        "summary": "Could not analyze document.",
        "entities": {"names": [], "dates": [], "organizations": [], "amounts": []},
        "sentiment": "Neutral",
    }

    if not raw or not raw.strip():
        logger.warning("LLM returned empty response — using defaults")
        return default

    cleaned = raw.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[1:end])

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e} | Raw: {raw[:300]}")
        return default

    sentiment = parsed.get("sentiment", "Neutral").strip().capitalize()
    if sentiment not in {"Positive", "Neutral", "Negative"}:
        sentiment = "Neutral"

    return {
        "summary": parsed.get("summary", default["summary"]),
        "entities": {
            "names": parsed.get("entities", {}).get("names", []),
            "dates": parsed.get("entities", {}).get("dates", []),
            "organizations": parsed.get("entities", {}).get("organizations", []),
            "amounts": parsed.get("entities", {}).get("amounts", []),
        },
        "sentiment": sentiment,
    }


async def analyze_document(text: str) -> dict[str, Any]:
    """
    Run AI analysis. Tries OpenRouter models in order, then direct Gemini API.
    Raises RuntimeError only if all options fail.
    """
    if OPENROUTER_API_KEY:
        for model in OPENROUTER_MODELS:
            try:
                result = await _call_openrouter(text, model)
                logger.info(f"Analysis succeeded with model: {model}")
                return result
            except Exception as e:
                logger.warning(f"Model {model} failed: {e} — trying next")
                continue

    if GEMINI_API_KEY:
        try:
            result = await _call_gemini_direct(text)
            logger.info("Analysis succeeded via direct Gemini API")
            return result
        except Exception as e:
            logger.error(f"Direct Gemini also failed: {e}")

    raise RuntimeError(
        "All LLM options exhausted. Check OPENROUTER_API_KEY or GEMINI_API_KEY."
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
        "max_tokens": 1000,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)

        if not resp.is_success:
            logger.error(f"OpenRouter {resp.status_code} for {model}: {resp.text[:300]}")
            resp.raise_for_status()

        data = resp.json()

    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if content is None:
        raise ValueError(f"Model {model} returned None content")

    raw = content.strip()
    logger.info(f"[{model}] raw response: {raw[:200]}")
    return _parse_llm_response(raw)


async def _call_gemini_direct(text: str) -> dict[str, Any]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    full_prompt = f"{SYSTEM_PROMPT}\n\n{_build_user_prompt(text)}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        if not resp.is_success:
            logger.error(f"Gemini direct {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
        data = resp.json()

    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    logger.info(f"[Gemini direct] raw response: {raw[:200]}")
    return _parse_llm_response(raw)
