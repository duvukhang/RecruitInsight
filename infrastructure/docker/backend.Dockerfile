FROM python:3.11.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend/src:/app JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl procps tini && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock /tmp/requirements.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 --retries 10 pip==26.2.1 && pip install --timeout 120 --retries 10 -r /tmp/requirements.lock && pip check
RUN groupadd -g 10001 recruitment && useradd -u 10001 -g recruitment -m recruitment && mkdir -p /data/uploads /data/artifacts /data/events /data/checkpoints /data/backups && chown -R recruitment:recruitment /data
COPY backend /app/backend
COPY workers /app/workers
COPY bigdata /app/bigdata
COPY machine_learning /app/machine_learning
COPY tests /app/tests
COPY scripts /app/scripts
COPY pytest.ini /app/pytest.ini
USER recruitment
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "recruitment.main:app", "--host", "0.0.0.0", "--port", "8000"]
