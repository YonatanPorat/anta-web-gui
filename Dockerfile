FROM python:3.11-slim

# Added pyyaml for parsing yaml files dynamically
# Added --upgrade to ensure the latest versions of ANTA and Streamlit are pulled
RUN pip install --no-cache-dir --upgrade "anta[cli]" streamlit pandas pyyaml

WORKDIR /app

COPY inventory.yml catalog.yml entrypoint.sh app.py ./
RUN chmod +x entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]