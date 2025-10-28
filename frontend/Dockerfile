FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/main.py .
COPY dist/ ./static/

RUN chmod -R 755 /app/static

RUN --mount=type=secret,id=cookies \
    if [ -f /run/secrets/cookies ]; then \
        cat /run/secrets/cookies > /app/cookies.txt && \
        chmod 600 /app/cookies.txt && \
        echo "Cookies file created successfully"; \
    else \
        echo "Warning: No cookies secret provided"; \
    fi

RUN mkdir -p /music

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]