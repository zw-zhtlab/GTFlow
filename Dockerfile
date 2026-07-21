
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system gtflow \
    && adduser --system --ingroup gtflow --home /home/gtflow gtflow

WORKDIR /app
COPY pyproject.toml LICENSE README.md ./
COPY gtflow ./gtflow
RUN python -m pip install . \
    && chown -R gtflow:gtflow /app /home/gtflow

EXPOSE 8501
USER gtflow
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/', timeout=2).read(1)"
CMD ["gtflow-ui", "--host", "0.0.0.0", "--port", "8501", "--no-browser"]
