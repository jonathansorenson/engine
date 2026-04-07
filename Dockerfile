FROM python:3.11-slim

WORKDIR /app

# System dependencies for pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy frontend (served by FastAPI at /engine)
COPY frontend/ /frontend/

# Create persistent upload directory
RUN mkdir -p /app/uploads && chmod 755 /app/uploads

EXPOSE 8000

# Production: gunicorn with uvicorn workers
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
