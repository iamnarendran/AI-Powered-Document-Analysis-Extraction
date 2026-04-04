#[🗒️✨ AI-Powered-Document-Analysis-Extraction](https://docintel-ai.netlify.app/)

An AI-powered document processing API that extracts text, generates summaries, identifies entities, and classifies sentiment from PDF, DOCX, and image files.

Built for **GUVI Hackathon 2026 — Track 2: AI-Powered Document Analysis & Extraction**.

---

## Description

This API accepts a document (PDF, DOCX, or image) as a Base64-encoded string, extracts the text using specialized libraries, and sends it through a single optimized LLM call to produce:

- A **concise summary** of the document
- **Named entities** (people, dates, organizations, monetary amounts)
- **Sentiment classification** (Positive / Neutral / Negative)

### Strategy

1. **Text Extraction** — Format-specific libraries handle each type cleanly:
   - PDF → PyMuPDF (fast, accurate layout extraction)
   - DOCX → python-docx (paragraphs + table text)
   - Image → Tesseract OCR (English + Hindi language packs)

2. **Single-call AI Analysis** — One structured prompt to the LLM returns all three outputs (summary, entities, sentiment) as JSON. This keeps latency low (~2–3s) and cost minimal (~$0.003/doc).

3. **Dual LLM support** — Primary: Claude 3.5 Sonnet via OpenRouter. Fallback: Gemini 2.0 Flash via OpenRouter or direct Gemini API.

---

## Tech Stack

- **Framework:** FastAPI (async Python)
- **Document Processing:** PyMuPDF, python-docx, Tesseract OCR (via pytesseract)
- **AI Model:** Claude 3.5 Sonnet (primary) / Gemini 2.0 Flash (fallback) via OpenRouter
- **HTTP Client:** httpx (async)
- **Deployment:** Docker + Render

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/doc-analyzer.git
cd doc-analyzer
```

### 2. Install system dependencies

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tam
```

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set environment variables

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 5. Run the application

```bash
uvicorn src.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## API Usage

### Authentication

All requests require the header:
```
x-api-key: YOUR_API_KEY
```

### Endpoint

```
POST /api/document-analyze
```

### Request Body

```json
{
  "fileName": "invoice.pdf",
  "fileType": "pdf",
  "fileBase64": "<base64-encoded file content>"
}
```

`fileType` accepts: `pdf`, `docx`, `image`

### Example (cURL)

```bash
# Encode file to base64 first
BASE64=$(base64 -i your_file.pdf)

curl -X POST https://your-domain.onrender.com/api/document-analyze \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk_track2_987654321" \
  -d "{\"fileName\": \"test.pdf\", \"fileType\": \"pdf\", \"fileBase64\": \"$BASE64\"}"
```

### Success Response

```json
{
  "status": "success",
  "fileName": "invoice.pdf",
  "summary": "This document is an invoice issued by ABC Pvt Ltd to Ravi Kumar on 10 March 2026 for an amount of ₹10,000.",
  "entities": {
    "names": ["Ravi Kumar"],
    "dates": ["10 March 2026"],
    "organizations": ["ABC Pvt Ltd"],
    "amounts": ["₹10,000"]
  },
  "sentiment": "Neutral"
}
```

---

## Deployment (Render)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects the `Dockerfile`
5. Add environment variables in the Render dashboard:
   - `API_KEY`
   - `OPENROUTER_API_KEY`
   - `GEMINI_API_KEY` (optional)
6. Deploy — your public URL will be `https://doc-analyzer.onrender.com`

> **Tip:** Add a free UptimeRobot monitor pinging `/health` every 5 minutes to prevent Render's free tier from sleeping.

---

## Project Structure

```
doc-analyzer/
├── src/
├── __init__.py
├── main.py                # FastAPI app, routes, auth
├── document_processor.py  # PDF / DOCX / Image text extraction
├── ai_analyzer.py         # LLM call for summary, entities, sentiment
├── Dockerfile
├── render.yaml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
