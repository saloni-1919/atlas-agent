FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY web/ ./web/
COPY sample_docs/ ./sample_docs/
ENV ATLAS_DB=/data/atlas.sqlite ATLAS_AI_PROVIDER=offline ATLAS_RETRIEVAL=lexical
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
