from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QScrollArea, QGridLayout, QLabel,
                             QFileDialog, QMessageBox, QProgressDialog,
                             QFrame, QLineEdit, QMenu, QComboBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QAction
from pathlib import Path
import sys, shutil, json, re
from book_parser import BookParser
from zip_handler import ZipHandler
from book_normalizer import (normalize_book, SUPPORTED as NORMALIZER_SUPPORTED,
                             convert_book_fb2c, _find_fb2c)
from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal as _Signal

# ── Локализация библиотеки ────────────────────────────────────────────────────
_LIB_STRINGS = {
    'ru': {
        # Статус-бар
        'ready':              'Готов',
        'shown_of':           'Показано: {shown} из {n}',
        'books_count':        'Книг: {n}',
        # Тултипы кнопок тулбара
        'add_books':          'Добавить книги',
        'scan_folder':        'Сканировать папку',
        'cleanup':            'Очистить несуществующие записи',
        'export_notes':       'Экспорт заметок',
        'refresh':            'Обновить',
        'backup':             'Создать резервную копию',
        'restore':            'Восстановить из резервной копии',
        'settings':           'Настройки',
        # Поиск и сортировка
        'search_placeholder': 'Поиск по названию, автору, серии...',
        'sort_last_read':     'По последнему чтению',
        'sort_date_added':    'По дате добавления',
        'sort_title':         'По названию',
        'sort_author':        'По автору',
        'filter_all':         'Все форматы',
        'filter_comics':      'Комиксы',
        # Диалог добавления
        'add_dialog_title':   'Выберите книги',
        'add_filter_books':   'Книги (*.epub *.fb2 *.fb2.zip *.zip *.mobi *.azw3 *.cbz *.pdf)',
        'add_filter_comics':  'Комиксы (*.cbz *.cbr)',
        'add_filter_manga':   'Манга (*.cbz *.cbr)',
        'add_filter_pdf':     'PDF (*.pdf)',
        'add_filter_all':     'Все файлы (*)',
        'add_progress':       'Добавление книг...',
        'add_cancel':         'Отмена',
        'add_processing':     'Обработка: {name}',
        'add_done':           'Готово',
        'add_result':         'Добавлено: {added}\nПропущено: {skipped}',
        'no_books_found':     'Книги не найдены.',
        # Сканирование
        'scan_dialog_title':  'Выберите папку для сканирования',
        'scan_progress':      'Сканирование...',
        'scan_result':        'Добавлено: {added}\nПропущено: {skipped}',
        # Очистка
        'cleanup_confirm':    'Удалить {n} несуществующих записей?',
        # Удаление книги
        'delete_title':       'Удалить книгу',
        'delete_msg_multi':   'Удалить «{title}»?\n\nФорматы: {formats}',
        'delete_msg_single':  'Удалить «{title}»?\n\nФайл будет удалён с диска.',
        'delete_fmt_title':   'Удалить формат {fmt}',
        'delete_fmt_msg':     'Удалить «{title}» в формате {fmt}?\n\nФайл будет удалён с диска.',
        'delete_btn_current': 'Текущий формат',
        'delete_btn_all':     'Все форматы',
        'delete_btn_cancel':  'Отмена',
        'error_delete':       'Не удалось удалить файлы:\n{e}',
        'error_delete_fmt':   'Не удалось удалить файл:\n{e}',
        # Экспорт заметок
        'export_title':       'Экспорт заметок',
        'export_choose_fmt':  'Выберите формат экспорта:',
        'export_done':        'Экспорт завершён',
        'export_saved':       'Сохранено в:\n{path}',
        'export_error':       'Ошибка экспорта',
        'export_error_msg':   'Не удалось сохранить файл:\n{e}',
        # Бэкап / восстановление
        'backup_title':       'Создать резервную копию',
        'backup_done_title':  'Резервная копия создана',
        'backup_done_msg':    'Сохранено в:\n{path}',
        'backup_error':       'Ошибка',
        'backup_error_msg':   'Не удалось создать резервную копию:\n{e}',
        'restore_title':      'Восстановить из резервной копии',
        'restore_hint':       'Выберите файл, созданный кнопкой «Создать резервную копию».',
        'restore_filter':     'Резервная копия (*.zip)',
        'restore_items':      'Настройки программы',
        'restore_lib':        'Список библиотеки + позиции чтения',
        'restore_confirm':    'Восстановить из резервной копии?',
        'restore_error':      'Ошибка восстановления',
        'restore_open_err':   'Не удалось открыть архив:\n{e}',
        # Контекстное меню карточки
        'ctx_open':           'Открыть',
        'ctx_open_in':        'Открыть в...',
        'ctx_delete_fmt':     'Удалить формат',
        'ctx_delete':         'Удалить',
        'ctx_convert':        'Конвертировать в EPUB (fb2c)',
        'ctx_normalize':      'Нормализовать',
        'ctx_edit_meta':      'Редактировать метаданные',
        # Ошибки
        'error':              'Ошибка',
        'cbr_no_extractor':   'Не удалось распаковать {name} — установите unrar, bsdtar или 7z',
        # Пустая библиотека
        'empty_lib':          'Библиотека пуста.\nДобавьте книги кнопкой «+».',
    },
    'en': {
        # Status bar
        'ready':              'Ready',
        'shown_of':           'Shown: {shown} of {n}',
        'books_count':        'Books: {n}',
        # Toolbar tooltips
        'add_books':          'Add books',
        'scan_folder':        'Scan folder',
        'cleanup':            'Remove missing entries',
        'export_notes':       'Export notes',
        'refresh':            'Refresh',
        'backup':             'Create backup',
        'restore':            'Restore from backup',
        'settings':           'Settings',
        # Search and sort
        'search_placeholder': 'Search by title, author, series...',
        'sort_last_read':     'Last read',
        'sort_date_added':    'Date added',
        'sort_title':         'By title',
        'sort_author':        'By author',
        'filter_all':         'All formats',
        'filter_comics':      'Comics',
        # Add dialog
        'add_dialog_title':   'Select books',
        'add_filter_books':   'Books (*.epub *.fb2 *.fb2.zip *.zip *.mobi *.azw3 *.cbz *.pdf)',
        'add_filter_comics':  'Comics (*.cbz *.cbr)',
        'add_filter_manga':   'Manga (*.cbz *.cbr)',
        'add_filter_pdf':     'PDF (*.pdf)',
        'add_filter_all':     'All files (*)',
        'add_progress':       'Adding books...',
        'add_cancel':         'Cancel',
        'add_processing':     'Processing: {name}',
        'add_done':           'Done',
        'add_result':         'Added: {added}\nSkipped: {skipped}',
        'no_books_found':     'No books found.',
        # Scan
        'scan_dialog_title':  'Select folder to scan',
        'scan_progress':      'Scanning...',
        'scan_result':        'Added: {added}\nSkipped: {skipped}',
        # Cleanup
        'cleanup_confirm':    'Delete {n} missing entries?',
        # Delete
        'delete_title':       'Delete book',
        'delete_msg_multi':   'Delete "{title}"?\n\nFormats: {formats}',
        'delete_msg_single':  'Delete "{title}"?\n\nFile will be removed from disk.',
        'delete_fmt_title':   'Delete format {fmt}',
        'delete_fmt_msg':     'Delete "{title}" in {fmt} format?\n\nFile will be removed from disk.',
        'delete_btn_current': 'Current format',
        'delete_btn_all':     'All formats',
        'delete_btn_cancel':  'Cancel',
        'error_delete':       'Failed to delete files:\n{e}',
        'error_delete_fmt':   'Failed to delete file:\n{e}',
        # Export
        'export_title':       'Export notes',
        'export_choose_fmt':  'Choose export format:',
        'export_done':        'Export complete',
        'export_saved':       'Saved to:\n{path}',
        'export_error':       'Export error',
        'export_error_msg':   'Failed to save file:\n{e}',
        # Backup / restore
        'backup_title':       'Create backup',
        'backup_done_title':  'Backup created',
        'backup_done_msg':    'Saved to:\n{path}',
        'backup_error':       'Error',
        'backup_error_msg':   'Failed to create backup:\n{e}',
        'restore_title':      'Restore from backup',
        'restore_hint':       'Select a file created by the "Create backup" button.',
        'restore_filter':     'Backup file (*.zip)',
        'restore_items':      'App settings',
        'restore_lib':        'Library list + reading positions',
        'restore_confirm':    'Restore from backup?',
        'restore_error':      'Restore error',
        'restore_open_err':   'Failed to open archive:\n{e}',
        # Card context menu
        'ctx_open':           'Open',
        'ctx_open_in':        'Open in...',
        'ctx_delete_fmt':     'Delete format',
        'ctx_delete':         'Delete',
        'ctx_convert':        'Convert to EPUB (fb2c)',
        'ctx_normalize':      'Normalize',
        'ctx_edit_meta':      'Edit metadata',
        # Errors
        'error':              'Error',
        'cbr_no_extractor':   'Could not extract {name} — install unrar, bsdtar or 7z',
        # Empty library
        'empty_lib':          'Library is empty.\nAdd books using the «+» button.',
    },
}


def _ls(config, key: str, **kwargs) -> str:
    """Получить локализованную строку библиотеки."""
    lang = config.get('language', 'ru') if config else 'ru'
    strings = _LIB_STRINGS.get(lang, _LIB_STRINGS['ru'])
    s = strings.get(key, _LIB_STRINGS['ru'].get(key, key))
    return s.format(**kwargs) if kwargs else s

CARD_W  = 170
CARD_H  = 280
CARD_S  = 14

# ── Встроенные темы библиотеки ────────────────────────────────────────────────
DARK_THEME = {
    "BG":       "#1e1e2e",
    "SURFACE":  "#282838",
    "BORDER":   "#3a3a50",
    "ACCENT":   "#1a73e8",
    "TEXT":     "#e8eaed",
    "SUB":      "#9aa0a6",
    "SERIES":   "#7ecfff",
    "TOOLBAR":  "#252535",
    "PROGRESS": "#1a73e8",
}

