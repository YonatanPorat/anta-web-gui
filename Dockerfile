FROM python:3.11-slim

RUN pip install --no-cache-dir --upgrade "anta[cli]" streamlit pandas pyyaml

WORKDIR /app

COPY inventory.yml entrypoint.sh app.py ./
RUN chmod +x entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]