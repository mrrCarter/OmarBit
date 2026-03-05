FROM python:3.12-slim@sha256:af4e85f1f51b24e04e2bbd8e60cc564e5c528daca72c76e03a474c22dba32b4e AS base

WORKDIR /app

RUN adduser --disabled-password --no-create-home appuser

COPY requirements-locked.txt .
RUN pip install --no-cache-dir -r requirements-locked.txt

COPY . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
