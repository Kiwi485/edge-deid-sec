FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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
RUN pip install --no-cache-dir -r requirements.txt

ARG INSTALL_TFLITE=0
RUN if [ "$INSTALL_TFLITE" = "1" ]; then pip install --no-cache-dir ai-edge-litert==1.4.0; fi

# 再把專案程式碼放進容器
COPY . .

# 預設啟動 extraction service；compose 會依服務覆蓋 command。
CMD ["python", "src/services/extraction_service.py"]
