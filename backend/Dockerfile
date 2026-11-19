# NEW 20 Nov 2026 (deep scan H4). The API container for Cloud Run (ADR-033).
#   docker build -t thutora-api backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LOG_FORMAT=json
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

RUN useradd --create-home thutora && chown -R thutora /app
USER thutora

# --proxy-headers: Cloud Run is reached only through Google's front end, so
# the learner's real address arrives in X-Forwarded-For. Without this every
# request looks like it comes from one proxy address, and the per-address
# login and sign-up limits would lock out whole schools at once.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips="*"
