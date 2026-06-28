FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.3

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

CMD ["python3", "app.py"]
