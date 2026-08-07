ARG BUILD_FROM
FROM ${BUILD_FROM}
ENV LANG=C.UTF-8 PLATFORMIO_CORE_DIR=/data/platformio
RUN apt-get update && apt-get install -y --no-install-recommends bash git curl ca-certificates build-essential libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/esp_manager
COPY requirements.txt .
RUN python3 -m venv venv && . venv/bin/activate && pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir platformio
COPY app app
RUN python3 app/patch_v052.py && rm app/patch_v052.py
RUN python3 app/patch_v053.py && rm app/patch_v053.py
COPY run.sh /run.sh
RUN chmod +x /run.sh
EXPOSE 8099
CMD ["/run.sh"]
