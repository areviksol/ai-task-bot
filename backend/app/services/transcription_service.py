
import io

import httpx
from openai import OpenAI

from app.core.config import get_settings


class TranscriptionError(Exception):
    pass


class TranscriptionService:
    MAX_AUDIO_BYTES = 20 * 1024 * 1024

    def __init__(self):
        self.settings = get_settings()

        self.client = OpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            timeout=60.0,
            max_retries=0,
        )

    def transcribe(self, file_id: str) -> str:
        audio = self._download_audio(file_id)

        audio_file = io.BytesIO(audio)
        audio_file.name = "voice.ogg"

        result = self.client.audio.transcriptions.create(
            model=self.settings.openai_transcription_model,
            file=audio_file,
        )

        text = result.text.strip()

        if not text:
            raise TranscriptionError(
                "Audio transcription returned empty text"
            )

        return text

    def _download_audio(self, file_id: str) -> bytes:
        token = (
            self.settings.telegram_bot_token
            .get_secret_value()
        )

        base_url = f"https://api.telegram.org/bot{token}"

        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{base_url}/getFile",
                params={"file_id": file_id},
            )
            response.raise_for_status()

            payload = response.json()

            if not payload.get("ok"):
                raise TranscriptionError(
                    "Telegram rejected file request"
                )

            file_data = payload["result"]

            if (
                file_data.get("file_size", 0)
                > self.MAX_AUDIO_BYTES
            ):
                raise TranscriptionError(
                    "Audio file exceeds maximum size"
                )

            file_path = file_data.get("file_path")

            if not file_path:
                raise TranscriptionError(
                    "Telegram file path missing"
                )

            file_url = (
                f"https://api.telegram.org/file/"
                f"bot{token}/{file_path}"
            )

            with client.stream("GET", file_url) as download:
                download.raise_for_status()
                content = bytearray()

                for chunk in download.iter_bytes():
                    content.extend(chunk)

                    if len(content) > self.MAX_AUDIO_BYTES:
                        raise TranscriptionError(
                            "Audio file exceeds maximum size"
                        )

        return bytes(content)
