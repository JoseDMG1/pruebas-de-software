FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
CMD ["uvicorn", "rag_service.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
