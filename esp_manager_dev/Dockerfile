ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}
ENV LANG=C.UTF-8 PLATFORMIO_CORE_DIR=/data/platformio PYTHONPATH=/opt/esp_manager
RUN apt-get update && apt-get install -y --no-install-recommends bash git curl ca-certificates build-essential libffi-dev libssl-dev nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/esp_manager
COPY requirements.txt .
RUN python3 -m venv venv && . venv/bin/activate && pip install --no-cache-dir -r requirements.txt platformio
COPY app app
COPY tests tests
COPY pytest.ini pytest.ini
RUN python3 -m py_compile app/*.py
RUN node --check app/static/app.js && node --check app/static/hardware.js
RUN . venv/bin/activate && pytest -q tests/test_contract.py
COPY run.sh /run.sh
RUN chmod +x /run.sh
EXPOSE 8100
CMD ["/run.sh"]
