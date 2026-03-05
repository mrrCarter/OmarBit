FROM python:3.12-slim@sha256:2be8daddbb6e8795a65c0a28e04222aa54d4a6ab2ac0b043a1d8fe699b0f5230

RUN apt-get update && \
    apt-get install -y --no-install-recommends stockfish=15.1+ds-1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-locked.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-locked.txt

RUN useradd --create-home --shell /bin/bash appuser
COPY server.py /app/server.py
WORKDIR /app
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
