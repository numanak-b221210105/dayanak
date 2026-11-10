FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DAYANAK_DATA_DIR=/data

COPY pyproject.toml README.md ./
COPY src ./src
COPY samples ./samples
RUN pip install --no-cache-dir -e .

RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser
VOLUME /data

EXPOSE 8100
CMD ["uvicorn", "dayanak.api:app", "--host", "0.0.0.0", "--port", "8100"]
