#!/usr/bin/env python3
"""
audio_recorder.py — рекордер аудиокниг для NovaReader.

Превращает текст глав книги в MP3-файлы (по одному файлу на главу).
Работает как самостоятельный модуль — тестируется через test_audio_recorder.py
без читалки.

Название книги озвучивается перед КАЖДОЙ главой (например «Вперёд в
прошлое», пауза — и сразу текст главы) — так каждый файл самодостаточен
и понятен сам по себе, независимо от формата книги. Номер/название главы
здесь НЕ добавляется — это уже есть в самом тексте главы (её заголовок),
повторное произнесение "Глава N" привело бы к дублированию.

Пайплайн (Piper):
  вступление (только название книги) + текст главы → разбивка на предложения
    → piper --output_raw (PCM s16le mono) для каждого предложения
    → склейка PCM с паузой между вступлением и текстом главы
    → ffmpeg → MP3

Пайплайн (Edge TTS):
  синтез через edge_tts.Communicate.stream() (а не .save() — у .save()
  изредка "проглатывается" самое начало аудио, из-за чего терялось
  название главы; stream() читает чанки вручную и это не теряет).
  Вступление и текст главы синтезируются отдельно и склеиваются через
  ffmpeg с паузой между ними.
"""

import re
import sys
import json
import shutil
import asyncio
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Dict


# ── разбивка текста на предложения ─────────────────────────────
_SENT_SPLIT = re.compile(r'(?<=[.!?…])\s+(?=[A-ZА-ЯЁ"«—–-])')

def split_sentences(text: str) -> List[str]:
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    return [p.strip() for p in _SENT_SPLIT.split(text) if len(p.strip()) >= 2]


def safe_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip('. ')
    return name[:max_len] or 'chapter'


