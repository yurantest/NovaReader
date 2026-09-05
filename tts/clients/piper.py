"""
Piper TTS client - версия с нативными бинарниками
"""
import subprocess
import tempfile
import threading
import time
import sys
import os
import re
import stat
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from .base import TTSClient

def _estimate_word_timings(text: str, duration_ms: int) -> List[Dict[str, Any]]:
    """Расчётные тайминги слов (у Piper нет нативных WordBoundary-меток).
    Распределяет duration_ms пропорционально "речевому весу" слова.
    Формат идентичен нативным таймингам Edge — JS-сторона обрабатывает
    оба источника одним кодом."""
    words = re.findall(r'\S+', text)
    if not words or duration_ms <= 0:
        return []
    
    PER_WORD_BASE = 90
    PAUSE_AFTER_PUNCT = 120
    
    weights = []
    for w in words:
        weight = PER_WORD_BASE + len(w) * 55
        if re.search(r'[.!?,:;—-]$', w):
            weight += PAUSE_AFTER_PUNCT
        weights.append(weight)
    
    total_weight = sum(weights) or 1
    scale = duration_ms / total_weight
    
    timings = []
    cursor_ms = 0.0
    for w, weight in zip(words, weights):
        span = weight * scale
        timings.append({
            "start_ms": round(cursor_ms),
            "end_ms": round(cursor_ms + span),
            "text": w,
        })
        cursor_ms += span
    
    return timings

CREATE_NO_WINDOW = 0x08000000

def _run_hidden(cmd, **kwargs):
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | CREATE_NO_WINDOW
    return subprocess.Popen(cmd, **kwargs)

def _run_hidden_and_wait(cmd, **kwargs):
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)

