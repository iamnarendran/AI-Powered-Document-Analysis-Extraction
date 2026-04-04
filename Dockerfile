FROM python:3.10-slim

WORKDIR /app

# Install system deps + Tesseract via apt (reliable, no wget timeouts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-tam \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 10000

# src/main.py → must be called as src.main:app from WORKDIR /app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "10000"]
