# -*- coding: utf-8 -*-
"""
Загрузка голосов Piper TTS из репозитория Hugging Face
"""
import os
import json
import requests
import threading
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass


@dataclass
class PiperVoiceInfo:
    """Информация о голосе Piper"""
    name: str
    quality: str
    onnx_url: str
    json_url: str
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None


class PiperVoiceDownloader:
    """Загрузчик голосов Piper TTS из Hugging Face"""

    HF_BASE_URL = "https://huggingface.co"

    RUSSIAN_VOICES = [
        {
            "name": "ru_RU_denis_medium",
            "display_name": "Денис",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx.json"
        },
        {
            "name": "ru_RU_dmitri_medium",
            "display_name": "Дмитрий",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json"
        },
        {
            "name": "ru_RU_irina_medium",
            "display_name": "Ирина",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json"
        },
        {
            "name": "eu_ES-antton-medium",
            "display_name": "Antton ES",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/eu/eu_ES/antton/medium/eu_ES-antton-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/eu/eu_ES/antton/medium/eu_ES-antton-medium.onnx.json"
        },
        {
            "name": "eu_ES-maider-medium",
            "display_name": "Maider",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/eu/eu_ES/maider/medium/eu_ES-maider-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/eu/eu_ES/maider/medium/eu_ES-maider-medium.onnx.json"
        },
        {
            "name": "de_DE-mls-medium",
            "display_name": "Mls DE",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/mls/medium/de_DE-mls-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/mls/medium/de_DE-mls-medium.onnx.json"
        },
        {
            "name": "de_DE-thorsten-high",
            "display_name": "Thorsten",
            "quality": "high",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json"
        },
    ]

    def __init__(self, voices_dir: Path = None):
        from config import Config
        self.voices_dir = voices_dir or Config._get_config_dir() / 'voices'
        self.voices_dir.mkdir(parents=True, exist_ok=True)

    def get_available_voices(self) -> List[PiperVoiceInfo]:
        voices = []
        for voice_data in self.RUSSIAN_VOICES:
            voice = PiperVoiceInfo(
                name=voice_data["name"],
                quality=voice_data["quality"],
                onnx_url=voice_data["onnx"],
                json_url=voice_data["json"]
            )
            voices.append(voice)
        return voices

    def check_voice_exists(self, voice_name: str) -> bool:
        voice_dir = self.voices_dir / voice_name
        if voice_dir.exists():
            onnx_file = voice_dir / f"{voice_name}.onnx"
            json_file = voice_dir / f"{voice_name}.onnx.json"
            if onnx_file.exists() and json_file.exists():
                if onnx_file.stat().st_size > 0 and json_file.stat().st_size > 0:
                    return True

        for name_variant in [
            voice_name.replace('_', '-'),
            voice_name.replace('-', '_'),
        ]:
            onnx_file = self.voices_dir / f"{name_variant}.onnx"
            json_file = self.voices_dir / f"{name_variant}.onnx.json"
            if onnx_file.exists() and json_file.exists():
                if onnx_file.stat().st_size > 0 and json_file.stat().st_size > 0:
                    return True

        return False

    def download_voice(
        self,
        voice: PiperVoiceInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        voice_name = voice.name.replace('_', '-')
        onnx_path = self.voices_dir / f"{voice_name}.onnx"
        json_path = self.voices_dir / f"{voice_name}.onnx.json"

        try:
            if status_callback:
                status_callback(f"Скачивание {voice.name}.onnx...")

            success = self._download_file(
                voice.onnx_url,
                str(onnx_path),
                progress_callback,
                status_callback
            )

            if not success:
                return False

            if status_callback:
                status_callback(f"Скачивание {voice.name}.onnx.json...")

            success = self._download_file(
                voice.json_url,
                str(json_path),
                None,
                status_callback
            )

            if success and status_callback:
                status_callback(f"Голос {voice.name} успешно загружен!")

            return success
        except Exception as e:
            if status_callback:
                status_callback(f"Ошибка загрузки {voice.name}: {str(e)}")
            return False

    def _download_file(
        self,
        url: str,
        dest_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_pct = -1

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            pct = int(downloaded * 100 / total_size)
                            if pct != last_pct:
                                last_pct = pct
                                progress_callback(downloaded, total_size)

            return True
        except Exception as e:
            if status_callback:
                status_callback(f"Ошибка: {str(e)}")
            return False

    def get_local_voices(self) -> List[dict]:
        voices = []
        if not self.voices_dir.exists():
            return voices

        for onnx_file in self.voices_dir.glob('*.onnx'):
            voice_id = onnx_file.stem
            json_file = onnx_file.with_suffix('.onnx.json')
            if json_file.exists():
                size_mb = onnx_file.stat().st_size / (1024 * 1024)
                voices.append({
                    'id': voice_id,
                    'name': voice_id.replace('ru_RU-', '').replace('_', ' ').replace('-', ' ').title(),
                    'path': str(self.voices_dir),
                    'size_mb': round(size_mb, 2),
                    'onnx_path': str(onnx_file),
                    'json_path': str(json_file)
                })

        return voices

    def delete_voice(self, voice_id: str) -> bool:
        """
        Удаляет голос. Пробует несколько вариантов имени файла:
          - voice_id из UI: ru_RU_denis_medium
          - при скачивании сохраняется: ru_RU-denis-medium.onnx
        """
        try:
            deleted = False

            # 1. Вариант с дефисами (как реально сохраняется)
            name_with_dashes = voice_id.replace('_', '-')
            onnx_file = self.voices_dir / f"{name_with_dashes}.onnx"
            json_file = self.voices_dir / f"{name_with_dashes}.onnx.json"

            if onnx_file.exists():
                onnx_file.unlink()
                deleted = True
                print(f"[PiperVoiceDownloader] Удалён: {onnx_file}")
            if json_file.exists():
                json_file.unlink()
                deleted = True
                print(f"[PiperVoiceDownloader] Удалён: {json_file}")

            # 2. Вариант с подчёркиваниями (на всякий случай)
            if voice_id != name_with_dashes:
                onnx_file2 = self.voices_dir / f"{voice_id}.onnx"
                json_file2 = self.voices_dir / f"{voice_id}.onnx.json"

                if onnx_file2.exists():
                    onnx_file2.unlink()
                    deleted = True
                    print(f"[PiperVoiceDownloader] Удалён: {onnx_file2}")
                if json_file2.exists():
                    json_file2.unlink()
                    deleted = True
                    print(f"[PiperVoiceDownloader] Удалён: {json_file2}")

            if not deleted:
                print(f"[PiperVoiceDownloader] Голос не найден на диске: {voice_id}")

            return deleted
        except Exception as e:
            print(f"[PiperVoiceDownloader] Ошибка удаления {voice_id}: {e}")
            return False


class DownloadWorker(threading.Thread):
    def __init__(
        self,
        downloader: PiperVoiceDownloader,
        voice: PiperVoiceInfo,
        progress_callback: Callable[[int, int], None],
        status_callback: Callable[[str], None],
        finished_callback: Callable[[bool], None]
    ):
        super().__init__()
        self.downloader = downloader
        self.voice = voice
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.finished_callback = finished_callback
        self.success = False

    def run(self):
        self.success = self.downloader.download_voice(
            self.voice,
            self.progress_callback,
            self.status_callback
        )
        if self.finished_callback:
            self.finished_callback(self.success)
