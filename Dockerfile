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

# 再把專案程式碼放進容器
COPY . .

# 先預留 API port，可依需求調整
EXPOSE 8000

# 目前先用 placeholder 指令，之後換成真正 API 入口
CMD ["python", "mp_test.py"]