class PiperClient(TTSClient):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_voice = config.get('piper_voice', 'ru_RU_irina_medium')
        self.current_rate = float(config.get('tts_rate', 1.0))
        
        # ИСПРАВЛЕНО: RLock вместо Lock — speak() вызывает stop(), который
        # тоже берёт лок; с обычным Lock это deadlock (программа висла).
        self._lock = threading.RLock()
        self._speaking_thread: Optional[threading.Thread] = None
        self._player_proc: Optional[subprocess.Popen] = None
        self._stop_flag = False
        self._sentence_callback: Optional[Callable] = None
        self._word_timing_callback: Optional[Callable] = None
        self._duration_callback: Optional[Callable] = None
        
        self.piper_bin = self._find_binary()
        self.player = self._find_player()
        
        if not config.find_voice_path(self.current_voice):
            print(f"[Piper] ВНИМАНИЕ: сохранённый голос '{self.current_voice}' "
                  f"не найден на диске — ищем установленную замену...")
            fallback = self._find_any_installed_voice()
            if fallback:
                print(f"[Piper] Переключаемся на установленный голос: {fallback}")
                self.current_voice = fallback
                config.set('piper_voice', fallback)
            else:
                print(f"[Piper] ВНИМАНИЕ: установленных голосов Piper не найдено вообще")
        
        print("[Piper] " + "=" * 40)
        print(f"[Piper] Платформа: {sys.platform}")
        print(f"[Piper] Бинарник: {self.piper_bin or 'НЕ НАЙДЕН'}")
        print(f"[Piper] Папка голосов: {config.voices_dir}")
        print(f"[Piper] Плеер: {self.player or 'НЕ НАЙДЕН'}")
        print(f"[Piper] Голос по умолчанию: {self.current_voice}")
        
        if not self.piper_bin:
            print("[Piper] КРИТИЧЕСКАЯ ОШИБКА: Бинарник Piper не найден!")
        
        if not list(config.voices_dir.glob('*.onnx')):
            print(f"[Piper] ПРЕДУПРЕЖДЕНИЕ: Нет голосов. Положите .onnx и .onnx.json в: ")
            print(f"[Piper]    {config.voices_dir}")
    
    def _find_binary(self) -> Optional[Path]:
        base_dir = Path(__file__).parent.parent.parent
        if sys.platform == 'win32':
            binary = base_dir / 'tts' / 'piper-win' / 'piper.exe'
        else:
            binary = base_dir / 'tts' / 'piper' / 'piper'
            if binary.exists():
                try:
                    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
                except Exception as e:
                    print(f"[Piper] Не удалось установить права на исполнение: {e}")
        if binary.exists():
            return binary
        return None
    
    def _find_player(self) -> Optional[str]:
        import shutil
        if sys.platform == 'win32':
            return None
        if shutil.which('pactl'):
            try:
                _run_hidden_and_wait(['pactl', 'info'], capture_output=True, timeout=1)
                return 'paplay'
            except Exception:
                pass
        if shutil.which('aplay'):
            return 'aplay'
        for player in ['ffplay', 'mpv', 'vlc', 'mplayer']:
            if shutil.which(player):
                return player
        return None
    
    def _find_any_installed_voice(self) -> Optional[str]:
        try:
            voices_dir = self.config.voices_dir
            if not voices_dir.exists():
                return None
            for onnx_file in sorted(voices_dir.glob('*.onnx')):
                json_file = onnx_file.with_suffix('.onnx.json')
                if json_file.exists():
                    return onnx_file.stem.replace('-', '_')
        except Exception as e:
            print(f"[Piper] Ошибка поиска установленных голосов: {e}")
        return None
    
    @property
    def name(self) -> str:
        return "Piper"
    
    def get_voices(self) -> List[Dict[str, Any]]:
        voices = []
        voices_dir = self.config.voices_dir
        if not voices_dir.exists():
            print(f"[Piper] Папка голосов не существует: {voices_dir}")
            return voices
        
        found_onnx = list(voices_dir.glob('*.onnx'))
        for sub in voices_dir.iterdir() if voices_dir.exists() else []:
            if sub.is_dir():
                found_onnx.extend(sub.glob('*.onnx'))
        
        for onnx in found_onnx:
            voice_id = onnx.stem
            json_file = onnx.with_suffix('.onnx.json')
            if not json_file.exists():
                continue
            display = voice_id.replace('-', ' ').replace('_', ' ')
            display = re.sub(r'^[a-z]{2}[_-][A-Z]{2}[_-]', '', display).title()
            voices.append({
                'id': voice_id,
                'name': f"{display} [PiperNative]",
                'engine': 'piper',
                'local': True,
                'path': str(onnx),
            })
        
        print(f"[Piper] Найдено голосов: {len(voices)}")
        return voices
    
    def speak(self, text: str, callback: Optional[Callable] = None) -> bool:
        if not text or len(text.strip()) < 2:
            if callback:
                threading.Timer(0.05, callback).start()
            return True
        
        with self._lock:
            if self.is_speaking:
                self.stop()
                time.sleep(0.05)
            self._stop_flag = False
            self.is_speaking = True
            self._sentence_callback = callback
            self.on_finish_callback = None
            # _duration_callback и _word_timing_callback НЕ обнуляем —
            # reader_window ставит их ДО speak().
        
        t = threading.Thread(target=self._speak_thread, args=(text,), daemon=True)
        self._speaking_thread = t
        t.start()
        return True
    
    def _speak_thread(self, text: str):
        if not self.piper_bin:
            print("[Piper] ОШИБКА: Бинарник Piper не найден")
            self._finish()
            return
        
        print(f"[Piper] Текст: {text[:100]}...")
        
        voice_path = self.config.find_voice_path(self.current_voice)
        if not voice_path:
            print(f"[Piper] ОШИБКА: Голос не найден: {self.current_voice}")
            self._finish()
            return
        
        with self._lock:
            if not self.is_speaking:
                print("[Piper] Отменено")
                self._finish()
                return
        
        from audio_player import get_audio_player
        player = get_audio_player()
        if not player.is_playing:
            player.start()
        player.prepare_sentence(self._on_audio_finished)
        
        try:
            cmd = [str(self.piper_bin), '-m', str(voice_path), '--output_raw']
            if self.current_rate != 1.0:
                cmd.extend(['--length-scale', str(round(1.0 / self.current_rate, 3))])
            
            print(f"[Piper] Команда: {' '.join(cmd)}")
            
            self._proc = _run_hidden(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     env=self._quiet_env())
            
            stdout_data, stderr_data = self._proc.communicate(
                input=text.encode('utf-8'), timeout=60)
            
            if self._stop_flag:
                print("[Piper] Прервано")
                return
            
            if stdout_data and len(stdout_data) > 100:
                print(f"[Piper] PCM данных: {len(stdout_data)} байт")
                
                piper_sr = 22050
                try:
                    import json as _json
                    json_path = Path(str(voice_path) + '.json')
                    if json_path.exists():
                        _cfg = _json.loads(json_path.read_text(encoding='utf-8'))
                        piper_sr = int(_cfg.get('audio', {}).get('sample_rate', 22050))
                except Exception:
                    pass
                
                duration_ms = int(len(stdout_data) / (piper_sr * 2) * 1000)
                
                if self._duration_callback:
                    try:
                        self._duration_callback(duration_ms)
                    except Exception as _de:
                        print(f"[Piper] duration_callback error: {_de}")
                
                if self._word_timing_callback:
                    try:
                        timings = _estimate_word_timings(text, duration_ms)
                        if timings:
                            self._word_timing_callback(timings)
                    except Exception as _we:
                        print(f"[Piper] word_timing_callback error: {_we}")
                
                player.play_chunk(stdout_data, is_last=True)
                print(f"[Piper] PCM → AudioPlayer (duration={duration_ms}ms, sr={piper_sr})")
            else:
                print("[Piper] ERROR: PCM не получен")
                if stderr_data:
                    stderr_text = stderr_data.decode('utf-8', errors='replace')
                    if stderr_text.strip():
                        print(f"[Piper] stderr: {stderr_text[:200]}")
                self._finish()
        
        except subprocess.TimeoutExpired:
            print("[Piper] Таймаут")
            if hasattr(self, '_proc') and self._proc:
                self._proc.kill()
            self._finish()
        
        except Exception as e:
            print(f"[Piper] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self._finish()
    
    def _quiet_env(self) -> dict:
        env = os.environ.copy()
        env['ALSA_PCM_CARD'] = 'default'
        env['PYTHONWARNINGS'] = 'ignore'
        env['LIBASOUND_DEBUG'] = '0'
        return env
    
    def _on_audio_finished(self):
        print("[Piper] AudioPlayer callback → ttsNext")
        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None
        if callback:
            try:
                callback()
            except Exception as e:
                print(f"[Piper] Ошибка в callback: {e}")
        else:
            print("[Piper] callback=None (предложение уже завершено)")
    
    def _finish(self):
        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None
        if callback:
            threading.Timer(0.1, callback).start()
    
    def stop(self):
        self._stop_flag = True
        with self._lock:
            self.is_speaking = False
            self._sentence_callback = None
            self.on_finish_callback = None
            if hasattr(self, '_proc') and self._proc:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=2)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                self._proc = None
        try:
            from audio_player import get_audio_player
            player = get_audio_player()
            player.clear_queue()
        except Exception:
            pass
    
    def set_voice(self, voice_id: str):
        print(f"[Piper] Голос: {voice_id}")
        self.current_voice = voice_id
        self.config.set('piper_voice', voice_id)
        self.config.set('tts_voice', voice_id)
    
    def set_rate(self, rate: float):
        self.current_rate = float(rate)
        self.config.set('tts_rate', rate)