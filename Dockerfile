FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/opt/browsers AUDIT_DATA_DIR=/data PORT=8000
WORKDIR /app
COPY requirements-service.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-service.txt && python -m playwright install --with-deps chromium && chmod -R a+rX /opt/browsers
RUN useradd --create-home auditor && mkdir /data && chown auditor:auditor /data
COPY --chown=auditor:auditor audit.py media_audit.py report.py runner.py job_support.py service.py checklist.json ./
COPY --chown=auditor:auditor docs ./docs
USER auditor
EXPOSE 8000
CMD ["sh", "-c", "uvicorn service:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 30"]
