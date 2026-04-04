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