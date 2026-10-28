FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib

# 安裝 OpenCV 需要的系統相依套件（含 libxcb1 等）
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 先安裝專案需要的 Python 套件
COPY requirements.txt ./
RUN --mount=type=cache,target=/tmp/.cache/pip pip install --default-timeout=300 --retries 10 -r requirements.txt

ARG INSTALL_TFLITE=0
RUN --mount=type=cache,target=/tmp/.cache/pip if [ "$INSTALL_TFLITE" = "1" ]; then pip install --default-timeout=300 --retries 10 ai-edge-litert==1.4.0; fi

# 再把專案程式碼放進容器
COPY . .

# CIS 4.7：最後移除 setuid/setgid，容器以非 root 執行且不需要提權工具
RUN groupadd --gid 10001 edge-deid \
    && useradd --uid 10001 --gid 10001 --no-create-home edge-deid \
    && mkdir -p /app/data/out /app/logs /app/evidence /app/docs /run/edge-deid \
    && chown 10001:10001 /run/edge-deid \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} +

USER 10001:10001

# CIS 4.5：基本存活檢查（唯讀根目錄下 /tmp tmpfs 可寫入）；compose 會依服務覆蓋成更具體的檢查。
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import tempfile; tempfile.TemporaryFile().close()"]

# 預設啟動 extraction service；compose 會依服務覆蓋 command。
CMD ["python", "src/services/extraction_service.py"]
