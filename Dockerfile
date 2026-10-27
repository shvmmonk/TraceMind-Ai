FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 PUBLIC_DEMO=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser engine/ ./engine/
COPY --chown=appuser:appuser frontend/ ./frontend/
COPY --chown=appuser:appuser run_demo.py ./
RUN mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:'+__import__('os').getenv('PORT','8000')+'/api/health', timeout=3).close()" || exit 1
CMD ["python", "run_demo.py"]
