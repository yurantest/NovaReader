#!/usr/bin/env python3
"""
AudioPlayer — непрерывное TTS воспроизведение с callback.
ОДИН экземпляр на всё приложение.

ИСПРАВЛЕНИЯ v2:
  - start() теперь ОБНОВЛЯЕТ callback если поток уже запущен (не делает return молча)
  - prepare_sentence(cb) — сбрасывает счётчики и устанавливает callback для нового предложения
  - Callback вызывается через Timer(0.15s) — даём sounddevice-буферу физически доиграть
  - _sentence_generation защищает от устаревших (отменённых) callback
"""

import threading
import queue
import numpy as np
import sounddevice as sd


class AudioPlayer:
    """Глобальный аудиоплеер для TTS."""

    SAMPLE_RATE = 22050
    CHANNELS = 1
    DTYPE = 'int16'
    FADE_SAMPLES = 110

    def __init__(self):
        self._queue = queue.Queue()
        self._stream = None
        self._is_playing = False
        self._lock = threading.Lock()
        self._stop_flag = False

        # Счётчики текущего предложения
        self._pending_chunks = 0
        self._sentence_chunks = 0
        self._is_last = False
        self._total_bytes_queued = 0
        self._total_bytes_played = 0
        self._chunks_received = 0
        self._chunks_played = 0
        self._current_chunk_size = 0
        self._bytes_played = 0

        self._sentence_callback = None
        self._warned_no_callback = False
        # Счётчик генерации: инкрементируется при prepare_sentence/stop/clear
        # Позволяет отменить «устаревшие» отложенные callback
        self._sentence_generation = 0

    # ──────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────

    def start(self, on_sentence_finished=None):
        """
        Запустить аудио-поток (один раз при старте приложения).
        Если поток уже запущен — только обновляет callback.
        """
        if self._is_playing:
            # БАГ-ФИКС: раньше делали return и callback терялся для 2-го+ предложения
            if on_sentence_finished is not None:
                with self._lock:
                    self._sentence_callback = on_sentence_finished
                    self._warned_no_callback = False
            return

        self._sentence_callback = on_sentence_finished
        self._is_playing = True
        self._stop_flag = False
        self._sentence_generation = 0
        self._reset_sentence_counters()

        self._stream = sd.OutputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            callback=self._audio_callback,
            blocksize=1024,
        )
        self._stream.start()
        print(f"[AudioPlayer] 🔊 Поток запущен (sr={self.SAMPLE_RATE})")

    def prepare_sentence(self, on_finished=None):
        """
        Подготовить AudioPlayer для НОВОГО предложения.

        ОБЯЗАТЕЛЬНО вызывать перед каждым play_chunk() нового предложения.
        Сбрасывает счётчики и устанавливает callback.
        Запускает поток если не запущен.

        Правильный паттерн в TTS клиентах:
            player = get_audio_player()
            if not player.is_playing:
                player.start()
            player.prepare_sentence(self._on_audio_finished)
            player.play_chunk(pcm_data, is_last=True)
        """
        if not self._is_playing:
            self.start()

        with self._lock:
            self._sentence_generation += 1
            self._sentence_callback = on_finished
            self._warned_no_callback = False
            self._reset_sentence_counters()

        print(f"[AudioPlayer] 🆕 prepare_sentence gen={self._sentence_generation} "
              f"callback={'✅' if on_finished else '❌'}")

    def stop(self):
        """Остановить и очистить очередь."""
        if not self._is_playing:
            return

        self._is_playing = False
        self._stop_flag = True

        with self._lock:
            self._sentence_generation += 1  # отменяем отложенные callback
            self._sentence_callback = None
            self._reset_sentence_counters()

        self._drain_queue()

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        print("[AudioPlayer] ⏹ Поток остановлен")

    def play_chunk(self, audio_data: bytes, is_last=False):
        """
        Добавить PCM данные (16-bit, 22050 Hz, mono) в очередь.

        Args:
            audio_data: сырые PCM байты
            is_last:    True → это последний чанк предложения, после него вызвать callback
        """
        if not self._is_playing or self._stop_flag:
            print(f"[AudioPlayer] ⚠️ play_chunk отклонён: "
                  f"is_playing={self._is_playing}, stop_flag={self._stop_flag}")
            return

        # fade-out только на последнем чанке
        if is_last and len(audio_data) >= self.FADE_SAMPLES * 2:
            audio_data = self._apply_fade_out(audio_data)

        with self._lock:
            self._pending_chunks += 1
            self._sentence_chunks += 1
            self._total_bytes_queued += len(audio_data)
            self._chunks_received += 1
            if is_last:
                self._is_last = True
            self._current_chunk_size = len(audio_data)

        self._queue.put(audio_data)
        print(f"[AudioPlayer] ⬇️ queued {len(audio_data)} байт "
              f"is_last={is_last} pending={self._pending_chunks}")

    def clear_queue(self):
        """Очистить очередь (для pause — не останавливает поток)."""
        self._drain_queue()
        with self._lock:
            self._sentence_generation += 1  # отменяем отложенные callback
            self._sentence_callback = None
            self._reset_sentence_counters()
        print("[AudioPlayer] 🧹 Очередь очищена")

    # ──────────────────────────────────────────────────────────────────
    # Внутренние методы
    # ──────────────────────────────────────────────────────────────────

    def _reset_sentence_counters(self):
        """Сброс счётчиков предложения. Вызывать под self._lock или при инициализации."""
        self._pending_chunks = 0
        self._sentence_chunks = 0
        self._total_bytes_queued = 0
        self._total_bytes_played = 0
        self._chunks_received = 0
        self._chunks_played = 0
        self._current_chunk_size = 0
        self._bytes_played = 0
        self._is_last = False
        self._warned_no_callback = False

    def _drain_queue(self):
        """Быстро слить всю очередь."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _apply_fade_out(self, audio_data: bytes) -> bytes:
        """Применить fade-out к последним 5ms."""
        arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        fade = np.linspace(1.0, 0.0, self.FADE_SAMPLES, dtype=np.float32)
        arr[-self.FADE_SAMPLES:] *= fade
        return arr.astype(np.int16).tobytes()

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Callback sounddevice OutputStream.
        Вызывается в реальном времени из аудио-потока ОС.
        НЕ делать тяжёлых операций, НЕ ждать lock долго.
        """
        if status:
            print(f'[AudioPlayer] ⚠ Status: {status}')

        bytes_needed = frames * self.CHANNELS * 2
        buf = bytearray(bytes_needed)
        offset = 0
        chunks_consumed = 0

        while offset < bytes_needed:
            try:
                chunk = self._queue.get(timeout=0.001)
                size = len(chunk)
                if offset + size <= bytes_needed:
                    buf[offset:offset + size] = chunk
                    offset += size
                    chunks_consumed += 1
                else:
                    rem = bytes_needed - offset
                    buf[offset:offset + rem] = chunk[:rem]
                    offset += rem
                    self._queue.put(chunk[rem:])
                    break
            except queue.Empty:
                break

        fire_callback = False
        captured_callback = None
        captured_gen = 0

        with self._lock:
            self._total_bytes_played += offset

            if chunks_consumed > 0:
                self._pending_chunks = max(0, self._pending_chunks - chunks_consumed)
                self._chunks_played += chunks_consumed

            # Условие завершения предложения:
            # pending=0, is_last=True, весь буфер предложения воспроизведён
            if (self._pending_chunks <= 0 and
                    self._is_last and
                    self._total_bytes_queued > 0 and
                    self._total_bytes_played >= self._total_bytes_queued):

                if self._sentence_callback:
                    captured_callback = self._sentence_callback
                    captured_gen = self._sentence_generation

                    # Сбрасываем до вызова callback — защита от повторного триггера
                    self._sentence_callback = None
                    self._is_last = False
                    self._reset_sentence_counters()
                    fire_callback = True

                    print(f"[AudioPlayer] ✅ Предложение завершено "
                          f"gen={captured_gen}")

                elif not self._warned_no_callback:
                    print(f"[AudioPlayer] ⚠ Предложение завершено, callback=None")
                    self._warned_no_callback = True
                    self._is_last = False
                    self._reset_sentence_counters()

        # Вызываем callback ВОВНЕ lock через Timer — даём sounddevice доиграть буфер
        # blocksize=1024 → ~46ms задержка буфера; берём 150ms с запасом
        if fire_callback and captured_callback:
            gen = captured_gen

            def _fire():
                # Проверяем, не была ли генерация сменена (stop/prepare_sentence)
                # пока timer ждал. Если generation совпадает — никто не прервал.
                # Если изменилась — stop()/prepare_sentence() уже вызваны,
                # значит callback НЕ НУЖЕН (предложение отменено).
                with self._lock:
                    current_gen = self._sentence_generation
                # Генерация увеличивается в prepare_sentence и stop.
                # Но мы захватили callback ДО сброса — если gen совпадает,
                # значит никто не вмешался. Если нет — пропускаем.
                if current_gen != gen:
                    print(f"[AudioPlayer] ⚠ Callback отменён: "
                          f"gen захвачен={gen}, текущий={current_gen}")
                    return
                try:
                    captured_callback()
                except Exception as e:
                    print(f"[AudioPlayer] ❌ Ошибка в callback: {e}")

            threading.Timer(0.15, _fire).start()

        outdata[:] = np.frombuffer(buf, dtype=np.int16).reshape(-1, self.CHANNELS)

    # ──────────────────────────────────────────────────────────────────
    # Свойства
    # ──────────────────────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self._is_playing and self._stream is not None

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def pending_chunks(self) -> int:
        return self._pending_chunks


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────
_audio_player = None
_lock = threading.Lock()


def get_audio_player() -> AudioPlayer:
    """Получить глобальный AudioPlayer."""
    global _audio_player
    with _lock:
        if _audio_player is None:
            _audio_player = AudioPlayer()
        return _audio_player


def release_audio_player():
    """Освободить (только при закрытии приложения)."""
    global _audio_player
    with _lock:
        if _audio_player:
            _audio_player.stop()
            _audio_player = None
