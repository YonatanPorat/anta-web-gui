FROM python:3.11-slim

RUN pip install --no-cache-dir "anta[cli]==1.10.0" streamlit pandas pyyaml

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY inventory.yml entrypoint.sh app.py ./
RUN mkdir -p /app/data && chmod +x entrypoint.sh && chown -R appuser:appuser /app

USER appuser

# Mount a volume here (see restart.sh) so settings.json survives container
# rebuilds/redeploys instead of resetting to defaults every time.
VOLUME ["/app/data"]

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]