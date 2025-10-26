FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY ./bin .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p /music

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]