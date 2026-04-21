FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPER_VERSION=1.2.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Piper binary and runtime libraries.
RUN mkdir -p /opt/piper && \
    curl -fsSL "https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_linux_x86_64.tar.gz" \
    | tar -xz -C /opt/piper --strip-components=1 && \
    chmod +x /opt/piper/piper

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY app /app/app
COPY models /app/models

# Voce pode colocar arquivos .onnx em models/ via git; se nao existirem, baixa a voz padrao no build (necessario no Render sem LFS).
ARG DOWNLOAD_DEFAULT_VOICE=1
RUN if [ "$DOWNLOAD_DEFAULT_VOICE" = "1" ] && [ ! -s /app/models/pt_BR-faber-medium.onnx ]; then \
    echo "Downloading default Piper voice (pt_BR-faber-medium)..." && \
    curl -fsSL -o /app/models/pt_BR-faber-medium.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx" && \
    curl -fsSL -o /app/models/pt_BR-faber-medium.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"; \
    fi

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
