from typing import List, Optional, Dict, Any, Callable
from .clients.base import TTSClient
from .clients.piper import PiperClient
from .clients.edge import EdgeClient
# Используем только Edge и Piper на всех платформах
EspeakClient = None
RhVoiceTTSClient = None
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from audio_player import get_audio_player, release_audio_player


class TTSController:
    """
    TTS Controller — управляет TTS клиентами.
    Поддерживает: Edge TTS, Piper, RhVoice (rhvoice-wrapper), speech-dispatcher, SAPI5, eSpeak.
    RhVoice теперь через rhvoice-wrapper (потоковый PCM).
    """

    def __init__(self, config):
        self.config = config
        self.clients: List[TTSClient] = []
        self.active_client: Optional[TTSClient] = None
        self.state = 'stopped'
        self._init_clients()

    def _init_clients(self):
        """Инициализация клиентов.
        Windows: только Edge TTS и Piper.
        Linux: Edge, Piper, RhVoice, SpeechD, eSpeak.
        """
        # Edge TTS
        try:
            c = EdgeClient(self.config)
            if c._available:
                self.clients.append(c)
                print(f"[TTS] OK Edge TTS")
        except Exception as e:
            print(f"[TTS] Edge TTS: {e}")

        # Piper TTS
        try:
            c = PiperClient(self.config)
            self.clients.append(c)
            print(f"[TTS] OK Piper")
        except Exception as e:
            print(f"[TTS] Piper: {e}")

        # RhVoice, SpeechD, SAPI5, eSpeak убраны — используем только Edge и Piper

        if self.clients:
            self.active_client = self.clients[0]
            print(f"[TTS] Активный: {self.active_client.name}")
        else:
            print("[TTS] ERROR Нет доступных TTS движков")

    def set_preferred_engine(self, engine_name: str) -> bool:
        """Установить предпочтительный движок по имени (ключ из JS VOICES{})."""
        print(f"[TTS] Выбор движка: {engine_name}")
        # Нормализуем для поиска: дефисы → подчёркивания, lower
        key = engine_name.lower().replace('-', '_')
        for client in self.clients:
            cname = client.name.lower().replace('-', '_')
            if cname == key:
                self.active_client = client
                
                # Синхронизация голоса при переключении движка
                # Для Piper используем piper_voice, для остальных - tts_voice
                if client.name.lower() == 'piper':
                    voice_key = 'piper_voice'
                    default_voice = 'ru_RU_irina_medium'
                elif client.name.lower() == 'edge':
                    voice_key = 'edge_tts_voice'
                    default_voice = 'ru-RU-DariyaNeural'
                else:
                    voice_key = 'tts_voice'
                    default_voice = ''
                
                # Получаем голос из настроек
                saved_voice = self.config.get(voice_key, default_voice)
                if saved_voice:
                    client.set_voice(saved_voice)
                    print(f"[TTS] Установлен голос для {client.name}: {saved_voice}")
                
                print(f"[TTS] OK Активный: {client.name}")
                return True
        print(f"[TTS] ERROR Движок не найден: {engine_name} (доступны: {[c.name for c in self.clients]})")
        return False

    def get_available_engines(self) -> List[Dict[str, Any]]:
        engines = []
        for client in self.clients:
            voices = client.get_voices()
            engines.append({
                'name': client.name,
                'voices': voices,
                'voice_count': len(voices)
            })
        return engines

    def get_engine_voices(self, engine_name: str) -> List[Dict]:
        key = engine_name.lower().replace('-', '_')
        for client in self.clients:
            if client.name.lower().replace('-', '_') == key:
                return client.get_voices()
        return []

    def speak(self, text: str, callback: Optional[Callable] = None):
        if not self.active_client:
            print("[TTS] Нет активного клиента")
            if callback:
                callback()
            return

        # Нормализуем текст: римские цифры → арабские, очистка SSML
        from .utils import normalize_text_for_tts
        text = normalize_text_for_tts(text)
        
        # Применяем коррекции произношения
        text = self.apply_tts_corrections(text)

        self.state = 'playing'
        def on_finished():
            self.state = 'stopped'  # Обновляем состояние после завершения
            if callback:
                callback()
        self.active_client.speak(text, on_finished)

    def apply_tts_corrections(self, text: str) -> str:
        """Применить замены слов из списка коррекций"""
        corrections = self.config.get('tts_corrections', [])
        if not corrections:
            return text
        
        result = text
        for item in corrections:
            wrong = item.get('wrong', '')
            correct = item.get('correct', '')
            if wrong and correct:
                # Простая замена всех вхождений
                result = result.replace(wrong, correct)
        
        if result != text:
            print(f"[TTS] Коррекция: '{text[:50]}...' → '{result[:50]}...'")
        
        return result

    def stop(self):
        """Остановить воспроизведение."""
        self.state = 'stopped'

        # Останавливаем активный клиент (он сам вызывает player.clear_queue())
        if self.active_client:
            self.active_client.stop()

        # Останавливаем AudioPlayer (на случай если клиент не остановил)
        from audio_player import get_audio_player
        player = get_audio_player()
        player.stop()

    def pause(self):
        """Поставить на паузу — МГНОВЕННО прерывает текущее воспроизведение."""
        try:
            self.state = 'paused'

            if self.active_client:
                print(f"[TTS] Пауза: прерываем {self.active_client.name}")
                # Устанавливаем флаг — прервёт цикл воспроизведения
                self.active_client._stop_flag = True
                with self.active_client._lock:
                    self.active_client.is_speaking = False
                # stop() очищает очередь AudioPlayer (один раз)
                self.active_client.stop()
            else:
                # Нет активного клиента — очищаем AudioPlayer напрямую
                from audio_player import get_audio_player
                get_audio_player().clear_queue()

        except Exception as e:
            print(f"[TTS] ERROR pause(): {e}")
            import traceback
            traceback.print_exc()

    def resume(self):
        """Возобновить воспроизведение после паузы — продолжает с текущего предложения."""
        if self.state != 'paused':
            return
        try:
            self.state = 'playing'
            # Сигнал JS-стороне — она сама вызовет speakCurrentSentence()
            # через window.resumeTTS(), уже обработанный в reader.html.
            # Здесь мы только меняем state, чтобы bridge._toggle_tts_pause
            # и closeEvent корректно видели статус.
            print("[TTS] resume(): state → playing (JS продолжит с текущего предложения)")
        except Exception as e:
            print(f"[TTS] ERROR resume(): {e}")
            import traceback
            traceback.print_exc()

    def shutdown(self):
        """Полная остановка всех клиентов и процессов при закрытии приложения."""
        self.state = 'stopped'

        # Останавливаем AudioPlayer
        from audio_player import release_audio_player
        release_audio_player()

        for client in self.clients:
            try:
                client.stop()
            except Exception:
                pass

    def set_voice(self, voice_id: str):
        if self.active_client:
            self.active_client.set_voice(voice_id)

    def set_rate(self, rate: float):
        if self.active_client:
            self.active_client.set_rate(rate)

    def get_voices(self) -> List[Dict]:
        if self.active_client:
            return self.active_client.get_voices()
        return []
