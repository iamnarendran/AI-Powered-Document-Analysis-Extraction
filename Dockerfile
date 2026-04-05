FROM python:3.10-bullseye

WORKDIR /app

# Install system dependencies (CLEAN + STABLE)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    wget \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create tessdata directory
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata

# Download languages (INCLUDING ENG — critical)
RUN wget -O /usr/share/tesseract-ocr/4.00/tessdata/eng.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata

RUN wget -O /usr/share/tesseract-ocr/4.00/tessdata/tam.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/tam.traineddata

RUN wget -O /usr/share/tesseract-ocr/4.00/tessdata/hin.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/hin.traineddata

ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
