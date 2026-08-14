# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY features.yaml .
COPY src ./src
COPY data ./data
ENV PYTHONPATH=/app/src
ENV PORT=8080
ENV BOOK_PATH=/data/client_book.json
ENV MARKET_PATH=/data/market_data.json
ENV DATA_DIR=/tmp/valura
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "valura_arena.app:app", "--host", "0.0.0.0", "--port", "8080"]
