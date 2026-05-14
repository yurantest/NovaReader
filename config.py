import json
import hashlib
import uuid
import os
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime


class Config:
    """Менеджер конфигурации и библиотеки"""

    @staticmethod
    def _get_config_dir() -> Path:
        """Возвращает папку конфигурации по стандарту ОС:
           Linux/Mac : ~/.config/NovaReader
           Windows   : %APPDATA%/NovaReader
        """
        import sys, os
        if sys.platform == 'win32':
            base = Path(os.environ.get('APPDATA', Path.home()))
        elif sys.platform == 'darwin':
            base = Path.home() / 'Library' / 'Application Support'
        else:
            xdg = os.environ.get('XDG_CONFIG_HOME', '')
            base = Path(xdg) if xdg else Path.home() / '.config'
        d = base / 'NovaReader'
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _get_default_library_dir() -> Path:
        """Возвращает дефолтную папку библиотеки:
           Linux/Mac: ~/Библиотека
           Windows  : ~/Documents/NovaReader Books
        """
        import sys
        if sys.platform == 'win32':
            p = Path.home() / 'Documents' / 'NovaReader Books'
        else:
            # ~/Библиотека — удобно на Linux/Mac для русских пользователей
            p = Path.home() / 'Библиотека'
        p.mkdir(parents=True, exist_ok=True)
        return p

    def __init__(self):
        self.config_dir = self._get_config_dir()

        self.config_file = self.config_dir / 'settings.json'
        self.library_file = self.config_dir / 'library.json'
        self.positions_file = self.config_dir / 'positions.json'
        self.highlights_file = self.config_dir / 'highlights.json'
        self.notes_file = self.config_dir / 'notes.json'
        self.bookmarks_file = self.config_dir / 'bookmarks.json'

        # Директория для голосов
        self.voices_dir = self.config_dir / 'voices'
        self.voices_dir.mkdir(exist_ok=True)

        # Также проверяем стандартные расположения голосов Piper
        self.piper_voices_dirs = [
            Path.home() / '.local/share/piper-tts/voices',
            Path.home() / '.local/share/piper/voices',
            Path('/usr/share/piper-tts/voices'),
            Path('/usr/local/share/piper-tts/voices'),
        ]

        self._data = self._load()
        self._library = self._load_library()   # может запустить миграцию
        self._positions = self._load_positions()
        self._highlights = self._load_highlights()
        self._notes = self._load_notes()
        self._bookmarks = self._load_bookmarks()

        # Путь к библиотеке (может быть изменен пользователем)
        self.library_path = Path(self.get('library_path', str(self.config_dir / 'books')))
        self.library_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_path(path) -> str:
        """Приводит путь к единому формату: прямые слеши / (POSIX-стиль)"""
        return str(path).replace('\\', '/')

    def _load(self) -> dict:
        """Загрузить настройки"""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding='utf-8'))
            except:
                pass

        # Настройки по умолчанию
        return {
            'window_width': 1200,
            'window_height': 800,
            'library_width': 1000,
            'library_height': 700,
            'theme_bg': '#f4ecd8',
            'theme_text': '#5b4636',
            'font_size': 16,
            'line_height': 1.5,
            'column_width': 500,
            'spread_mode': 'auto',
            'tts_rate': 1.0,
            # Голос по умолчанию для Piper
            'tts_voice': 'ru_RU_irina_medium',
            'tts_engine': 'Piper',
            'preferred_engine': 'Piper',
            # Голоса по умолчанию для каждого движка
            'piper_voice': 'ru_RU_irina_medium',      # Piper → Ирина
            'edge_tts_voice': 'ru-RU-DariyaNeural',   # Edge TTS
            'speechd_voice': 'ru_RU',                 # SpeechD (RHVoice) → Анна будет выбрана автоматически
            'library_path': str(Config._get_default_library_dir()),
            'first_run': True,
            'language': 'ru',
            'language': 'ru',
            # Настройки подсветки по умолчанию
            'default_highlight_style': 'highlight',
            'default_highlight_color': 'blue',
            # Цвет TTS-подсветки по умолчанию
            'tts_highlight_color': 'cyan',
        }

    # ══════════════════════════════════════════════════════════════════
    # НАСТРОЙКИ
    # ══════════════════════════════════════════════════════════════════

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()
        if key == 'library_path':
            self.library_path = Path(value)
            self.library_path.mkdir(parents=True, exist_ok=True)

    def save(self):
        self.config_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding='utf-8')

    def is_first_run(self) -> bool:
        return self.get('first_run', True)

    def get_library_path(self) -> Path:
        return self.library_path

    # ══════════════════════════════════════════════════════════════════
    # ЗАКЛАДКИ (навигационные, не путать с позицией чтения)
    # ══════════════════════════════════════════════════════════════════

    def save_bookmarks(self):
        self.bookmarks_file.write_text(
            json.dumps(self._bookmarks, indent=2, ensure_ascii=False),
            encoding='utf-8')

    def add_bookmark(self, book_path: str, bookmark: Dict):
        normalized_path = self._normalize_path(book_path)
        self._bookmarks.setdefault(normalized_path, []).append(bookmark)
        self.save_bookmarks()
        print(f"[Config] Закладка сохранена: {bookmark.get('label')}")

    def get_bookmarks(self, book_path: str) -> List[Dict]:
        normalized_path = self._normalize_path(book_path)
        return self._bookmarks.get(normalized_path, [])

    def remove_bookmark(self, book_path: str, bookmark_id: str) -> bool:
        normalized_path = self._normalize_path(book_path)
        if normalized_path in self._bookmarks:
            orig = len(self._bookmarks[normalized_path])
            self._bookmarks[normalized_path] = [
                b for b in self._bookmarks[normalized_path]
                if b.get('id') != bookmark_id
            ]
            self.save_bookmarks()
            return orig != len(self._bookmarks[normalized_path])
        return False

    # ══════════════════════════════════════════════════════════════════
    # БИБЛИОТЕКА: структура library.json
    #
    # Каждая запись — одна книга по смыслу:
    # {
    #   "id": "uuid",
    #   "title": "...", "author": "...", "series": ..., "series_number": ...,
    #   "description": null, "cover_path": "...",
    #   "formats": {"epub": "/path/book.epub", "fb2": "/path/book.fb2"}
    # }
    #
    # positions.json — позиции чтения, вынесены отдельно:
    # { "/path/book.epub": {"progress": 0.47, "position": {...}, "last_read": "..."} }
    # ══════════════════════════════════════════════════════════════════

    def _load_library(self) -> List[Dict]:
        """Загружает library.json, при необходимости запускает миграцию."""
        if not self.library_file.exists():
            return []
        try:
            raw = json.loads(self.library_file.read_text(encoding='utf-8'))
        except Exception:
            return []
        if not isinstance(raw, list) or not raw:
            return []

        first = raw[0]
        # ── Определяем версию формата ──────────────────────────────────
        if isinstance(first.get('formats'), dict):
            first_fmt_val = next(iter(first['formats'].values()), None)
            if isinstance(first_fmt_val, str):
                # Уже финальный формат v2 (formats: {fmt: path_str})
                return raw
            elif isinstance(first_fmt_val, dict):
                # Промежуточный формат v1 (formats: {fmt: {file_path, progress, ...}})
                return self._migrate_v1_to_v2(raw)
        # Старый плоский формат — полная миграция
        return self._migrate_flat_to_v2(raw)

    def _load_positions(self) -> Dict:
        """Загрузить positions.json с нормализацией ключей."""
        if self.positions_file.exists():
            try:
                raw = json.loads(self.positions_file.read_text(encoding='utf-8'))
                # Нормализуем все ключи
                return {self._normalize_path(k): v for k, v in raw.items()}
            except Exception:
                pass
        return {}

    def save_positions(self):
        """Сохранить positions.json с нормализацией ключей."""
        normalized = {self._normalize_path(k): v for k, v in self._positions.items()}
        self.positions_file.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding='utf-8')

    # ── Миграции ──────────────────────────────────────────────────────

    def _backup_library(self, suffix: str = '.json.bak'):
        """Создать резервную копию library.json перед миграцией."""
        import shutil
        backup = self.library_file.with_name(self.library_file.stem + suffix)
        try:
            shutil.copy2(self.library_file, backup)
            print(f'[Config] Резервная копия: {backup}')
        except Exception as e:
            print(f'[Config] Не удалось создать резервную копию: {e}')

    def _migrate_flat_to_v2(self, old_list: List[Dict]) -> List[Dict]:
        """
        Старый плоский формат → v2.
        Каждая запись: {title, author, ..., file_path, format, progress, position, last_read}
        Группирует по title+author, извлекает позиции в positions.json.
        """
        import shutil
        self._backup_library('.json.bak')

        positions: Dict[str, Dict] = {}
        seen: Dict[tuple, Dict] = {}
        new_books: List[Dict] = []

        for old in old_list:
            title  = (old.get('title') or '').strip()
            author = (old.get('author') or 'Неизвестен').strip()
            key    = self._book_key(title, author)

            fp      = self._normalize_path(old.get('file_path', ''))
            fmt_str = (old.get('format') or '').lower().lstrip('.')
            if not fmt_str and fp:
                fmt_str = Path(fp).suffix.lower().lstrip('.') or 'unknown'

            # Извлекаем позицию
            if fp and (old.get('progress') or old.get('position') or old.get('last_read')):
                positions[fp] = {
                    'progress':  old.get('progress', 0),
                    'position':  old.get('position'),
                    'last_read': old.get('last_read'),
                }

            if key in seen:
                seen[key]['formats'][fmt_str] = fp
            else:
                record = {
                    'id':            str(uuid.uuid4()),
                    'title':         title,
                    'author':        author,
                    'series':        old.get('series'),
                    'series_number': old.get('series_number'),
                    'description':   old.get('description'),
                    'cover_path':    self._normalize_path(old.get('cover_path', '')),
                    'formats':       {fmt_str: fp},
                }
                seen[key] = record
                new_books.append(record)

        # Сохраняем
        self.library_file.write_text(
            json.dumps(new_books, indent=2, ensure_ascii=False), encoding='utf-8')
        # Мержим с существующим positions.json
        existing = self._load_positions()
        existing.update(positions)
        self._positions = existing
        self.save_positions()

        print(f'[Config] Миграция flat→v2: {len(old_list)} записей → '
              f'{len(new_books)} книг, {len(positions)} позиций')
        return new_books

    def _migrate_v1_to_v2(self, v1_list: List[Dict]) -> List[Dict]:
        """
        Промежуточный формат v1 → v2.
        formats: {fmt: {file_path, progress, position, last_read, added}} →
        formats: {fmt: file_path_str}, позиции → positions.json
        """
        self._backup_library('.v1.json.bak')
        positions: Dict[str, Dict] = {}

        for book in v1_list:
            new_fmts: Dict[str, str] = {}
            for fmt, fdata in (book.get('formats') or {}).items():
                if isinstance(fdata, dict):
                    fp = self._normalize_path(fdata.get('file_path', ''))
                    new_fmts[fmt] = fp
                    if fp and (fdata.get('progress') or fdata.get('position') or fdata.get('last_read')):
                        positions[fp] = {
                            'progress':  fdata.get('progress', 0),
                            'position':  fdata.get('position'),
                            'last_read': fdata.get('last_read'),
                        }
                elif isinstance(fdata, str):
                    new_fmts[fmt] = self._normalize_path(fdata)
            book['formats'] = new_fmts
            book['cover_path'] = self._normalize_path(book.get('cover_path', ''))
            # Убираем поля позиций из корня книги если остались
            for field in ('progress', 'position', 'last_read', 'added', 'file_path', 'format'):
                book.pop(field, None)

        self.library_file.write_text(
            json.dumps(v1_list, indent=2, ensure_ascii=False), encoding='utf-8')
        existing = self._load_positions()
        existing.update(positions)
        self._positions = existing
        self.save_positions()
        print(f'[Config] Миграция v1→v2: {len(positions)} позиций перенесено')
        return v1_list

    # ── Вспомогательные ───────────────────────────────────────────────

    _FMT_PRIORITY = ['epub', 'fb2', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr', 'unknown']

    def _primary_format(self, book: Dict) -> tuple:
        """(fmt_str, file_path) приоритетного формата."""
        fmts = book.get('formats', {})
        for fmt in self._FMT_PRIORITY:
            fp = fmts.get(fmt, '')
            if fp and Path(fp).exists():
                return fmt, fp
        # Берём первый существующий
        for fmt, fp in fmts.items():
            if fp and Path(fp).exists():
                return fmt, fp
        # Fallback: первый с непустым путём
        for fmt, fp in fmts.items():
            if fp:
                return fmt, fp
        return '', ''

    def _book_by_path(self, file_path: str) -> tuple:
        """(book_record, fmt_str) по file_path или (None, '')."""
        fp = self._normalize_path(file_path)
        for book in self._library:
            for fmt, path in book.get('formats', {}).items():
                if self._normalize_path(path) == fp:
                    return book, fmt
        return None, ''

    def _book_by_id(self, book_id: str) -> Optional[Dict]:
        for book in self._library:
            if book.get('id') == book_id:
                return book
        return None

    def _book_key(self, title: str, author: str) -> tuple:
        return (
            ' '.join((title or '').strip().lower().split()),
            ' '.join((author or 'неизвестен').strip().lower().split()),
        )

    # ── Публичный API ─────────────────────────────────────────────────

    def get_books(self) -> List[Dict]:
        """Плоский список view-объектов (один на книгу).
        Совместим со старым кодом. Позиция берётся из positions.json."""
        result = []
        for book in self._library:
            fmt, fp = self._primary_format(book)
            if not fp:
                continue
            pos_data = self._positions.get(self._normalize_path(fp), {})
            # last_read = максимум по всем форматам книги
            last_read = max(
                (self._positions.get(self._normalize_path(path), {}).get('last_read') or ''
                 for path in book.get('formats', {}).values() if path),
                default='') or None
            view = {
                '_book_id':      book['id'],
                'id':            book['id'],
                'title':         book.get('title', ''),
                'author':        book.get('author', ''),
                'series':        book.get('series'),
                'series_number': book.get('series_number'),
                'description':   book.get('description'),
                'cover_path':    book.get('cover_path', ''),
                'file_path':     fp,
                'format':        fmt,
                'progress':      pos_data.get('progress', 0),
                'position':      pos_data.get('position'),
                'last_read':     last_read,
                # Все форматы книги: {fmt: file_path}
                'formats':       {f: p for f, p in book.get('formats', {}).items() if p},
            }
            result.append(view)
        return result

    def get_book_record(self, book_id: str) -> Optional[Dict]:
        """Полная запись книги по ID."""
        return self._book_by_id(book_id)

    def get_book_by_path(self, file_path: str) -> Optional[Dict]:
        """View-объект книги по file_path."""
        book, _ = self._book_by_path(file_path)
        if not book:
            return None
        views = [v for v in self.get_books() if v['id'] == book['id']]
        return views[0] if views else None

    def save_library(self):
        """Сохранить library.json с нормализацией путей."""
        # Создаём копию с нормализованными путями
        normalized_library = []
        for book in self._library:
            book_copy = book.copy()
            if 'formats' in book_copy:
                book_copy['formats'] = {fmt: self._normalize_path(p) for fmt, p in book_copy['formats'].items()}
            if 'cover_path' in book_copy and book_copy['cover_path']:
                book_copy['cover_path'] = self._normalize_path(book_copy['cover_path'])
            normalized_library.append(book_copy)
        self.library_file.write_text(
            json.dumps(normalized_library, indent=2, ensure_ascii=False),
            encoding='utf-8')

    def add_book(self, book_info: Dict):
        """Добавить книгу или новый формат к существующей."""
        title  = (book_info.get('title') or '').strip()
        author = (book_info.get('author') or 'Неизвестен').strip()
        key    = self._book_key(title, author)

        fp      = self._normalize_path(book_info.get('file_path', ''))
        fmt_str = (book_info.get('format') or '').lower().lstrip('.')
        if not fmt_str and fp:
            fmt_str = Path(fp).suffix.lower().lstrip('.') or 'unknown'

        now = datetime.now().isoformat()

        for book in self._library:
            if self._book_key(book.get('title', ''),
                              book.get('author', '')) == key:
                book.setdefault('formats', {})[fmt_str] = fp
                if book_info.get('cover_path'):
                    book['cover_path'] = self._normalize_path(book_info['cover_path'])
                # Обновляем метку последнего изменения —
                # новый формат (напр. EPUB после конвертации) должен
                # "всплыть" в сортировке «По последнему чтению»
                book['last_modified'] = now
                self.save_library()
                print(f'[Config] Формат {fmt_str} добавлен к «{title}»')
                return

        record = {
            'id':            str(uuid.uuid4()),
            'title':         title,
            'author':        author,
            'series':        book_info.get('series'),
            'series_number': book_info.get('series_number'),
            'description':   book_info.get('description'),
            'cover_path':    self._normalize_path(book_info.get('cover_path', '')),
            'formats':       {fmt_str: fp},
            'added':         now,
            'last_modified': now,
        }
        self._library.append(record)
        self.save_library()
        print(f'[Config] Книга добавлена: «{title}» ({fmt_str})')

    def remove_format(self, file_path: str):
        """Удалить формат. Если форматов не осталось — удаляет запись."""
        book, fmt = self._book_by_path(file_path)
        if not book:
            return
        book.get('formats', {}).pop(fmt, None)
        normalized_path = self._normalize_path(file_path)
        self._positions.pop(normalized_path, None)
        if not book.get('formats'):
            self._library = [b for b in self._library if b['id'] != book['id']]
        self.save_library()
        self.save_positions()

    def remove_book(self, file_path: str):
        """Удалить книгу целиком (все форматы) по file_path."""
        book, _ = self._book_by_path(file_path)
        if book:
            for fp in book.get('formats', {}).values():
                self._positions.pop(self._normalize_path(fp), None)
            self._library = [b for b in self._library if b['id'] != book['id']]
            self.save_library()
            self.save_positions()

    def remove_book_by_id(self, book_id: str):
        """Удалить книгу целиком по ID."""
        book = self._book_by_id(book_id)
        if book:
            for fp in book.get('formats', {}).values():
                self._positions.pop(self._normalize_path(fp), None)
            self._library = [b for b in self._library if b['id'] != book_id]
            self.save_library()
            self.save_positions()

    def cleanup_missing(self):
        """Удалить форматы с несуществующими файлами."""
        changed = False
        to_remove = []
        for book in self._library:
            fmts = book.get('formats', {})
            dead = [f for f, p in fmts.items()
                    if not (p and Path(p).exists())]
            for f in dead:
                self._positions.pop(self._normalize_path(fmts.pop(f, '')), None)
                changed = True
            if not fmts:
                to_remove.append(book['id'])
        if to_remove:
            self._library = [b for b in self._library
                             if b['id'] not in to_remove]
            changed = True
        if changed:
            self.save_library()
            self.save_positions()
        return changed

    def update_progress(self, file_path: str, progress: float, position):
        """Обновить прогресс и позицию в positions.json."""
        if not file_path:
            return
        if isinstance(position, str):
            try:
                position = json.loads(position)
            except Exception:
                position = {'section': 0}
        normalized_path = self._normalize_path(file_path)
        self._positions[normalized_path] = {
            'progress':  progress,
            'position':  position,
            'last_read': datetime.now().isoformat(),
        }
        self.save_positions()

    def mark_as_read(self, file_path: str):
        """Обновить last_read в positions.json."""
        if file_path:
            normalized_path = self._normalize_path(file_path)
            rec = self._positions.setdefault(normalized_path, {})
            rec['last_read'] = datetime.now().isoformat()
            self.save_positions()

    def get_bookmark(self, file_path: str) -> Optional[Dict]:
        """Позиция и прогресс из positions.json."""
        if not file_path:
            return None
        normalized_path = self._normalize_path(file_path)
        rec = self._positions.get(normalized_path)
        if not rec:
            # fallback для старых записей с двойными обратными слешами
            alt_path = str(file_path).replace('/', '\\\\')
            rec = self._positions.get(alt_path)
        if not rec:
            return None
        return {
            'progress': rec.get('progress', 0),
            'position': rec.get('position'),
        }

    def get_position_for_path(self, file_path: str) -> Dict:
        """Полная запись позиции из positions.json."""
        normalized_path = self._normalize_path(file_path)
        return self._positions.get(normalized_path, {})


    def _load_highlights(self) -> Dict:
        if self.highlights_file.exists():
            try:
                raw = json.loads(self.highlights_file.read_text(encoding='utf-8'))
                # Нормализуем ключи
                return {self._normalize_path(k): v for k, v in raw.items()}
            except Exception:
                pass
        return {}

    def _load_notes(self) -> Dict:
        if self.notes_file.exists():
            try:
                raw = json.loads(self.notes_file.read_text(encoding='utf-8'))
                # Нормализуем ключи
                return {self._normalize_path(k): v for k, v in raw.items()}
            except Exception:
                pass
        return {}

    def _load_bookmarks(self) -> Dict:
        if self.bookmarks_file.exists():
            try:
                raw = json.loads(self.bookmarks_file.read_text(encoding='utf-8'))
                # Нормализуем ключи
                return {self._normalize_path(k): v for k, v in raw.items()}
            except Exception:
                pass
        return {}

    # ==================== МЕТОДЫ ДЛЯ ПОДСВЕТОК ====================

    def save_highlights(self):
        """Сохранить highlights.json с нормализацией ключей."""
        normalized = {self._normalize_path(k): v for k, v in self._highlights.items()}
        self.highlights_file.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding='utf-8')

    def save_notes(self):
        """Сохранить notes.json с нормализацией ключей."""
        normalized = {self._normalize_path(k): v for k, v in self._notes.items()}
        self.notes_file.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding='utf-8')

    def add_highlight(self, book_path: str, highlight: Dict):
        """Добавить подсветку для книги"""
        normalized_path = self._normalize_path(book_path)
        if normalized_path not in self._highlights:
            self._highlights[normalized_path] = []

        self._highlights[normalized_path].append(highlight)
        self.save_highlights()
        print(f"[Config] Подсветка сохранена: {highlight.get('id')} - {highlight.get('color')}")

    def get_highlights(self, book_path: str) -> List[Dict]:
        """Получить все подсветки для книги"""
        normalized_path = self._normalize_path(book_path)
        return self._highlights.get(normalized_path, [])

    def remove_highlight(self, book_path: str, highlight_id: str) -> bool:
        """Удалить подсветку по ID"""
        normalized_path = self._normalize_path(book_path)
        if normalized_path in self._highlights:
            original_count = len(self._highlights[normalized_path])
            self._highlights[normalized_path] = [
                h for h in self._highlights[normalized_path]
                if h.get('id') != highlight_id
            ]
            removed_count = original_count - len(self._highlights[normalized_path])
            self.save_highlights()
            print(f"[Config] Подсветка удалена: {highlight_id}, удалено: {removed_count}")
            return removed_count > 0
        return False

    def clear_highlights(self, book_path: str):
        """Удалить все подсветки для книги"""
        normalized_path = self._normalize_path(book_path)
        if normalized_path in self._highlights:
            self._highlights[normalized_path] = []
            self.save_highlights()
            print(f"[Config] Все подсветки для {book_path} удалены")

    # ==================== МЕТОДЫ ДЛЯ ЗАМЕТОК ====================

    def add_note(self, book_path: str, note: Dict):
        """Добавить заметку для книги"""
        normalized_path = self._normalize_path(book_path)
        if normalized_path not in self._notes:
            self._notes[normalized_path] = []

        self._notes[normalized_path].append(note)
        self.save_notes()
        print(f"[Config] Заметка сохранена")

    def get_notes(self, book_path: str) -> List[Dict]:
        """Получить все заметки для книги"""
        normalized_path = self._normalize_path(book_path)
        return self._notes.get(normalized_path, [])

    def remove_note(self, book_path: str, note_id: str):
        """Удалить заметку по ID"""
        normalized_path = self._normalize_path(book_path)
        if normalized_path in self._notes:
            self._notes[normalized_path] = [
                n for n in self._notes[normalized_path]
                if n.get('id') != note_id
            ]
            self.save_notes()

    # ==================== ЭКСПОРТ ЗАМЕТОК И ПОДСВЕТОК ====================

    def get_all_notes_and_highlights(self) -> Dict[str, Dict]:
        """Получить все заметки и подсветки для всех книг.
        Возвращает dict: {book_path: {'book_info': {...}, 'notes': [...], 'highlights': [...]}}
        """
        result = {}
        # Строим индекс file_path → метаданные из новой структуры
        books_by_path: Dict[str, Dict] = {}
        for book in self._library:
            for fmt, fp in book.get('formats', {}).items():
                if fp:
                    books_by_path[self._normalize_path(fp)] = {
                        'title':  book.get('title', 'Неизвестно'),
                        'author': book.get('author', 'Неизвестен'),
                    }
        all_book_paths = set(self._notes.keys()) | set(self._highlights.keys())
        for book_path in all_book_paths:
            book_info = books_by_path.get(book_path, {})
            result[book_path] = {
                'book_info': {
                    'title':     book_info.get('title', 'Неизвестно'),
                    'author':    book_info.get('author', 'Неизвестен'),
                    'file_path': book_path,
                },
                'notes':      self._notes.get(book_path, []),
                'highlights': self._highlights.get(book_path, []),
            }
        return result

    def export_notes_to_txt(self, output_path: str) -> int:
        """Экспортировать все заметки и подсветки в TXT файл.
        Возвращает количество экспортированных книг.
        """
        from pathlib import Path
        
        data = self.get_all_notes_and_highlights()
        if not data:
            return 0
        
        lines = []
        lines.append("=" * 60)
        lines.append("NovaReader — Заметки и выделенные цитаты")
        lines.append(f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("=" * 60)
        lines.append("")
        
        books_count = 0
        for book_path, book_data in sorted(data.items(), key=lambda x: x[1]['book_info'].get('title', '')):
            book_info = book_data['book_info']
            notes = book_data['notes']
            highlights = book_data['highlights']
            
            # Пропускаем книги без заметок и подсветок
            if not notes and not highlights:
                continue
            
            books_count += 1
            
            # Заголовок книги
            lines.append("-" * 60)
            lines.append(f" {book_info['title']}")
            lines.append(f"   Автор: {book_info['author']}")
            lines.append("-" * 60)
            lines.append("")
            
            # Заметки
            if notes:
                lines.append(" ЗАМЕТКИ:")
                lines.append("")
                for i, note in enumerate(notes, 1):
                    note_text = note.get('text', '')
                    note_content = note.get('content', '')
                    timestamp = note.get('timestamp', '')
                    
                    if note_text:
                        lines.append(f"  [{i}] {note_text}")
                    if note_content:
                        lines.append(f"      {note_content}")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            lines.append(f"      {dt.strftime('%d.%m.%Y %H:%M')}")
                        except:
                            pass
                    lines.append("")
            
            # Подсветки
            if highlights:
                lines.append(" ВЫДЕЛЕННЫЕ ЦИТАТЫ:")
                lines.append("")
                for i, h in enumerate(highlights, 1):
                    text = h.get('text', '')
                    color = h.get('color', '')
                    style = h.get('style', 'highlight')
                    timestamp = h.get('timestamp', '')
                    
                    # Добавляем эмодзи цвета
                    color_emoji = {
                        'yellow': '', 'blue': '', 'green': '',
                        'pink': '', 'orange': '', 'purple': '',
                        'cyan': ''
                    }.get(color, '')
                    
                    style_prefix = {'underline': ' ', 'strikethrough': ' '}.get(style, '')
                    
                    lines.append(f"  {color_emoji}{style_prefix}\"{text}\"")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            lines.append(f"      {dt.strftime('%d.%m.%Y %H:%M')}")
                        except:
                            pass
                    lines.append("")
            
            lines.append("")
        
        # Записываем в файл
        output_file = Path(output_path)
        output_file.write_text('\n'.join(lines), encoding='utf-8')
        
        return books_count

    def export_notes_to_markdown(self, output_path: str) -> int:
        """Экспортировать все заметки и подсветки в Markdown файл.
        Возвращает количество экспортированных книг.
        """
        from pathlib import Path
        
        data = self.get_all_notes_and_highlights()
        if not data:
            return 0
        
        lines = []
        lines.append("#  NovaReader — Заметки и выделенные цитаты")
        lines.append("")
        lines.append(f"*Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}*")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        books_count = 0
        for book_path, book_data in sorted(data.items(), key=lambda x: x[1]['book_info'].get('title', '')):
            book_info = book_data['book_info']
            notes = book_data['notes']
            highlights = book_data['highlights']
            
            # Пропускаем книги без заметок и подсветок
            if not notes and not highlights:
                continue
            
            books_count += 1
            
            # Заголовок книги
            lines.append(f"##  {book_info['title']}")
            lines.append("")
            lines.append(f"**Автор:** {book_info['author']}")
            lines.append("")
            
            # Заметки
            if notes:
                lines.append("###  Заметки")
                lines.append("")
                for i, note in enumerate(notes, 1):
                    note_text = note.get('text', '')
                    note_content = note.get('content', '')
                    timestamp = note.get('timestamp', '')
                    
                    if note_text:
                        lines.append(f"**{i}.** {note_text}")
                    if note_content:
                        lines.append(f"> {note_content}")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            lines.append(f"*{dt.strftime('%d.%m.%Y %H:%M')}*")
                        except:
                            pass
                    lines.append("")
            
            # Подсветки
            if highlights:
                lines.append("###  Выделенные цитаты")
                lines.append("")
                for i, h in enumerate(highlights, 1):
                    text = h.get('text', '')
                    color = h.get('color', '')
                    style = h.get('style', 'highlight')
                    timestamp = h.get('timestamp', '')
                    
                    # Форматируем по цвету
                    color_name = {
                        'yellow': 'Жёлтый', 'blue': 'Синий', 'green': 'Зелёный',
                        'pink': 'Розовый', 'orange': 'Оранжевый', 'purple': 'Фиолетовый',
                        'cyan': 'Голубой'
                    }.get(color, color.title())
                    
                    style_format = {
                        'underline': f'__{text}__',
                        'strikethrough': f'~~{text}~~',
                        'highlight': f'=={text}=='
                    }.get(style, text)
                    
                    lines.append(f"- {style_format} *({color_name})*")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            lines.append(f"  — *{dt.strftime('%d.%m.%Y %H:%M')}*")
                        except:
                            pass
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # Записываем в файл
        output_file = Path(output_path)
        output_file.write_text('\n'.join(lines), encoding='utf-8')
        
        return books_count

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ГОЛОСАМИ ====================

    def get_available_voices(self) -> List[Dict]:
        """Получить список доступных голосов"""
        voices = []

        # Проверяем директорию приложения
        if self.voices_dir.exists():
            for voice_dir in self.voices_dir.iterdir():
                if voice_dir.is_dir():
                    onnx_file = voice_dir / f"{voice_dir.name}.onnx"
                    if onnx_file.exists():
                        voices.append({
                            'id': voice_dir.name,
                            'name': voice_dir.name.replace('_', ' ').title(),
                            'path': str(onnx_file),
                            'engine': 'piper',
                            'local': True
                        })

        # Проверяем стандартные расположения Piper
        for base_dir in self.piper_voices_dirs:
            if base_dir.exists():
                for onnx_file in base_dir.glob("*.onnx"):
                    voice_id = onnx_file.stem
                    # Проверяем, не добавили ли уже этот голос
                    if not any(v['id'] == voice_id for v in voices):
                        voices.append({
                            'id': voice_id,
                            'name': voice_id.replace('_', ' ').title(),
                            'path': str(onnx_file),
                            'engine': 'piper',
                            'local': True
                        })

        # Добавляем eSpeak как запасной вариант
        voices.append({
            'id': 'espeak-ru',
            'name': 'eSpeak (Русский)',
            'engine': 'espeak',
            'local': True
        })

        return voices


    def find_piper_binary(self):
        """
        Найти исполняемый файл piper.
        Порядок поиска:
          1. Рядом с exe (PyInstaller сборка — piper скопирован туда)
          2. venv рядом с исходниками
          3. ~/.local/bin  (pip install --user)
          4. Системный piper-tts (Arch Linux package)
          5. PATH
        """
        import subprocess, sys, shutil

        app_dir = Path(__file__).parent

        # Определяем папку с exe
        # PyInstaller: sys.frozen=True
        # Nuitka: __compiled__ существует
        frozen_dir = None
        is_compiled = getattr(sys, 'frozen', False) or '__compiled__' in dir(__builtins__)
        if is_compiled:
            frozen_dir = Path(sys.executable).parent

        candidates = []

        # 1. Рядом с exe (PyInstaller / Nuitka)
        if frozen_dir:
            candidates.append(frozen_dir / 'piper')
            candidates.append(frozen_dir / 'piper.exe')
            # Nuitka: рядом с exe лежит python3 скопированный build.py
            for py_name in ['python3.14', 'python3.12', 'python3', 'python3.exe']:
                py_candidate = frozen_dir / py_name
                if py_candidate.exists():
                    candidates.append(py_candidate)

        # 2. Venv рядом с исходниками
        for venv_name in ['venv', '.venv', 'env']:
            bin_dir = app_dir / venv_name / ('Scripts' if sys.platform == 'win32' else 'bin')
            candidates.append(bin_dir / 'piper')
            candidates.append(bin_dir / 'piper.exe')

        # 3. Рядом с текущим python-интерпретатором
        py_bin_dir = Path(sys.executable).parent
        candidates += [py_bin_dir / 'piper', py_bin_dir / 'piper.exe']

        # 4. Windows: Program Files и AppData
        if sys.platform == 'win32':
            # Program Files
            program_files = Path(os.getenv('PROGRAMFILES', 'C:\\Program Files'))
            candidates.append(program_files / 'Piper' / 'piper.exe')
            candidates.append(program_files / 'piper-tts' / 'piper.exe')

            # Local AppData
            local_appdata = Path(os.getenv('LOCALAPPDATA', ''))
            if local_appdata.exists():
                candidates.append(local_appdata / 'Piper' / 'piper.exe')
                candidates.append(local_appdata / 'Programs' / 'Piper' / 'piper.exe')

            # Python Scripts directory
            candidates.append(py_bin_dir / 'piper.exe')

        # 5. ~/.local/bin (pip install --user) — Linux
        if sys.platform != 'win32':
            candidates.append(Path.home() / '.local' / 'bin' / 'piper')

            # Системный piper-tts (Arch Linux: /usr/bin/piper-tts)
            candidates.append(Path('/usr/bin/piper-tts'))
            candidates.append(Path('/usr/local/bin/piper-tts'))

            # Стандартные системные пути
            for p in ['/usr/local/bin/piper', '/usr/bin/piper',
                      '/opt/piper/piper', '/snap/bin/piper']:
                candidates.append(Path(p))

        for c in candidates:
            if c.exists() and c.is_file():
                try:
                    subprocess.run([str(c), '--version'],
                                   capture_output=True, timeout=3)
                    print(f"[Config] OK piper найден: {c}")
                    return str(c)
                except Exception:
                    pass

        # Fallback: PATH
        path_piper = shutil.which('piper')
        if path_piper:
            print(f"[Config] OK piper в PATH: {path_piper}")
            return path_piper

        # Fallback: проверяем, установлен ли Python модуль piper
        # pip install piper-tts устанавливает модуль, который запускается через python -m piper
        try:
            import importlib.util
            if importlib.util.find_spec('piper') is not None:
                # В Nuitka-сборке sys.executable — это сам бинарник, не Python.
                # Ищем python3 рядом с exe или в системе.
                if is_compiled and frozen_dir:
                    for py_name in ['python3.14', 'python3.12', 'python3']:
                        py_path = frozen_dir / py_name
                        if py_path.exists():
                            print(f"[Config] OK piper через {py_path.name} -m piper")
                            return str(py_path)
                    # Системный python как fallback
                    sys_py = shutil.which('python3.14') or shutil.which('python3.12') or shutil.which('python3')
                    if sys_py:
                        print(f"[Config] OK piper через системный {sys_py} -m piper")
                        return sys_py
                else:
                    print(f"[Config] OK piper как Python модуль (sys.executable={sys.executable})")
                    return sys.executable
        except Exception:
            pass

        print("[Config] ERROR piper не найден. Установите: pip install piper-tts")
        return None

    def find_voice_path(self, voice_name: str):
        """
        Найти путь к файлу голоса Piper.
        Голоса ищутся в:
          1. ~/.ebook-reader/voices/<name>.onnx  (плоская — РЕКОМЕНДУЕТСЯ)
          2. ~/.ebook-reader/voices/<name>/<name>.onnx
          3. Стандартные piper-dirs
        Для добавления голоса положите .onnx и .onnx.json в:
          ~/.ebook-reader/voices/
        """
        base = voice_name.replace('.onnx', '').strip()
        search_dirs = [self.voices_dir] + self.piper_voices_dirs

        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            # Плоская структура
            direct = base_dir / f"{base}.onnx"
            if direct.exists():
                print(f"[Config] OK Голос (плоская): {direct}")
                return direct
            # Вложенная структура
            nested = base_dir / base / f"{base}.onnx"
            if nested.exists():
                print(f"[Config] OK Голос (вложенная): {nested}")
                return nested

        # Нечёткий поиск — дефисы vs подчёркивания
        normalized = base.lower().replace('-', '_').replace(' ', '_')
        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            for onnx_file in base_dir.rglob('*.onnx'):
                fname = onnx_file.stem.lower().replace('-', '_').replace(' ', '_')
                if fname == normalized or normalized in fname:
                    print(f"[Config] OK Голос (нечёткий): {onnx_file}")
                    return onnx_file

        print(f"[Config] ERROR Голос '{voice_name}' не найден.")
        print(f"[Config]    Положите .onnx и .onnx.json в: {self.voices_dir}")
        return None

    # ── резервное копирование ─────────────────────────────────────
    def iter_backup_files(self):
        """Генератор (arc_name, abs_path) всех файлов резервной копии."""
        config_files = {
            'config/settings.json':   self.config_file,
            'config/library.json':    self.library_file,
            'config/positions.json':  self.positions_file,
            'config/highlights.json': self.highlights_file,
            'config/notes.json':      self.notes_file,
            'config/bookmarks.json':  self.bookmarks_file,
        }
        for arc_name, src in config_files.items():
            if src.exists():
                yield arc_name, src
       # if self.covers_dir.exists():
           # for f in sorted(self.covers_dir.rglob('*')):
               # if f.is_file():
                  #  yield 'covers/' + f.relative_to(self.covers_dir).as_posix(), f
        if self.library_path.exists():
            for f in sorted(self.library_path.rglob('*')):
                if f.is_file():
                    yield 'library/' + f.relative_to(self.library_path).as_posix(), f

    def backup_stats(self):
        """Возвращает (total_files, total_bytes) для предпросмотра."""
        total_files, total_bytes = 0, 0
        for _arc, src in self.iter_backup_files():
            total_files += 1
            try:
                total_bytes += src.stat().st_size
            except OSError:
                pass
        return total_files, total_bytes

    def backup_to_zip(self, dest_path: str, progress_cb=None, cancel_flag=None) -> dict:
        """Создать ZIP-архив. Возвращает {'files', 'bytes_src', 'cancelled', 'library_path'}."""
        import zipfile

        files_written = 0
        bytes_src = 0
        all_files = list(self.iter_backup_files())
        total = len(all_files)

        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for idx, (arc_name, src) in enumerate(all_files):
                if cancel_flag and cancel_flag[0]:
                    return {'files': files_written, 'bytes_src': bytes_src,
                            'cancelled': True, 'library_path': str(self.library_path)}
                try:
                    size = src.stat().st_size
                    zf.write(src, arc_name)
                    files_written += 1
                    bytes_src += size
                except OSError as e:
                    print(f'[Backup] skip {src}: {e}')
                if progress_cb:
                    progress_cb(idx + 1, total, arc_name)
            zf.writestr('novareader_backup.marker',
                        json.dumps({'version': 1,
                                    'library_path': str(self.library_path)},
                                   ensure_ascii=False))

        return {'files': files_written, 'bytes_src': bytes_src,
                'cancelled': False, 'library_path': str(self.library_path)}

    def restore_from_zip(self, src_path: str, progress_cb=None, cancel_flag=None) -> dict:
        """Восстановить из ZIP с автоматическим ремаппингом путей и перегенерацией ID подсветок.
        Возвращает {'config_files', 'library_files', 'cover_files', 'cancelled',
                    'path_remapped', 'old_lib_path', 'new_lib_path'}."""
        import zipfile
        import time

        result = {'config_files': 0, 'library_files': 0, 'cover_files': 0,
                  'cancelled': False, 'path_remapped': False,
                  'old_lib_path': '', 'new_lib_path': str(self.library_path)}

        config_map = {
            'config/settings.json':   self.config_file,
            'config/library.json':    self.library_file,
            'config/positions.json':  self.positions_file,
            'config/highlights.json': self.highlights_file,
            'config/notes.json':      self.notes_file,
            'config/bookmarks.json':  self.bookmarks_file,
            # обратная совместимость (старый формат без папки config/)
            'settings.json':   self.config_file,
            'library.json':    self.library_file,
            'positions.json':  self.positions_file,
            'highlights.json': self.highlights_file,
            'notes.json':      self.notes_file,
            'bookmarks.json':  self.bookmarks_file,
        }
        path_bearing = {
            'config/settings.json',   'settings.json',
            'config/library.json',    'library.json',
            'config/positions.json',  'positions.json',
            'config/bookmarks.json',  'bookmarks.json',
            'config/highlights.json', 'highlights.json',
            'config/notes.json',      'notes.json',
        }

        with zipfile.ZipFile(src_path, 'r') as zf:
            names = zf.namelist()
            total = len(names)

            # Читаем library_path из маркера, иначе из settings.json внутри архива
            backup_lib_path = None
            if 'novareader_backup.marker' in names:
                try:
                    marker = json.loads(zf.read('novareader_backup.marker'))
                    backup_lib_path = marker.get('library_path', '')
                except Exception:
                    pass
            if not backup_lib_path:
                for sname in ('config/settings.json', 'settings.json'):
                    if sname in names:
                        try:
                            s = json.loads(zf.read(sname))
                            backup_lib_path = s.get('library_path', '')
                            if backup_lib_path:
                                break
                        except Exception:
                            pass

            current_lib = str(self.library_path)
            backup_lib  = (backup_lib_path or '')
            need_remap  = bool(backup_lib and backup_lib != current_lib)

            if need_remap:
                result.update({'path_remapped': True,
                               'old_lib_path': backup_lib,
                               'new_lib_path': current_lib})
                print(f'[Restore] Ремаппинг: {backup_lib!r} → {current_lib!r}')

            restore_lib = self.library_path

            for idx, arc_name in enumerate(names):
                if cancel_flag and cancel_flag[0]:
                    result['cancelled'] = True
                    break

                try:
                    data = zf.read(arc_name)
                except Exception as e:
                    print(f'[Restore] skip {arc_name}: {e}')
                    if progress_cb:
                        progress_cb(idx + 1, total, arc_name)
                    continue

                if arc_name in config_map:
                    if need_remap and arc_name in path_bearing:
                        try:
                            text = data.decode('utf-8')
                            old_posix = self._normalize_path(backup_lib)
                            new_posix = self._normalize_path(current_lib)

                            # Парсим JSON как объект и заменяем ТОЛЬКО ключи-пути.
                            # Нельзя делать text.replace('\\', '/') по всему тексту —
                            # это ломает экранированные строки внутри JSON
                            # (например поле cfi в highlights.json хранит
                            # сериализованный JSON с \" которые станут /" и сломают парсинг).
                            obj = json.loads(text)

                            def _remap_keys(o):
                                """Рекурсивно переименовать ключи-пути в словарях."""
                                if isinstance(o, dict):
                                    new_d = {}
                                    for k, v in o.items():
                                        # Нормализуем ключ и заменяем базовый путь
                                        nk = self._normalize_path(k)
                                        nk = nk.replace(old_posix, new_posix)
                                        new_d[nk] = _remap_keys(v)
                                    return new_d
                                if isinstance(o, list):
                                    return [_remap_keys(i) for i in o]
                                # Строковые значения — заменяем только если это путь к файлу
                                # (не CFI, не обычный текст). Признак пути — содержит old_posix.
                                if isinstance(o, str) and old_posix in self._normalize_path(o):
                                    # Проверяем что это не CFI и не сериализованный JSON
                                    if not o.startswith('epubcfi(') and not o.startswith('{'):
                                        return self._normalize_path(o).replace(old_posix, new_posix)
                                return o

                            obj = _remap_keys(obj)

                            if arc_name in ('config/settings.json', 'settings.json'):
                                obj['library_path'] = new_posix
                                obj['first_run'] = False  # не показывать визард после восстановления

                            text = json.dumps(obj, ensure_ascii=False, indent=2)
                            data = text.encode('utf-8')
                        except Exception as e:
                            print(f'[Restore] remap error {arc_name}: {e}')
                    config_map[arc_name].write_bytes(data)
                    result['config_files'] += 1

               # elif arc_name.startswith('covers/'):
                   # rel = arc_name[len('covers/'):]
                   # if rel:
                     #   dest = self.covers_dir / rel
                      #  dest.parent.mkdir(parents=True, exist_ok=True)
                       # dest.write_bytes(data)
                       # result['cover_files'] += 1

                elif arc_name.startswith('library/'):
                    rel = arc_name[len('library/'):]
                    if rel:
                        dest = restore_lib / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
                        result['library_files'] += 1

                if progress_cb:
                    progress_cb(idx + 1, total, arc_name)

        self._data       = self._load()
        self._library    = self._load_library()
        self._positions  = self._load_positions()
        self._highlights = self._load_highlights()
        self._notes      = self._load_notes()
        self._bookmarks  = self._load_bookmarks()
        self.library_path = Path(self.get('library_path', str(self.config_dir / 'books')))
        self.library_path.mkdir(parents=True, exist_ok=True)

        return result