LIGHT_THEME = {
    "BG":       "#f5f5f5",
    "SURFACE":  "#ffffff",
    "BORDER":   "#d0d0d0",
    "ACCENT":   "#1a73e8",
    "TEXT":     "#1a1a1a",
    "SUB":      "#666666",
    "SERIES":   "#1565c0",
    "TOOLBAR":  "#e8e8e8",
    "PROGRESS": "#1a73e8",
}

# Текущие активные цвета — простые глобальные переменные.
# f-строки в методах читают их в момент вызова, поэтому
# достаточно обновить эти переменные и пересоздать виджеты.
BG       = DARK_THEME["BG"]
SURFACE  = DARK_THEME["SURFACE"]
BORDER   = DARK_THEME["BORDER"]
ACCENT   = DARK_THEME["ACCENT"]
TEXT     = DARK_THEME["TEXT"]
SUB      = DARK_THEME["SUB"]
SERIES   = DARK_THEME["SERIES"]
TOOLBAR  = DARK_THEME["TOOLBAR"]
PROGRESS = DARK_THEME["PROGRESS"]


def _apply_theme_to_globals(colors: dict) -> None:
    """Записать словарь цветов в глобальные переменные модуля."""
    global BG, SURFACE, BORDER, ACCENT, TEXT, SUB, SERIES, TOOLBAR, PROGRESS
    BG       = colors["BG"]
    SURFACE  = colors["SURFACE"]
    BORDER   = colors["BORDER"]
    ACCENT   = colors["ACCENT"]
    TEXT     = colors["TEXT"]
    SUB      = colors["SUB"]
    SERIES   = colors["SERIES"]
    TOOLBAR  = colors["TOOLBAR"]
    PROGRESS = colors.get("PROGRESS", colors["ACCENT"])  # fallback на ACCENT


def init_lib_colors(config) -> None:
    """Загрузить цвета библиотеки из конфига и применить к глобалам."""
    name = config.get("library_theme_name", "dark")
    if name == "light":
        _apply_theme_to_globals(LIGHT_THEME)
    elif name == "custom":
        colors = dict(DARK_THEME)
        colors.update(config.get("library_theme_custom", {}))
        _apply_theme_to_globals(colors)
    else:
        _apply_theme_to_globals(DARK_THEME)


# Unicode fallback symbols if Material Icons not available
_ICON_FALLBACK = {
    'add':          '+',
    'folder_open':  '⊞',
    'delete_sweep': '',
    'refresh':      '↻',
    'search':       '',
    'settings':     '',
    'backup':       '',
    'restore':      '',
}

def _mbtn(icon_name, tooltip, sz=36):
    """Кнопка с Material Icons или Unicode-символом как fallback."""
    from PyQt6.QtGui import QFontDatabase
    has_mi = 'Material Icons' in QFontDatabase.families()
    label  = icon_name if has_mi else _ICON_FALLBACK.get(icon_name, icon_name[:1])
    font_family = "'Material Icons'" if has_mi else "sans-serif"
    font_size   = sz // 2 if has_mi else sz // 2 + 4

    b = QPushButton(label)
    b.setFixedSize(sz, sz)
    b.setToolTip(tooltip)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;border:none;"
        f"border-radius:{sz//2}px;color:{SUB};"
        f"font-family:{font_family};font-size:{font_size}px;}}"
        f"QPushButton:hover{{background:rgba(255,255,255,.08);color:{TEXT};}}"
        f"QPushButton:pressed{{background:rgba(255,255,255,.15);}}")
    return b


