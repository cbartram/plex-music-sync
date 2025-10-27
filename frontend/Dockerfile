FROM nikolaik/python-nodejs:python3.12-nodejs24

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
COPY server/main.py .
COPY package.json tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts index.html components.json eslint.config.js ./
COPY public/ ./public/
COPY src/ ./src/

RUN npm install && \
    npm run build && \
    mv /app/dist /app/static

RUN chmod -R 755 /app/static &&  \
    pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /music

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]