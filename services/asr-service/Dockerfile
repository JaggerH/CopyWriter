# ASR语音识别服务 Dockerfile (NVIDIA NGC - 最高性能)
# 使用NVIDIA官方优化的PyTorch容器，支持CUDA 12.8
FROM nvcr.io/nvidia/pytorch:24.12-py3

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=/app
ENV MODEL_CACHE_DIR=/app/models

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 首先安装音频处理相关依赖
RUN pip install torchaudio soundfile librosa --extra-index-url https://download.pytorch.org/whl/cu124

# 然后安装其他应用依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/media/{raw,audio,text} /app/models

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]