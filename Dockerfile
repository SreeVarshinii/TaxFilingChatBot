FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for psycopg2, pdfplumber, and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Chainlit port
EXPOSE 8000

# Run Chainlit
CMD ["chainlit", "run", "app.py", "-w", "--port", "8000", "--host", "0.0.0.0"]
