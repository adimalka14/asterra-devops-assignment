FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for GeoPandas and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

CMD ["python", "main.py"]