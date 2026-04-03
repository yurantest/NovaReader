"""
Edge TTS client.
ИСПРАВЛЕНИЯ:
  - Убран дублирующий on_finish_callback: все завершения идут через _sentence_callback
  - _finish() больше НЕ вызывает on_finish_callback (это вызывало двойной ttsNext)
  - prepare_sentence() вместо паттерна "if not player.is_playing: player.start(cb)"
  - stop() корректно инкрементирует generation через clear_queue
"""
import asyncio
import subprocess
import threading
import time
import sys
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from .base import TTSClient

try:
    import edge_tts
    EDGE_AVAILABLE = True
except ImportError:
    EDGE_AVAILABLE = False
    print("[EdgeTTS] Модуль edge-tts не установлен. Установите: pip install edge-tts")


class EdgeClient(TTSClient):
    """Клиент для Edge TTS с полной поддержкой голосов"""

    RUSSIAN_VOICES = [
        {"id": "ru-RU-DariyaNeural",   "name": "Дария (женский)",    "gender": "Female"},
        {"id": "ru-RU-SvetlanaNeural", "name": "Светлана (женский)", "gender": "Female"},
        {"id": "ru-RU-CatherineNeural","name": "Екатерина (женский)","gender": "Female"},
        {"id": "ru-RU-MikhailNeural",  "name": "Михаил (мужской)",   "gender": "Male"},
        {"id": "ru-RU-DmitryNeural",   "name": "Дмитрий (мужской)",  "gender": "Male"},
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_voice = config.get('edge_tts_voice', 'ru-RU-DariyaNeural')
        self.current_rate = config.get('tts_rate', 1.0)
        self._lock = threading.Lock()
        self._loop = None
        self._thread = None
        self._available = EDGE_AVAILABLE
        self._stop_flag = False

        # БАГ-ФИКС: один callback — _sentence_callback.
        # on_finish_callback из базового класса больше НЕ используется для TTS-цепочки.
        self._sentence_callback: Optional[Callable] = None
        self._finished_called = False
        self._current_future = None  # Future текущей корутины — для отмены при stop()

        if self._available:
            # Не запускаем event loop сразу — только при первом вызове speak()
            # Это экономит ~5 MB и один фоновый поток если Edge никогда не используется
            print("[EdgeTTS] ✅ Edge TTS готов к работе (event loop запустится при первом использовании)")

    def _start_event_loop(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _ensure_loop(self):
        """Запустить asyncio event loop при первом реальном использовании."""
        if self._loop is None:
            self._start_event_loop()
            print("[EdgeTTS] 🔁 Event loop запущен (lazy init)")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def name(self) -> str:
        return "Edge"

    def speak(self, text: str, callback: Optional[Callable] = None) -> bool:
        # Сброс флагов для нового предложения
        self._stop_flag = False
        self._finished_called = False

        if not self._available:
            print("[EdgeTTS] ❌ Edge TTS не доступен")
            if callback:
                threading.Timer(0.1, callback).start()
            return False

        # Гарантируем что event loop запущен (lazy init)
        self._ensure_loop()

        if not text or not text.strip():
            print("[EdgeTTS] Пустой текст → callback")
            if callback:
                threading.Timer(0.1, callback).start()
            return True

        with self._lock:
            if self.is_speaking:
                self.stop()
                time.sleep(0.05)

            # БАГ-ФИКС: сохраняем callback ТОЛЬКО в _sentence_callback
            # (раньше дублировалось в on_finish_callback → двойной вызов)
            self._sentence_callback = callback
            self.is_speaking = True

        print(f"[EdgeTTS] Озвучивание: {self.current_voice} | {text[:60]}")
        future = asyncio.run_coroutine_threadsafe(
            self._speak_async(text),
            self._loop
        )
        self._current_future = future
        return True

    async def _speak_async(self, text: str):
        """Синтез речи: MP3 → PCM → AudioPlayer. Callback вызывается из AudioPlayer."""
        print(f"[EdgeTTS] === СИНТЕЗ ===")
        try:
            communicate = edge_tts.Communicate(
                text,
                self.current_voice,
                rate=f"{int((self.current_rate - 1.0) * 100):+d}%"
            )

            mp3_data = b''
            chunk_count = 0
            async for chunk in communicate.stream():
                if self._stop_flag:
                    print("[EdgeTTS] ⚠️ Прервано")
                    return
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]
                    chunk_count += 1

            print(f"[EdgeTTS] MP3: {chunk_count} чанков, {len(mp3_data)} байт")

            if not mp3_data:
                print("[EdgeTTS] ⚠️ Нет аудио данных → _on_audio_finished")
                self._on_audio_finished()
                return

            # Получаем AudioPlayer (импорт уже сделан при инициализации)
            from audio_player import get_audio_player
            player = get_audio_player()

            # БАГ-ФИКС: prepare_sentence() устанавливает callback и сбрасывает счётчики
            # для КАЖДОГО предложения, даже если поток уже запущен.
            player.prepare_sentence(self._on_audio_finished)

            # Декодируем MP3 → PCM
            print("[EdgeTTS] Декодирование MP3 → PCM...")
            pcm_data = self._decode_mp3_to_pcm(mp3_data)
            mp3_data = None  # освобождаем память — больше не нужен
            print(f"[EdgeTTS] PCM: {len(pcm_data)} байт")

            if self._stop_flag:
                print("[EdgeTTS] ⚠️ Прервано после декодирования")
                return

            if pcm_data and len(pcm_data) > 0:
                player.play_chunk(pcm_data, is_last=True)
                print("[EdgeTTS] Ждём callback из AudioPlayer...")
            else:
                print("[EdgeTTS] ⚠️ PCM пуст → _on_audio_finished")
                self._on_audio_finished()

        except Exception as e:
            print(f"[EdgeTTS] ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self._on_audio_finished()

    @staticmethod
    def _find_ffmpeg() -> str:
        """Ищет ffmpeg: рядом с exe → рядом с этим файлом → в PATH."""
        import sys, shutil
        from pathlib import Path
        if getattr(sys, 'frozen', False):
            p = Path(sys.executable).parent / ('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
            if p.exists():
                return str(p)
        for base in [Path(__file__).parent, Path(__file__).parent.parent]:
            p = base / ('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
            if p.exists():
                return str(p)
        return shutil.which('ffmpeg') or 'ffmpeg'

    def _decode_mp3_to_pcm(self, mp3_data: bytes) -> bytes:
        """Декодировать MP3 в PCM 16-bit 22050 Hz mono через ffmpeg."""
        try:
            cmd = [
                self._find_ffmpeg(), '-i', 'pipe:0',
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', '22050', '-ac', '1',
                'pipe:1',
            ]
            kwargs = {}
            if sys.platform == 'win32':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = si
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs,
            )
            pcm_data, stderr = proc.communicate(input=mp3_data, timeout=60)
            if proc.returncode != 0:
                err = stderr.decode('utf-8', errors='replace')[:1000]
                print(f"[EdgeTTS] ffmpeg error: {err}")
                return b''
            return pcm_data
        except subprocess.TimeoutExpired:
            print("[EdgeTTS] ffmpeg timeout")
            return b''
        except Exception as e:
            print(f"[EdgeTTS] decode error: {e}")
            return b''


    def _on_audio_finished(self):
        """
        Вызывается AudioPlayer ПОСЛЕ физического завершения воспроизведения.
        БАГ-ФИКС: защита _finished_called + вызов ТОЛЬКО _sentence_callback.
        Раньше ещё вызывался _finish() → on_finish_callback → двойной ttsNext.
        """
        if self._finished_called:
            print("[EdgeTTS] ⚠ _on_audio_finished уже вызывался, игнорируем")
            return

        self._finished_called = True
        print("[EdgeTTS] === AUDIO FINISHED ===")

        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None

        if callback:
            print("[EdgeTTS] → вызов callback (ttsNext)")
            # Вызываем напрямую (AudioPlayer уже добавил задержку 150ms через Timer)
            try:
                callback()
            except Exception as e:
                print(f"[EdgeTTS] ❌ Ошибка в callback: {e}")
        else:
            print("[EdgeTTS] ⚠ callback=None (предложение уже завершено)")

    def stop(self):
        """Немедленная остановка."""
        self._stop_flag = True

        # Отменяем текущую корутину синтеза если она ещё выполняется
        future = self._current_future
        if future and not future.done():
            future.cancel()
        self._current_future = None

        with self._lock:
            self.is_speaking = False
            self._sentence_callback = None
            self.on_finish_callback = None
            self._finished_called = False

        # Очищаем очередь AudioPlayer (заодно инкрементирует generation)
        try:
            from audio_player import get_audio_player
            player = get_audio_player()
            player.clear_queue()
        except Exception:
            pass

    def get_voices(self) -> List[Dict[str, Any]]:
        voices = []
        if not self._available:
            return voices
        for v in self.RUSSIAN_VOICES:
            voices.append({
                'id':     v['id'],
                'name':   v['name'],
                'engine': 'edge',
                'gender': v['gender'],
                'local':  False,
            })
        return voices

    def set_voice(self, voice_id: str):
        print(f"[EdgeTTS] Голос: {voice_id}")
        self.current_voice = voice_id
        self.config.set('edge_tts_voice', voice_id)

    def set_rate(self, rate: float):
        self.current_rate = rate
        self.config.set('tts_rate', rate)
