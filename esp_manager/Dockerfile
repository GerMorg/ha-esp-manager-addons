FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git curl build-essential && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir platformio fastapi uvicorn pyyaml python-multipart paho-mqtt
WORKDIR /app
COPY app /app
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000"]