def _run_async(coro):
    """Запускает корутину даже из фонового (не главного) потока.

    asyncio.run() иногда падает в дочерних QThread с
    'There is no current event loop in thread ...' — создаём и закрываем
    цикл явно, это надёжно работает в любом потоке."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        finally:
            asyncio.set_event_loop(None)


# Пауза между вступлением (название книги/главы) и текстом главы.
_INTRO_PAUSE_MS = 700


class AudiobookRecorder:
    """Рекордер аудиокниг: главы → MP3."""

    def __init__(self, config, output_dir: str,
                 engine: str = 'Piper',
                 voice: Optional[str] = None,
                 rate: float = 1.0):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = engine
        self.rate = float(rate)
        if voice:
            self.voice = voice
        elif engine == 'Edge':
            self.voice = config.get('edge_tts_voice', 'ru-RU-DariyaNeural')
        else:
            self.voice = config.get('piper_voice', 'ru_RU_irina_medium')
        self._stop = False
        self.last_error: Optional[str] = None

        self.piper_bin = self._find_piper_binary()
        self.ffmpeg = shutil.which('ffmpeg')

    def stop(self):
        self._stop = True

    # ── поиск бинарников ───────────────────────────────────────
    def _find_piper_binary(self) -> Optional[Path]:
        root = Path(__file__).resolve().parent
        candidates = []
        if sys.platform == 'win32':
            candidates.append(root / 'tts' / 'piper-win' / 'piper.exe')
        else:
            candidates.append(root / 'tts' / 'piper' / 'piper')
        candidates.append(root / 'piper')
        for c in candidates:
            if c.exists():
                return c
        in_path = shutil.which('piper')
        return Path(in_path) if in_path else None

    def _voice_path(self) -> Optional[Path]:
        if hasattr(self.config, 'find_voice_path'):
            p = self.config.find_voice_path(self.voice)
            if p:
                return Path(p)
        vd = getattr(self.config, 'voices_dir', None)
        if vd:
            for f in Path(vd).rglob(f'{self.voice}.onnx'):
                return f
        return None

    def _voice_sample_rate(self, voice_path: Path) -> int:
        try:
            cfg = json.loads(Path(str(voice_path) + '.json')
                             .read_text(encoding='utf-8'))
            return int(cfg.get('audio', {}).get('sample_rate', 22050))
        except Exception:
            return 22050

    @staticmethod
    def _silence_pcm(sample_rate: int, ms: int) -> bytes:
        """Тишина (16-бит моно PCM) заданной длительности — пауза между
        вступлением (название книги/главы) и текстом главы."""
        n_samples = int(sample_rate * ms / 1000)
        return b'\x00\x00' * n_samples

    # ── Piper: одно предложение → PCM ──────────────────────────
    def _piper_sentence_pcm(self, text: str, voice_path: Path) -> Optional[bytes]:
        if not self.piper_bin:
            return None
        cmd = [str(self.piper_bin), '-m', str(voice_path), '--output_raw']
        if self.rate != 1.0:
            cmd.extend(['--length-scale', f'{round(1.0 / self.rate, 3)}'])
        try:
            proc = subprocess.run(cmd, input=text.encode('utf-8'),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=300)
        except subprocess.TimeoutExpired:
            return None
        if proc.returncode != 0 or not proc.stdout:
            return None
        return proc.stdout

    # ── запись одной главы ─────────────────────────────────────
    def record_chapter(self, index: int, title: str, text: str,
                       progress_cb: Optional[Callable] = None,
                       intro_text: Optional[str] = None,
                       book_title: Optional[str] = None) -> Optional[Path]:
        """intro_text — вступление, произносимое перед текстом главы, с
        паузой после него (только название книги — без номера/названия
        главы, оно уже есть в тексте самой главы).
        book_title — для ID3-тега album (в дополнение к intro_text,
        который может включать ещё и часть книги)."""
        self.last_error = None
        sentences = split_sentences(text)
        if not sentences:
            self.last_error = 'empty_text'
            return None
        intro_text = (intro_text or '').strip() or None
        fname = safe_filename(f'{index:03d} - {title}')
        out_path = self.output_dir / f'{fname}.mp3'
        tags = self._id3_tags(index, title, book_title or intro_text)

        if self.engine == 'Piper':
            return self._record_piper(intro_text, sentences, out_path, progress_cb, tags)
        if self.engine == 'Edge':
            return self._record_edge(intro_text, text, out_path, progress_cb, tags)
        self.last_error = 'unknown_engine'
        return None

    @staticmethod
    def _id3_tags(index: int, title: str, album: Optional[str]) -> List[str]:
        """ffmpeg -metadata аргументы. Исполнитель ("artist"/"album_artist")
        захардкожен как "audiobook" — так эти файлы однозначно узнаются как
        сгенерированная аудиокнига, а не перепутываются с обычной музыкой."""
        args = [
            '-metadata', 'artist=audiobook',
            '-metadata', 'album_artist=audiobook',
            '-metadata', f'title={title}',
            '-metadata', f'track={index}',
            '-metadata', 'genre=Audiobook',
        ]
        if album:
            args += ['-metadata', f'album={album}']
        return args

    def _record_piper(self, intro_text, sentences, out_path, progress_cb=None, tags=None):
        voice_path = self._voice_path()
        if not voice_path:
            self.last_error = 'no_voice'
            print(f'[Recorder] Голос не найден: {self.voice}')
            return None
        if not self.piper_bin:
            self.last_error = 'no_piper'
            print('[Recorder] Бинарник piper не найден')
            return None
        if not self.ffmpeg:
            self.last_error = 'no_ffmpeg'
            print('[Recorder] ffmpeg не найден — установите ffmpeg')
            return None

        sample_rate = self._voice_sample_rate(voice_path)
        pcm_chunks = []
        total = len(sentences) + (1 if intro_text else 0)
        done = 0

        if intro_text:
            if self._stop:
                self.last_error = 'stopped'
                return None
            # Вступление синтезируется ОДНИМ куском (не через
            # split_sentences) — короткие фразы вроде названия книги
            # при синтезе по предложениям обрезались в конце (движок не
            # успевал доозвучить последний слог перед склейкой).
            intro_pcm = self._piper_sentence_pcm(intro_text.strip() + ' ', voice_path)
            if intro_pcm:
                # Небольшой хвостовой запас тишины ПЕРЕД склейкой —
                # подстраховка от обрезания последнего слога движком.
                pcm_chunks.append(intro_pcm)
                pcm_chunks.append(self._silence_pcm(sample_rate, 200))
            pcm_chunks.append(self._silence_pcm(sample_rate, _INTRO_PAUSE_MS))
            done += 1
            if progress_cb:
                progress_cb(done, total)

        for sent in sentences:
            if self._stop:
                self.last_error = 'stopped'
                return None
            pcm = self._piper_sentence_pcm(sent, voice_path)
            if pcm:
                pcm_chunks.append(pcm)
            done += 1
            if progress_cb:
                progress_cb(done, total)

        if not pcm_chunks:
            self.last_error = self.last_error or 'no_audio'
            return None
        pcm_all = b''.join(pcm_chunks)

        cmd = [self.ffmpeg, '-y',
               '-f', 's16le', '-ar', str(sample_rate), '-ac', '1',
               '-i', 'pipe:0',
               '-c:a', 'libmp3lame', '-b:a', '128k',
               *(tags or []),
               str(out_path)]
        try:
            proc = subprocess.run(cmd, input=pcm_all,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=600)
        except subprocess.TimeoutExpired:
            self.last_error = 'ffmpeg_failed'
            return None
        if proc.returncode != 0 or not out_path.exists():
            self.last_error = 'ffmpeg_failed'
            print('[Recorder] ffmpeg ошибка:',
                  proc.stderr.decode('utf-8', 'ignore')[-300:])
            return None
        return out_path

    # ── Edge TTS ─────────────────────────────────────────────────
    def _edge_synthesize(self, text: str, out_path: Path) -> bool:
        """Синтезирует text в mp3-файл out_path через edge_tts.

        Используем Communicate.stream() и сами собираем аудио-чанки —
        в отличие от Communicate.save(), это не теряет самое начало
        аудио (у .save() изредка "проглатывается" первое слово, из-за
        чего в главе пропадало произнесённое название)."""
        try:
            import edge_tts
        except ImportError:
            self.last_error = 'no_edge_tts'
            print('[Recorder] edge-tts не установлен')
            return False
        voice = self.voice or self.config.get('edge_tts_voice', 'ru-RU-DmitryNeural')

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=self._edge_rate())
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk.get('type') == 'audio' and chunk.get('data'):
                    audio.extend(chunk['data'])
            return bytes(audio)

        try:
            audio_bytes = _run_async(_run())
        except Exception as e:
            self.last_error = 'edge_error'
            print(f'[Recorder] Edge ошибка: {e}')
            return False
        if not audio_bytes:
            self.last_error = self.last_error or 'no_audio'
            print('[Recorder] Edge: пустой ответ от сервиса синтеза')
            return False
        try:
            out_path.write_bytes(audio_bytes)
        except OSError as e:
            self.last_error = 'write_failed'
            print(f'[Recorder] Не удалось записать файл: {e}')
            return False
        return True

    def _record_edge(self, intro_text, text, out_path, progress_cb=None, tags=None):
        """Синтез Edge TTS ПО ПРЕДЛОЖЕНИЯМ (как у Piper) — иначе вся
        глава уходит одним сетевым запросом, и прогресс-бар «зависает»
        на 1-2 шагах на долгое время, не показывая реального движения."""
        if not self.ffmpeg:
            self.last_error = 'no_ffmpeg'
            print('[Recorder] ffmpeg не найден — установите ffmpeg')
            return None
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
                if self._stop:
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
                if self._stop:
                    self.last_error = 'stopped'
                    return None
                seg_path = tmp_dir / f'seg_{i:04d}.mp3'
                if self._edge_synthesize(sent, seg_path):
                    segment_paths.append(('body', seg_path))
                done += 1
                if progress_cb:
                    progress_cb(done, total)
            body_ok = any(kind == 'body' for kind, _ in segment_paths)
            if not body_ok:
                self.last_error = self.last_error or 'no_audio'
                return None
            return self._concat_edge_segments(segment_paths, out_path, tags)

    def _concat_edge_segments(self, segment_paths, out_path, tags=None) -> Optional[Path]:
        """Склеивает mp3-сегменты (по предложениям) в один файл через
        ffmpeg concat, вставляя паузу там, где отмечено ('pause', None)."""
        pause_s = _INTRO_PAUSE_MS / 1000.0
        inputs = []
        filter_parts = []
        n = 0
        for kind, path in segment_paths:
            if kind == 'pause':
                inputs += ['-f', 'lavfi', '-t', f'{pause_s}', '-i', 'anullsrc=r=24000:cl=mono']
            else:
                inputs += ['-i', str(path)]
            filter_parts.append(f'[{n}:a]')
            n += 1
        filter_complex = ''.join(filter_parts) + f'concat=n={n}:v=0:a=1[out]'
        cmd = [self.ffmpeg, '-y', *inputs,
               '-filter_complex', filter_complex,
               '-map', '[out]',
               '-c:a', 'libmp3lame', '-b:a', '128k',
               *(tags or []),
               str(out_path)]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=600)
        except subprocess.TimeoutExpired:
            self.last_error = 'ffmpeg_failed'
            return None
        if proc.returncode != 0 or not out_path.exists():
            self.last_error = 'ffmpeg_failed'
            print('[Recorder] ffmpeg (склейка) ошибка:',
                  proc.stderr.decode('utf-8', 'ignore')[-300:])
            return None
        return out_path

    def _edge_rate(self) -> str:
        pct = int((self.rate - 1.0) * 100)
        return f'+{pct}%' if pct >= 0 else f'{pct}%'

    # ── запись всей книги ──────────────────────────────────────
    def record_book(self, chapters: List[Dict], book_title: str = '',
                    chapter_cb: Optional[Callable] = None,
                    sentence_cb: Optional[Callable] = None) -> List[Path]:
        """chapters: [{title, text, ...}]. Возвращает список созданных MP3.

        Нумерация файлов — по порядку среди переданных chapters (вызывающий
        код должен заранее убрать титульный лист/аннотацию/сноски, если они
        не нужны). Вступление в каждом файле — только название книги, без
        "Глава N" (номер/заголовок главы уже есть в тексте самой главы)."""
        results = []
        total = len(chapters)
        for i, ch in enumerate(chapters):
            if self._stop:
                break
            title = ch.get('title') or f'Глава {i+1}'
            text = ch.get('text', '')
            # Только название книги — номер/заголовок главы уже есть в
            # тексте самой главы, дублировать не нужно.
            intro = book_title if book_title else None
            def _sent_cb(done, tot, _i=i):
                if sentence_cb:
                    sentence_cb(_i, done, tot)
            path = self.record_chapter(i + 1, title, text,
                                       progress_cb=_sent_cb, intro_text=intro)
            if path:
                results.append(path)
            if chapter_cb:
                chapter_cb(i + 1, total, path)
        return results
