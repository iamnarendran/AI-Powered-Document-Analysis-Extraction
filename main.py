import os
import base64
import logging
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from document_processor import extract_text
from ai_analyzer import analyze_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Document Analysis API started")
    yield
    logger.info("Document Analysis API shutting down")


app = FastAPI(
    title="Document Analysis API",
    description="AI-powered document analysis: extraction, summarization, entity recognition, sentiment analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY", "sk_track2_987654321")


# --- Auth ---
def verify_api_key(x_api_key: str = Header(..., description="Your secret API key")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key")
    return x_api_key


# --- Request / Response Models ---
class DocumentRequest(BaseModel):
    fileName: str
    fileType: str   # pdf | docx | image
    fileBase64: str

    class Config:
        json_schema_extra = {
            "example": {
                "fileName": "invoice.pdf",
                "fileType": "pdf",
                "fileBase64": "JVBERi0xLjQ..."
            }
        }


class EntitiesModel(BaseModel):
    names: list[str]
    dates: list[str]
    organizations: list[str]
    amounts: list[str]


class DocumentResponse(BaseModel):
    status: str
    fileName: str
    summary: str
    entities: EntitiesModel
    sentiment: str


# --- Routes ---
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Document Analysis API is running"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


@app.post(
    "/api/document-analyze",
    response_model=DocumentResponse,
    tags=["Analysis"],
    summary="Analyze a document (PDF, DOCX, or image)",
)
async def analyze(
    request: DocumentRequest,
    api_key: str = Depends(verify_api_key),
):
    logger.info(f"Processing file: {request.fileName} | type: {request.fileType}")

    # Validate file type
    allowed_types = {"pdf", "docx", "image"}
    if request.fileType.lower() not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported fileType '{request.fileType}'. Use: pdf, docx, image",
        )

    # Decode base64
    try:
        file_bytes = base64.b64decode(request.fileBase64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 encoding in fileBase64")

    # Extract text
    try:
        text = extract_text(file_bytes, request.fileType.lower())
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=422, detail=f"Text extraction failed: {str(e)}")

    if not text or len(text.strip()) < 10:
        raise HTTPException(status_code=422, detail="Could not extract meaningful text from the document")

    # AI Analysis
    try:
        result = await analyze_document(text)
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

    return {
        "status": "success",
        "fileName": request.fileName,
        **result,
    }
