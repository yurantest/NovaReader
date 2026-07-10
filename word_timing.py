"""
word_timing.py — определение границ слов внутри PCM-аудио
через анализ амплитуды (Voice Activity Detection).

Используется для пословной подсветки когда TTS-движок не предоставляет
нативных таймингов (как у Piper, в отличие от Edge TTS WordBoundary).

Принцип:
  1. PCM int16 моно разбивается на короткие окна (~10-20ms)
  2. Для каждого окна считается RMS-энергия
  3. Окна с энергией ниже порога считаются "тишиной" (паузы между словами)
  4. Последовательности "звука" между паузами — это произнесённые слова
  5. Найденные сегменты сопоставляются по порядку с реальными словами текста

ВАЖНО: это эвристика, не идеальный speech-to-text alignment.
Работает достаточно хорошо для слитной речи с естественными паузами,
но может ошибаться на слитно произнесённых коротких словах (предлоги,
союзы) — в таких случаях несколько слов попадают в один сегмент.
"""

from __future__ import annotations
import numpy as np


def detect_word_segments(
    pcm_bytes: bytes,
    sample_rate: int = 22050,
    n_words: int = 1,
    window_ms: float = 10.0,
    min_silence_ms: float = 60.0,
    min_word_ms: float = 40.0,
    energy_percentile: float = 15.0,
) -> list[tuple[float, float]]:
    """
    Находит временные границы слов в PCM-аудио через анализ энергии.

    Args:
        pcm_bytes: сырой PCM int16 mono
        sample_rate: частота дискретизации (Piper обычно 22050)
        n_words: ожидаемое количество слов (для коррекции при несовпадении)
        window_ms: размер окна анализа в миллисекундах
        min_silence_ms: минимальная длина паузы чтобы считать её разделителем
        min_word_ms: минимальная длина сегмента чтобы считать его словом
        energy_percentile: процентиль энергии для адаптивного порога тишины

    Returns:
        Список (start_sec, end_sec) — по одному на каждый найденный сегмент.
        Если найдено сегментов больше/меньше чем n_words, сегменты
        перераспределяются пропорционально (см. _redistribute_to_word_count).
    """
    if not pcm_bytes or len(pcm_bytes) < 4:
        return [(0.0, 0.0)] * max(n_words, 1)

    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    total_samples = len(audio)
    total_duration = total_samples / sample_rate

    if n_words <= 1:
        return [(0.0, total_duration)]

    window_samples = max(1, int(sample_rate * window_ms / 1000))
    n_windows = total_samples // window_samples

    if n_windows < 2:
        return _redistribute_to_word_count([(0.0, total_duration)], n_words)

    # RMS-энергия по окнам
    energies = np.zeros(n_windows)
    for i in range(n_windows):
        chunk = audio[i * window_samples:(i + 1) * window_samples]
        energies[i] = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0.0

    # Адаптивный порог тишины — процентиль энергии (а не абсолютное число),
    # чтобы работать одинаково и на тихих, и на громких голосах/записях
    nonzero = energies[energies > 0]
    if len(nonzero) == 0:
        return _redistribute_to_word_count([(0.0, total_duration)], n_words)
    silence_threshold = max(
        np.percentile(nonzero, energy_percentile),
        nonzero.max() * 0.03,  # не даём порогу быть нулевым на полной тишине
    )

    is_voiced = energies > silence_threshold

    # Сглаживаем — убираем одиночные провалы/всплески короче min_word_ms
    min_silence_windows = max(1, int(min_silence_ms / window_ms))
    min_word_windows = max(1, int(min_word_ms / window_ms))

    is_voiced = _remove_short_runs(is_voiced, min_silence_windows, target=False)
    is_voiced = _remove_short_runs(is_voiced, min_word_windows, target=True)

    # Находим сегменты "звука"
    segments = []
    start_idx = None
    for i, v in enumerate(is_voiced):
        if v and start_idx is None:
            start_idx = i
        elif not v and start_idx is not None:
            segments.append((start_idx * window_ms / 1000, i * window_ms / 1000))
            start_idx = None
    if start_idx is not None:
        segments.append((start_idx * window_ms / 1000, total_duration))

    if not segments:
        segments = [(0.0, total_duration)]

    return _redistribute_to_word_count(segments, n_words, total_duration)


def _remove_short_runs(arr: np.ndarray, min_len: int, target: bool) -> np.ndarray:
    """Убирает короткие последовательности значения `target` короче min_len,
    заменяя их на противоположное значение (сглаживание шума)."""
    result = arr.copy()
    i = 0
    n = len(arr)
    while i < n:
        if arr[i] == target:
            j = i
            while j < n and arr[j] == target:
                j += 1
            if (j - i) < min_len:
                result[i:j] = not target
            i = j
        else:
            i += 1
    return result


def _redistribute_to_word_count(
    segments: list[tuple[float, float]],
    n_words: int,
    total_duration: float | None = None,
) -> list[tuple[float, float]]:
    """
    Подгоняет количество найденных аудио-сегментов под ожидаемое
    количество слов:
      - Если сегментов больше слов → объединяем соседние самые короткие паузы
      - Если сегментов меньше слов → делим самые длинные сегменты пополам
      - В крайнем случае — просто делим общую длительность поровну
    """
    if total_duration is None:
        total_duration = segments[-1][1] if segments else 0.0

    if n_words <= 0:
        return segments

    segs = list(segments)

    # Слишком много сегментов — сливаем ближайшие пары пока не дойдём до n_words
    while len(segs) > n_words and len(segs) > 1:
        # Находим пару с минимальным промежутком (тишиной) между ними
        gaps = [segs[i + 1][0] - segs[i][1] for i in range(len(segs) - 1)]
        merge_idx = int(np.argmin(gaps))
        merged = (segs[merge_idx][0], segs[merge_idx + 1][1])
        segs = segs[:merge_idx] + [merged] + segs[merge_idx + 2:]

    # Слишком мало сегментов — делим самые длинные пополам
    while len(segs) < n_words:
        durations = [e - s for s, e in segs]
        split_idx = int(np.argmax(durations))
        s, e = segs[split_idx]
        mid = (s + e) / 2
        segs = segs[:split_idx] + [(s, mid), (mid, e)] + segs[split_idx + 1:]

    # Финальная подстраховка — если всё ещё не совпадает, равномерно режем всю длительность
    if len(segs) != n_words:
        step = total_duration / n_words
        segs = [(i * step, (i + 1) * step) for i in range(n_words)]

    return segs


def estimate_word_timings_ms(
    pcm_bytes: bytes,
    word_count: int,
    sample_rate: int = 22050,
) -> list[dict]:
    """
    Удобная обёртка: возвращает список словарей с таймингами в миллисекундах,
    готовый для передачи в JS через JSON.

    Returns:
        [{"start_ms": int, "end_ms": int}, ...] — по одному на каждое слово
    """
    segments = detect_word_segments(pcm_bytes, sample_rate=sample_rate, n_words=word_count)
    return [
        {"start_ms": round(start * 1000), "end_ms": round(end * 1000)}
        for start, end in segments
    ]