class BookCard(QFrame):
    clicked    = pyqtSignal(object)
    delete_req = pyqtSignal(object)

    def __init__(self, book_info, config=None):
        super().__init__()
        self.book_info = book_info
        self.config = config
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_W, CARD_H)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._paint(False)
        self._build()

    def _paint(self, hov):
        c, w = (ACCENT, 2) if hov else (BORDER, 1)
        self.setStyleSheet(
            f"BookCard{{background:{SURFACE};border-radius:10px;border:{w}px solid {c};}}")

    def enterEvent(self, e):  self._paint(True);  super().enterEvent(e)
    def leaveEvent(self, e):  self._paint(False); super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # По умолчанию открываем EPUB если он есть в папке книги
            book_path = Path(self.book_info.get("file_path", ""))
            best_path = str(book_path)
            if book_path.parent.exists():
                for fmt in ['epub', 'mobi', 'azw3', 'fb2']:
                    candidates = list(book_path.parent.glob(f'*.{fmt}'))
                    if candidates:
                        best_path = str(candidates[0])
                        break
            self.clicked.emit({**self.book_info, "file_path": best_path})

    def _ctx_menu(self, pos):
        """Контекстное меню с выбором формата для открытия/удаления."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{SURFACE};border:1px solid {BORDER};"
            f"color:{TEXT};font-size:13px;padding:4px 0;}}"
            f"QMenu::item{{padding:7px 22px;}}"
            f"QMenu::item:selected{{background:{ACCENT};color:white;}}")
        
        title = self.book_info.get("title", "Книга")[:40]
        hdr = QAction(title, self)
        hdr.setEnabled(False)
        menu.addAction(hdr)
        menu.addSeparator()
        
        # Находим все файлы в папке этой книги
        book_path = Path(self.book_info.get("file_path", ""))
        book_dir = book_path.parent if book_path.exists() else None
        
        if book_dir and book_dir.exists():
            # Ищем все файлы книг в папке
            book_formats = {}
            for f in book_dir.iterdir():
                if f.suffix.lower() in ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']:
                    fmt = f.suffix.lower().lstrip('.')
                    book_formats[fmt] = f
            
            if len(book_formats) > 1:
                # Несколько форматов — добавляем подменю "Открыть в..."
                open_menu = menu.addMenu(" Открыть в...")
                
                # Приоритет форматов: EPUB > FB2 > остальные
                priority = ['epub', 'fb2', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr']
                for fmt in priority:
                    if fmt in book_formats:
                        fpath = book_formats[fmt]
                        mark = ' ' if fmt == 'epub' else ''
                        act = QAction(f"{mark}{fmt.upper()} — {fpath.name}", self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._open_book_format(fp))
                        open_menu.addAction(act)
                
                menu.addSeparator()

                # Нормализовать для TTS (подменю по форматам)
                norm_formats = {fmt: fp for fmt, fp in book_formats.items()
                                if ('.' + fmt) in NORMALIZER_SUPPORTED}
                if norm_formats:
                    if len(norm_formats) == 1:
                        fmt, fpath = next(iter(norm_formats.items()))
                        act = QAction(f" Нормализовать для TTS ({fmt.upper()})", self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                        menu.addAction(act)
                    else:
                        norm_menu = menu.addMenu(" Нормализовать для TTS")
                        for fmt, fpath in norm_formats.items():
                            act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                            act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                            norm_menu.addAction(act)

                menu.addSeparator()

                # Конвертировать FB2 → EPUB
                if 'fb2' in book_formats:
                    fb2_path = str(book_formats['fb2'])
                    if _find_fb2c():
                        act = QAction(" Конвертировать FB2 → EPUB", self)
                        act.triggered.connect(lambda checked, fp=fb2_path: self._convert_book(fp))
                    else:
                        act = QAction(" Конвертировать FB2 → EPUB (fb2c не найден)", self)
                        act.setEnabled(False)
                    menu.addAction(act)

                menu.addSeparator()

                # Подменю "Удалить формат"
                delete_menu = menu.addMenu(" Удалить формат")
                for fmt, fpath in sorted(book_formats.items()):
                    act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                    act.triggered.connect(lambda checked, fp=str(fpath), fm=fmt: self._delete_format(fp, fm))
                    delete_menu.addAction(act)
            else:
                # Один формат
                src_path = str(book_path)
                ext = book_path.suffix.lower()
                if ext in NORMALIZER_SUPPORTED:
                    act = QAction(" Нормализовать для TTS", self)
                    act.triggered.connect(lambda checked, fp=src_path: self._normalize_book(fp))
                    menu.addAction(act)
                if ext == '.fb2':
                    if _find_fb2c():
                        act = QAction(" Конвертировать FB2 → EPUB", self)
                        act.triggered.connect(lambda checked, fp=src_path: self._convert_book(fp))
                    else:
                        act = QAction(" Конвертировать FB2 → EPUB (fb2c не найден)", self)
                        act.setEnabled(False)
                    menu.addAction(act)
                menu.addSeparator()
                act = QAction(" Удалить книгу", self)
                act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
                menu.addAction(act)
        else:
            act = QAction(" Удалить книгу", self)
            act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
            menu.addAction(act)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _open_book_format(self, file_path):
        """Открыть книгу в указанном формате."""
        self.clicked.emit({**self.book_info, "file_path": str(file_path)})
    
    def _delete_format(self, file_path, format_name):
        """Удалить конкретный формат книги. Папка и другие форматы остаются."""
        title = self.book_info.get("title", "Книга")[:40]
        r = QMessageBox.question(
            self, _ls(self.config, 'delete_fmt_title', fmt=format_name.upper()),
            _ls(self.config, 'delete_fmt_msg',
                title=title, fmt=format_name.upper()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        try:
            fp = Path(file_path)

            # Сначала обновляем конфиг — remove_format убирает только этот формат.
            # Если других форматов нет — запись удалится; если есть — останется.
            self.config.remove_format(str(fp))

            # Удаляем только один файл, папку не трогаем
            if fp.exists():
                fp.unlink()
                print(f"[Library] Удалён формат {format_name}: {fp.name}")

            # Ищем оставшиеся форматы, чтобы обновить book_info карточки
            BOOK_EXTS = {'.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr'}
            book_dir  = fp.parent
            remaining = (
                [f for f in book_dir.iterdir() if f.suffix.lower() in BOOK_EXTS]
                if book_dir.exists() else []
            )

            if remaining:
                prio = ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']
                remaining.sort(key=lambda f: prio.index(f.suffix.lower())
                               if f.suffix.lower() in prio else 99)
                new_path = str(remaining[0])
                self.book_info = {**self.book_info, "file_path": new_path}
                print(f"[Library] Остался формат: {remaining[0].name}")
            else:
                # Это был последний формат — папку можно почистить
                cover = book_dir / "cover.jpg"
                if cover.exists():
                    try: cover.unlink()
                    except Exception: pass
                meta_f = book_dir / "metadata.json"
                if meta_f.exists():
                    try: meta_f.unlink()
                    except Exception: pass
                try:
                    book_dir.rmdir()
                    author_dir = book_dir.parent
                    lib_root   = self.config.get_library_path()
                    if (author_dir != lib_root and author_dir.exists()
                            and not any(author_dir.iterdir())):
                        author_dir.rmdir()
                except Exception as e:
                    print(f"[Library] Не удалось удалить папку: {e}")

        except Exception as e:
            print(f"[Library] Delete format error: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить файл:\n{e}")

        # Обновляем библиотеку
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_on_library_updated'):
                parent._on_library_updated()
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None

    def _normalize_book(self, file_path: str):
        """Нормализовать книгу для корректной работы TTS."""
        from PyQt6.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout
        
        src = Path(file_path)
        ext = src.suffix.lower()
        
        # Диалог выбора куда сохранить
        # Предлагаем имя с суффиксом _fixed
        default_name = src.stem + '_fixed' + ext
        dst_str, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить нормализованную книгу",
            str(src.parent / default_name),
            f"Книги (*{ext});;Все файлы (*.*)"
        )
        if not dst_str:
            return  # пользователь отменил

        dst = Path(dst_str)
        
        # Диалог прогресса с логом
        dlg = QDialog(self)
        dlg.setWindowTitle(" Нормализация книги")
        dlg.setMinimumSize(520, 380)
        dlg.setStyleSheet(f"QDialog{{background:{BG};color:{TEXT};}}"
                          f"QTextEdit{{background:#1a1a2a;color:#c8ffc8;"
                          f"border:1px solid {BORDER};border-radius:6px;font-family:monospace;font-size:12px;}}"
                          f"QPushButton{{background:{ACCENT};color:white;border:none;"
                          f"padding:8px 20px;border-radius:6px;font-size:13px;}}"
                          f"QPushButton:disabled{{background:#444;color:#888;}}"
                          f"QLabel{{color:{TEXT};}}")
        lay = QVBoxLayout(dlg)
        
        title_label = QLabel(f"Нормализация: <b>{src.name}</b>")
        title_label.setStyleSheet(f"color:{TEXT};font-size:13px;padding:4px 0;")
        lay.addWidget(title_label)
        
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        lay.addWidget(log_box)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.setEnabled(False)
        open_btn  = QPushButton(" Открыть папку")
        open_btn.setEnabled(False)
        open_btn.setStyleSheet(f"background:#2d5a27;color:white;border:none;"
                               f"padding:8px 20px;border-radius:6px;font-size:13px;")
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        close_btn.clicked.connect(dlg.accept)

        # Worker-поток
        class _Worker(QThread):
            log_line = _Signal(str)
            done     = _Signal(bool)

            def __init__(self, src, dst):
                super().__init__()
                self._src, self._dst = src, dst

            def run(self):
                ok = normalize_book(str(self._src), str(self._dst),
                                    log=lambda msg: self.log_line.emit(msg))
                self.done.emit(ok)

        worker = _Worker(src, dst)

        def on_log(msg):
            log_box.append(msg)

        def on_done(ok):
            close_btn.setEnabled(True)
            if ok:
                log_box.append("")
                log_box.append(f" Готово! Файл сохранён: {dst}")
                open_btn.setEnabled(True)
                open_btn.clicked.connect(lambda: __import__('subprocess').Popen(
                    ['xdg-open' if __import__('sys').platform != 'win32' else 'explorer',
                     str(dst.parent)]))
            else:
                log_box.append("")
                log_box.append(" Нормализация завершилась с ошибкой")

        worker.log_line.connect(on_log)
        worker.done.connect(on_done)
        worker.start()

        dlg.exec()

    def _convert_book(self, file_path: str):
        """Конвертировать FB2 → EPUB через fb2c."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                     QLabel, QPushButton, QTextEdit)
        from PyQt6.QtCore import QThread
        from PyQt6.QtCore import pyqtSignal as _Signal

        src = Path(file_path)
        if not src.exists():
            return

        # ── Предупреждение о потере позиции ────────────────────────────
        # Позиция в FB2 хранится как CFI, который привязан к DOM-структуре.
        # После конвертации fb2c строит другой XHTML — старый CFI не совпадёт.
        has_position = False
        if self.config:
            for book in self.config.get_books():
                if book.get("file_path") == str(src):
                    pos = book.get("position")
                    prog = book.get("progress", 0)
                    if pos or prog:
                        has_position = True
                    break

        if has_position:
            warn = QMessageBox(self)
            warn.setWindowTitle(" Позиция чтения будет сброшена")
            warn.setText(
                "<b>Внимание!</b><br><br>"
                "У этой книги сохранена позиция, на которой вы остановились.<br><br>"
                "После конвертации в EPUB структура документа изменится, "
                "и старая позиция не будет соответствовать новому файлу. "
                "<b>Позиция будет сброшена на начало.</b><br><br>"
                "Если хотите продолжить с того же места после конвертации — "
                "запомните страницу или главу сейчас."
            )
            warn.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            warn.button(QMessageBox.StandardButton.Ok).setText("Продолжить")
            warn.button(QMessageBox.StandardButton.Cancel).setText("Отмена")
            warn.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if warn.exec() != QMessageBox.StandardButton.Ok:
                return

        # fb2c кладёт результат в ту же папку что и исходник
        dst_dir = src.parent

        # ── Ищем LibraryWindow как родителя диалога ───────────────────
        # Диалог НЕ должен быть дочерним BookCard — при пересоздании карточек
        # (_on_library_updated) Qt уничтожает дочерние виджеты карточки,
        # что немедленно закрывает диалог конвертации.
        lib_win_parent = self.parent()
        while lib_win_parent and not hasattr(lib_win_parent, '_on_library_updated'):
            lib_win_parent = (lib_win_parent.parent()
                              if hasattr(lib_win_parent, 'parent') else None)
        dlg_parent = lib_win_parent or self

        # ── Диалог прогресса ───────────────────────────────────────────
        dlg = QDialog(dlg_parent)
        dlg.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint)
        dlg.setWindowTitle(" Конвертация FB2 → EPUB")
        dlg.setMinimumSize(500, 320)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};}}"
            f"QLabel{{color:{TEXT};}}"
            f"QPushButton{{background:{ACCENT};color:white;border:none;"
            f"padding:8px 20px;border-radius:6px;font-size:13px;}}"
            f"QPushButton:disabled{{background:#444;color:#888;}}")
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel(f"<b>{src.name}</b> → EPUB"))
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setStyleSheet(
            "background:#1a1a2a;color:#c8ffc8;border:1px solid #333;"
            "border-radius:6px;font-family:monospace;font-size:12px;")
        lay.addWidget(log_box)

        stop_flag = [False]
        result_path: list[Path | None] = [None]

        btn_row = QHBoxLayout()
        stop_btn  = QPushButton(" Отмена")
        stop_btn.setStyleSheet("background:#7a2020;")
        close_btn = QPushButton("Закрыть")
        close_btn.setEnabled(False)
        open_btn  = QPushButton(" Открыть папку")
        open_btn.setEnabled(False)
        open_btn.setStyleSheet("background:#2d5a27;")
        open_book_btn = QPushButton(" Открыть книгу")
        open_book_btn.setEnabled(False)
        open_book_btn.setStyleSheet("background:#1a4a6a;")
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(open_book_btn)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        stop_btn.clicked.connect(lambda: stop_flag.__setitem__(0, True))
        close_btn.clicked.connect(dlg.accept)

        _log_buf = []

        def _flush_log():
            if _log_buf:
                msg = _log_buf.pop(0)
                from PyQt6.QtGui import QTextCursor
                cursor = log_box.textCursor()
                if msg.strip().startswith(''):
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                    if '' in cursor.selectedText():
                        cursor.removeSelectedText()
                        cursor.deletePreviousChar()
                log_box.append(msg)

        _log_timer = QTimer()
        _log_timer.setInterval(200)
        _log_timer.timeout.connect(_flush_log)
        _log_timer.start()

        class _Worker(QThread):
            log_line = _Signal(str)
            done     = _Signal(object)  # Path | None

            def __init__(self, src, dst_dir, stop_flag):
                super().__init__()
                self._src, self._dst_dir = src, dst_dir
                self._stop = stop_flag

            def run(self):
                result = convert_book_fb2c(
                    self._src, self._dst_dir,
                    out_fmt='epub',
                    log=lambda m: self.log_line.emit(m),
                    stop_flag=self._stop)
                self.done.emit(result)

        worker = _Worker(src, dst_dir, stop_flag)

        def on_done(result):
            _log_timer.stop()
            for m in _log_buf:
                log_box.append(m)
            _log_buf.clear()
            stop_btn.setEnabled(False)
            close_btn.setEnabled(True)
            result_path[0] = result

            if result:
                # ── Переименовываем файл fb2c: убираем спецсимволы ────────
                # fb2c генерирует имя из метаданных fb2 — они могут содержать
                # кавычки, двоеточия и прочее, опасное для NTFS3.
                parent_win = self.parent()
                while parent_win and not hasattr(parent_win, '_safe_name'):
                    parent_win = parent_win.parent() if hasattr(parent_win, 'parent') else None
                safe_fn = (parent_win._safe_name(result.stem)
                           if parent_win else result.stem) + result.suffix
                safe_path = result.parent / safe_fn
                if safe_path != result:
                    try:
                        result.rename(safe_path)
                        result = safe_path
                        result_path[0] = result
                        log_box.append(f"   Файл переименован: {safe_fn}")
                    except Exception as e:
                        log_box.append(f"   Переименование не удалось: {e}")

                open_btn.setEnabled(True)
                open_book_btn.setEnabled(True)

                # ── Регистрируем EPUB как второй формат в библиотеке ──────
                if self.config:
                    epub_path = str(result)
                    fb2_path  = str(src)

                    # Добавляем epub к записи книги (config.add_book умеет
                    # находить книгу по title+author и дописывать fmt)
                    meta = dict(self.book_info)
                    meta['file_path'] = epub_path
                    meta['format']    = 'epub'
                    self.config.add_book(meta)
                    log_box.append("   EPUB добавлен в библиотеку как второй формат")

                    # Сбрасываем CFI-позицию: FB2 DOM != EPUB DOM
                    for path in (epub_path, fb2_path):
                        if path in self.config._positions:
                            self.config._positions[path]['position'] = None
                            self.config._positions[path]['progress'] = 0
                    self.config.save_positions()
                    log_box.append("   Позиция сброшена — EPUB откроется с начала")

                    # Обновляем карточки после того как диалог закроется —
                    # иначе пересоздание карточек убьёт диалог немедленно.
                    if lib_win_parent:
                        dlg.finished.connect(
                            lambda _: lib_win_parent._on_library_updated())
            else:
                log_box.append("\n Конвертация не удалась")

        def on_open_folder():
            import subprocess
            folder = str(dst_dir)
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', folder])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])

        def on_open_book():
            if result_path[0]:
                self.clicked.emit({**self.book_info, 'file_path': str(result_path[0])})
                dlg.accept()

        open_btn.clicked.connect(on_open_folder)
        open_book_btn.clicked.connect(on_open_book)
        worker.log_line.connect(lambda m: _log_buf.append(m))
        worker.done.connect(on_done)
        worker.start()
        dlg.exec()


    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        cov = QLabel()
        cov.setFixedSize(CARD_W - 16, 190)
        cov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cov.setStyleSheet(
            f"background:{BG};border-radius:6px;color:{SUB};font-size:38px;")
        cp = self.book_info.get("cover_path")
        if cp and Path(cp).exists():
            px = QPixmap(cp)
            if not px.isNull():
                px = px.scaled(CARD_W - 16, 190,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                cov.setPixmap(px)
            else:
                cov.setText("\U0001F4D6")
        else:
            cov.setText("\U0001F4D6")
        lay.addWidget(cov, alignment=Qt.AlignmentFlag.AlignCenter)

        tl = QLabel(self.book_info.get("title", "Без названия"))
        tl.setWordWrap(True); tl.setMaximumHeight(40)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setStyleSheet(f"color:{TEXT};font-size:12px;font-weight:bold;")
        lay.addWidget(tl)

        al = QLabel(self.book_info.get("author", "Неизвестен"))
        al.setWordWrap(True); al.setMaximumHeight(30)
        al.setAlignment(Qt.AlignmentFlag.AlignCenter)
        al.setStyleSheet(f"color:{SUB};font-size:11px;")
        lay.addWidget(al)

        series = self.book_info.get("series")
        snum   = self.book_info.get("series_number")
        if series:
            s = series
            if snum is not None:
                try:
                    v = float(snum)
                    s += f" #{int(v) if v == int(v) else v}"
                except Exception:
                    s += f" #{snum}"
            sl = QLabel(s)
            sl.setWordWrap(True); sl.setMaximumHeight(28)
            sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sl.setStyleSheet(f"color:{SERIES};font-size:10px;font-weight:bold;")
            lay.addWidget(sl)

        lay.addStretch()

        p = self.book_info.get("progress", 0)
        if p and p > 0:
            bg = QFrame(); bg.setFixedHeight(3)
            bg.setStyleSheet(f"background:{BORDER};border-radius:2px;")
            fill = QFrame(bg); fill.setFixedHeight(3)
            fill.setFixedWidth(max(4, int((CARD_W - 16) * min(p, 1.0))))
            fill.setStyleSheet(f"background:{PROGRESS};border-radius:2px;")
            lay.addWidget(bg)


class LibraryWindow(QMainWindow):
    book_selected = pyqtSignal(str)

    @staticmethod
    def _norm_path(p) -> str:
        """Нормализация пути к единому формату (прямые слеши)"""
        return str(p).replace('\\', '/')

    def __init__(self, config):
        super().__init__()
        self.config = config
        init_lib_colors(config)  # применяем сохранённую тему до построения UI
        self.parser = BookParser()
        self.zip_handler = ZipHandler()
        self._all_books = []
        self.setStyleSheet(f"QMainWindow{{background:{BG};}}")
        self.setWindowTitle("NovaReader")
        self.resize(config.get("library_width", 1200),
                    config.get("library_height", 800))
        self._setup_ui()
        self._load_books()

    def _setup_ui(self):
        self._central_widget = QWidget()
        self._central_widget.setStyleSheet(f"background:{BG};")
        self.setCentralWidget(self._central_widget)
        root = QVBoxLayout(self._central_widget)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._make_toolbar())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{BG};}}"
            f"QScrollBar:vertical{{width:8px;background:{BG};}}"
            f"QScrollBar::handle:vertical{{background:{BORDER};"
            f"border-radius:4px;min-height:24px;}}"
            f"QScrollBar::add-line:vertical,"
            f"QScrollBar::sub-line:vertical{{height:0;}}")

        self.books_container = QWidget()
        self.books_container.setStyleSheet(f"background:{BG};")
        self.books_layout = QGridLayout(self.books_container)
        self.books_layout.setSpacing(CARD_S)
        self.books_layout.setContentsMargins(16, 16, 16, 16)
        self.books_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self.books_container)
        root.addWidget(self._scroll)

        self.statusBar().setStyleSheet(
            f"QStatusBar{{background:{TOOLBAR};color:{SUB};"
            f"font-size:12px;padding:2px 8px;}}")
        self.status_label = QLabel(_ls(self.config, 'ready'))
        self.status_label.setStyleSheet(f"color:{SUB};")
        self.statusBar().addWidget(self.status_label)

    def _make_toolbar(self):
        self._toolbar_bar = QWidget()
        self._toolbar_bar.setFixedHeight(56)
        self._toolbar_bar.setStyleSheet(
            f"QWidget{{background:{TOOLBAR};border-bottom:1px solid {BORDER};}}")
        lay = QHBoxLayout(self._toolbar_bar)
        lay.setContentsMargins(12, 0, 12, 0); lay.setSpacing(4)

        self.add_btn      = _mbtn("add",          _ls(self.config, 'add_books'))
        self.scan_btn     = _mbtn("folder_open",  _ls(self.config, 'scan_folder'))
        self.cleanup_btn  = _mbtn("delete_sweep", _ls(self.config, 'cleanup'))
        self.export_btn   = _mbtn("content_copy", _ls(self.config, 'export_notes'))
        self.refresh_btn  = _mbtn("refresh",      _ls(self.config, 'refresh'))
        self.backup_btn   = _mbtn("backup",       _ls(self.config, 'backup'))
        self.restore_btn  = _mbtn("restore",      _ls(self.config, 'restore'))
        self.settings_btn = _mbtn("settings",     _ls(self.config, 'settings'))

        self.add_btn.clicked.connect(self.add_books)
        self.scan_btn.clicked.connect(self.scan_folder)
        self.cleanup_btn.clicked.connect(self.cleanup_library)
        self.export_btn.clicked.connect(self.export_notes)
        self.refresh_btn.clicked.connect(self._load_books)
        self.backup_btn.clicked.connect(self.backup_config)
        self.restore_btn.clicked.connect(self.restore_config)
        self.settings_btn.clicked.connect(self.open_settings)

        self._toolbar_seps = []

        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setFixedHeight(24)
            s.setStyleSheet(f"color:{BORDER};")
            self._toolbar_seps.append(s)
            return s

        # Левая группа: работа с книгами
        for btn in (self.add_btn, self.scan_btn, self.cleanup_btn, self.export_btn):
            lay.addWidget(btn)

        lay.addWidget(_sep())

        # Бэкап / восстановление
        lay.addWidget(self.backup_btn)
        lay.addWidget(self.restore_btn)

        lay.addWidget(_sep())

        # Настройки
        lay.addWidget(self.settings_btn)

        # Растяжка — справа поиск, сортировка, фильтр, обновить
        lay.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(_ls(self.config, 'search_placeholder'))
        self.search_box.setFixedSize(260, 34)
        self.search_box.setStyleSheet(
            f"QLineEdit{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QLineEdit:focus{{border:1px solid {ACCENT};}}")
        self.search_box.textChanged.connect(self._on_search)
        lay.addWidget(self.search_box)

        # Сортировка
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            _ls(self.config, 'sort_last_read'),
            _ls(self.config, 'sort_date_added'),
            _ls(self.config, 'sort_title'),
            _ls(self.config, 'sort_author'),
        ])
        self.sort_combo.setFixedSize(180, 34)
        self.sort_combo.setStyleSheet(
            f"QComboBox{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QComboBox:focus{{border:1px solid {ACCENT};}}")
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        lay.addWidget(self.sort_combo)

        # Фильтр по формату
        self.format_filter = QComboBox()
        self.format_filter.addItems([
            _ls(self.config, 'filter_all'),
            "EPUB", "FB2", "PDF", "MOBI", "CBZ",
            _ls(self.config, 'filter_comics'),
        ])
        self.format_filter.setFixedSize(140, 34)
        self.format_filter.setStyleSheet(
            f"QComboBox{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QComboBox:focus{{border:1px solid {ACCENT};}}")
        self.format_filter.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.format_filter)

        sep_r = QFrame()
        sep_r.setFrameShape(QFrame.Shape.VLine)
        sep_r.setFixedHeight(24)
        sep_r.setStyleSheet(f"color:{BORDER};")
        self._toolbar_seps.append(sep_r)
        lay.addWidget(sep_r)
        lay.addWidget(self.refresh_btn)
        return self._toolbar_bar

    # ── responsive grid ───────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._reflow)

    def _cols(self):
        avail = self.books_container.width() - 32
        return max(1, avail // (CARD_W + CARD_S))

    def _reflow(self):
        cols = self._cols()
        items = [self.books_layout.itemAt(i).widget()
                 for i in range(self.books_layout.count())
                 if self.books_layout.itemAt(i).widget()]
        for w in items:
            self.books_layout.removeWidget(w)
        for idx, w in enumerate(items):
            self.books_layout.addWidget(w, idx // cols, idx % cols)

    # ── load / display ────────────────────────────────────────
    def _load_books(self):
        for i in reversed(range(self.books_layout.count())):
            w = self.books_layout.itemAt(i).widget()
            if w: w.deleteLater()
        books = self.config.get_books()
        # Сортировка по умолчанию - по последнему чтению
        self._all_books = self._sort_books(books)
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        self._display(self._filter(self._all_books, q))

    def _filter(self, books, q):
        q = q.strip().lower()
        if not q: return books
        return [b for b in books
                if q in " ".join([b.get("title", ""), b.get("author", ""),
                                   b.get("series", "") or ""]).lower()]

    def _sort_books(self, books):
        """Сортировка книг по выбранному критерию (по индексу, не тексту)."""
        sort_idx = self.sort_combo.currentIndex() if hasattr(self, "sort_combo") else 0
        # 0=last_read  1=date_added  2=title  3=author

        if sort_idx == 0:
            # Читавшиеся — по дате последнего чтения (новее = выше).
            # Новые (нет last_read) — по дате добавления (новее = выше),
            # но всегда ПОСЛЕ читавшихся, а не в самом низу.
            read     = [b for b in books if b.get("last_read")]
            unread   = [b for b in books if not b.get("last_read")]
            read.sort(key=lambda b: b.get("last_read", ""),   reverse=True)
            unread.sort(key=lambda b: b.get("added", ""),     reverse=True)
            return read + unread

        elif sort_idx == 1:
            return sorted(books, key=lambda b: b.get("added", ""), reverse=True)
        elif sort_idx == 2:
            return sorted(books, key=lambda b: b.get("title", "").lower())
        elif sort_idx == 3:
            return sorted(books, key=lambda b: (b.get("author", "") or "").lower())
        return books

    def _on_sort_changed(self):
        """Изменение типа сортировки."""
        self._display(self._filter(self._all_books, self.search_box.text() if hasattr(self, "search_box") else ""))

    def _on_library_updated(self):
        """Обновление списка книг при изменении библиотеки (real-time)."""
        # Защита от рекурсивного вызова
        if hasattr(self, '_updating') and self._updating:
            print("[Library]  Защита от рекурсивного _on_library_updated()")
            return
        
        self._updating = True
        try:
            scroll_area = self.books_container.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            pos = scroll_area.verticalScrollBar().value() if scroll_area else 0

            books = self.config.get_books()
            self._all_books = self._sort_books(books)
            self._display(self._filter(self._all_books,
                          self.search_box.text() if hasattr(self, "search_box") else ""))
            if scroll_area:
                scroll_area.verticalScrollBar().setValue(pos)
        finally:
            self._updating = False

    def _display(self, books):
        for i in reversed(range(self.books_layout.count())):
            w = self.books_layout.itemAt(i).widget()
            if w: w.deleteLater()
        if not books:
            has_q = hasattr(self, "search_box") and self.search_box.text()
            msg = ("Ничего не найдено" if has_q
                   else "Библиотека пуста\n\nНажмите + чтобы добавить книги")
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{SUB};font-size:16px;padding:60px;")
            self.books_layout.addWidget(lbl, 0, 0)
            n = len(self._all_books)
            self.status_label.setText(
                "Библиотека пуста" if not n else f"Ничего не найдено из {n}")
            return
        cols = self._cols()
        for idx, book in enumerate(books):
            card = BookCard(book, self.config)
            card.clicked.connect(self._on_book_clicked)
            card.delete_req.connect(self._on_delete_book)
            self.books_layout.addWidget(card, idx // cols, idx % cols)
        n, shown = len(self._all_books), len(books)
        self.status_label.setText(
            _ls(self.config, 'shown_of', shown=shown, n=n)
            if shown != n else
            _ls(self.config, 'books_count', n=n))

    def _on_search(self, q):
        self._display(self._filter(self._all_books, q))

    def _on_filter_changed(self, _text):
        """Фильтрация по формату книги (по индексу, не тексту)."""
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        books = self._filter(self._all_books, q)
        idx = self.format_filter.currentIndex() if hasattr(self, "format_filter") else 0
        # 0=все  1=epub  2=fb2  3=pdf  4=mobi  5=cbz  6=комиксы
        FMT_MAP = {1: 'epub', 2: 'fb2', 3: 'pdf', 4: 'mobi', 5: 'cbz'}
        if idx == 6:
            books = [b for b in books
                     if b.get('format', '').lower() in ('cbz', 'cbr', 'comic')]
        elif idx in FMT_MAP:
            books = [b for b in books
                     if b.get('format', '').lower() == FMT_MAP[idx]]
        self._display(books)

    def _on_book_clicked(self, book_info):
        """Открытие книги с приоритетом EPUB > FB2 > остальные."""
        # book_info может быть строкой (старый код) или словарём
        if isinstance(book_info, str):
            fp = book_info
        else:
            fp = book_info.get("file_path")
        if not fp or not Path(fp).exists():
            return
        
        # Находим папку книги и ищем все форматы
        book_path = Path(fp)
        book_dir = book_path.parent
        
        if book_dir.exists():
            # Приоритет форматов: FB2 > EPUB > остальные
            priority = ['fb2', 'epub', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr']
            for fmt in priority:
                for f in book_dir.iterdir():
                    if f.suffix.lower() == f'.{fmt}':
                        self.book_selected.emit(str(f))
                        return
            
            # Если ни одного из приоритетных — открываем первый найденный
            for f in book_dir.iterdir():
                if f.suffix.lower() in ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']:
                    self.book_selected.emit(str(f))
                    return
        
        # Fallback
        self.book_selected.emit(fp)

    # ── удаление книги ────────────────────────────────────────
    def _on_delete_book(self, book_info):
        """Удаление книги.
        Если форматов несколько — спрашивает: удалить выбранный формат или все.
        """
        title    = book_info.get("title", "Книга")[:60]
        book_id  = book_info.get("_book_id") or book_info.get("id")
        formats  = book_info.get("formats", {})  # {fmt: file_path}
        cur_path = book_info.get("file_path", "")

        if len(formats) > 1:
            # Несколько форматов — даём выбор
            fmt_list = "\n".join(
                f"  • {fmt.upper()} — {Path(fp).name}"
                for fmt, fp in formats.items())
            mb = QMessageBox(self)
            mb.setWindowTitle(_ls(self.config, 'delete_title'))
            mb.setText(
                f"<b>{title}</b><br><br>"
                f"Доступно форматов:<br>{fmt_list.replace(chr(10), '<br>')}<br><br>"
                f"Что удалить?")
            btn_cur = mb.addButton(
                f"Только {Path(cur_path).suffix.upper()} (текущий)",
                QMessageBox.ButtonRole.AcceptRole)
            btn_all = mb.addButton(
                _ls(self.config, 'delete_btn_all'),
                QMessageBox.ButtonRole.DestructiveRole)
            btn_can = mb.addButton(
                _ls(self.config, 'delete_btn_cancel'),
                QMessageBox.ButtonRole.RejectRole)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked == btn_can or clicked is None:
                return
            delete_all = (clicked == btn_all)
        else:
            r = QMessageBox.question(
                self, _ls(self.config, 'delete_title'),
                _ls(self.config, 'delete_msg_single', title=title),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return
            delete_all = True

        # Собираем файлы для удаления
        if delete_all:
            paths_to_delete = list(formats.values())
            if book_id:
                self.config.remove_book_by_id(book_id)
            else:
                self.config.remove_book(cur_path)
        else:
            paths_to_delete = [cur_path]
            # remove_format убирает только этот формат из записи.
            # Если остался хотя бы один другой формат — запись сохраняется.
            self.config.remove_format(cur_path)

        try:
            if delete_all:
                # ── Удаляем ВСЕ форматы и саму папку книги ────────────────
                fp = Path(cur_path)
                book_dir = fp.parent if fp.exists() or fp.parent.exists() else None

                for path in paths_to_delete:
                    p = Path(path)
                    if p.exists():
                        p.unlink()
                        print(f"[Library] Удалён файл: {p.name}")

                if book_dir and book_dir.exists():
                    cover = book_dir / "cover.jpg"
                    if cover.exists():
                        cover.unlink(missing_ok=True)
                    meta_f = book_dir / "metadata.json"
                    if meta_f.exists():
                        meta_f.unlink(missing_ok=True)
                    # Папку удаляем только если она пуста
                    try:
                        book_dir.rmdir()
                        print(f"[Library] Удалена папка книги: {book_dir.name}")
                        # Папку автора — тоже если пуста
                        author_dir = book_dir.parent
                        lib_root   = self.config.get_library_path()
                        if (author_dir != lib_root and author_dir.exists()
                                and not any(author_dir.iterdir())):
                            author_dir.rmdir()
                            print(f"[Library] Удалена папка автора: {author_dir.name}")
                    except OSError:
                        pass  # в папке что-то осталось — не трогаем
            else:
                # ── Удаляем ТОЛЬКО один файл, папку и остальные НЕ трогаем ─
                p = Path(cur_path)
                if p.exists():
                    p.unlink()
                    print(f"[Library] Удалён формат: {p.name}")
                # Папка остаётся; другие форматы остаются.
                # remove_format уже обновил конфиг.

        except Exception as e:
            print(f"[Library] Delete error: {e}")
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось удалить файлы:\n{e}")

        # Удаляем обложку из кэша только при полном удалении
        if delete_all:
            cp = book_info.get("cover_path")
            if cp:
                try: Path(cp).unlink(missing_ok=True)
                except Exception: pass

        self._load_books()

    # ── добавление ────────────────────────────────────────────
    def add_books(self):
        files, selected_filter = QFileDialog.getOpenFileNames(
            self, _ls(self.config, 'add_dialog_title'),
            str(self.config.get_library_path()),
            f"{_ls(self.config,'add_filter_books')};;"
            f"{_ls(self.config,'add_filter_comics')};;"
            f"{_ls(self.config,'add_filter_manga')};;"
            f"{_ls(self.config,'add_filter_pdf')};;"
            f"{_ls(self.config,'add_filter_all')}")
        if not files:
            return
        if _ls(self.config, 'add_filter_manga') in selected_filter:
            comic_type = "Манга"
        elif _ls(self.config, 'add_filter_comics') in selected_filter:
            comic_type = "Комиксы"
        else:
            comic_type = None
        self._process_books(files, comic_type=comic_type)

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, _ls(self.config, 'scan_dialog_title'),
            str(self.config.get_library_path()))
        if not folder: return
        books = []
        for ext in ["*.epub", "*.fb2", "*.fb2.zip", "*.zip", "*.mobi", "*.cbz", "*.pdf"]:
            books.extend(Path(folder).rglob(ext))
        if not books:
            QMessageBox.information(self, _ls(self.config, 'add_done'),
                                    _ls(self.config, 'no_books_found')); return
        r = QMessageBox.question(
            self, _ls(self.config, 'scan_dialog_title'),
            f"Найдено {len(books)} книг. Добавить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._process_books([str(b) for b in books])

    def cleanup_library(self):
        books = self.config.get_books()
        miss  = [b for b in books
                 if not (b.get("file_path") and Path(b["file_path"]).exists())]
        if not miss:
            QMessageBox.information(self, _ls(self.config, 'add_done'),
                                    "Все записи актуальны."); return
        r = QMessageBox.question(
            self, _ls(self.config, 'cleanup'),
            _ls(self.config, 'cleanup_confirm', n=len(miss)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.config.cleanup_missing()
            self._load_books()

    def export_notes(self):
        """Экспорт заметок и подсветок в TXT или Markdown"""
        # Проверяем, есть ли заметки или подсветки
        data = self.config.get_all_notes_and_highlights()
        has_data = any(
            b['notes'] or b['highlights']
            for b in data.values()
        )
        
        if not has_data:
            QMessageBox.information(
                self, "Экспорт заметок",
                "Нет заметок или выделенных цитат для экспорта.\n\n"
                "Вы можете выделять текст в читалке и добавлять заметки,\n"
                "а затем экспортировать их через это меню."
            )
            return
        
        # Диалог выбора формата
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QRadioButton, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Экспорт заметок")
        dialog.setModal(True)
        dialog.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};}}"
            f"QRadioButton{{color:{TEXT};font-size:14px;}}"
            f"QLabel{{color:{SUB};font-size:13px;}}"
        )
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Выберите формат экспорта:")
        title.setStyleSheet(f"color:{TEXT};font-size:16px;font-weight:bold;")
        layout.addWidget(title)
        
        self.txt_radio = QRadioButton(" TXT — простой текст")
        self.txt_radio.setChecked(True)
        layout.addWidget(self.txt_radio)
        
        self.md_radio = QRadioButton(" Markdown — с форматированием")
        layout.addWidget(self.md_radio)
        
        info = QLabel("\nTXT подойдёт для чтения в любом текстовом редакторе.\n"
                      "Markdown поддерживает форматирование и открывается в Obsidian, Typora и др.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Кнопки OK/Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        # Выбор формата
        use_markdown = self.md_radio.isChecked()
        
        # Диалог сохранения файла
        default_name = "notes.md" if use_markdown else "notes.txt"
        filter_str = "Markdown (*.md)" if use_markdown else "Text files (*.txt)"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить заметки",
            str(self.config.get_library_path() / default_name),
            filter_str
        )
        
        if not file_path:
            return
        
        # Экспорт
        try:
            if use_markdown:
                count = self.config.export_notes_to_markdown(file_path)
            else:
                count = self.config.export_notes_to_txt(file_path)
            
            QMessageBox.information(
                self,
                "Экспорт завершён",
                f" Заметки успешно экспортированы!\n\n"
                f" Экспортировано книг: {count}\n"
                f" Файл сохранён:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f" Не удалось экспортировать заметки:\n{e}"
            )

    def _process_books(self, file_paths, comic_type=None):
        expanded = []
        for fp in file_paths: expanded.extend(self._expand_file(fp))
        if not expanded:
            QMessageBox.warning(self, _ls(self.config, 'error'),
                                _ls(self.config, 'no_books_found')); return
        prog = QProgressDialog(
            _ls(self.config, 'add_progress'),
            _ls(self.config, 'add_cancel'),
            0, len(expanded), self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        added = skipped = 0
        for i, (src_path, tmp_cleanup) in enumerate(expanded):
            if prog.wasCanceled(): break
            prog.setValue(i)
            prog.setLabelText(_ls(self.config, 'add_processing', name=Path(src_path).name))
            try:
                meta = self.parser.extract_metadata(src_path) or {}
                meta.setdefault("title", Path(src_path).stem)
                meta.setdefault("author", "Неизвестен")
                ext = Path(src_path).suffix.lower()
                if comic_type:
                    meta["comic_type"] = comic_type
                elif ext in (".cbz", ".cbr"):
                    meta["comic_type"] = "Комиксы"
                book_key = self._get_book_key(meta)
                existing_book = self._find_existing_book(book_key)
                dest = self._copy_structured(src_path, meta, existing_book)
                if not dest: skipped += 1; continue
                cover_data = self.parser.extract_cover(src_path)
                cover_path = None
                if cover_data:
                    cover_path = dest.parent / "cover.jpg"
                    cover_path.write_bytes(cover_data)
                   # (self.config.covers_dir / f"{dest.stem}.jpg").write_bytes(cover_data)
                (dest.parent / "metadata.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                # НОРМАЛИЗУЕМ ПУТИ перед сохранением в конфиг
                meta["file_path"] = self._norm_path(dest)
                meta["format"] = dest.suffix.lower().lstrip(".")
                meta["cover_path"] = self._norm_path(cover_path) if cover_path else ""
                self.config.add_book(meta); added += 1
            except Exception as e:
                print(f"[Library] error: {e}"); skipped += 1
            finally:
                if tmp_cleanup and Path(tmp_cleanup).exists():
                    shutil.rmtree(tmp_cleanup, ignore_errors=True)
        prog.setValue(len(expanded))
        QMessageBox.information(self, _ls(self.config, 'add_done'),
                                _ls(self.config, 'add_result', added=added, skipped=skipped))
        self._load_books()

    def _expand_file(self, file_path):
        import zipfile as _zf, tempfile as _tmp
        p = Path(file_path)

        # Обычные форматы — передаём как есть
        if p.suffix.lower() in (".epub", ".fb2", ".mobi", ".azw3", ".cbz", ".pdf"):
            return [(str(p), None)]

        # ZIP / FB2.ZIP — распаковываем и ищем книги внутри
        if ("".join(p.suffixes).lower() in (".zip", ".fb2.zip", ".cbz.zip")
                or p.suffix.lower() == ".zip"):
            results = []
            try:
                tmp = _tmp.mkdtemp(prefix="novareader_")
                with _zf.ZipFile(str(p), "r") as z: z.extractall(tmp)
                for found in Path(tmp).rglob("*"):
                    if found.suffix.lower() in (".epub", ".fb2", ".mobi", ".cbz", ".pdf"):
                        results.append((str(found), tmp))
                if not results: shutil.rmtree(tmp, ignore_errors=True)
            except Exception as e:
                print(f"[Library] zip: {e}")
            return results

        # CBR (RAR) — конвертируем в CBZ чтобы foliate мог открыть
        if p.suffix.lower() == ".cbr":
            return self._cbr_to_cbz(p)

        return [(str(p), None)]

    def _cbr_to_cbz(self, cbr_path: Path):
        """Конвертирует CBR (RAR) → CBZ (ZIP) во временной папке.
        Возвращает [(cbz_path, tmp_dir)] или [] при ошибке.
        """
        import tempfile as _tmp, zipfile as _zf, subprocess as _sp
        tmp = _tmp.mkdtemp(prefix="novareader_cbr_")
        try:
            extracted = False

            # Пробуем rarfile (Python-обёртка над unrar/bsdtar)
            try:
                import rarfile as _rf
                with _rf.RarFile(str(cbr_path)) as rf:
                    rf.extractall(tmp)
                extracted = True
                print(f"[Library] CBR: распакован через rarfile")
            except ImportError:
                pass
            except Exception as e:
                print(f"[Library] CBR rarfile error: {e}")

            # Пробуем системный unrar/bsdtar
            if not extracted:
                for cmd in (
                    ["unrar", "x", "-y", str(cbr_path), tmp + "/"],
                    ["bsdtar", "-xf", str(cbr_path), "-C", tmp],
                    ["7z", "x", str(cbr_path), f"-o{tmp}", "-y"],
                ):
                    try:
                        r = _sp.run(cmd, capture_output=True, timeout=60)
                        if r.returncode == 0:
                            extracted = True
                            print(f"[Library] CBR: распакован через {cmd[0]}")
                            break
                    except (FileNotFoundError, _sp.TimeoutExpired):
                        continue

            if not extracted:
                print(f"[Library] CBR: не удалось распаковать {cbr_path.name} — "
                      f"установите unrar, bsdtar или 7z")
                shutil.rmtree(tmp, ignore_errors=True)
                return []

            # Собираем все изображения в CBZ
            IMG = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif')
            images = sorted([
                f for f in Path(tmp).rglob("*")
                if f.suffix.lower() in IMG and f.is_file()
            ])
            if not images:
                print(f"[Library] CBR: нет изображений в {cbr_path.name}")
                shutil.rmtree(tmp, ignore_errors=True)
                return []

            cbz_path = Path(tmp) / (cbr_path.stem + ".cbz")
            with _zf.ZipFile(str(cbz_path), "w", _zf.ZIP_DEFLATED) as zf:
                for img in images:
                    # Сохраняем относительный путь внутри архива
                    zf.write(img, img.relative_to(tmp))

            print(f"[Library] CBR → CBZ: {cbz_path.name} ({len(images)} страниц)")
            return [(str(cbz_path), tmp)]

        except Exception as e:
            print(f"[Library] CBR → CBZ error: {e}")
            shutil.rmtree(tmp, ignore_errors=True)
            return []

    @staticmethod
    def _safe_name(name: str, max_len: int = 60) -> str:
        """Очистить имя файла/папки от символов, опасных для NTFS3 и любых ФС.

        Убираем:
          - Windows-запрещённые: < > : " / \\ | ? *
          - Одинарные кавычки и апострофы: '
          - Спецсимволы: & ; = + , [ ] { } ^ % @ ! ~ `
          - Управляющие символы (категории Cc, Cf)
        Разрешены: буквы (кириллица/Unicode), цифры, пробелы, дефис, точка,
        круглые скобки, подчёркивание, #.
        """
        import unicodedata as _ud, re as _re
        # Убираем управляющие символы
        name = "".join(ch for ch in name
                       if _ud.category(ch) not in ("Cc", "Cf") and ord(ch) >= 0x20)
        # Заменяем запрещённые символы на подчёркивание
        FORBIDDEN = set('<>:"/\\|?*\'&;=+,[]{|}^%@!~`')
        name = "".join("_" if ch in FORBIDDEN else ch for ch in name)
        # Схлопываем повторы
        name = _re.sub(r'_+', '_', name)
        name = _re.sub(r' +', ' ', name)
        # Windows не любит точки и пробелы на краях
        name = name.strip(". ")
        return name[:max_len] or "Без_названия"

    def _get_book_key(self, meta):
        """Уникальный ключ книги по метаданным (title + author)."""
        title = (meta.get("title") or "").strip().lower()
        author = (meta.get("author") or "Неизвестен").strip().lower()
        # Нормализуем: убираем лишние пробелы
        title = " ".join(title.split())
        author = " ".join(author.split())
        return (title, author)

    def _find_existing_book(self, book_key):
        """Ищет существующую книгу с такими же метаданными."""
        for book in self.config.get_books():
            existing_key = self._get_book_key(book)
            if existing_key == book_key:
                return book
        return None

    def _copy_structured(self, src_path, meta, existing_book=None):
        """Копирует книгу в библиотеку. Если existing_book указан — кладёт в ту же папку."""
        try:
            src = Path(src_path)

            if existing_book:
                existing_path = Path(existing_book.get("file_path", ""))
                book_dir = existing_path.parent
            else:
                lib  = self.config.get_library_path()
                ext  = src.suffix.lower()
                comic_type = meta.get("comic_type")  # "Комиксы" | "Манга" | None

                if comic_type or ext in (".cbz", ".cbr"):
                    # Комиксы и манга — в отдельные папки без папки автора
                    folder_name = comic_type or "Комиксы"
                    title = self._safe_name(meta.get("title") or src.stem)
                    series = meta.get("series")
                    snum   = meta.get("series_number")
                    if series:
                        n = ""
                        if snum is not None:
                            try:
                                v = float(snum)
                                n = f" #{int(v) if v == int(v) else v}"
                            except Exception:
                                n = f" #{snum}"
                        dname = self._safe_name(f"{series}{n}. {title}")
                    else:
                        dname = title
                    book_dir = lib / folder_name / dname
                else:
                    # Обычные книги — Автор / Название
                    author = self._safe_name(meta.get("author") or "Неизвестен")
                    title  = meta.get("title") or src.stem
                    series = meta.get("series"); snum = meta.get("series_number")
                    if series:
                        n = ""
                        if snum is not None:
                            try:
                                v = float(snum)
                                n = f" #{int(v) if v == int(v) else v}"
                            except Exception:
                                n = f" #{snum}"
                        dname = self._safe_name(f"{series}{n}. {title}")
                    else:
                        dname = self._safe_name(title)
                    book_dir = lib / author / dname

                book_dir.mkdir(parents=True, exist_ok=True)

            dest = book_dir / src.name
            if dest.exists() and dest.stat().st_size == src.stat().st_size:
                return dest
            shutil.copy2(src, dest)
            return dest
        except Exception as e:
            print(f"[Library] copy: {e}"); return None

    # ── настройки ─────────────────────────────────────────────
    # ── тема библиотеки ───────────────────────────────────────
    def apply_lib_theme(self, theme_name: str, custom_colors: dict = None) -> None:
        """Применить тему библиотеки немедленно без перезапуска."""
        import library_window as _lw
        if theme_name == "light":
            colors = dict(LIGHT_THEME)
        elif theme_name == "custom" and custom_colors:
            colors = dict(DARK_THEME)
            colors.update(custom_colors)
        else:
            colors = dict(DARK_THEME)

        _lw._apply_theme_to_globals(colors)

        # Сохраняем в конфиг
        self.config.set("library_theme_name", theme_name)
        if theme_name == "custom" and custom_colors:
            self.config.set("library_theme_custom", custom_colors)

        # Обновляем стили существующих виджетов (без пересоздания — сетка не едет)
        self._apply_theme_styles()
        # Перекрашиваем карточки
        self._load_books()

    def _apply_theme_styles(self) -> None:
        """Перекрасить все виджеты библиотеки по текущим глобальным цветам."""
        self.setStyleSheet(f"QMainWindow{{background:{BG};}}")

        if hasattr(self, "_central_widget"):
            self._central_widget.setStyleSheet(f"background:{BG};")

        if hasattr(self, "_scroll"):
            self._scroll.setStyleSheet(
                f"QScrollArea{{border:none;background:{BG};}}"
                f"QScrollBar:vertical{{width:8px;background:{BG};}}"
                f"QScrollBar::handle:vertical{{background:{BORDER};"
                f"border-radius:4px;min-height:24px;}}"
                f"QScrollBar::add-line:vertical,"
                f"QScrollBar::sub-line:vertical{{height:0;}}")

        if hasattr(self, "books_container"):
            self.books_container.setStyleSheet(f"background:{BG};")

        self.statusBar().setStyleSheet(
            f"QStatusBar{{background:{TOOLBAR};color:{SUB};"
            f"font-size:12px;padding:2px 8px;}}")
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(f"color:{SUB};")

        if hasattr(self, "_toolbar_bar"):
            self._toolbar_bar.setStyleSheet(
                f"QWidget{{background:{TOOLBAR};border-bottom:1px solid {BORDER};}}")

        for sep in getattr(self, "_toolbar_seps", []):
            sep.setStyleSheet(f"color:{BORDER};")

        for btn in (getattr(self, n, None) for n in (
                "add_btn", "scan_btn", "cleanup_btn", "export_btn",
                "refresh_btn", "backup_btn", "restore_btn", "settings_btn")):
            if btn:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;border:none;"
                    f"border-radius:18px;color:{SUB};"
                    f"font-family:'Material Icons';font-size:18px;}}"
                    f"QPushButton:hover{{background:rgba(128,128,128,.12);color:{TEXT};}}"
                    f"QPushButton:pressed{{background:rgba(128,128,128,.22);}}")

        combo_ss = (
            f"QComboBox{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QComboBox:focus{{border:1px solid {ACCENT};}}")
        for w in (getattr(self, n, None) for n in
                  ("search_box", "sort_combo", "format_filter")):
            if w:
                w.setStyleSheet(combo_ss)

        if hasattr(self, "search_box"):
            self.search_box.setStyleSheet(
                f"QLineEdit{{background:{BG};color:{TEXT};"
                f"border:1px solid {BORDER};border-radius:17px;"
                f"padding:0 14px;font-size:13px;}}"
                f"QLineEdit:focus{{border:1px solid {ACCENT};}}")

    def open_settings(self):
        """Открыть окно настроек как независимое окно (не дочернее)."""
        from settings_window import SettingsWindow
        # parent=None + Qt.WindowType.Window = своя кнопка в taskbar, независимое сворачивание
        dlg = SettingsWindow(self.config, parent=None,
                             lib_theme_callback=self.apply_lib_theme)
        dlg.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint)
        dlg.show()   # show() вместо exec() — не блокирует, не является дочерним

    # ── резервное копирование ──────────────────────────────────
    def backup_config(self):
        """Создать ZIP-архив с настройками, книгами, обложками,
        закладками, выделениями и позициями чтения."""
        import datetime
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar
        from PyQt6.QtCore import QThread

        # ── предварительный подсчёт ──────────────────────────
        total_files, total_bytes = self.config.backup_stats()

        def _fmt_size(b):
            for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
                if b < 1024:
                    return f"{b:.1f} {unit}" if unit != 'Б' else f"{b} {unit}"
                b /= 1024
            return f"{b:.1f} ГБ"

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"novareader_backup_{ts}.zip"

        # Показываем что будет в архиве
        info = QMessageBox(self)
        info.setWindowTitle("Создать резервную копию")
        info.setText(
            "<b>В архив войдут:</b><br><br>"
            "   Настройки программы<br>"
            "   Все книги из библиотеки<br>"
            "    Обложки<br>"
            "   Закладки<br>"
            "    Выделения и заметки<br>"
            "   Позиции чтения<br><br>"
            f"Файлов: <b>{total_files}</b> &nbsp;·&nbsp; "
            f"Размер: <b>~{_fmt_size(total_bytes)}</b>")
        info.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        info.button(QMessageBox.StandardButton.Ok).setText("Выбрать файл…")
        if info.exec() != QMessageBox.StandardButton.Ok:
            return

        dest, _ = QFileDialog.getSaveFileName(
            self, "Сохранить резервную копию",
            str(Path.home() / default_name),
            "ZIP-архив (*.zip);;Все файлы (*.*)")
        if not dest:
            return

        # ── прогресс-диалог ───────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("Создание резервной копии")
        dlg.setFixedWidth(460)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};}}"
            f"QLabel{{color:{TEXT};}}"
            f"QProgressBar{{background:#2a2a3a;border:1px solid {BORDER};"
            f"border-radius:4px;height:18px;text-align:center;color:{TEXT};}}"
            f"QProgressBar::chunk{{background:{ACCENT};border-radius:3px;}}"
            f"QPushButton{{background:#7a2020;color:white;border:none;"
            f"padding:7px 20px;border-radius:6px;font-size:13px;}}"
            f"QPushButton:disabled{{background:#444;color:#888;}}")
        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(20, 16, 20, 16)
        vlay.setSpacing(10)

        lbl_title = QLabel(" Упаковка архива...")
        lbl_title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:bold;")
        vlay.addWidget(lbl_title)

        progress = QProgressBar()
        progress.setRange(0, total_files or 1)
        vlay.addWidget(progress)

        lbl_file = QLabel("Подготовка...")
        lbl_file.setStyleSheet(f"color:{SUB};font-size:11px;")
        lbl_file.setWordWrap(True)
        vlay.addWidget(lbl_file)

        lbl_count = QLabel(f"0 / {total_files} файлов")
        lbl_count.setStyleSheet(f"color:{SUB};font-size:12px;")
        vlay.addWidget(lbl_count)

        hlay = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        hlay.addStretch()
        hlay.addWidget(cancel_btn)
        vlay.addLayout(hlay)

        cancel_flag = [False]
        cancel_btn.clicked.connect(lambda: cancel_flag.__setitem__(0, True))

        class _BackupWorker(QThread):
            progress_sig = pyqtSignal(int, int, str)
            done_sig     = pyqtSignal(dict)
            error_sig    = pyqtSignal(str)

            def __init__(self, cfg, dest, cancel_flag):
                super().__init__()
                self._cfg = cfg
                self._dest = dest
                self._cancel = cancel_flag

            def run(self):
                try:
                    result = self._cfg.backup_to_zip(
                        self._dest,
                        progress_cb=lambda cur, tot, name:
                            self.progress_sig.emit(cur, tot, name),
                        cancel_flag=self._cancel)
                    self.done_sig.emit(result)
                except Exception as e:
                    self.error_sig.emit(str(e))

        worker = _BackupWorker(self.config, dest, cancel_flag)

        def on_progress(cur, tot, name):
            progress.setValue(cur)
            lbl_count.setText(f"{cur} / {tot} файлов")
            lbl_file.setText(f"→ {name}")

        def on_done(result):
            dlg.accept()
            if result.get('cancelled'):
                # Удаляем неполный архив
                try:
                    Path(dest).unlink(missing_ok=True)
                except Exception:
                    pass
                QMessageBox.warning(self, "Отменено",
                                    "Создание резервной копии отменено.\n"
                                    "Неполный архив удалён.")
            else:
                sz = Path(dest).stat().st_size
                QMessageBox.information(
                    self, "Резервная копия создана",
                    f" Архив сохранён:\n{dest}\n\n"
                    f" Файлов: {result['files']}\n"
                    f" Размер архива: {_fmt_size(sz)}")

        def on_error(msg):
            dlg.accept()
            try:
                Path(dest).unlink(missing_ok=True)
            except Exception:
                pass
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось создать резервную копию:\n{msg}")

        worker.progress_sig.connect(on_progress)
        worker.done_sig.connect(on_done)
        worker.error_sig.connect(on_error)
        worker.start()
        dlg.exec()
        cancel_flag[0] = True   # на случай закрытия окна крестиком
        worker.wait()

    def restore_config(self):
        """Восстановить настройки, библиотеку, закладки и позиции из ZIP-архива."""
        import zipfile
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar
        from PyQt6.QtCore import QThread

        src, _ = QFileDialog.getOpenFileName(
            self, "Выбрать резервную копию",
            str(Path.home()),
            "ZIP-архив (*.zip);;Все файлы (*.*)")
        if not src:
            return

        # Проверяем архив
        known_config = {"config/settings.json", "config/library.json",
                        "settings.json", "library.json"}
        try:
            with zipfile.ZipFile(src, "r") as zf:
                names = set(zf.namelist())
                total_arc = len(zf.namelist())
                has_lib    = any(n.startswith("library/") for n in names)
                has_covers = any(n.startswith("covers/")  for n in names)
                has_marker = "novareader_backup.marker" in names
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть архив:\n{e}")
            return

        if not names & known_config:
            QMessageBox.warning(
                self, "Неверный архив",
                "Архив не содержит файлов резервной копии NovaReader.\n"
                "Выберите файл, созданный кнопкой «Создать резервную копию».")
            return

        def _fmt_size(b):
            for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
                if b < 1024:
                    return f"{b:.1f} {unit}" if unit != 'Б' else f"{b} {unit}"
                b /= 1024
            return f"{b:.1f} ГБ"

        arc_size = Path(src).stat().st_size

        # Перечисляем что будет восстановлено
        items = ["Настройки программы", "Список библиотеки + позиции чтения",
                 "Закладки", "Выделения", "Заметки"]
        if has_lib:
            items.append("Файлы книг")
        if has_covers:
            items.append("Обложки")

        r = QMessageBox.question(
            self, "Восстановить из резервной копии",
            "  <b>Текущие данные будут заменены!</b><br><br>"
            "Будет восстановлено:<br>  • " +
            "<br>  • ".join(items) +
            f"<br><br>Файлов в архиве: <b>{total_arc}</b> · "
            f"Размер: <b>{_fmt_size(arc_size)}</b><br><br>"
            "Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        # ── прогресс-диалог ───────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("Восстановление из резервной копии")
        dlg.setFixedWidth(460)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};}}"
            f"QLabel{{color:{TEXT};}}"
            f"QProgressBar{{background:#2a2a3a;border:1px solid {BORDER};"
            f"border-radius:4px;height:18px;text-align:center;color:{TEXT};}}"
            f"QProgressBar::chunk{{background:{ACCENT};border-radius:3px;}}"
            f"QPushButton{{background:#7a2020;color:white;border:none;"
            f"padding:7px 20px;border-radius:6px;font-size:13px;}}"
            f"QPushButton:disabled{{background:#444;color:#888;}}")
        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(20, 16, 20, 16)
        vlay.setSpacing(10)

        lbl_title = QLabel(" Восстановление данных...")
        lbl_title.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:bold;")
        vlay.addWidget(lbl_title)

        progress = QProgressBar()
        progress.setRange(0, total_arc or 1)
        vlay.addWidget(progress)

        lbl_file = QLabel("Подготовка...")
        lbl_file.setStyleSheet(f"color:{SUB};font-size:11px;")
        lbl_file.setWordWrap(True)
        vlay.addWidget(lbl_file)

        lbl_count = QLabel(f"0 / {total_arc} файлов")
        lbl_count.setStyleSheet(f"color:{SUB};font-size:12px;")
        vlay.addWidget(lbl_count)

        hlay = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        hlay.addStretch()
        hlay.addWidget(cancel_btn)
        vlay.addLayout(hlay)

        cancel_flag = [False]
        cancel_btn.clicked.connect(lambda: cancel_flag.__setitem__(0, True))

        class _RestoreWorker(QThread):
            progress_sig = pyqtSignal(int, int, str)
            done_sig     = pyqtSignal(dict)
            error_sig    = pyqtSignal(str)

            def __init__(self, cfg, src, cancel_flag):
                super().__init__()
                self._cfg = cfg
                self._src = src
                self._cancel = cancel_flag

            def run(self):
                try:
                    result = self._cfg.restore_from_zip(
                        self._src,
                        progress_cb=lambda cur, tot, name:
                            self.progress_sig.emit(cur, tot, name),
                        cancel_flag=self._cancel)
                    self.done_sig.emit(result)
                except Exception as e:
                    self.error_sig.emit(str(e))

        worker = _RestoreWorker(self.config, src, cancel_flag)

        def on_progress(cur, tot, name):
            progress.setValue(cur)
            lbl_count.setText(f"{cur} / {tot} файлов")
            lbl_file.setText(f"→ {name}")

        def on_done(result):
            dlg.accept()
            if result.get('cancelled'):
                QMessageBox.warning(self, "Отменено",
                                    "Восстановление отменено.\n"
                                    "Часть данных могла быть восстановлена частично.")
            else:
                remap_note = ''
                if result.get('path_remapped'):
                    remap_note = (
                        f"\n\n <b>Пути автоматически переписаны:</b><br>"
                        f"  было:  <code>{result['old_lib_path']}</code><br>"
                        f"  стало: <code>{result['new_lib_path']}</code>")

                msg = QMessageBox(self)
                msg.setWindowTitle("Восстановление завершено")
                msg.setTextFormat(Qt.TextFormat.RichText)
                msg.setText(
                    f" <b>Восстановлено:</b><br><br>"
                    f"   Конфигов: {result['config_files']}<br>"
                    f"   Файлов книг: {result['library_files']}<br>"
                    f"    Обложек: {result['cover_files']}"
                    + remap_note)
                msg.exec()
                
                # АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ БИБЛИОТЕКИ ПОСЛЕ ВОССТАНОВЛЕНИЯ
                self._load_books()
                # Принудительно пересканируем папку библиотеки
               # QTimer.singleShot(500, self._auto_rescan_after_restore)
            
            dlg.accept()

        def on_error(msg):
            dlg.accept()
            QMessageBox.critical(self, "Ошибка восстановления",
                                 f"Не удалось восстановить данные:\n{msg}")

        def on_rescan_cancelled():
            # Если пользователь отменил сканирование, просто обновляем отображение
            self._load_books()

        worker.progress_sig.connect(on_progress)
        worker.done_sig.connect(on_done)
        worker.error_sig.connect(on_error)
        worker.start()
        dlg.exec()
        cancel_flag[0] = True
        worker.wait()

    def _auto_rescan_after_restore(self):
        """Автоматический скан папки после восстановления бэкапа"""
        folder = str(self.config.get_library_path())
        books = []
        for ext in ["*.epub", "*.fb2", "*.fb2.zip", "*.zip", "*.mobi", "*.azw3", "*.cbz", "*.cbr", "*.pdf"]:
            books.extend(Path(folder).rglob(ext))
        
        if books:
            # Предлагаем пользователю добавить найденные книги
            r = QMessageBox.question(
                self,
                "Сканирование после восстановления",
                f"Найдено {len(books)} книг в папке библиотеки.\n\n"
                "Добавить их в библиотеку?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r == QMessageBox.StandardButton.Yes:
                self._process_books([str(b) for b in books])
        else:
            self._load_books()

    def closeEvent(self, e):
        self.config.set("library_width",  self.width())
        self.config.set("library_height", self.height())
        e.accept()