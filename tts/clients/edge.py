#!/usr/bin/env python3
"""
Edge TTS client — живое чтение + запись в MP3 (AudioRecorder).

Живое чтение:
  speak() -> _speak_async(): edge_tts.Communicate.stream() собирает MP3-чанки
  и нативные WordBoundary-тайминги слов -> MP3 декодируется в PCM ->
  AudioPlayer. Тайминги слов уходят в _word_timing_callback для пословной
  подсветки, длительность — в _duration_callback.

Запись (AudioRecorder):
  record_chapter() / _record_edge(): вступление и текст главы синтезируются
  отдельными MP3 и склеиваются ffmpeg с паузой между ними. Работает и тогда,
  когда рекордер дёргает клиент напрямую, и когда использует свой код.
"""
import asyncio
import subprocess
import tempfile
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

# Пауза между вступлением (название книги) и текстом главы.
_INTRO_PAUSE_MS = 700


def _run_async(coro):
    """Запускает корутину даже из фонового (не главного) потока."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        finally:
            asyncio.set_event_loop(None)


class EdgeClient(TTSClient):
    """Клиент Edge TTS: живое чтение со слово-таймингами + запись в MP3."""

    RUSSIAN_VOICES = [
        {"id": "ru-RU-SvetlanaNeural", "name": "Светлана (женский)", "gender": "Female"},
        {"id": "ru-RU-DmitryNeural", "name": "Дмитрий (мужской)", "gender": "Male"},
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_voice = config.get('edge_tts_voice', 'ru-RU-DariyaNeural')
        self.current_rate = float(config.get('tts_rate', 1.0))
        # RLock — speak() может вызвать stop(), уже держа лок.
        self._lock = threading.RLock()
        self._loop = None
        self._thread = None
        self._available = EDGE_AVAILABLE
        self._stop_flag = False
        self._sentence_callback: Optional[Callable] = None
        self._word_timing_callback: Optional[Callable] = None
        self._duration_callback: Optional[Callable] = None
        self._finished_called = False
        self._current_future = None
        self.last_error: Optional[str] = None
        self.ffmpeg = self._find_ffmpeg()
        if self._available:
            print("[EdgeTTS] Edge TTS готов (event loop запустится при первом использовании)")

    def _start_event_loop(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _ensure_loop(self):
        if self._loop is None:
            self._start_event_loop()
            print("[EdgeTTS] Event loop запущен (lazy init)")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def name(self) -> str:
        return "Edge"

    def get_voices(self) -> List[Dict[str, Any]]:
        voices = []
        if not self._available:
            return voices
        for v in self.RUSSIAN_VOICES:
            voices.append({'id': v['id'], 'name': v['name'],
                           'engine': 'edge', 'gender': v['gender'], 'local': False})
        return voices

    # ═══════════════════ ЖИВОЕ ЧТЕНИЕ ═══════════════════
    def speak(self, text: str, callback: Optional[Callable] = None) -> bool:
        self._stop_flag = False
        self._finished_called = False
        if not self._available:
            print("[EdgeTTS] Edge TTS не доступен")
            if callback:
                threading.Timer(0.1, callback).start()
            return False
        self._ensure_loop()
        if not text or not text.strip():
            if callback:
                threading.Timer(0.1, callback).start()
            return True
        with self._lock:
            if self.is_speaking:
                self.stop()
                time.sleep(0.05)
            self._sentence_callback = callback
            self.is_speaking = True
        print(f"[EdgeTTS] Озвучивание: {self.current_voice} | {text[:60]}")
        future = asyncio.run_coroutine_threadsafe(self._speak_async(text), self._loop)
        self._current_future = future
        return True

    async def _speak_async(self, text: str):
        print("[EdgeTTS] === СИНТЕЗ ===")
        try:
            communicate = edge_tts.Communicate(text, self.current_voice, rate=self._edge_rate())
            mp3_data = b''
            chunk_count = 0
            word_boundaries = []
            async for chunk in communicate.stream():
                if self._stop_flag:
                    print("[EdgeTTS] Прервано")
                    return
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]
                    chunk_count += 1
                elif chunk["type"] == "WordBoundary":
                    word_boundaries.append({
                        "start_ms": round(chunk["offset"] / 10000),
                        "end_ms": round((chunk["offset"] + chunk["duration"]) / 10000),
                        "text": chunk["text"],
                    })
            print(f"[EdgeTTS] MP3: {chunk_count} чанков, {len(mp3_data)} байт, "
                  f"слов с таймингом: {len(word_boundaries)}")
            if not mp3_data:
                self._on_audio_finished()
                return
            from audio_player import get_audio_player
            player = get_audio_player()
            if not player.is_playing:
                player.start()
            player.prepare_sentence(self._on_audio_finished)
            pcm_data = self._decode_mp3_to_pcm(mp3_data)
            mp3_data = None
            if self._stop_flag:
                return
            if pcm_data and len(pcm_data) > 0:
                if self._duration_callback:
                    try:
                        self._duration_callback(int(len(pcm_data) / (22050 * 2) * 1000))
                    except Exception as e:
                        print(f"[EdgeTTS] duration_callback error: {e}")
                if self._word_timing_callback and word_boundaries:
                    try:
                        self._word_timing_callback(word_boundaries)
                    except Exception as e:
                        print(f"[EdgeTTS] word_timing_callback error: {e}")
                player.play_chunk(pcm_data, is_last=True)
            else:
                self._on_audio_finished()
        except Exception as e:
            print(f"[EdgeTTS] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self._on_audio_finished()

    def _find_ffmpeg(self):
        import shutil
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
        try:
            cmd = [self.ffmpeg, '-i', 'pipe:0', '-f', 's16le', '-acodec',
                   'pcm_s16le', '-ar', '22050', '-ac', '1', 'pipe:1']
            kwargs = {}
            if sys.platform == 'win32':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = si
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
            pcm_data, stderr = proc.communicate(input=mp3_data, timeout=60)
            if proc.returncode != 0:
                print(f"[EdgeTTS] ffmpeg error: {stderr.decode('utf-8','ignore')[:1000]}")
                return b''
            return pcm_data
        except subprocess.TimeoutExpired:
            print("[EdgeTTS] ffmpeg timeout")
            return b''
        except Exception as e:
            print(f"[EdgeTTS] decode error: {e}")
            return b''

    def _on_audio_finished(self):
        if self._finished_called:
            return
        self._finished_called = True
        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None
        if callback:
            try:
                callback()
            except Exception as e:
                print(f"[EdgeTTS] Ошибка в callback: {e}")

    def stop(self):
        self._stop_flag = True
        future = self._current_future
        if future and not future.done():
            future.cancel()
        self._current_future = None
        with self._lock:
            self.is_speaking = False
            self._sentence_callback = None
            self.on_finish_callback = None
            self._finished_called = False
        try:
            from audio_player import get_audio_player
            get_audio_player().clear_queue()
        except Exception:
            pass

    def set_voice(self, voice_id: str):
        self.current_voice = voice_id
        self.config.set('edge_tts_voice', voice_id)

    def set_rate(self, rate: float):
        self.current_rate = float(rate)
        self.config.set('tts_rate', rate)

    def _edge_rate(self) -> str:
        pct = int((self.current_rate - 1.0) * 100)
        return f'+{pct}%' if pct >= 0 else f'{pct}%'

    # ═══════════════════ ЗАПИСЬ В MP3 (AudioRecorder) ═══════════════════
    def _edge_synthesize(self, text: str, out_path: Path) -> bool:
        """Синтезирует text в mp3-файл out_path (stream(), не save() —
        save() изредка "проглатывает" начало аудио)."""
        try:
            import edge_tts as _et
        except ImportError:
            self.last_error = 'no_edge_tts'
            print('[EdgeTTS] edge-tts не установлен')
            return False
        voice = self.current_voice or self.config.get('edge_tts_voice', 'ru-RU-DmitryNeural')

        async def _run():
            communicate = _et.Communicate(text, voice, rate=self._edge_rate())
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk.get('type') == 'audio' and chunk.get('data'):
                    audio.extend(chunk['data'])
            return bytes(audio)
        try:
            audio_bytes = _run_async(_run())
        except Exception as e:
            self.last_error = 'edge_error'
            print(f'[EdgeTTS] Edge ошибка: {e}')
            return False
        if not audio_bytes:
            self.last_error = 'no_audio'
            print('[EdgeTTS] Edge: пустой ответ от сервиса синтеза')
            return False
        try:
            out_path.write_bytes(audio_bytes)
        except OSError as e:
            self.last_error = 'write_failed'
            print(f'[EdgeTTS] Не удалось записать файл: {e}')
            return False
        return True

    def record_chapter(self, index: int, title: str, text: str,
                       progress_cb: Optional[Callable] = None,
                       intro_text: Optional[str] = None) -> Optional[Path]:
        """Запись одной главы в MP3 (вступление + текст, склеенные с паузой)."""
        from audio_recorder import safe_filename
        self.last_error = None
        fname = safe_filename(f'{index:03d} - {title}')
        out_path = self.output_dir / f'{fname}.mp3' if hasattr(self, 'output_dir') else \
            Path(self.config.get('audiobook_output_dir', '.')) / f'{fname}.mp3'
        return self._record_edge(intro_text, text, out_path, progress_cb)

    def _record_edge(self, intro_text, text, out_path, progress_cb=None):
        if not self.ffmpeg:
            self.last_error = 'no_ffmpeg'
            print('[EdgeTTS] ffmpeg не найден — установите ffmpeg')
            return None
        from audio_recorder import split_sentences
        sentences = split_sentences(text)
        if not sentences:
            self.last_error = 'empty_text'
            return None
        total = len(sentences) + (1 if intro_text else 0)
        done = 0
        with tempfile.TemporaryDirectory(prefix='novareader_rec_') as tmp:
            tmp_dir = Path(tmp)
            segment_paths = []
            if intro_text:
                if self._stop_flag:
                    self.last_error = 'stopped'
                    return None
                intro_mp3 = tmp_dir / 'seg_intro.mp3'
                if self._edge_synthesize(intro_text.strip(), intro_mp3):
                    segment_paths.append(('intro', intro_mp3))
                    segment_paths.append(('pause', None))
                done += 1
                if progress_cb:
                    progress_cb(done, total)
            for i, sent in enumerate(sentences):
                if self._stop_flag:
                    self.last_error = 'stopped'
                    return None
                seg_path = tmp_dir / f'seg_{i:04d}.mp3'
                if self._edge_synthesize(sent, seg_path):
                    segment_paths.append(('body', seg_path))
                done += 1
                if progress_cb:
                    progress_cb(done, total)
            if not any(kind == 'body' for kind, _ in segment_paths):
                self.last_error = self.last_error or 'no_audio'
                return None
            return self._concat_edge_segments(segment_paths, out_path)

    def _concat_edge_segments(self, segment_paths, out_path) -> Optional[Path]:
        pause_s = _INTRO_PAUSE_MS / 1000.0
        inputs, filter_parts, n = [], [], 0
        for kind, path in segment_paths:
            if kind == 'pause':
                inputs += ['-f', 'lavfi', '-t', f'{pause_s}', '-i', 'anullsrc=r=24000:cl=mono']
            else:
                inputs += ['-i', str(path)]
            filter_parts.append(f'[{n}:a]')
            n += 1
        filter_complex = ''.join(filter_parts) + f'concat=n={n}:v=0:a=1[out]'
        cmd = [self.ffmpeg, '-y', *inputs, '-filter_complex', filter_complex,
               '-map', '[out]', '-c:a', 'libmp3lame', '-b:a', '128k', str(out_path)]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=600)
        except subprocess.TimeoutExpired:
            self.last_error = 'ffmpeg_failed'
            return None
        if proc.returncode != 0 or not out_path.exists():
            self.last_error = 'ffmpeg_failed'
            print('[EdgeTTS] ffmpeg (склейка) ошибка:',
                  proc.stderr.decode('utf-8', 'ignore')[-300:])
            return None
        return out_path
