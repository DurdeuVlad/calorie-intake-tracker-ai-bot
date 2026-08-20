FROM python:3.11-slim AS build
WORKDIR /workspace
COPY pyproject.toml .
COPY app app
COPY alembic alembic
COPY alembic.ini .
COPY run.py .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim
RUN groupadd --system app && useradd --system --gid app app
WORKDIR /app
COPY --from=build /install /usr/local
COPY --chown=app:app app app
COPY --chown=app:app alembic alembic
COPY --chown=app:app alembic.ini .
COPY --chown=app:app run.py .
USER app
EXPOSE 8080
ENV MANAGEMENT_PORT=8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"MANAGEMENT_PORT\",\"8081\")}/health/readiness').read()" || exit 1
ENTRYPOINT ["python", "run.py"]
