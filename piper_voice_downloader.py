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
    quality: str  # small, medium, large
    onnx_url: str
    json_url: str
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None


class PiperVoiceDownloader:
    """Загрузчик голосов Piper TTS из Hugging Face"""
    
    HF_BASE_URL = "https://huggingface.co"
    
    # Прямые ссылки на русские голоса (Denis, Dmitry и Irina - medium)
    RUSSIAN_VOICES = [
        {
            "name": "ru_RU_denis_medium",
            "display_name": "Денис",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx.json"
        },
        {
            "name": "ru_RU_dmitry_medium",
            "display_name": "Дмитрий",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitry/medium/ru_RU-dmitry-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitry/medium/ru_RU-dmitry-medium.onnx.json"
        },
        {
            "name": "ru_RU_irina_medium",
            "display_name": "Ирина",
            "quality": "medium",
            "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx",
            "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json"
        },
    ]
    
    def __init__(self, voices_dir: Path = None):
        """
        Инициализация загрузчика

        Args:
            voices_dir: директория для сохранения голосов
        """
        from config import Config
        self.voices_dir = voices_dir or Config._get_config_dir() / 'voices'
        self.voices_dir.mkdir(parents=True, exist_ok=True)
    
    def get_available_voices(self) -> List[PiperVoiceInfo]:
        """
        Получает список доступных голосов
        
        Returns:
            Список информации о голосах
        """
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
        """Проверяет, существует ли голос уже локально (поддержка плоской и вложенной структуры)"""
        # Вложенная структура: voices_dir/ru_RU_irina_medium/ru_RU_irina_medium.onnx
        voice_dir = self.voices_dir / voice_name
        if voice_dir.exists():
            onnx_file = voice_dir / f"{voice_name}.onnx"
            json_file = voice_dir / f"{voice_name}.onnx.json"
            if onnx_file.exists() and json_file.exists():
                if onnx_file.stat().st_size > 0 and json_file.stat().st_size > 0:
                    return True
        
        # Плоская структура: voices_dir/ru_RU-irina-medium.onnx
        # Пробуем разные варианты имени
        for name_variant in [
            voice_name.replace('_', '-'),  # ru_RU-irina-medium
            voice_name.replace('-', '_'),  # ru_RU_irina_medium
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
        """
        Скачивает голосовую модель (плоская структура: voices_dir/ru_RU-irina-medium.onnx)

        Args:
            voice: информация о голосе
            progress_callback: callback для обновления прогресса ( downloaded, total)
            status_callback: callback для обновления статуса

        Returns:
            True если успешно
        """
        # Плоская структура: ru_RU-irina-medium.onnx
        voice_name = voice.name.replace('_', '-')  # ru_RU_denis_medium → ru_RU-denis-medium
        onnx_path = self.voices_dir / f"{voice_name}.onnx"
        json_path = self.voices_dir / f"{voice_name}.onnx.json"
        
        try:
            # Скачиваем .onnx файл
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
            
            # Скачиваем .json файл
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
        """
        Скачивает файл с URL
        
        Args:
            url: URL файла
            dest_path: путь для сохранения
            progress_callback: callback прогресса
            status_callback: callback статуса
            
        Returns:
            True если успешно
        """
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            return True
            
        except Exception as e:
            if status_callback:
                status_callback(f"Ошибка: {str(e)}")
            return False
    
    def get_local_voices(self) -> List[dict]:
        """
        Получает список локально установленных голосов (плоская структура)

        Returns:
            Список голосов с информацией
        """
        voices = []

        if not self.voices_dir.exists():
            return voices

        # Плоская структура: *.onnx файлы напрямую в voices_dir
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
        Удаляет голос (плоская структура)

        Args:
            voice_id: идентификатор голоса

        Returns:
            True если успешно
        """
        try:
            # Плоская структура
            onnx_file = self.voices_dir / f"{voice_id}.onnx"
            json_file = self.voices_dir / f"{voice_id}.onnx.json"
            
            deleted = False
            if onnx_file.exists():
                onnx_file.unlink()
                deleted = True
            if json_file.exists():
                json_file.unlink()
                deleted = True
            
            return deleted
        except Exception:
            return False


class DownloadWorker(threading.Thread):
    """Воркер для загрузки голосов в отдельном потоке"""
    
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
        """Выполняет загрузку"""
        self.success = self.downloader.download_voice(
            self.voice,
            self.progress_callback,
            self.status_callback
        )
        if self.finished_callback:
            self.finished_callback(self.success)
