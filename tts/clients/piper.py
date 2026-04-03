"""
Piper TTS client - версия с нативными бинарниками
"""
import subprocess
import tempfile
import threading
import time
import sys
import os
import stat
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from .base import TTSClient

# === ДОБАВЛЕНО: константа и функции для скрытия окон ===
CREATE_NO_WINDOW = 0x08000000

def _run_hidden(cmd, **kwargs):
    """Запускает процесс без окна (кроссплатформенный)"""
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | CREATE_NO_WINDOW
    return subprocess.Popen(cmd, **kwargs)

def _run_hidden_and_wait(cmd, **kwargs):
    """Запускает процесс без окна и ждёт завершения"""
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)
# ==================================================

class PiperClient(TTSClient):
    """Клиент для Piper TTS с нативными бинарниками из папки проекта."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_voice = config.get('piper_voice', 'ru_RU_irina_medium')
        self.current_rate = float(config.get('tts_rate', 1.0))
        self._lock = threading.Lock()
        self._speaking_thread: Optional[threading.Thread] = None
        self._player_proc: Optional[subprocess.Popen] = None
        self._stop_flag = False
        self._sentence_callback: Optional[Callable] = None  # единый callback для AudioPlayer

        # Находим бинарник в папке проекта
        self.piper_bin = self._find_binary()
        self.player = self._find_player()

        print("[Piper] " + "=" * 40)
        print(f"[Piper] Платформа: {sys.platform}")
        print(f"[Piper] Бинарник: {self.piper_bin or 'НЕ НАЙДЕН'}")
        print(f"[Piper] Папка голосов: {config.voices_dir}")
        print(f"[Piper] Плеер: {self.player or 'НЕ НАЙДЕН'}")
        print(f"[Piper] Голос по умолчанию: {self.current_voice}")
        
        if not self.piper_bin:
            print("[Piper] КРИТИЧЕСКАЯ ОШИБКА: Бинарник Piper не найден!")
            print("[Piper] Ожидаемые пути:")
            print(f"[Piper]   Linux: {Path(__file__).parent.parent.parent / 'tts' / 'piper' / 'piper'}")
            print(f"[Piper]   Windows: {Path(__file__).parent.parent.parent / 'tts' / 'piper-win' / 'piper.exe'}")
        
        if not list(config.voices_dir.glob('*.onnx')):
            print(f"[Piper] ПРЕДУПРЕЖДЕНИЕ: Нет голосов. Положите .onnx и .onnx.json в:")
            print(f"[Piper]    {config.voices_dir}")

    def _find_binary(self) -> Optional[Path]:
        """
        Находит бинарник Piper в папке проекта.
        Возвращает Path или None, если бинарник не найден.
        """
        # Базовая папка: там, где лежит этот файл (tts/clients/)
        base_dir = Path(__file__).parent.parent.parent
        
        if sys.platform == 'win32':
            # Windows: ./tts/piper-win/piper.exe
            binary = base_dir / 'tts' / 'piper-win' / 'piper.exe'
        else:
            # Linux: ./tts/piper/piper
            binary = base_dir / 'tts' / 'piper' / 'piper'
            
            # Делаем исполняемым для Linux
            if binary.exists():
                try:
                    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
                except Exception as e:
                    print(f"[Piper] Не удалось установить права на исполнение: {e}")
        
        if binary.exists():
            return binary
        return None

    def _find_player(self) -> Optional[str]:
        """Найти аудио-плеер в системе"""
        import shutil
        import subprocess

        if sys.platform == 'win32':
            return None

        if shutil.which('pactl'):
            try:
                # ИСПРАВЛЕНО: используем _run_hidden_and_wait
                _run_hidden_and_wait(['pactl', 'info'], capture_output=True, timeout=1)
                return 'paplay'
            except:
                pass
        
        if shutil.which('aplay'):
            return 'aplay'
        
        for player in ['ffplay', 'mpv', 'vlc', 'mplayer']:
            if shutil.which(player):
                return player
        return None

    @property
    def name(self) -> str:
        return "Piper"

    def get_voices(self) -> List[Dict[str, Any]]:
        """Возвращает голоса из папки voices"""
        voices = []
        voices_dir = self.config.voices_dir

        if not voices_dir.exists():
            print(f"[Piper] Папка голосов не существует: {voices_dir}")
            return voices

        # Ищем все .onnx файлы
        found_onnx = list(voices_dir.glob('*.onnx'))
        for sub in voices_dir.iterdir() if voices_dir.exists() else []:
            if sub.is_dir():
                found_onnx.extend(sub.glob('*.onnx'))

        for onnx in found_onnx:
            voice_id = onnx.stem
            # Проверяем наличие JSON конфига
            json_file = onnx.with_suffix('.onnx.json')
            if not json_file.exists():
                continue
                
            # Красивое имя для отображения
            display = voice_id.replace('-', ' ').replace('_', ' ')
            import re
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
            # КРИТИЧЕСКИ ВАЖНО: сбрасываем _stop_flag перед новым запуском.
            # stop()/pause() устанавливают _stop_flag=True — без сброса
            # следующий speak() немедленно вернёт "Прервано".
            self._stop_flag = False
            self.is_speaking = True
            self._sentence_callback = callback
            self.on_finish_callback = None

        t = threading.Thread(target=self._speak_thread, args=(text,), daemon=True)
        self._speaking_thread = t
        t.start()
        return True

    def _speak_thread(self, text: str):
        """Поток синтеза — callback вызывается из AudioPlayer после воспроизведения."""
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

        # Проверяем флаг остановки
        with self._lock:
            if not self.is_speaking:
                print("[Piper] Отменено")
                self._finish()
                return

        # Импортируем AudioPlayer
        from audio_player import get_audio_player

        player = get_audio_player()
        # БАГ-ФИКС: prepare_sentence() правильно обновляет callback для КАЖДОГО
        # предложения (не только первого), запускает поток если нужно
        if not player.is_playing:
            player.start()
        player.prepare_sentence(self._on_audio_finished)

        # ЗАПУСКАЕМ PIPER (--output_raw)
        try:
            cmd = [
                str(self.piper_bin),
                '-m', str(voice_path),
                '--output_raw',
            ]

            if self.current_rate != 1.0:
                cmd.extend(['--length-scale', str(round(1.0 / self.current_rate, 3))])

            print(f"[Piper] Команда: {' '.join(cmd)}")

            # Запускаем процесс
            self._proc = _run_hidden(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._quiet_env()
            )

            # Получаем PCM
            stdout_data, stderr_data = self._proc.communicate(
                input=text.encode('utf-8'),
                timeout=60
            )

            # Проверка остановки
            if self._stop_flag:
                print("[Piper] Прервано")
                return

            # Проверяем PCM данные
            if stdout_data and len(stdout_data) > 100:
                print(f"[Piper] PCM данных: {len(stdout_data)} байт")
                # Отправляем PCM в AudioPlayer с is_last=True
                player.play_chunk(stdout_data, is_last=True)
                # НЕ вызываем _finish() здесь — callback вызовется из AudioPlayer!
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
        """Окружение с подавлением лишних логов"""
        import os
        env = os.environ.copy()
        env['ALSA_PCM_CARD'] = 'default'
        env['PYTHONWARNINGS'] = 'ignore'
        env['LIBASOUND_DEBUG'] = '0'
        return env

    def _on_audio_finished(self):
        """Вызывается AudioPlayer ПОСЛЕ физического завершения воспроизведения."""
        print("[Piper] AudioPlayer callback → ttsNext")
        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None

        if callback:
            try:
                callback()
            except Exception as e:
                print(f"[Piper] ❌ Ошибка в callback: {e}")
        else:
            print("[Piper] ⚠ callback=None (предложение уже завершено)")

    def _finish(self):
        """Завершение при ошибке/отмене — вызывает callback если он ещё есть."""
        with self._lock:
            self.is_speaking = False
            callback = self._sentence_callback
            self._sentence_callback = None

        if callback:
            # Небольшая задержка чтобы не гонять callback сразу при ошибке
            threading.Timer(0.1, callback).start()

    def stop(self):
        """Немедленная остановка."""
        self._stop_flag = True

        with self._lock:
            self.is_speaking = False
            self._sentence_callback = None
            self.on_finish_callback = None  # на всякий случай

            # Прерываем процесс Piper
            if hasattr(self, '_proc') and self._proc:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=2)
                except Exception:
                    try:
                        self._proc.kill()
                    except:
                        pass
                self._proc = None

        # Очищаем очередь AudioPlayer (инкрементирует generation — отменяет Timer)
        try:
            from audio_player import get_audio_player
            player = get_audio_player()
            player.clear_queue()
        except Exception:
            pass

    def set_voice(self, voice_id: str):
        print(f"[Piper] Голос: {voice_id}")
        self.current_voice = voice_id
        # Сохраняем в настройку piper_voice для Piper
        self.config.set('piper_voice', voice_id)
        # Также обновляем общий tts_voice для совместимости
        self.config.set('tts_voice', voice_id)

    def set_rate(self, rate: float):
        self.current_rate = float(rate)
        self.config.set('tts_rate', rate)