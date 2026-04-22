FROM python:3.11-slim

# Evita prompts do debconf no build (Render/GitHub Actions).
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPER_VERSION=1.2.0

# Nao instalar ffmpeg via apt: puxa muitas libs (OpenGL, etc.) e o build no Render Free costuma falhar (OOM / timeout).
# Binario estatico pequeno so para conversao WAV -> MP3.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download em arquivo (evita pipe curl|tar falhar silenciosamente no Render).
RUN set -eux \
    && mkdir -p /tmp/ffstatic \
    && curl -fsSL --retry 8 --retry-delay 3 --connect-timeout 30 --max-time 900 \
        -A "HamletTTS-DockerBuild/1.0" \
        -o /tmp/ffmpeg-static.tar.xz \
        "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
    && tar -xJf /tmp/ffmpeg-static.tar.xz -C /tmp/ffstatic \
    && FFMPEG_BIN="$(find /tmp/ffstatic -maxdepth 4 -type f -name ffmpeg -print -quit)" \
    && test -n "${FFMPEG_BIN:-}" \
    && install -m 0755 "$FFMPEG_BIN" /usr/local/bin/ffmpeg \
    && rm -rf /tmp/ffstatic /tmp/ffmpeg-static.tar.xz \
    && ffmpeg -version | head -1

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
