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
        self.highlights_file = self.config_dir / 'highlights.json'
        self.notes_file = self.config_dir / 'notes.json'
        self.bookmarks_file = self.config_dir / 'bookmarks.json'
        self.covers_dir = self.config_dir / 'covers'
        self.covers_dir.mkdir(exist_ok=True)

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
        self._library = self._load_library()
        self._highlights = self._load_highlights()
        self._notes = self._load_notes()
        self._bookmarks = self._load_bookmarks()

        # Путь к библиотеке (может быть изменен пользователем)
        self.library_path = Path(self.get('library_path', str(self.config_dir / 'books')))
        self.library_path.mkdir(parents=True, exist_ok=True)

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
            # Настройки подсветки по умолчанию
            'default_highlight_style': 'highlight',
            'default_highlight_color': 'blue',
            # Цвет TTS-подсветки по умолчанию
            'tts_highlight_color': 'cyan',
        }

    def _load_library(self) -> List[Dict]:
        """Загрузить библиотеку книг"""
        if self.library_file.exists():
            try:
                return json.loads(self.library_file.read_text(encoding='utf-8'))
            except:
                pass
        return []

    def _load_highlights(self) -> Dict:
        """Загрузить подсветки"""
        if self.highlights_file.exists():
            try:
                return json.loads(self.highlights_file.read_text(encoding='utf-8'))
            except:
                pass
        return {}

    def _load_notes(self) -> Dict:
        """Загрузить заметки"""
        if self.notes_file.exists():
            try:
                return json.loads(self.notes_file.read_text(encoding='utf-8'))
            except:
                pass
        return {}

    def _load_bookmarks(self) -> Dict:
        """Загрузить закладки"""
        if self.bookmarks_file.exists():
            try:
                return json.loads(self.bookmarks_file.read_text(encoding='utf-8'))
            except:
                pass
        return {}

    def save_bookmarks(self):
        """Сохранить закладки"""
        self.bookmarks_file.write_text(
            json.dumps(self._bookmarks, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def add_bookmark(self, book_path: str, bookmark: Dict):
        """Добавить закладку для книги"""
        if book_path not in self._bookmarks:
            self._bookmarks[book_path] = []
        self._bookmarks[book_path].append(bookmark)
        self.save_bookmarks()
        print(f"[Config] Закладка сохранена: {bookmark.get('label')}")

    def get_bookmarks(self, book_path: str) -> List[Dict]:
        """Получить все закладки для книги"""
        return self._bookmarks.get(book_path, [])

    def remove_bookmark(self, book_path: str, bookmark_id: str) -> bool:
        """Удалить закладку по ID"""
        if book_path in self._bookmarks:
            orig = len(self._bookmarks[book_path])
            self._bookmarks[book_path] = [
                b for b in self._bookmarks[book_path]
                if b.get('id') != bookmark_id
            ]
            self.save_bookmarks()
            return orig != len(self._bookmarks[book_path])
        return False

    def save(self):
        """Сохранить настройки"""
        self.config_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def save_library(self):
        """Сохранить библиотеку"""
        self.library_file.write_text(
            json.dumps(self._library, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def save_highlights(self):
        """Сохранить подсветки"""
        self.highlights_file.write_text(
            json.dumps(self._highlights, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def save_notes(self):
        """Сохранить заметки"""
        self.notes_file.write_text(
            json.dumps(self._notes, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()

        # Если изменился путь к библиотеке, обновляем
        if key == 'library_path':
            self.library_path = Path(value)
            self.library_path.mkdir(parents=True, exist_ok=True)

    def is_first_run(self) -> bool:
        """Проверить, первый ли это запуск"""
        return self.get('first_run', True)

    def get_library_path(self) -> Path:
        """Получить путь к библиотеке"""
        return self.library_path

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С КНИГАМИ ====================

    def add_book(self, book_info: Dict):
        """Добавить книгу в библиотеку"""
        # Проверяем, нет ли уже такой книги
        for book in self._library:
            if book.get('file_path') == book_info.get('file_path'):
                # Обновляем метаданные если книга уже есть
                book.update(book_info)
                self.save_library()
                return

        book_info['added'] = datetime.now().isoformat()
        book_info['last_read'] = None
        book_info['progress'] = 0
        self._library.append(book_info)
        self.save_library()

    def remove_book(self, file_path: str):
        """Удалить книгу из библиотеки"""
        self._library = [b for b in self._library if b.get('file_path') != file_path]
        self.save_library()

    def get_books(self) -> List[Dict]:
        """Получить список книг"""
        return self._library

    def get_book_by_path(self, file_path: str) -> Optional[Dict]:
        """Получить книгу по пути"""
        for book in self._library:
            if book.get('file_path') == file_path:
                return book
        return None

    def update_progress(self, file_path: str, progress: float, position):
        """Обновить прогресс чтения"""
        for book in self._library:
            if book.get('file_path') == file_path:
                book['progress'] = progress
                if isinstance(position, str):
                    try:
                        position = json.loads(position)
                    except:
                        position = {'section': 0, 'timestamp': 0}
                book['position'] = position
                book['last_read'] = datetime.now().isoformat()
                self.save_library()
                break

    def mark_as_read(self, file_path: str):
        """Отметить книгу как открытую (обновить last_read)"""
        for book in self._library:
            if book.get('file_path') == file_path:
                book['last_read'] = datetime.now().isoformat()
                self.save_library()
                break

    def get_bookmark(self, file_path: str) -> Optional[Dict]:
        """Получить закладку для книги"""
        for book in self._library:
            if book.get('file_path') == file_path:
                return {
                    'progress': book.get('progress', 0),
                    'position': book.get('position')
                }
        return None

    # ==================== МЕТОДЫ ДЛЯ ПОДСВЕТОК ====================

    def add_highlight(self, book_path: str, highlight: Dict):
        """Добавить подсветку для книги"""
        if book_path not in self._highlights:
            self._highlights[book_path] = []

        self._highlights[book_path].append(highlight)
        self.save_highlights()
        print(f"[Config] Подсветка сохранена: {highlight.get('id')} - {highlight.get('color')}")

    def get_highlights(self, book_path: str) -> List[Dict]:
        """Получить все подсветки для книги"""
        return self._highlights.get(book_path, [])

    def remove_highlight(self, book_path: str, highlight_id: str) -> bool:
        """Удалить подсветку по ID"""
        if book_path in self._highlights:
            original_count = len(self._highlights[book_path])
            self._highlights[book_path] = [
                h for h in self._highlights[book_path]
                if h.get('id') != highlight_id
            ]
            removed_count = original_count - len(self._highlights[book_path])
            self.save_highlights()
            print(f"[Config] Подсветка удалена: {highlight_id}, удалено: {removed_count}")
            return removed_count > 0
        return False

    def clear_highlights(self, book_path: str):
        """Удалить все подсветки для книги"""
        if book_path in self._highlights:
            self._highlights[book_path] = []
            self.save_highlights()
            print(f"[Config] Все подсветки для {book_path} удалены")

    # ==================== МЕТОДЫ ДЛЯ ЗАМЕТОК ====================

    def add_note(self, book_path: str, note: Dict):
        """Добавить заметку для книги"""
        if book_path not in self._notes:
            self._notes[book_path] = []

        self._notes[book_path].append(note)
        self.save_notes()
        print(f"[Config] Заметка сохранена")

    def get_notes(self, book_path: str) -> List[Dict]:
        """Получить все заметки для книги"""
        return self._notes.get(book_path, [])

    def remove_note(self, book_path: str, note_id: str):
        """Удалить заметку по ID"""
        if book_path in self._notes:
            self._notes[book_path] = [
                n for n in self._notes[book_path]
                if n.get('id') != note_id
            ]
            self.save_notes()

    # ==================== ЭКСПОРТ ЗАМЕТОК И ПОДСВЕТОК ====================

    def get_all_notes_and_highlights(self) -> Dict[str, Dict]:
        """Получить все заметки и подсветки для всех книг.
        Возвращает dict: {book_path: {'book_info': {...}, 'notes': [...], 'highlights': [...]}}
        """
        result = {}
        
        # Собираем информацию о книгах
        books_by_path = {b['file_path']: b for b in self._library}
        
        # Объединяем все book_path из заметок и подсветок
        all_book_paths = set(self._notes.keys()) | set(self._highlights.keys())
        
        for book_path in all_book_paths:
            book_info = books_by_path.get(book_path, {})
            result[book_path] = {
                'book_info': {
                    'title': book_info.get('title', 'Неизвестно'),
                    'author': book_info.get('author', 'Неизвестен'),
                    'file_path': book_path,
                },
                'notes': self._notes.get(book_path, []),
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
            lines.append(f"📖 {book_info['title']}")
            lines.append(f"   Автор: {book_info['author']}")
            lines.append("-" * 60)
            lines.append("")
            
            # Заметки
            if notes:
                lines.append("📝 ЗАМЕТКИ:")
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
                lines.append("✨ ВЫДЕЛЕННЫЕ ЦИТАТЫ:")
                lines.append("")
                for i, h in enumerate(highlights, 1):
                    text = h.get('text', '')
                    color = h.get('color', '')
                    style = h.get('style', 'highlight')
                    timestamp = h.get('timestamp', '')
                    
                    # Добавляем эмодзи цвета
                    color_emoji = {
                        'yellow': '🟡', 'blue': '🔵', 'green': '🟢',
                        'pink': '🩷', 'orange': '🟠', 'purple': '🟣',
                        'cyan': '🔷'
                    }.get(color, '⚪')
                    
                    style_prefix = {'underline': '📏 ', 'strikethrough': '❌ '}.get(style, '')
                    
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
        lines.append("# 📚 NovaReader — Заметки и выделенные цитаты")
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
            lines.append(f"## 📖 {book_info['title']}")
            lines.append("")
            lines.append(f"**Автор:** {book_info['author']}")
            lines.append("")
            
            # Заметки
            if notes:
                lines.append("### 📝 Заметки")
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
                lines.append("### ✨ Выделенные цитаты")
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
