FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install openenv-core>=0.2.2 fastapi uvicorn pydantic

COPY . .
# 7860 is standard port for HuggingFace Spaces
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
