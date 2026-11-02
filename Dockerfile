FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Do NOT bake the key into the image. Pass it at runtime:
#   docker run -p 8000:8000 -e ODDS_API_KEY=yourkey beast
#   docker run -p 8000:8000 --env-file .env beast
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
