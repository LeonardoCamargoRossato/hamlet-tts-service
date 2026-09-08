<div align="center">

# Hamlet TTS Service

### FastAPI + Piper Speech Microservice

**A containerized text-to-speech backend that provides Portuguese voice generation for the Hamlet platform through a protected service layer.**

![Tier](https://img.shields.io/badge/Portfolio-Tier%20A-0A66C2?style=for-the-badge) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)

</div>

## Service Overview

This repository contains the dedicated TTS backend for Hamlet. The service isolates speech synthesis from the frontend and exposes a small authenticated HTTP API. Requests are expected to arrive through the Hamlet edge/service layer rather than directly from the browser.

## Architecture

```text
Hamlet Frontend
      ↓
Edge Function / Secure Service Layer
      ↓  Bearer token
FastAPI TTS Service
      ↓
Piper Speech Synthesis
      ↓
WAV ──→ optional FFmpeg conversion ──→ MP3
      ↓
Binary Audio Response
```

## Core Capabilities

- Protected `POST /tts` endpoint
- `GET /health` health check / prewarm endpoint
- Piper-based PT-BR speech synthesis
- WAV and MP3 output
- Configurable voice and synthesis parameters
- Dockerized runtime
- Render deployment blueprint
- Environment-based secrets/configuration

## API

### `GET /health`
Health check used for availability monitoring and prewarming.

### `POST /tts`

```json
{
  "text": "Text to narrate",
  "voice": "pt_BR-faber-medium",
  "length_scale": 1.0,
  "format": "mp3"
}
```

Authentication:

```text
Authorization: Bearer <API_TOKEN>
```

## Tech Stack

`Python` · `FastAPI` · `Piper TTS` · `FFmpeg` · `Docker` · `Docker Compose` · `Render`

## Local Development

```bash
cp .env.example .env
docker compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

## Configuration

Important environment variables include `API_TOKEN`, `DEFAULT_VOICE`, `DEFAULT_FORMAT`, `PIPER_TIMEOUT_SECONDS`, `FFMPEG_TIMEOUT_SECONDS`, `MODELS_DIR` and `MP3_BITRATE`.

Secrets should remain in environment configuration and must not be committed to source control.

## Deployment

The repository is prepared for a Docker-based Render deployment using the root `Dockerfile` and `render.yaml`. The service exposes `/health` for platform health checks and uses the provider-supplied `PORT` environment variable.

On sleeping/free infrastructure, the first request can experience a cold start. The architecture supports prewarming through `/health`; production workloads should use an always-on deployment tier when latency is important.

## Integration Notes

The calling edge layer must preserve the TTS response as binary data (`arrayBuffer` / byte stream). Treating MP3/WAV output as text or JSON will corrupt the audio payload.

## Engineering Perspective

This service demonstrates backend/API design, containerization, secret-based service authentication, media processing and separation of concerns within a larger full-stack product.

## Portfolio Classification

**Tier A — Featured Portfolio Project.** Selected as the backend/service counterpart to Hamlet, representing API engineering, containerization and production-oriented integration.

---

**Leonardo Camargo Rossato** · Developer & Solution Architect · AI, Data & Deep Tech
