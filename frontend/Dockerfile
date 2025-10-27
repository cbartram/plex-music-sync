FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
COPY server/main.py .
COPY dist/ /app/static/

RUN chmod -R 755 /app/static &&  \
    pip install --no-cache-dir -r requirements.txt && \
    pip install spotdl && \
    mkdir -p /music

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]