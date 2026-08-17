FROM python:3.11-slim

RUN pip install --no-cache-dir --upgrade "anta[cli]" streamlit pandas pyyaml

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY inventory.yml entrypoint.sh app.py ./
RUN chmod +x entrypoint.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]