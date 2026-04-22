import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, field_validator


app = FastAPI(title="Hamlet TTS Service", version="1.0.0")


API_TOKEN = os.getenv("API_TOKEN", "")
PIPER_BIN = os.getenv("PIPER_BIN", "/opt/piper/piper")
MODELS_DIR = Path(os.getenv("MODELS_DIR", "/app/models"))
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "pt_BR-faber-medium")
DEFAULT_FORMAT = os.getenv("DEFAULT_FORMAT", "mp3")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field(default=DEFAULT_VOICE, min_length=3, max_length=120)
    length_scale: float = Field(default=1.0, ge=0.2, le=3.0)
    format: str = Field(default=DEFAULT_FORMAT)

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        fmt = value.lower()
        if fmt not in {"wav", "mp3"}:
            raise ValueError("format must be 'wav' or 'mp3'")
        return fmt


def verify_bearer_token(authorization: str = Header(default="")) -> None:
    if not API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server auth token is not configured",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if token != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token",
        )


def _delete_file_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        # Avoid breaking response lifecycle on cleanup failures.
        pass


def _run_piper(text: str, model_path: Path, output_wav: Path, length_scale: float) -> None:
    cmd = [
        PIPER_BIN,
        "--model",
        str(model_path),
        "--output_file",
        str(output_wav),
        "--length_scale",
        str(length_scale),
    ]

    try:
        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="TTS generation timed out",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Piper binary not found at {PIPER_BIN}",
        ) from exc

    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Piper generation failed: {result.stderr.strip() or 'unknown error'}",
        )


def _wav_to_mp3(input_wav: Path, output_mp3: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_wav),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_mp3),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Audio conversion timed out",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ffmpeg binary not found in container",
        ) from exc

    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MP3 conversion failed: {result.stderr.strip() or 'unknown error'}",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/tts")
def tts(payload: TTSRequest, _: None = Depends(verify_bearer_token)) -> FileResponse:
    model_path = MODELS_DIR / f"{payload.voice}.onnx"
    if not model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voice model not found: {payload.voice}",
        )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wav_path = Path(tmp_wav.name)

    _run_piper(
        text=payload.text.strip(),
        model_path=model_path,
        output_wav=wav_path,
        length_scale=payload.length_scale,
    )

    if payload.format == "wav":
        return FileResponse(
            path=wav_path,
            media_type="audio/wav",
            filename=f"{payload.voice}.wav",
            background=BackgroundTask(_delete_file_if_exists, wav_path),
        )

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
        mp3_path = Path(tmp_mp3.name)
    _wav_to_mp3(wav_path, mp3_path)
    _delete_file_if_exists(wav_path)

    return FileResponse(
        path=mp3_path,
        media_type="audio/mpeg",
        filename=f"{payload.voice}.mp3",
        background=BackgroundTask(_delete_file_if_exists, mp3_path),
    )
