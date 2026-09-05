from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QPushButton, QScrollArea, QGridLayout, QLabel,
QFileDialog, QMessageBox, QProgressDialog,
QFrame, QLineEdit, QMenu, QComboBox, QInputDialog,
QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QObject
from PyQt6.QtGui import QPixmap, QAction, QIcon, QFont, QFontMetrics, QPainter, QColor
from pathlib import Path
import sys, shutil, json, re
from datetime import datetime
from book_parser import BookParser
from zip_handler import ZipHandler
from book_normalizer import (normalize_book, SUPPORTED as NORMALIZER_SUPPORTED,
convert_book_fb2c, _find_fb2c)
from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal as _Signal

CARD_W  = 170
CARD_H  = 335
CARD_S  = 14

# ══════════════════════════════════════════════════════════════════════════
# РЕЖИМ ПАНЕЛИ ФИЛЬТРОВ
# 'horizontal' — комбобоксы в ряд (компактно, как было в тулбаре)
# 'vertical'   — комбобоксы в столбик с подписями (удобнее на узких окнах)
# ══════════════════════════════════════════════════════════════════════════
FILTER_PANEL_MODE = 'horizontal'   # ← поменяйте на 'vertical' для проверки

# ─── Локализация библиотеки ───────────────────────────────────────────────────
_LIB_STRINGS = {
'ru': {
'ready':              'Готов',
'shown_of':           'Показано: {shown} из {n}',
'books_count':        'Книг: {n}',
'add_books':          'Добавить книги',
'scan_folder':        'Сканировать папку',
'cleanup':            'Очистить несуществующие записи',
'export_notes':       'Экспорт заметок',
'refresh':            'Обновить',
'backup':             'Создать резервную копию',
'restore':            'Восстановить из резервной копии',
'restore_url':        'Восстановить по ссылке',
'restore_url_prompt': 'Вставьте прямую ссылку на ZIP-архив резервной копии:',
'restore_url_title':  'Восстановить по ссылке',
'restore_url_download': 'Загрузка архива…',
'restore_url_error':  'Не удалось загрузить архив:\n{e}',
'online_search':      'Поиск книг онлайн',
'settings':           'Настройки',
'search_placeholder': 'Поиск по названию, автору, серии...',
'sort_last_read':     'По последнему чтению',
'sort_date_added':    'По дате добавления',
'sort_title':         'По названию',
'sort_author':        'По автору',
'filter_all':         'Все форматы',
'filter_comics':      'Комиксы',
'add_dialog_title':   'Выберите книги',
# Исправлены фильтры: убраны пробелы перед расширениями
'add_filter_books':   'Книги (*.epub *.fb2 *.fb2.zip *.zip *.mobi *.azw3 *.cbz *.pdf)',
'add_filter_comics':  'Комиксы (*.cbz *.cbr)',
'add_filter_manga':   'Манга (*.cbz *.cbr)',
'add_filter_pdf':     'PDF (*.pdf)',
'add_filter_all':     'Все файлы (*.*)',
'add_progress':       'Добавление книг...',
'add_cancel':         'Отмена',
'add_processing':     'Обработка: {name}',
'add_done':           'Готово',
'add_result':         'Добавлено: {added}\nПропущено: {skipped}',
'no_books_found':     'Книги не найдены.',
'empty_lib_short':    'Библиотека пуста',
'no_results_short':   'Ничего не найдено',
'no_results_of':      'Ничего не найдено из {n}',
'empty_lib_hint':     'Библиотека пуста\n\nНажмите + чтобы добавить книги',
'scan_dialog_title':  'Выберите папку для сканирования',
'scan_progress':      'Сканирование...',
'scan_result':        'Добавлено: {added}\nПропущено: {skipped}',
'cleanup_confirm':    'Удалить {n} несуществующих записей?',
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
'export_title':       'Экспорт заметок',
'export_choose_fmt':  'Выберите формат экспорта:',
'export_no_data_title':'Экспорт заметок',
'export_no_data_msg': 'Нет заметок для экспорта.',
'export_fmt_txt':     'TXT — простой текст',
'export_fmt_md':      'Markdown — с форматированием',
'export_fmt_hint':    '\nTXT подойдёт для чтения в любом текстовом редакторе.\n'
'Markdown поддерживает форматирование и открывается в Obsidian, Typora и др.',
'export_done':        'Экспорт завершён',
'export_saved':       'Заметки экспортированы.\nКниг: {count}\nФайл: {path}',
'export_error':       'Ошибка экспорта',
'export_error_msg':   'Не удалось экспортировать заметки:\n{e}',
'backup_title':       'Создать резервную копию',
'backup_contents_title': 'В архив войдут:',
'backup_item_settings': 'Настройки программы',
'backup_item_library':  'Все книги из библиотеки',
'backup_item_positions':'Закладки, выделения, позиции',
'backup_toggle_voices':'Голоса Piper (~/.config/NovaReader/voices/)',
'backup_toggle_fonts': 'Пользовательские шрифты (~/.config/NovaReader/fonts/)',
'backup_stats':       'Файлов:  <b>{n}</b>  ·  Размер:  <b>~{size}</b>',
'backup_saved_stats': 'Архив сохранён:\n{path}\n\nФайлов: {files}\nРазмер: {size}',
'backup_cancelled_title': 'Отменено',
'backup_cancelled_msg':   'Создание резервной копии отменено.\nНеполный архив удалён.',
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
'restore_invalid_title': 'Неверный архив',
'restore_invalid_msg':   'Архив не содержит файлов резервной копии NovaReader.\n'
'Выберите файл, созданный кнопкой «Создать резервную копию».',
'ctx_open':           'Открыть',
'ctx_open_in':        'Открыть в...',
'ctx_delete_fmt':     'Удалить формат',
'ctx_delete':         'Удалить книгу',
'ctx_convert':        'Конвертировать в EPUB (fb2c)',
'ctx_convert_fb2c':   'Конвертировать FB2 → EPUB',
'ctx_convert_fb2c_missing': 'Конвертировать FB2 → EPUB (fb2c не найден)',
'ctx_normalize':      'Нормализовать',
'ctx_normalize_tts':  'Нормализовать для TTS',
'ctx_normalize_tts_fmt': 'Нормализовать для TTS ({fmt})',
'ctx_edit_meta':      'Редактировать метаданные',
'status_all':         'Все книги',
'status_only_new':    'Только новые',
'status_only_reading': 'Только читаемые',
'status_hide_new':    'Скрыть новые',
'status_hide_reading':'Скрыть читаемые',
'error':              'Ошибка',
'cbr_no_extractor':   'Не удалось распаковать {name} — установите unrar, bsdtar или 7z',
'empty_lib':          'Библиотека пуста.\nДобавьте книги кнопкой «+».',
'dlg_back':           'Назад',
'dlg_forward':        'Вперёд',
'dlg_up':             'На уровень выше',
'dlg_new_folder':     'Новая папка',
'dlg_view_list':      'Список',
'dlg_view_detail':    'Детали',
'dlg_save_norm':      'Сохранить нормализованную книгу',
'dlg_filter_books':   'Книги (*{ext});;Все файлы (*.*)',
'dlg_save_notes':     'Сохранить заметки',
'dlg_filter_md':      'Markdown (*.md)',
'dlg_filter_txt':     'Текстовые файлы (*.txt)',
'dlg_save_backup':    'Сохранить резервную копию',
'dlg_filter_zip':     'ZIP-архив (*.zip);;Все файлы (*.*)',
'dlg_open_backup':    'Выбрать резервную копию',
'dlg_choose_file':    'Выбрать файл…',
'close':             'Закрыть',
'cancel':            'Отмена',
'drop_to_add':       'Перетащите книги для добавления',
'yes':               'Да',
'no':                'Нет',
'found_books':       'Найдено {n} книг. Добавить?',
'all_records_ok':    'Все записи актуальны.',
'restore_item_settings': 'Настройки программы',
'restore_item_lib':      'Список библиотеки + позиции чтения',
'restore_item_bookmarks':'Закладки',
'restore_item_highlights':'Выделения',
'restore_item_notes':    'Заметки',
'restore_item_books':    'Файлы книг',
'restore_item_covers':   'Обложки',
# Новые строки для панели фильтров
'filter_sort_label':  'Сортировка:',
'filter_format_label':'Формат:',
'filter_status_label':'Статус:',
'filter_toggle_tip':  'Фильтры и сортировка',
},
'en': {
'ready':              'Ready',
'shown_of':           'Shown: {shown} of {n}',
'books_count':        'Books: {n}',
'add_books':          'Add books',
'scan_folder':        'Scan folder',
'cleanup':            'Remove missing entries',
'export_notes':       'Export notes',
'refresh':            'Refresh',
'backup':             'Create backup',
'restore':            'Restore from backup',
'restore_url':        'Restore from URL',
'restore_url_prompt': 'Paste a direct link to the backup ZIP archive:',
'restore_url_title':  'Restore from URL',
'restore_url_download': 'Downloading archive…',
'restore_url_error':  'Failed to download archive:\n{e}',
'settings':           'Settings',
'online_search':      'Search for books online',
'search_placeholder': 'Search by title, author, series...',
'sort_last_read':     'Last read',
'sort_date_added':    'Date added',
'sort_title':         'By title',
'sort_author':        'By author',
'filter_all':         'All formats',
'filter_comics':      'Comics',
'add_dialog_title':   'Select books',
'add_filter_books':   'Books (*.epub *.fb2 *.fb2.zip *.zip *.mobi *.azw3 *.cbz *.pdf)',
'add_filter_comics':  'Comics (*.cbz *.cbr)',
'add_filter_manga':   'Manga (*.cbz *.cbr)',
'add_filter_pdf':     'PDF (*.pdf)',
'add_filter_all':     'All files (*.*)',
'add_progress':       'Adding books...',
'add_cancel':         'Cancel',
'add_processing':     'Processing: {name}',
'add_done':           'Done',
'add_result':         'Added: {added}\nSkipped: {skipped}',
'no_books_found':     'No books found.',
'empty_lib_short':    'Library is empty',
'no_results_short':   'No results found',
'no_results_of':      'No results found out of {n}',
'empty_lib_hint':     'Library is empty\n\nClick + to add books',
'scan_dialog_title':  'Select folder to scan',
'scan_progress':      'Scanning...',
'scan_result':        'Added: {added}\nSkipped: {skipped}',
'cleanup_confirm':    'Delete {n} missing entries?',
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
'export_title':       'Export notes',
'export_choose_fmt':  'Choose export format:',
'export_no_data_title':'Export notes',
'export_no_data_msg': 'No notes to export.',
'export_fmt_txt':     'TXT — plain text',
'export_fmt_md':      'Markdown — with formatting',
'export_fmt_hint':    '\nTXT works in any text editor.\n'
'Markdown supports formatting and opens in Obsidian, Typora, etc.',
'export_done':        'Export complete',
'export_saved':       'Notes exported.\nBooks: {count}\nFile: {path}',
'export_error':       'Export error',
'export_error_msg':   'Failed to export notes:\n{e}',
'backup_title':       'Create backup',
'backup_contents_title': 'The archive will include:',
'backup_item_settings': 'App settings',
'backup_item_library':  'All books from the library',
'backup_item_positions':'Bookmarks, highlights, positions',
'backup_toggle_voices':'Piper voices (~/.config/NovaReader/voices/)',
'backup_toggle_fonts': 'Custom fonts (~/.config/NovaReader/fonts/)',
'backup_stats':       'Files:  <b>{n}</b>  ·  Size:  <b>~{size}</b>',
'backup_saved_stats': 'Archive saved:\n{path}\n\nFiles: {files}\nSize: {size}',
'backup_cancelled_title': 'Cancelled',
'backup_cancelled_msg':   'Backup creation was cancelled.\nThe incomplete archive was removed.',
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
'restore_invalid_title': 'Invalid archive',
'restore_invalid_msg':   'This archive does not contain NovaReader backup files.\n'
'Select a file created by the "Create backup" button.',
'ctx_open':           'Open',
'ctx_open_in':        'Open in...',
'ctx_delete_fmt':     'Delete format',
'ctx_delete':         'Delete book',
'ctx_convert':        'Convert to EPUB (fb2c)',
'ctx_convert_fb2c':   'Convert FB2 → EPUB',
'ctx_convert_fb2c_missing': 'Convert FB2 → EPUB (fb2c not found)',
'ctx_normalize':      'Normalize',
'ctx_normalize_tts':  'Normalize for TTS',
'ctx_normalize_tts_fmt': 'Normalize for TTS ({fmt})',
'ctx_edit_meta':      'Edit metadata',
'status_all':         'All books',
'status_only_new':    'Unread only',
'status_only_reading':'In progress only',
'status_hide_new':    'Hide unread',
'status_hide_reading':'Hide in progress',
'error':              'Error',
'cbr_no_extractor':   'Could not extract {name} — install unrar, bsdtar or 7z',
'empty_lib':          'Library is empty.\nAdd books using the «+» button.',
'dlg_back':           'Back',
'dlg_forward':        'Forward',
'dlg_up':             'Up one level',
'dlg_new_folder':     'New folder',
'dlg_view_list':      'List',
'dlg_view_detail':    'Details',
'dlg_save_norm':      'Save normalized book',
'dlg_filter_books':   'Books (*{ext});;All files (*.*)',
'dlg_save_notes':     'Save notes',
'dlg_filter_md':      'Markdown (*.md)',
'dlg_filter_txt':     'Text files (*.txt)',
'dlg_save_backup':    'Save backup',
'dlg_filter_zip':     'ZIP archive (*.zip);;All files (*.*)',
'dlg_open_backup':    'Select backup',
'dlg_choose_file':    'Choose file…',
'close':             'Close',
'cancel':            'Cancel',
'drop_to_add':       'Drop books here to add',
'yes':               'Yes',
'no':                'No',
'found_books':       'Found {n} books. Add them?',
'all_records_ok':    'All records are up to date.',
'restore_item_settings': 'App settings',
'restore_item_lib':      'Library list + reading positions',
'restore_item_bookmarks':'Bookmarks',
'restore_item_highlights':'Highlights',
'restore_item_notes':    'Notes',
'restore_item_books':    'Book files',
'restore_item_covers':   'Cover images',
# Новые строки для панели фильтров
'filter_sort_label':  'Sort:',
'filter_format_label':'Format:',
'filter_status_label':'Status:',
'filter_toggle_tip':  'Filters and sorting',
},
}

def _ls(config, key: str, **kwargs) -> str:
    """Получить локализованную строку библиотеки."""
    lang = config.get('language', 'ru') if config else 'ru'
    strings = _LIB_STRINGS.get(lang, _LIB_STRINGS['ru'])
    s = strings.get(key, _LIB_STRINGS['ru'].get(key, key))
    return s.format(**kwargs) if kwargs else s

# ─── Встроенные темы библиотеки ────────────────────────────────────────────────
DARK_THEME = {
    "BG":        "#1e1e2e",
    "SURFACE":   "#282838",
    "BORDER":    "#3a3a50",
    "ACCENT":    "#1a73e8",
    "TEXT":      "#e8eaed",
    "SUB":       "#9aa0a6",
    "SERIES":    "#7ecfff",
    "TOOLBAR":   "#252535",
    "PROGRESS":  "#1a73e8",
}

LIGHT_THEME = {
    "BG":        "#f5f5f5",
    "SURFACE":   "#ffffff",
    "BORDER":    "#c4c4c4",
    "ACCENT":    "#1a73e8",
    "TEXT":      "#1a1a1a",
    "SUB":       "#666666",
    "SERIES":    "#1565c0",
    "TOOLBAR":   "#e8e8e8",
    "PROGRESS":  "#1a73e8",
}

# Текущие активные цвета
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
    PROGRESS = colors.get("PROGRESS", colors["ACCENT"])

def init_lib_colors(config) -> None:
    """Загрузить цвета библиотеки из конфига и применить к глобалам."""
    name = config.get("library_theme_name", None)
    if name is None:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPalette
        bg = QApplication.palette().color(QPalette.ColorGroup.Normal,
                                         QPalette.ColorRole.Window)
        name = "light" if bg.lightness() >= 128 else "dark"
        config.set("library_theme_name", name)
    if name == "light":
        _apply_theme_to_globals(LIGHT_THEME)
    elif name == "custom":
        colors = dict(DARK_THEME)
        colors.update(config.get("library_theme_custom", {}))
        _apply_theme_to_globals(colors)
    else:
        _apply_theme_to_globals(DARK_THEME)

# ─── Styled file dialog ───────────────────────────────────────────────────────
def _make_styled_file_dialog(parent, title: str, start_dir: str,
                            filter_str: str = '',
                            multi: bool = False,
                            mode: str = 'open',
                            config=None,
                            colors: dict | None = None) -> QFileDialog:
    """Создаёт QFileDialog в стиле NovaReader (не нативный)."""
    _c = colors or {}
    _BG      = _c.get('BG', BG)
    _SURFACE = _c.get('SURFACE', SURFACE)
    _TEXT    = _c.get('TEXT', TEXT)
    _BORDER  = _c.get('BORDER', BORDER)
    _ACCENT  = _c.get('ACCENT', ACCENT)
    _SUB     = _c.get('SUB', SUB)
    _TOOLBAR = _c.get('TOOLBAR', TOOLBAR)

    dlg = QFileDialog(parent, title, start_dir, filter_str)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)

    if mode == 'save':
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setFileMode(QFileDialog.FileMode.AnyFile)
    elif mode == 'folder':
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    else:
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFileMode(
            QFileDialog.FileMode.ExistingFiles if multi
            else QFileDialog.FileMode.ExistingFile
        )

    dlg.setViewMode(QFileDialog.ViewMode.List)
    radius = "6px"

    dlg.setStyleSheet(f"""
        QFileDialog, QDialog {{
            background: {_BG};
            color: {_TEXT};
            font-size: 14px;
        }}
        QLabel {{
            color: {_TEXT};
            font-size: 13px;
        }}
        QListView, QTreeView {{
            background: {_SURFACE};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: {radius};
            outline: none;
            font-size: 13px;
        }}
        QListView::item, QTreeView::item {{
            padding: 4px 8px;
            border-radius: 4px;
        }}
        QListView::item:selected, QTreeView::item:selected {{
            background: {_ACCENT};
            color: #ffffff;
        }}
        QListView::item:hover, QTreeView::item:hover {{
            background: rgba(255,255,255,0.07);
        }}
        QHeaderView::section {{
            background: {_TOOLBAR};
            color: {_TEXT};
            border: none;
            border-bottom: 1px solid {_BORDER};
            padding: 4px 8px;
            font-size: 12px;
        }}
        QLineEdit {{
            background: {_SURFACE};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: {radius};
            padding: 5px 8px;
            font-size: 13px;
            selection-background-color: {_ACCENT};
        }}
        QLineEdit:focus {{
            border-color: {_ACCENT};
        }}
        QComboBox {{
            background: {_SURFACE};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: {radius};
            padding: 4px 8px;
            font-size: 13px;
        }}
        QComboBox:hover {{
            border-color: {_ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background: {_SURFACE};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: {radius};
            selection-background-color: {_ACCENT};
            selection-color: #ffffff;
        }}
        QPushButton {{
            background: {_SURFACE};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: {radius};
            padding: 6px 18px;
            font-size: 13px;
            min-width: 72px;
        }}
        QPushButton:hover {{
            background: rgba(255,255,255,0.08);
            border-color: {_ACCENT};
        }}
        QPushButton:pressed {{
            background: {_ACCENT};
            color: #ffffff;
            border-color: {_ACCENT};
        }}
        QPushButton[text="Open"], QPushButton[text="Открыть"] {{
            background: {_ACCENT};
            color: #ffffff;
            border-color: {_ACCENT};
        }}
        QPushButton[text="Open"]:hover, QPushButton[text="Открыть"]:hover {{
            background: {_ACCENT};
            opacity: 0.9;
        }}
        QToolBar, QToolButton {{
            background: {_TOOLBAR};
            color: {_TEXT};
            border: none;
        }}
        QToolButton:hover {{
            background: rgba(255,255,255,0.08);
            border-radius: 4px;
        }}
        QScrollBar:vertical {{
            background: {_BG};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {_BORDER};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {_ACCENT};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {_BG};
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {_BORDER};
            border-radius: 4px;
            min-width: 24px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {_ACCENT};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QFileDialog QLabel {{
            color: {_TEXT};
            font-size: 12px;
        }}
        QSplitter::handle {{
            background: {_BORDER};
            width: 1px;
        }}
    """)

    dlg.resize(780, 520)

    from PyQt6.QtCore import QUrl as _QUrl, QStorageInfo as _QSI
    import os as _os

    _sidebar_urls = dlg.sidebarUrls()
    _seen = {u.toLocalFile() for u in _sidebar_urls}

    if sys.platform == 'win32':
        for _vol in _QSI.mountedVolumes():
            _path = _vol.rootPath()
            if _vol.isValid() and _vol.isReady() and _path not in _seen:
                _sidebar_urls.append(_QUrl.fromLocalFile(_path))
                _seen.add(_path)
    else:
        for _mount_root in ('/media', '/run/media', '/mnt'):
            if not _os.path.isdir(_mount_root):
                continue
            try:
                for _user in _os.listdir(_mount_root):
                    _user_path = _os.path.join(_mount_root, _user)
                    if not _os.path.isdir(_user_path):
                        continue
                    _candidates = [_user_path]
                    try:
                        _candidates += [_os.path.join(_user_path, d)
                                       for d in _os.listdir(_user_path)]
                    except PermissionError:
                        pass
                    for _path in _candidates:
                        if (_os.path.isdir(_path)
                                and _os.path.ismount(_path)
                                and _path not in _seen):
                            _sidebar_urls.append(_QUrl.fromLocalFile(_path))
                            _seen.add(_path)
            except PermissionError:
                pass

    dlg.setSidebarUrls(_sidebar_urls)

    from PyQt6.QtWidgets import QLabel as _QLabel, QPushButton as _QPBl

    _lang = config.get('language', 'ru') if config else 'ru'
    if _lang == 'ru':
        _lbl_map = {
            'Look in:':        'Папка:',
            '&Look in:':       'Папка:',
            'File name:':      'Имя файла:',
            '&File name:':     'Имя файла:',
            'Files of type:':  'Тип файлов:',
            '&Files of type:': 'Тип файлов:',
            'Directory:':      'Папка:',
            '&Directory:':     'Папка:',
        }
        _btn_map = {
            'Open':    'Открыть',
            '&Open':   'Открыть',
            'Choose':  'Выбрать',
            '&Choose': 'Выбрать',
            'Save':    'Сохранить',
            '&Save':   'Сохранить',
            'Cancel':  'Отмена',
            '&Cancel': 'Отмена',
        }
    else:
        _lbl_map = {}
        _btn_map = {}

    for lbl in dlg.findChildren(_QLabel):
        raw = lbl.text()
        for key in (raw.rstrip(), raw.strip(), raw.replace('&', '').rstrip()):
            if key in _lbl_map:
                lbl.setText(_lbl_map[key])
                break

    def _retranslate_buttons():
        for btn in dlg.findChildren(_QPBl):
            raw = btn.text()
            for key in (raw, raw.strip(), raw.replace('&', '').strip()):
                if key in _btn_map:
                    btn.setText(_btn_map[key])
                    break

    _retranslate_buttons()
    dlg.show()
    _retranslate_buttons()

    from PyQt6.QtGui import QFontDatabase, QFont
    _has_mi = 'Material Icons' in QFontDatabase.families()
    if _has_mi:
        from PyQt6.QtWidgets import QToolButton
        from PyQt6.QtGui import QIcon
        _BTN_SZ   = 36
        _FONT_SZ  = _BTN_SZ // 2
        _mi_font  = QFont('Material Icons', _FONT_SZ)
        _cfg = config
        _MI_MAP = {
            'backButton':       ('arrow_back',          _ls(_cfg,'dlg_back')),
            'forwardButton':    ('arrow_forward',        _ls(_cfg,'dlg_forward')),
            'toParentButton':   ('arrow_upward',         _ls(_cfg,'dlg_up')),
            'newFolderButton':  ('create_new_folder',    _ls(_cfg,'dlg_new_folder')),
            'listModeButton':   ('view_list',            _ls(_cfg,'dlg_view_list')),
            'detailModeButton': ('view_module',          _ls(_cfg,'dlg_view_detail')),
        }
        _btn_style = (
            f"QToolButton{{"
            f"background:transparent;border:none;"
            f"border-radius:{_BTN_SZ // 2}px;color:{_SUB};"
            f"font-family:'Material Icons';font-size:{_FONT_SZ}px;}}"
            f"QToolButton:hover{{background:rgba(255,255,255,.08);color:{_TEXT};}}"
            f"QToolButton:pressed{{background:rgba(255,255,255,.15);}}"
        )
        for btn in dlg.findChildren(QToolButton):
            name = btn.objectName()
            if name not in _MI_MAP:
                continue
            ligature, tip = _MI_MAP[name]
            btn.setIcon(QIcon())
            btn.setText(ligature)
            btn.setFont(_mi_font)
            btn.setFixedSize(_BTN_SZ, _BTN_SZ)
            btn.setToolTip(tip)
            btn.setStyleSheet(_btn_style)

    from PyQt6.QtWidgets import QPushButton as _QPB
    from PyQt6.QtGui import QIcon as _QIcon
    for btn in dlg.findChildren(_QPB):
        btn.setIcon(_QIcon())

    return dlg

def _styled_get_open_filenames(parent, title, start_dir, filter_str, config=None, colors=None) -> tuple:
    dlg = _make_styled_file_dialog(parent, title, start_dir, filter_str, multi=True, mode='open', config=config, colors=colors)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        return dlg.selectedFiles(), dlg.selectedNameFilter()
    return [], ''

def _styled_get_open_filename(parent, title, start_dir, filter_str, config=None, colors=None) -> tuple:
    dlg = _make_styled_file_dialog(parent, title, start_dir, filter_str, multi=False, mode='open', config=config, colors=colors)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ''), dlg.selectedNameFilter()
    return '', ''

def _styled_get_save_filename(parent, title, start_dir, filter_str,
                             default_name: str = '', config=None, colors=None) -> tuple:
    path = str(Path(start_dir) / default_name) if default_name else start_dir
    dlg = _make_styled_file_dialog(parent, title, path, filter_str, mode='save', config=config, colors=colors)
    if default_name:
        dlg.selectFile(default_name)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ''), dlg.selectedNameFilter()
    return '', ''

def _styled_get_existing_directory(parent, title, start_dir, config=None, colors=None) -> str:
    dlg = _make_styled_file_dialog(parent, title, start_dir, mode='folder', config=config, colors=colors)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ''
    return ''

def _apply_msgbox_style(mb):
    from PyQt6.QtWidgets import QPushButton as _P
    from PyQt6.QtGui import QIcon as _I
    for btn in mb.findChildren(_P):
        btn.setIcon(_I())
    mb.setStyleSheet(f"""
        QMessageBox {{
            background: {BG};
            color: {TEXT};
        }}
        QLabel {{
            color: {TEXT};
            font-size: 14px;
        }}
        QPushButton {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 6px 16px;
            font-size: 13px;
            min-width: 0px;
        }}
        QPushButton:hover {{
            border-color: {ACCENT};
            background: rgba(255,255,255,0.08);
        }}
        QPushButton:pressed {{
            background: {ACCENT};
            color: #ffffff;
            border-color: {ACCENT};
        }}
        QPushButton:default {{
            border-color: {ACCENT};
        }}
    """)

def _styled_question(parent, title: str, text: str, config=None) -> bool:
    from PyQt6.QtWidgets import QMessageBox as _QMB
    mb = _QMB(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    mb.setStandardButtons(_QMB.StandardButton.Yes | _QMB.StandardButton.No)
    mb.setDefaultButton(_QMB.StandardButton.No)
    yes_text = _ls(config, 'yes') if config else 'Yes'
    no_text  = _ls(config, 'no')  if config else 'No'
    from PyQt6.QtGui import QIcon as _QIcon
    mb.button(_QMB.StandardButton.Yes).setText(yes_text)
    mb.button(_QMB.StandardButton.No).setText(no_text)
    _apply_msgbox_style(mb)
    return mb.exec() == _QMB.StandardButton.Yes

# ─── Кнопки тулбара ───────────────────────────────────────────────────────────
_ICON_FALLBACK = {
    'add':          '+',
    'folder_open':  '📁',
    'delete_sweep': '🗑',
    'refresh':      '↻',
    'search':       '',
    'settings':     '⚙',
    'backup':       '💾',
    'restore':      '📂',
    'link':         '🔗',
    'restore_url':  '🔗',
    'content_copy': '📋',
    'filter_list':  '≡',
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

# ─── Глобальный стиль приложения ──────────────────────────────────────────────
def apply_global_app_style(app) -> None:
    """Единая точка управления внешним видом всего приложения NovaReader."""
    from PyQt6.QtWidgets import QStyleFactory
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setStyleSheet(f"""
        QWidget {{ font-family: 'Segoe UI', Arial, sans-serif; background: {BG}; color: {TEXT}; }}
        QScrollArea {{ border: none; background: {BG}; }}
        QScrollBar:vertical {{ border: none;  background: {SURFACE}; width: 8px; border-radius: 4px; }}
        QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 20px; }}
        QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
        QLineEdit {{
            padding: 6px 10px; border: 1px solid {BORDER}; border-radius: 8px;
            font-size: 13px; background: {SURFACE}; color: {TEXT};
        }}
        QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        QPushButton {{
            padding: 8px 20px; background: {ACCENT}; color: white;
            border: none; border-radius: 8px; font-weight: bold;
        }}
        QPushButton:hover {{ background: #1557b0; }}
        QPushButton:disabled {{ background: {BORDER}; color: {SUB}; }}
        QLabel {{ background: transparent; color: {TEXT}; }}
        QToolButton {{ background: transparent; border: none; }}
        QToolButton:hover {{ background: {BORDER}; border-radius: 4px; }}
        QListView, QTreeView {{
            background: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER}; border-radius: 6px;
            selection-background-color: {ACCENT}; selection-color: white;
        }}
        QListView::item, QTreeView::item {{ background: transparent; color: {TEXT}; }}
        QListView::item:selected, QTreeView::item:selected {{ background: {ACCENT}; color: white; }}
        QHeaderView::section {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; }}
        {_combo_style()}
    """)

def _combo_style():
    """Единый стиль для QComboBox — плоский, без системных стрелок."""
    return (
        f"QComboBox{{ "
        f"background:{BG};color:{TEXT}; "
        f"border:1px solid {BORDER};border-radius:17px; "
        f"padding:0 36px 0 14px;font-size:13px;}} "
        f"QComboBox::drop-down{{ "
        f"subcontrol-origin:padding;subcontrol-position:right center; "
        f"width:28px;border:none;border-radius:0 17px 17px 0;}} "
        f"QComboBox::down-arrow{{ "
        f"image:none; "
        f"border-left:4px solid transparent; "
        f"border-right:4px solid transparent; "
        f"border-top:5px solid {SUB}; "
        f"margin-right:8px;}} "
        f"QComboBox:hover::down-arrow{{border-top-color:{TEXT};}} "
        f"QComboBox:focus{{border-color:{ACCENT};}} "
        f"QComboBox:on::down-arrow{{ "
        f"border-top:none; "
        f"border-bottom:5px solid {ACCENT}; "
        f"border-left:4px solid transparent; "
        f"border-right:4px solid transparent;}} "
        f"QComboBox QAbstractItemView{{ "
        f"background:{BG};color:{TEXT}; "
        f"border:1px solid {BORDER};border-radius:8px; "
        f"selection-background-color:{ACCENT}; "
        f"selection-color:white; "
        f"padding:4px;outline:none;}} "
    )

def _autosize_combo(combo: QComboBox, min_w: int = 0) -> None:
    """Адаптивная ширина по САМОМУ ДЛИННОМУ пункту."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    f = QFont('Segoe UI')
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setPixelSize(13)
    fm = QFontMetrics(f)
    text_w = max((fm.horizontalAdvance(combo.itemText(i))
                 for i in range(combo.count())), default=0)
    combo.setMinimumWidth(max(min_w, text_w + 14 + 36 + 12))

# ─── Фильтр по статусу ───────────────────────────────────────────────────────
class StatusFilter(QObject):
    """Фильтр книг по статусу чтения."""
    filter_changed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._widget = None
        self._combo = None
        self._create_widget()

    def _create_widget(self):
        self._widget = QWidget()
        self._widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._combo = QComboBox()
        self._combo.addItems(self._status_labels())
        self._combo.setStyleSheet(_combo_style())
        _autosize_combo(self._combo)
        self._combo.setFixedHeight(34)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)

    def _status_labels(self):
        return [
            _ls(self.config, 'status_all'),
            _ls(self.config, 'status_only_new'),
            _ls(self.config, 'status_only_reading'),
            _ls(self.config, 'status_hide_new'),
            _ls(self.config, 'status_hide_reading'),
        ]

    def retranslate(self):
        """Перестраивает пункты под текущий язык, сохраняя выбор."""
        cur = self._combo.currentIndex()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(self._status_labels())
        self._combo.setCurrentIndex(cur)
        self._combo.blockSignals(False)
        _autosize_combo(self._combo)

    def _on_combo_changed(self, index):
        self.filter_changed.emit()

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def combo(self) -> QComboBox:
        return self._combo

    def get_current_index(self) -> int:
        return self._combo.currentIndex() if self._combo else 0

    def set_current_index(self, index: int):
        if self._combo:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(index)
            self._combo.blockSignals(False)

    def apply(self, books: list) -> list:
        idx = self.get_current_index()
        if idx == 0:
            return books
        elif idx == 1:
            return [b for b in books if not b.get('progress') or b.get('progress', 0) == 0]
        elif idx == 2:
            return [b for b in books if b.get('progress') and 0 < b.get('progress', 0) < 0.95]
        elif idx == 3:
            return [b for b in books if b.get('progress') and b.get('progress', 0) > 0]
        elif idx == 4:
            return [b for b in books if not b.get('progress') or b.get('progress', 0) == 0 or b.get('progress', 0) >= 0.95]
        return books

    def reset(self):
        self.set_current_index(0)

# ─── Обложка ─────────────────────────────────────────────────────────────────
class _CoverLabel(QLabel):
    """Лейбл обложки: хранит исходный pixmap и масштабирует его ВПИСЫВАНИЕМ."""
    def __init__(self):
        super().__init__()
        self._src = None

    def set_source_pixmap(self, px):
        self._src = px
        self._rescale()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()

    def _rescale(self):
        if self._src is None:
            return
        w = max(10, self.width())
        h = max(10, self.height())
        QLabel.setPixmap(self, self._src.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

# ─── Карточка книги ───────────────────────────────────────────────────────────
class BookCard(QFrame):
    clicked    = pyqtSignal(object)
    delete_req = pyqtSignal(object)

    def __init__(self, book_info, config=None):
        super().__init__()
        self.book_info = book_info
        self.config = config
        self._cover_pixmap = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_W, CARD_H)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._paint(False)
        self._build()

    def update_progress(self, new_book_info):
        """Точечное обновление ОДНОЙ карточки (прогресс/статус чтения)."""
        old_cover_path = self.book_info.get("cover_path")
        new_cover_path = new_book_info.get("cover_path")
        if old_cover_path != new_cover_path:
            self._cover_pixmap = None
        self.book_info = new_book_info
        old_layout = self.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            QWidget().setLayout(old_layout)
        self._build()

    def _paint(self, hov):
        c, w = (ACCENT, 2) if hov else (BORDER, 1)
        self.setStyleSheet(
            f"BookCard{{background:{SURFACE};border-radius:10px;border:{w}px solid {c};}}")

    def enterEvent(self, e):  self._paint(True);  super().enterEvent(e)
    def leaveEvent(self, e):  self._paint(False); super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
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

        book_path = Path(self.book_info.get("file_path", ""))
        book_dir = book_path.parent if book_path.exists() else None

        if book_dir and book_dir.exists():
            book_formats = {}
            for f in book_dir.iterdir():
                if f.suffix.lower() in ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']:
                    fmt = f.suffix.lower().lstrip('.')
                    book_formats[fmt] = f

            if len(book_formats) > 1:
                open_menu = menu.addMenu(f" {_ls(self.config, 'ctx_open_in')}")
                priority = ['epub', 'fb2', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr']
                for fmt in priority:
                    if fmt in book_formats:
                        fpath = book_formats[fmt]
                        mark = '✓' if fmt == 'epub' else ''
                        act = QAction(f"{mark}{fmt.upper()} — {fpath.name}", self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._open_book_format(fp))
                        open_menu.addAction(act)

                menu.addSeparator()
                norm_formats = {fmt: fp for fmt, fp in book_formats.items()
                               if ('.' + fmt) in NORMALIZER_SUPPORTED}
                if norm_formats:
                    if len(norm_formats) == 1:
                        fmt, fpath = next(iter(norm_formats.items()))
                        act = QAction(_ls(self.config, 'ctx_normalize_tts_fmt', fmt=fmt.upper()), self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                        menu.addAction(act)
                    else:
                        norm_menu = menu.addMenu(_ls(self.config, 'ctx_normalize_tts'))
                        for fmt, fpath in norm_formats.items():
                            act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                            act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                            norm_menu.addAction(act)

                menu.addSeparator()
                if 'fb2' in book_formats:
                    fb2_path = str(book_formats['fb2'])
                    if _find_fb2c():
                        act = QAction(_ls(self.config, 'ctx_convert_fb2c'), self)
                        act.triggered.connect(lambda checked, fp=fb2_path: self._convert_book(fp))
                    else:
                        act = QAction(_ls(self.config, 'ctx_convert_fb2c_missing'), self)
                        act.setEnabled(False)
                    menu.addAction(act)

                menu.addSeparator()
                delete_menu = menu.addMenu(f" {_ls(self.config, 'ctx_delete_fmt')}")
                for fmt, fpath in sorted(book_formats.items()):
                    act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                    act.triggered.connect(lambda checked, fp=str(fpath), fm=fmt: self._delete_format(fp, fm))
                    delete_menu.addAction(act)
            else:
                src_path = str(book_path)
                ext = book_path.suffix.lower()
                if ext in NORMALIZER_SUPPORTED:
                    act = QAction(_ls(self.config, 'ctx_normalize_tts'), self)
                    act.triggered.connect(lambda checked, fp=src_path: self._normalize_book(fp))
                    menu.addAction(act)
                if ext == '.fb2':
                    if _find_fb2c():
                        act = QAction(_ls(self.config, 'ctx_convert_fb2c'), self)
                        act.triggered.connect(lambda checked, fp=src_path: self._convert_book(fp))
                    else:
                        act = QAction(_ls(self.config, 'ctx_convert_fb2c_missing'), self)
                        act.setEnabled(False)
                    menu.addAction(act)
                menu.addSeparator()
                act = QAction(f" {_ls(self.config, 'ctx_delete')}", self)
                act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
                menu.addAction(act)
        else:
            act = QAction(f" {_ls(self.config, 'ctx_delete')}", self)
            act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
            menu.addAction(act)

        menu.exec(self.mapToGlobal(pos))

    def _open_book_format(self, file_path):
        """Открыть книгу в указанном формате."""
        self.clicked.emit({**self.book_info, "file_path": str(file_path)})

    def _delete_format(self, file_path, format_name):
        """Удалить конкретный формат книги."""
        title = self.book_info.get("title", "Книга")[:40]
        if not _styled_question(
                self,
                _ls(self.config, 'delete_fmt_title', fmt=format_name.upper()),
                _ls(self.config, 'delete_fmt_msg',
                   title=title, fmt=format_name.upper()),
                config=self.config):
            return

        try:
            fp = Path(file_path)
            self.config.remove_format(str(fp))
            if fp.exists():
                fp.unlink()
                print(f"[Library] Удалён формат {format_name}: {fp.name}")

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
            _qmb = QMessageBox(QMessageBox.Icon.Warning, "Ошибка",
                             f"Не удалось удалить файл:\n{e}",
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()

        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_on_library_updated'):
                parent._on_library_updated()
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None

    def _normalize_book(self, file_path: str):
        """Нормализовать книгу для корректной работы TTS."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout
        src = Path(file_path)
        ext = src.suffix.lower()
        default_name = src.stem + '_fixed' + ext
        dst_str, _ = _styled_get_save_filename(
            self,
            _ls(self.config, 'dlg_save_norm'),
            str(src.parent),
            _ls(self.config, 'dlg_filter_books', ext=ext),
            default_name=default_name,
            config=self.config
        )
        if not dst_str:
            return
        dst = Path(dst_str)

        dlg = QDialog(self)
        dlg.setWindowTitle("Нормализация книги")
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
        open_btn  = QPushButton("Открыть папку")
        open_btn.setEnabled(False)
        open_btn.setStyleSheet(f"background:#2d5a27;color:white;border:none;"
                              f"padding:8px 20px;border-radius:6px;font-size:13px;")
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        close_btn.clicked.connect(dlg.accept)

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
                log_box.append(f"✓ Готово! Файл сохранён: {dst}")
                open_btn.setEnabled(True)
                open_btn.clicked.connect(lambda: __import__('subprocess').Popen(
                    ['xdg-open' if __import__('sys').platform != 'win32' else 'explorer',
                     str(dst.parent)]))
            else:
                log_box.append("")
                log_box.append("✗ Нормализация завершилась с ошибкой")

        worker.log_line.connect(on_log)
        worker.done.connect(on_done)
        worker.start()
        dlg.exec()

    def _convert_book(self, file_path: str):
        """Конвертировать FB2 → EPUB через fb2c."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QLabel, QPushButton, QTextEdit, QFrame)
        from PyQt6.QtCore import QThread
        from PyQt6.QtCore import pyqtSignal as _Signal

        src = Path(file_path)
        if not src.exists():
            return

        has_position = False
        if self.config:
            src_norm = self.config._normalize_path(str(src))
            for book in self.config.get_books():
                if self.config._normalize_path(book.get("file_path", "")) == src_norm:
                    pos = book.get("position")
                    prog = book.get("progress", 0)
                    if pos or prog:
                        has_position = True
                    break

        if has_position:
            warn = QMessageBox(self)
            warn.setWindowTitle("Позиция чтения будет сброшена")
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
            _apply_msgbox_style(warn)
            warn.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if warn.exec() != QMessageBox.StandardButton.Ok:
                return

        dst_dir = src.parent
        lib_win_parent = self.parent()
        while lib_win_parent and not hasattr(lib_win_parent, '_on_library_updated'):
            lib_win_parent = (lib_win_parent.parent()
                             if hasattr(lib_win_parent, 'parent') else None)
        dlg_parent = lib_win_parent or self

        dlg = QDialog(dlg_parent)
        dlg.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint)
        dlg.setWindowTitle("Конвертация FB2 → EPUB")
        dlg.setMinimumSize(500, 340)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};color:{TEXT};"
            f"font-family:'Segoe UI','SF Pro Text','Helvetica Neue',sans-serif;}}"
            f"QLabel{{color:{TEXT};background:transparent;}}"
            f"QTextEdit{{background:{SURFACE};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;"
            f"font-family:monospace;font-size:12px;padding:6px;}}"
            f"QPushButton{{background:{SURFACE};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            f"padding:7px 18px;font-size:13px;min-width:80px;}}"
            f"QPushButton:hover{{border-color:{ACCENT};background:{BG};}}"
            f"QPushButton:pressed{{background:{BG};}}"
            f"QPushButton#accent{{background:{ACCENT};color:white;"
            f"border:none;font-weight:600;}}"
            f"QPushButton#accent:hover{{background:{ACCENT}dd;}}"
            f"QPushButton#danger{{background:transparent;color:#e57373;"
            f"border:1px solid #e57373;}}"
            f"QPushButton#danger:hover{{background:rgba(229,115,115,0.1);}}"
            f"QPushButton#success{{background:transparent;color:#81c784;"
            f"border:1px solid #81c784;}}"
            f"QPushButton#success:hover{{background:rgba(129,199,132,0.1);}}"
            f"QPushButton#info{{background:transparent;color:{ACCENT};"
            f"border:1px solid {ACCENT};}}"
            f"QPushButton#info:hover{{background:rgba(26,115,232,0.1);}}"
            f"QPushButton:disabled{{color:{SUB};border-color:{BORDER};"
            f"background:transparent;}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)

        title_lbl = QLabel(f"<b>{src.name}</b>  →  EPUB")
        title_lbl.setStyleSheet(f"font-size:14px;color:{TEXT};")
        lay.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{BORDER};max-height:1px;")
        lay.addWidget(sep)

        log_box = QTextEdit()
        log_box.setReadOnly(True)
        lay.addWidget(log_box)

        stop_flag = [False]
        result_path: list[Path | None] = [None]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        stop_btn  = QPushButton("Отмена")
        stop_btn.setObjectName("danger")
        close_btn = QPushButton("Закрыть")
        close_btn.setEnabled(False)
        close_btn.setObjectName("accent")
        open_btn  = QPushButton("Открыть папку")
        open_btn.setEnabled(False)
        open_btn.setObjectName("success")
        open_book_btn = QPushButton("Открыть книгу")
        open_book_btn.setEnabled(False)
        open_book_btn.setObjectName("info")
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
                if msg.strip().startswith('→'):
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                    if '→' in cursor.selectedText():
                        cursor.removeSelectedText()
                        cursor.deletePreviousChar()
                log_box.append(msg)

        _log_timer = QTimer()
        _log_timer.setInterval(200)
        _log_timer.timeout.connect(_flush_log)
        _log_timer.start()

        class _Worker(QThread):
            log_line = _Signal(str)
            done     = _Signal(object)
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
                if self.config:
                    epub_path = str(result)
                    fb2_path  = str(src)
                    meta = dict(self.book_info)
                    meta['file_path'] = epub_path
                    meta['format']    = 'epub'
                    self.config.add_book(meta)
                    log_box.append("   EPUB добавлен в библиотеку как второй формат")
                    for raw_path in (epub_path, fb2_path):
                        norm_path = self.config._normalize_path(raw_path)
                        if norm_path in self.config._positions:
                            self.config._positions[norm_path]['position'] = None
                            self.config._positions[norm_path]['progress'] = 0
                    self.config.save_positions()
                    log_box.append("   Позиция сброшена — EPUB откроется с начала")
                    if lib_win_parent:
                        dlg.finished.connect(
                            lambda _: lib_win_parent._on_library_updated())
            else:
                log_box.append("\n✗ Конвертация не удалась")

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
        cov.setFixedWidth(CARD_W - 16)
        cov.setMinimumHeight(140)
        cov.setMaximumHeight(190)
        cov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cov.setStyleSheet(
            f"background:{BG};border-radius:6px;color:{SUB};font-size:38px;")
        cp = self.book_info.get("cover_path")
        if self._cover_pixmap is not None:
            cov.setPixmap(self._cover_pixmap)
        elif cp and Path(cp).exists():
            px = QPixmap(cp)
            if not px.isNull():
                px = self._compose_cover(px, CARD_W - 16, 190)
                self._cover_pixmap = px
                cov.setPixmap(px)
            else:
                cov.setText("")
        else:
            cov.setText("📖")
        lay.addWidget(cov)

        tl = QLabel(self.book_info.get("title", "Без названия"))
        tl.setWordWrap(True); tl.setMaximumHeight(36)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setStyleSheet(f"color:{TEXT};font-size:10px;font-weight:bold;")
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
        last_read_str = self.book_info.get("last_read")
        last_read_fmt = None
        if last_read_str:
            try:
                dt = datetime.fromisoformat(last_read_str)
                last_read_fmt = dt.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                last_read_fmt = None

        if p and p > 0:
            sr_w = QWidget(); sr_w.setStyleSheet("background:transparent;")
            sr = QHBoxLayout(sr_w)
            sr.setContentsMargins(4, 0, 4, 2)
            sr.setSpacing(4)
            if p >= 0.95:
                st = QLabel("Прочитано")
                st.setStyleSheet(
                    "color:#1b5e20;font-size:9px;font-weight:bold;"
                    "background:#a5d6a7;border-radius:3px;padding:1px 5px;")
            else:
                st = QLabel("Читаю")
                st.setStyleSheet(
                    "color:#bf360c;font-size:9px;font-weight:bold;"
                    "background:#ffcc80;border-radius:3px;padding:1px 5px;")
            sr.addWidget(st)
            sr.addStretch()
            pct = QLabel(f"{int(round(p * 100))}%")
            pct.setStyleSheet(f"color:{TEXT};font-size:10px;font-weight:bold;background:transparent;")
            sr.addWidget(pct)
            lay.addWidget(sr_w)

        if last_read_fmt:
            dl = QLabel(f"Открыта: {last_read_fmt}")
            dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dl.setWordWrap(False)
            dl.setStyleSheet(f"color:{TEXT};font-size:10px;font-weight:600;background:transparent;")
            lay.addWidget(dl)

        if p and p > 0:
            bg = QFrame(); bg.setFixedHeight(3)
            bg.setStyleSheet(f"background:{BORDER};border-radius:2px;")
            fill = QFrame(bg); fill.setFixedHeight(3)
            fill.setFixedWidth(max(4, int((CARD_W - 16) * min(p, 1.0))))
            fill.setStyleSheet(f"background:{PROGRESS};border-radius:2px;")
            lay.addWidget(bg)

    def _compose_cover(self, src: QPixmap, w: int, h: int) -> QPixmap:
        """Итоговая картинка обложки: сама обложка ПОЛНОСТЬЮ (без кропа)
        по центру, а вместо пустых боковых/верхних полос — та же обложка,
        растянутая на всю область и размытая, слегка затемнённая."""
        fg = src.scaled(w, h,
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        if fg.width() == w and fg.height() == h:
            return fg
        bg = src.scaled(w, h,
                       Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        bg = bg.scaledToWidth(max(8, w // 8),
                             Qt.TransformationMode.SmoothTransformation)
        bg = bg.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
        canvas = QPixmap(w, h)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap(0, 0, bg)
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 90))
        p.drawPixmap((w - fg.width()) // 2, (h - fg.height()) // 2, fg)
        p.end()
        return canvas

# ══════════════════════════════════════════════════════════════════════════
# ГЛАВНОЕ ОКНО БИБЛИОТЕКИ
# ══════════════════════════════════════════════════════════════════════════
class LibraryWindow(QMainWindow):
    book_selected = pyqtSignal(str)

    @staticmethod
    def _norm_path(p) -> str:
        """Нормализация пути к единому формату (прямые слеши)."""
        s = str(p).replace('\\', '/')
        if sys.platform == 'win32':
            s = s.lower()
        return s

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.settings_window = None
        init_lib_colors(config)
        self.parser = BookParser()
        self.zip_handler = ZipHandler()
        self._all_books = []
        self._cards_by_path = {}
        self.setStyleSheet(f"QMainWindow{{background:{BG};}}")
        self.setWindowTitle("NovaReader")
        _LIB_DEF_W, _LIB_DEF_H = 1214, 700
        _LIB_MIN_W, _LIB_MIN_H = 1181, 640
        scr = QApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else None
        w = int(config.get("library_width", _LIB_DEF_W))
        h = int(config.get("library_height", _LIB_DEF_H))
        if avail:
            w = min(w, avail.width())
            h = min(h, avail.height())
        self.setMinimumSize(_LIB_MIN_W, _LIB_MIN_H)
        self.resize(max(w, _LIB_MIN_W), max(h, _LIB_MIN_H))
        self._setup_ui()
        self._load_books()

    def retranslate_ui(self, _code=None):
        """Обновляет все переводимые тексты БЕЗ пересоздания окна."""
        self.add_btn.setToolTip(_ls(self.config, 'add_books'))
        self.scan_btn.setToolTip(_ls(self.config, 'scan_folder'))
        self.cleanup_btn.setToolTip(_ls(self.config, 'cleanup'))
        self.export_btn.setToolTip(_ls(self.config, 'export_notes'))
        self.refresh_btn.setToolTip(_ls(self.config, 'refresh'))
        self.backup_btn.setToolTip(_ls(self.config, 'backup'))
        self.restore_btn.setToolTip(_ls(self.config, 'restore'))
        self.restore_url_btn.setToolTip(_ls(self.config, 'restore_url'))
        self.search_btn.setToolTip(_ls(self.config, 'online_search'))
        self.settings_btn.setToolTip(_ls(self.config, 'settings'))
        # Tooltip кнопки фильтров
        if hasattr(self, '_filter_toggle_btn'):
            self._filter_toggle_btn.setToolTip(_ls(self.config, 'filter_toggle_tip'))
        self.search_box.setPlaceholderText(_ls(self.config, 'search_placeholder'))
        # Обновляем комбобоксы в панели фильтров
        if hasattr(self, 'sort_combo') and self.sort_combo is not None:
            cur = self.sort_combo.currentIndex()
            self.sort_combo.blockSignals(True)
            self.sort_combo.clear()
            self.sort_combo.addItems([
                _ls(self.config, 'sort_last_read'),
                _ls(self.config, 'sort_date_added'),
                _ls(self.config, 'sort_title'),
                _ls(self.config, 'sort_author'),
            ])
            self.sort_combo.setCurrentIndex(cur)
            self.sort_combo.blockSignals(False)
            _autosize_combo(self.sort_combo)
        if hasattr(self, 'format_filter') and self.format_filter is not None:
            cur = self.format_filter.currentIndex()
            self.format_filter.blockSignals(True)
            self.format_filter.clear()
            self.format_filter.addItems([
                _ls(self.config, 'filter_all'),
                "EPUB", "FB2", "PDF", "MOBI", "CBZ",
                _ls(self.config, 'filter_comics'),
            ])
            self.format_filter.setCurrentIndex(cur)
            self.format_filter.blockSignals(False)
            _autosize_combo(self.format_filter)
        if hasattr(self, 'status_filter') and self.status_filter is not None:
            self.status_filter.retranslate()
        self._load_books()

    def _update_status_bar(self):
        """Пересчитывает текст статус-бара (счётчик книг) под текущий язык."""
        if hasattr(self, 'status_label'):
            n = len(self._all_books) if hasattr(self, '_all_books') else 0
            self.status_label.setText(_ls(self.config, 'books_count', n=n))

    def _setup_ui(self):
        self._central_widget = QWidget()
        self._central_widget.setStyleSheet(f"background:{BG};")
        self.setCentralWidget(self._central_widget)
        root = QVBoxLayout(self._central_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Тулбар (без комбобоксов — только кнопки + поиск + кнопка фильтров)
        root.addWidget(self._make_toolbar())
        # Панель фильтров (скрыта по умолчанию, создаётся после тулбара)
        self._filter_panel = self._build_filter_panel()
        self._filter_panel.setVisible(False)
        root.addWidget(self._filter_panel)
        self.setAcceptDrops(True)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        # ИСПРАВЛЕНИЕ: выравнивание по левому краю
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
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(4)
        self.add_btn      = _mbtn("add",          _ls(self.config, 'add_books'))
        self.scan_btn     = _mbtn("folder_open",  _ls(self.config, 'scan_folder'))
        self.cleanup_btn  = _mbtn("delete_sweep", _ls(self.config, 'cleanup'))
        self.export_btn   = _mbtn("content_copy", _ls(self.config, 'export_notes'))
        self.refresh_btn  = _mbtn("refresh",      _ls(self.config, 'refresh'))
        self.backup_btn   = _mbtn("backup",       _ls(self.config, 'backup'))
        self.restore_btn     = _mbtn("restore",     _ls(self.config, 'restore'))
        self.restore_url_btn = _mbtn("link",        _ls(self.config, 'restore_url'))
        self.search_btn      = _mbtn("search",      _ls(self.config, 'online_search'))
        self.settings_btn    = _mbtn("settings",    _ls(self.config, 'settings'))
        self.add_btn.clicked.connect(self.add_books)
        self.scan_btn.clicked.connect(self.scan_folder)
        self.cleanup_btn.clicked.connect(self.cleanup_library)
        self.export_btn.clicked.connect(self.export_notes)
        self.refresh_btn.clicked.connect(self._load_books)
        self.backup_btn.clicked.connect(self.backup_config)
        self.restore_btn.clicked.connect(self.restore_config)
        self.restore_url_btn.clicked.connect(self.restore_from_url)
        self.search_btn.clicked.connect(self.open_online_search)
        self.settings_btn.clicked.connect(self.open_settings)
        self._toolbar_seps = []
        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setFixedHeight(24)
            s.setStyleSheet(f"color:{BORDER};")
            self._toolbar_seps.append(s)
            return s
        for btn in (self.add_btn, self.scan_btn, self.cleanup_btn, self.export_btn):
            lay.addWidget(btn)
        lay.addWidget(_sep())
        lay.addWidget(self.backup_btn)
        lay.addWidget(self.restore_btn)
        lay.addWidget(self.restore_url_btn)
        lay.addWidget(_sep())
        self.search_btn.setVisible(self.config.get('online_search_enabled', False))
        lay.addWidget(self.search_btn)
        lay.addWidget(_sep())
        lay.addWidget(self.settings_btn)
        lay.addStretch()
        # Поле поиска
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(_ls(self.config, 'search_placeholder'))
        self.search_box.setFixedHeight(34)
        self.search_box.setMinimumWidth(140)
        self.search_box.setMaximumWidth(320)
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        self.search_box.setStyleSheet(
            f"QLineEdit{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QLineEdit:focus{{border:1px solid {ACCENT};}}")
        self.search_box.textChanged.connect(self._on_search)
        lay.addWidget(self.search_box)
        # Кнопка-гамбургер для открытия панели фильтров (вместо трёх комбобоксов)
        self._filter_toggle_btn = _mbtn("filter_list",
                                       _ls(self.config, 'filter_toggle_tip'),
                                       sz=36)
        self._filter_toggle_btn.setCheckable(True)
        self._filter_toggle_btn.clicked.connect(self._toggle_filter_panel)
        lay.addWidget(self._filter_toggle_btn)
        # Комбобоксы создаются отдельно в _build_filter_panel (см. ниже)
        # Здесь только создаём объекты, но не добавляем в тулбар
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            _ls(self.config, 'sort_last_read'),
            _ls(self.config, 'sort_date_added'),
            _ls(self.config, 'sort_title'),
            _ls(self.config, 'sort_author'),
        ])
        self.sort_combo.setStyleSheet(_combo_style())
        _autosize_combo(self.sort_combo)
        self.sort_combo.setFixedHeight(34)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.format_filter = QComboBox()
        self.format_filter.addItems([
            _ls(self.config, 'filter_all'),
            "EPUB", "FB2", "PDF", "MOBI", "CBZ",
            _ls(self.config, 'filter_comics'),
        ])
        self.format_filter.setStyleSheet(_combo_style())
        _autosize_combo(self.format_filter)
        self.format_filter.setFixedHeight(34)
        self.format_filter.currentTextChanged.connect(self._on_filter_changed)
        self.status_filter = StatusFilter(self.config)
        self.status_filter.filter_changed.connect(self._on_filter_changed)
        return self._toolbar_bar

    def _build_filter_panel(self):
        """Создаёт панель фильтров под тулбаром.
        Расположение комбобоксов зависит от FILTER_PANEL_MODE:
          'horizontal' — в ряд (компактно)
          'vertical'   — в столбик с подписями (удобнее на узких окнах)
        """
        panel = QWidget()
        panel.setObjectName("FilterPanel")
        panel.setStyleSheet(f"""
            QWidget#FilterPanel {{
                background: {SURFACE};
                border-top: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
            }}
            QLabel {{
                color: {TEXT};
                font-size: 12px;
                background: transparent;
                min-width: 70px;
            }}
        """)
        if FILTER_PANEL_MODE == 'vertical':
            # Вертикальный режим: каждый комбобокс с подписью в отдельной строке
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 6, 16, 6)
            layout.setSpacing(4)
            # Сортировка
            row1 = QHBoxLayout()
            row1.setContentsMargins(0, 0, 0, 0)
            lbl1 = QLabel(_ls(self.config, 'filter_sort_label'))
            row1.addWidget(lbl1)
            row1.addWidget(self.sort_combo)
            row1.addStretch()
            layout.addLayout(row1)
            # Формат
            row2 = QHBoxLayout()
            row2.setContentsMargins(0, 0, 0, 0)
            lbl2 = QLabel(_ls(self.config, 'filter_format_label'))
            row2.addWidget(lbl2)
            row2.addWidget(self.format_filter)
            row2.addStretch()
            layout.addLayout(row2)
            # Статус
            row3 = QHBoxLayout()
            row3.setContentsMargins(0, 0, 0, 0)
            lbl3 = QLabel(_ls(self.config, 'filter_status_label'))
            row3.addWidget(lbl3)
            row3.addWidget(self.status_filter.widget)
            row3.addStretch()
            layout.addLayout(row3)
        else:
            # Горизонтальный режим: комбобоксы в ряд (как было в тулбаре)
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(16, 6, 16, 6)
            layout.setSpacing(10)
            layout.addWidget(self.sort_combo)
            layout.addWidget(self.format_filter)
            layout.addWidget(self.status_filter.widget)
            layout.addStretch()
        return panel

    def _toggle_filter_panel(self):
        """Показать/скрыть панель фильтров."""
        visible = not self._filter_panel.isVisible()
        self._filter_panel.setVisible(visible)
        if hasattr(self, '_filter_toggle_btn'):
            self._filter_toggle_btn.setChecked(visible)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow(force_width=e.size().width() - 8)
        QTimer.singleShot(50, self._reflow)
        if hasattr(self, '_drop_overlay') and self._drop_overlay and self._drop_overlay.isVisible():
            self._drop_overlay.setGeometry(self._central_widget.rect())

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            QTimer.singleShot(0, self._reflow)
            QTimer.singleShot(50, self._reflow)
            QTimer.singleShot(150, self._reflow)

    def _cols(self):
        avail = self._scroll.viewport().width() - 32
        return max(1, avail // (CARD_W + CARD_S))

    def _reflow(self, force_width=None):
        base = force_width if force_width is not None \
            else self._scroll.viewport().width()
        avail = base - 32
        cols = max(1, avail // (CARD_W + CARD_S))
        if cols > 1:
            hsp = (avail - cols * CARD_W) // (cols - 1)
        else:
            hsp = CARD_S
        max_hsp = int(60 - (cols - 1) * 4)
        max_hsp = max(26, min(60, max_hsp))
        hsp = min(hsp, max_hsp)
        if (getattr(self, '_last_reflow_cols', None) == cols
                and getattr(self, '_last_hsp', None) == hsp):
            return
        self._last_reflow_cols = cols
        self._last_hsp = hsp
        self.books_layout.setHorizontalSpacing(hsp)
        items = [self.books_layout.itemAt(i).widget()
                for i in range(self.books_layout.count())
                if self.books_layout.itemAt(i).widget()]
        for w in items:
            self.books_layout.removeWidget(w)
        for idx, w in enumerate(items):
            self.books_layout.addWidget(w, idx // cols, idx % cols)

    def _load_books(self):
        for i in reversed(range(self.books_layout.count())):
            w = self.books_layout.itemAt(i).widget()
            if w: w.deleteLater()
        books = self.config.get_books()
        self._all_books = self._sort_books(books)
        self._on_filter_changed()

    def _filter(self, books, q):
        q = q.strip().lower()
        if not q: return books
        return [b for b in books
               if q in " ".join([b.get("title", ""), b.get("author", ""),
                                b.get("series", "") or ""]).lower()]

    def _sort_books(self, books):
        """Сортировка книг по выбранному критерию."""
        sort_idx = self.sort_combo.currentIndex() if hasattr(self, "sort_combo") else 0
        if sort_idx == 0:
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
        self._all_books = self._sort_books(self.config.get_books())
        self._on_filter_changed()

    def _on_library_updated(self):
        """Обновление списка книг при изменении библиотеки."""
        if hasattr(self, '_updating') and self._updating:
            print("[Library] Защита от рекурсивного _on_library_updated()")
            return
        self._updating = True
        try:
            scroll_area = self.books_container.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            pos = scroll_area.verticalScrollBar().value() if scroll_area else 0
            books = self.config.get_books()
            self._all_books = self._sort_books(books)
            self._on_filter_changed()
            if scroll_area:
                scroll_area.verticalScrollBar().setValue(pos)
        finally:
            self._updating = False

    def _display(self, books):
        for i in reversed(range(self.books_layout.count())):
            w = self.books_layout.itemAt(i).widget()
            if w: w.deleteLater()
        self._cards_by_path = {}
        if not books:
            has_q = hasattr(self, "search_box") and self.search_box.text()
            msg = (_ls(self.config, 'no_results_short') if has_q
                  else _ls(self.config, 'empty_lib_hint'))
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{SUB};font-size:16px;padding:60px;")
            self.books_layout.addWidget(lbl, 0, 0)
            n = len(self._all_books)
            self.status_label.setText(
                _ls(self.config, 'empty_lib_short') if not n
                else _ls(self.config, 'no_results_of', n=n))
            return
        cols = self._cols()
        for idx, book in enumerate(books):
            card = BookCard(book, self.config)
            card.clicked.connect(self._on_book_clicked)
            card.delete_req.connect(self._on_delete_book)
            self.books_layout.addWidget(card, idx // cols, idx % cols)
            fp = book.get("file_path")
            if fp:
                self._cards_by_path[self._norm_path(Path(fp).parent)] = card
        n, shown = len(self._all_books), len(books)
        self.status_label.setText(
            _ls(self.config, 'shown_of', shown=shown, n=n)
            if shown != n else
            _ls(self.config, 'books_count', n=n))

    def update_single_book_progress(self, book_path: str) -> bool:
        """Точечно обновляет ОДНУ карточку (прогресс/статус)."""
        dir_norm = self._norm_path(Path(book_path).parent)
        card = self._cards_by_path.get(dir_norm)
        if not card:
            return False
        updated_books = self.config.get_books()
        fresh_info = next(
            (b for b in updated_books
             if self._norm_path(Path(b.get("file_path", "")).parent) == dir_norm),
            None
        )
        if not fresh_info:
            return False
        for i, b in enumerate(self._all_books):
            if self._norm_path(Path(b.get("file_path", "")).parent) == dir_norm:
                self._all_books[i] = fresh_info
                break
        card.update_progress(fresh_info)
        self._all_books = self._sort_books(self._all_books)
        self._reorder_cards()
        return True

    def _reorder_cards(self):
        """Переставляет существующие карточки в сетке согласно текущей сортировке."""
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        books = self._filter(self._all_books, q)
        idx = self.format_filter.currentIndex() if hasattr(self, "format_filter") else 0
        FMT_MAP = {1: 'epub', 2: 'fb2', 3: 'pdf', 4: 'mobi', 5: 'cbz'}
        if idx == 6:
            books = [b for b in books
                    if b.get('format', '').lower() in ('cbz', 'cbr', 'comic')]
        elif idx in FMT_MAP:
            books = [b for b in books
                    if b.get('format', '').lower() == FMT_MAP[idx]]
        if hasattr(self, "status_filter"):
            books = self.status_filter.apply(books)
        visible = {self._norm_path(Path(b.get("file_path", "")).parent) for b in books}
        if visible != set(self._cards_by_path.keys()):
            self._display(books)
            return
        cols = self._cols()
        for pos, book in enumerate(books):
            dir_key = self._norm_path(Path(book.get("file_path", "")).parent)
            card = self._cards_by_path.get(dir_key)
            if card is None:
                self._display(books)
                return
            self.books_layout.removeWidget(card)
            self.books_layout.addWidget(card, pos // cols, pos % cols)

    def _on_search(self, q):
        self._on_filter_changed()

    def _on_filter_changed(self, _text=None):
        """Фильтрация по формату книги и по статусу чтения."""
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        books = self._filter(self._all_books, q)
        idx = self.format_filter.currentIndex() if hasattr(self, "format_filter") else 0
        FMT_MAP = {1: 'epub', 2: 'fb2', 3: 'pdf', 4: 'mobi', 5: 'cbz'}
        if idx == 6:
            books = [b for b in books
                    if b.get('format', '').lower() in ('cbz', 'cbr', 'comic')]
        elif idx in FMT_MAP:
            books = [b for b in books
                    if b.get('format', '').lower() == FMT_MAP[idx]]
        if hasattr(self, "status_filter"):
            books = self.status_filter.apply(books)
        self._display(books)

    def _on_book_clicked(self, book_info):
        """Открытие книги с приоритетом EPUB > FB2 > остальные."""
        if isinstance(book_info, str):
            fp = book_info
        else:
            fp = book_info.get("file_path")
        if not fp or not Path(fp).exists():
            return
        book_path = Path(fp)
        book_dir = book_path.parent
        if book_dir.exists():
            priority = ['fb2', 'epub', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr']
            for fmt in priority:
                for f in book_dir.iterdir():
                    if f.suffix.lower() == f'.{fmt}':
                        self.book_selected.emit(str(f))
                        return
            for f in book_dir.iterdir():
                if f.suffix.lower() in ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']:
                    self.book_selected.emit(str(f))
                    return
        self.book_selected.emit(fp)

    def _on_delete_book(self, book_info):
        """Удаление книги."""
        title    = book_info.get("title", "Книга")[:60]
        book_id  = book_info.get("_book_id") or book_info.get("id")
        formats  = book_info.get("formats", {})
        cur_path = book_info.get("file_path", "")
        if len(formats) > 1:
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
            _apply_msgbox_style(mb)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked == btn_can or clicked is None:
                return
            delete_all = (clicked == btn_all)
        else:
            if not _styled_question(
                    self,
                    _ls(self.config, 'delete_title'),
                    _ls(self.config, 'delete_msg_single', title=title),
                    config=self.config):
                return
            delete_all = True
        if delete_all:
            paths_to_delete = list(formats.values())
            if book_id:
                self.config.remove_book_by_id(book_id)
            else:
                self.config.remove_book(cur_path)
        else:
            paths_to_delete = [cur_path]
            self.config.remove_format(cur_path)
        try:
            if delete_all:
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
                    try:
                        book_dir.rmdir()
                        print(f"[Library] Удалена папка книги: {book_dir.name}")
                        author_dir = book_dir.parent
                        lib_root   = self.config.get_library_path()
                        if (author_dir != lib_root and author_dir.exists()
                                and not any(author_dir.iterdir())):
                            author_dir.rmdir()
                            print(f"[Library] Удалена папка автора: {author_dir.name}")
                    except OSError:
                        pass
            else:
                p = Path(cur_path)
                if p.exists():
                    p.unlink()
                    print(f"[Library] Удалён формат: {p.name}")
        except Exception as e:
            print(f"[Library] Delete error: {e}")
            _qmb = QMessageBox(QMessageBox.Icon.Warning, "Ошибка",
                             f"Не удалось удалить файлы:\n{e}",
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
        if delete_all:
            cp = book_info.get("cover_path")
            if cp:
                try: Path(cp).unlink(missing_ok=True)
                except Exception: pass
        self._load_books()

    def add_books(self):
        filter_str = (
            f"{_ls(self.config,'add_filter_books')};;"
            f"{_ls(self.config,'add_filter_comics')};;"
            f"{_ls(self.config,'add_filter_manga')};;"
            f"{_ls(self.config,'add_filter_pdf')};;"
            f"{_ls(self.config,'add_filter_all')}"
        )
        dlg = _make_styled_file_dialog(
            self,
            _ls(self.config, 'add_dialog_title'),
            str(self.config.get_library_path()),
            filter_str,
            multi=True,
            config=self.config,
        )
        if dlg.exec() != QFileDialog.DialogCode.Accepted:
            return
        files = dlg.selectedFiles()
        selected_filter = dlg.selectedNameFilter()
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
        folder = _styled_get_existing_directory(
            self, _ls(self.config, 'scan_dialog_title'),
            str(self.config.get_library_path()),
            config=self.config)
        if not folder: return
        books = []
        for ext in ["*.epub", "*.fb2", "*.fb2.zip", "*.zip", "*.mobi", "*.cbz", "*.pdf"]:
            books.extend(Path(folder).rglob(ext))
        if not books:
            _qmb = QMessageBox(QMessageBox.Icon.Information, _ls(self.config, 'add_done'),
                             _ls(self.config, 'no_books_found'),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec(); return
        if _styled_question(
                self,
                _ls(self.config, 'scan_dialog_title'),
                _ls(self.config, 'found_books', n=len(books)),
                config=self.config):
            self._process_books([str(b) for b in books])

    def cleanup_library(self):
        books = self.config.get_books()
        miss  = [b for b in books
                if not (b.get("file_path") and Path(b["file_path"]).exists())]
        if not miss:
            _qmb = QMessageBox(QMessageBox.Icon.Information, _ls(self.config, 'add_done'),
                             _ls(self.config, 'all_records_ok'),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec(); return
        if _styled_question(
                self,
                _ls(self.config, 'cleanup'),
                _ls(self.config, 'cleanup_confirm', n=len(miss)),
                config=self.config):
            self.config.cleanup_missing()
            self._load_books()

    def export_notes(self):
        """Экспорт заметок и подсветок в TXT или Markdown."""
        data = self.config.get_all_notes_and_highlights()
        has_data = any(
            b['notes'] or b['highlights']
            for b in data.values()
        )
        if not has_data:
            _qmb = QMessageBox(QMessageBox.Icon.Information,
                             _ls(self.config, 'export_no_data_title'),
                             _ls(self.config, 'export_no_data_msg'),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec(); return
        from PyQt6.QtWidgets import QDialog, QRadioButton, QVBoxLayout, QHBoxLayout, QLabel
        dialog = QDialog(self)
        dialog.setWindowTitle(_ls(self.config, 'export_title'))
        dialog.setModal(True)
        dialog.setFixedWidth(360)
        dialog.setStyleSheet(
            f'QDialog{{background:{BG};color:{TEXT};}}'
            f'QRadioButton{{color:{TEXT};font-size:14px;background:transparent;}}'
            f'QLabel{{color:{SUB};font-size:12px;background:transparent;}}'
            f'QPushButton{{background:{SURFACE};color:{TEXT};border:1px solid {BORDER};'
            f'border-radius:6px;padding:7px 18px;font-size:13px;min-width:0;}}'
            f'QPushButton:hover{{border-color:{ACCENT};background:rgba(255,255,255,.08);}}'
            f'QPushButton:pressed{{background:{ACCENT};color:#fff;border-color:{ACCENT};}}'
        )
        vlay = QVBoxLayout(dialog)
        vlay.setSpacing(12)
        vlay.setContentsMargins(20, 18, 20, 16)
        title = QLabel(_ls(self.config, 'export_choose_fmt'))
        title.setStyleSheet(f"color:{TEXT};font-size:15px;font-weight:bold;background:transparent;")
        vlay.addWidget(title)
        txt_radio = QRadioButton(_ls(self.config, 'export_fmt_txt'))
        txt_radio.setChecked(True)
        vlay.addWidget(txt_radio)
        md_radio = QRadioButton(_ls(self.config, 'export_fmt_md'))
        vlay.addWidget(md_radio)
        info = QLabel(_ls(self.config, 'export_fmt_hint'))
        info.setWordWrap(True)
        vlay.addWidget(info)
        vlay.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_ok = QPushButton(_ls(self.config, 'dlg_choose_file'))
        btn_ok.setStyleSheet(
            f'QPushButton{{background:{ACCENT};color:#fff;border:1px solid {ACCENT};'
            f'border-radius:6px;padding:7px 18px;font-size:13px;min-width:0;}}'
        )
        btn_cancel = QPushButton(_ls(self.config, 'cancel'))
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        vlay.addLayout(btn_row)
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        use_markdown = md_radio.isChecked()
        default_name = "notes.md" if use_markdown else "notes.txt"
        filter_str = _ls(self.config, 'dlg_filter_md') if use_markdown else _ls(self.config, 'dlg_filter_txt')
        file_path, _ = _styled_get_save_filename(
            self,
            _ls(self.config, 'dlg_save_notes'),
            str(self.config.get_library_path()),
            filter_str,
            default_name=default_name,
            config=self.config
        )
        if not file_path:
            return
        try:
            if use_markdown:
                count = self.config.export_notes_to_markdown(file_path)
            else:
                count = self.config.export_notes_to_txt(file_path)
            _qmb = QMessageBox(QMessageBox.Icon.Information,
                             _ls(self.config, 'export_done'),
                             _ls(self.config, 'export_saved', count=count, path=file_path),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
        except Exception as e:
            _qmb = QMessageBox(QMessageBox.Icon.Critical,
                             _ls(self.config, 'export_error'),
                             _ls(self.config, 'export_error_msg', e=e),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()

    def _process_books(self, file_paths, comic_type=None):
        expanded = []
        for fp in file_paths: expanded.extend(self._expand_file(fp))
        if not expanded:
            _qmb = QMessageBox(QMessageBox.Icon.Warning, _ls(self.config, 'error'),
                             _ls(self.config, 'no_books_found'),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec(); return
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
                existing_book = self._find_existing_book(book_key, src_path)
                dest = self._copy_structured(src_path, meta, existing_book)
                if not dest: skipped += 1; continue
                cover_data = self.parser.extract_cover(src_path)
                cover_path = None
                if cover_data:
                    cover_path = dest.parent / "cover.jpg"
                    cover_path.write_bytes(cover_data)
                (dest.parent / "metadata.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
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
        prog.close()
        _qmb = QMessageBox(QMessageBox.Icon.Information, _ls(self.config, 'add_done'),
                         _ls(self.config, 'add_result', added=added, skipped=skipped),
                         QMessageBox.StandardButton.Ok, self)
        _apply_msgbox_style(_qmb); _qmb.exec()
        self._load_books()

    def _expand_file(self, file_path):
        import zipfile as _zf, tempfile as _tmp
        p = Path(file_path)
        if p.suffix.lower() in (".epub", ".fb2", ".mobi", ".azw3", ".cbz", ".pdf"):
            return [(str(p), None)]
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
        if p.suffix.lower() == ".cbr":
            return self._cbr_to_cbz(p)
        return [(str(p), None)]

    def _cbr_to_cbz(self, cbr_path: Path):
        """Конвертирует CBR (RAR) → CBZ (ZIP) во временной папке."""
        import tempfile as _tmp, zipfile as _zf, subprocess as _sp
        tmp = _tmp.mkdtemp(prefix="novareader_cbr_")
        try:
            extracted = False
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
                    zf.write(img, img.relative_to(tmp))
            print(f"[Library] CBR → CBZ: {cbz_path.name} ({len(images)} страниц)")
            return [(str(cbz_path), tmp)]
        except Exception as e:
            print(f"[Library] CBR → CBZ error: {e}")
            shutil.rmtree(tmp, ignore_errors=True)
            return []

    @staticmethod
    def _safe_name(name: str, max_len: int = 60) -> str:
        """Очистить имя файла/папки от символов, опасных для NTFS3 и любых ФС."""
        import unicodedata as _ud, re as _re
        name = "".join(ch for ch in name
                      if _ud.category(ch) not in ("Cc", "Cf") and ord(ch) >= 0x20)
        FORBIDDEN = set('<>:"/\\|?*\'&;=+,[]{|}^%@!~`')
        name = "".join("_" if ch in FORBIDDEN else ch for ch in name)
        name = _re.sub(r'_+', '_', name)
        name = _re.sub(r' +', ' ', name)
        name = name.strip(". ")
        return name[:max_len] or "Без_названия"

    def _get_book_key(self, meta):
        """Уникальный ключ книги по метаданным (title + author)."""
        title = (meta.get("title") or "").strip().lower()
        author = (meta.get("author") or "Неизвестен").strip().lower()
        title = " ".join(title.split())
        author = " ".join(author.split())
        return (title, author)

    def _find_existing_book(self, book_key, src_path=None):
        """Ищет существующую книгу с такими же метаданными."""
        for book in self.config.get_books():
            existing_key = self._get_book_key(book)
            if existing_key == book_key:
                return book
        if src_path:
            src_stem = Path(src_path).stem.strip().lower()
            if src_stem:
                for book in self.config.get_books():
                    fp = book.get('file_path', '')
                    if fp and Path(fp).stem.strip().lower() == src_stem:
                        return book
        return None

    def _copy_structured(self, src_path, meta, existing_book=None):
        """Копирует книгу в библиотеку."""
        try:
            src = Path(src_path)
            if existing_book:
                existing_path = Path(existing_book.get("file_path", ""))
                book_dir = existing_path.parent
            else:
                lib  = self.config.get_library_path()
                ext  = src.suffix.lower()
                comic_type = meta.get("comic_type")
                if comic_type or ext in (".cbz", ".cbr"):
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
        self.config.set("library_theme_name", theme_name)
        if theme_name == "custom" and custom_colors:
            self.config.set("library_theme_custom", custom_colors)
        self._apply_theme_styles()
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
                "refresh_btn", "backup_btn", "restore_btn", "restore_url_btn", "settings_btn")):
            if btn:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;border:none;"
                    f"border-radius:18px;color:{SUB};"
                    f"font-family:'Material Icons';font-size:18px;}}"
                    f"QPushButton:hover{{background:rgba(128,128,128,.12);color:{TEXT};}}"
                    f"QPushButton:pressed{{background:rgba(128,128,128,.22);}}")
        combo_ss = _combo_style()
        # Обновляем комбобоксы в тулбаре и в панели фильтров
        for w in (getattr(self, n, None) for n in (
                "search_box", "sort_combo", "format_filter")):
            if w:
                w.setStyleSheet(combo_ss)

        # Обновляем комбобокс статуса (StatusFilter)
        if hasattr(self, "status_filter") and self.status_filter is not None:
            if hasattr(self.status_filter, "_combo") and self.status_filter._combo is not None:
                self.status_filter._combo.setStyleSheet(combo_ss)

        # Обновляем панель фильтров
        if hasattr(self, "_filter_panel") and self._filter_panel is not None:
            self._filter_panel.setStyleSheet(f"""
                QWidget#FilterPanel {{
                    background: {SURFACE};
                    border-top: 1px solid {BORDER};
                    border-bottom: 1px solid {BORDER};
                }}
                QLabel {{
                    color: {TEXT};
                    font-size: 12px;
                    background: transparent;
                    min-width: 70px;
                }}
            """)
            # Если вертикальный режим – обновляем все QLabel внутри панели (подписи)
            if FILTER_PANEL_MODE == 'vertical':
                for lbl in self._filter_panel.findChildren(QLabel):
                    lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; background:transparent; min-width:70px;")

        if hasattr(self, "search_box"):
            self.search_box.setStyleSheet(
                f"QLineEdit{{background:{BG};color:{TEXT};"
                f"border:1px solid {BORDER};border-radius:17px;"
                f"padding:0 14px;font-size:13px;}}"
                f"QLineEdit:focus{{border:1px solid {ACCENT};}}")

        # Обновляем кнопку переключения панели фильтров (гамбургер)
        if hasattr(self, "_filter_toggle_btn") and self._filter_toggle_btn is not None:
            self._filter_toggle_btn.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                f"border-radius:18px;color:{SUB};"
                f"font-family:'Material Icons';font-size:18px;}}"
                f"QPushButton:hover{{background:rgba(128,128,128,.12);color:{TEXT};}}"
                f"QPushButton:pressed{{background:rgba(128,128,128,.22);}}")

    def _on_online_search_toggled(self, enabled):
        """Callback из настроек: кнопка в тулбаре + глушим процесс поиска."""
        if hasattr(self, 'search_btn'):
            self.search_btn.setVisible(enabled)
        if not enabled:
            proc = getattr(self, '_search_proc', None)
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
            self._search_proc = None

    def open_online_search(self):
        """Открыть окно поиска ОТДЕЛЬНЫМ процессом (--search)."""
        if not self.config.get('online_search_enabled', True):
            return
        import subprocess
        proc = getattr(self, '_search_proc', None)
        if proc is not None and proc.poll() is None:
            return
        exe_dir = Path(sys.executable).parent
        cmd = None
        for app_name in ('NovaReader', 'NovaReader.exe', 'main', 'main.exe'):
            app_bin = exe_dir / app_name
            if app_bin.exists():
                cmd = [str(app_bin), '--search']
                break
        if cmd is None:
            cmd = [sys.executable,
                  str(Path(__file__).resolve().parent / 'main.py'), '--search']
        self._search_proc = subprocess.Popen(cmd)

    def open_settings(self):
        """Открыть окно настроек как независимое окно."""
        from settings_window import SettingsWindow
        if self.settings_window is not None:
            try:
                self.settings_window.show()
                self.settings_window.raise_()
                self.settings_window.activateWindow()
                return
            except RuntimeError:
                self.settings_window = None
        dlg = SettingsWindow(self.config, parent=None,
                            lib_theme_callback=self.apply_lib_theme,
                            online_search_changed_callback=self._on_online_search_toggled,
                            language_changed_callback=self.retranslate_ui)
        dlg.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint)
        self.settings_window = dlg
        dlg.show()

    def backup_config(self):
        """Создать ZIP-архив с настройками, книгами, обложками, закладками, выделениями и позициями."""
        import datetime
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QPushButton, QLabel)
        from settings_window import QToggleSwitch

        def _fmt_size(b):
            for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
                if b < 1024:
                    return f"{b:.1f} {unit}" if unit != 'Б' else f"{b} {unit}"
                b /= 1024
            return f"{b:.1f} ГБ"

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"novareader_backup_{ts}.zip"
        dlg_info = QDialog(self)
        dlg_info.setWindowTitle(_ls(self.config, 'backup_title'))
        dlg_info.setFixedWidth(380)
        dlg_info.setStyleSheet(
            f'QDialog{{background:{BG};color:{TEXT};}}'
            f'QLabel{{color:{TEXT};}}'
            f'QPushButton{{background:{SURFACE};color:{TEXT};border:1px solid {BORDER};'
            f'border-radius:6px;padding:7px 18px;font-size:13px;min-width:0;}}'
            f'QPushButton:hover{{border-color:{ACCENT};background:rgba(255,255,255,.08);}}'
            f'QPushButton:pressed{{background:{ACCENT};color:#fff;border-color:{ACCENT};}}'
        )
        vlay = QVBoxLayout(dlg_info)
        vlay.setSpacing(10)
        vlay.setContentsMargins(20, 18, 20, 16)
        lbl_title = QLabel(f"<b>{_ls(self.config, 'backup_contents_title')}</b>")
        vlay.addWidget(lbl_title)
        lbl_always = QLabel(
            f"&nbsp;&nbsp;✓&nbsp; {_ls(self.config, 'backup_item_settings')}<br>"
            f"&nbsp;&nbsp;✓&nbsp; {_ls(self.config, 'backup_item_library')}<br>"
            f"&nbsp;&nbsp;✓&nbsp; {_ls(self.config, 'backup_item_positions')}")
        lbl_always.setStyleSheet(f'color:{SUB};font-size:12px;')
        lbl_always.setTextFormat(Qt.TextFormat.RichText)
        vlay.addWidget(lbl_always)
        vlay.addSpacing(4)
        def _toggle_row(toggle, text):
            row = QWidget()
            row.setStyleSheet('background:transparent;')
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(10)
            rh.addWidget(toggle)
            lbl = QLabel(text)
            lbl.setStyleSheet(f'color:{TEXT}; font-size:13px; background:transparent;')
            rh.addWidget(lbl)
            rh.addStretch()
            return row
        chk_voices = QToggleSwitch(accent=ACCENT, track_off=BORDER)
        chk_fonts  = QToggleSwitch(accent=ACCENT, track_off=BORDER)
        chk_voices.setChecked(self.config.get('backup_include_voices', False))
        chk_fonts.setChecked(self.config.get('backup_include_fonts', False))
        vlay.addWidget(_toggle_row(chk_voices, _ls(self.config, 'backup_toggle_voices')))
        vlay.addWidget(_toggle_row(chk_fonts,  _ls(self.config, 'backup_toggle_fonts')))
        vlay.addSpacing(6)
        lbl_stats = QLabel()
        lbl_stats.setStyleSheet(f'color:{SUB};font-size:12px;')
        vlay.addWidget(lbl_stats)
        def _update_stats():
            nf, nb = self.config.backup_stats(
                include_voices=chk_voices.isChecked(),
                include_fonts=chk_fonts.isChecked())
            lbl_stats.setText(_ls(self.config, 'backup_stats', n=nf, size=_fmt_size(nb)))
            lbl_stats.setTextFormat(Qt.TextFormat.RichText)
        _update_stats()
        chk_voices.toggled.connect(lambda _: _update_stats())
        chk_fonts.toggled.connect(lambda _: _update_stats())
        vlay.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_ok = QPushButton(_ls(self.config, 'dlg_choose_file'))
        btn_ok.setStyleSheet(
            f'QPushButton{{background:{ACCENT};color:#fff;border:1px solid {ACCENT};'
            f'border-radius:6px;padding:7px 18px;font-size:13px;min-width:0;}}'
        )
        btn_cancel = QPushButton(_ls(self.config, 'cancel'))
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        vlay.addLayout(btn_row)
        btn_ok.clicked.connect(dlg_info.accept)
        btn_cancel.clicked.connect(dlg_info.reject)
        if dlg_info.exec() != QDialog.DialogCode.Accepted:
            return
        incl_voices = chk_voices.isChecked()
        incl_fonts  = chk_fonts.isChecked()
        self.config.set('backup_include_voices', incl_voices)
        self.config.set('backup_include_fonts', incl_fonts)
        total_files, total_bytes = self.config.backup_stats(
            include_voices=incl_voices, include_fonts=incl_fonts)
        dest, _ = _styled_get_save_filename(
            self, _ls(self.config, 'dlg_save_backup'),
            str(Path.home()),
            _ls(self.config, 'dlg_filter_zip'),
            default_name=default_name,
            config=self.config)
        if not dest:
            return
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
        lbl_title = QLabel("Упаковка архива...")
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
            def __init__(self, cfg, dest, cancel_flag, incl_voices=False, incl_fonts=False):
                super().__init__()
                self._cfg = cfg
                self._dest = dest
                self._cancel = cancel_flag
                self._incl_voices = incl_voices
                self._incl_fonts  = incl_fonts
            def run(self):
                try:
                    result = self._cfg.backup_to_zip(
                        self._dest,
                        progress_cb=lambda cur, tot, name:
                            self.progress_sig.emit(cur, tot, name),
                        cancel_flag=self._cancel,
                        include_voices=self._incl_voices,
                        include_fonts=self._incl_fonts)
                    self.done_sig.emit(result)
                except Exception as e:
                    self.error_sig.emit(str(e))
        worker = _BackupWorker(self.config, dest, cancel_flag,
                              incl_voices=incl_voices, incl_fonts=incl_fonts)
        def on_progress(cur, tot, name):
            progress.setValue(cur)
            lbl_count.setText(f"{cur} / {tot} файлов")
            lbl_file.setText(f"→ {name}")
        def on_done(result):
            dlg.accept()
            cancel_btn.setText(_ls(self.config, 'close') if hasattr(self, 'config') else 'Закрыть')
            if result.get('cancelled'):
                try:
                    Path(dest).unlink(missing_ok=True)
                except Exception:
                    pass
                _qmb = QMessageBox(QMessageBox.Icon.Warning,
                                 _ls(self.config, 'backup_cancelled_title'),
                                 _ls(self.config, 'backup_cancelled_msg'),
                                 QMessageBox.StandardButton.Ok, self)
                _apply_msgbox_style(_qmb); _qmb.exec()
            else:
                sz = Path(dest).stat().st_size
                _qmb = QMessageBox(QMessageBox.Icon.Information,
                                 _ls(self.config, 'backup_done_title'),
                                 _ls(self.config, 'backup_saved_stats',
                                    path=dest, files=result['files'], size=_fmt_size(sz)),
                                 QMessageBox.StandardButton.Ok, self)
                _apply_msgbox_style(_qmb); _qmb.exec()
        def on_error(msg):
            dlg.accept()
            try:
                Path(dest).unlink(missing_ok=True)
            except Exception:
                pass
            _qmb = QMessageBox(QMessageBox.Icon.Critical, "Ошибка",
                             f"Не удалось создать резервную копию:\n{msg}",
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
        worker.progress_sig.connect(on_progress)
        worker.done_sig.connect(on_done)
        worker.error_sig.connect(on_error)
        worker.start()
        dlg.exec()
        cancel_flag[0] = True
        worker.wait()

    def restore_config(self):
        """Выбрать ZIP-архив и восстановить из него."""
        src, _ = _styled_get_open_filename(
            self, _ls(self.config, 'dlg_open_backup'),
            str(Path.home()),
            _ls(self.config, 'dlg_filter_zip'),
            config=self.config)
        if not src:
            return
        self._restore_from_path(src)

    def _restore_from_path(self, src: str):
        """Восстановить настройки, библиотеку, закладки и позиции из ZIP-архива."""
        import zipfile
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QProgressBar
        from PyQt6.QtCore import QThread
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
            _qmb = QMessageBox(QMessageBox.Icon.Critical,
                             _ls(self.config, 'error'),
                             _ls(self.config, 'restore_open_err', e=e),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
            return
        if not names & known_config:
            _qmb = QMessageBox(QMessageBox.Icon.Warning,
                             _ls(self.config, 'restore_invalid_title'),
                             _ls(self.config, 'restore_invalid_msg'),
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
            return
        def _fmt_size(b):
            for unit in ('Б', 'КБ', 'МБ', 'ГБ'):
                if b < 1024:
                    return f"{b:.1f} {unit}" if unit != 'Б' else f"{b} {unit}"
                b /= 1024
            return f"{b:.1f} ГБ"
        arc_size = Path(src).stat().st_size
        items = [_ls(self.config, 'restore_item_settings'),
                _ls(self.config, 'restore_item_lib'),
                _ls(self.config, 'restore_item_bookmarks'),
                _ls(self.config, 'restore_item_highlights'),
                _ls(self.config, 'restore_item_notes')]
        if has_lib:
            items.append(_ls(self.config, 'restore_item_books'))
        if has_covers:
            items.append(_ls(self.config, 'restore_item_covers'))
        if not _styled_question(
                self, "Восстановить из резервной копии",
                "  <b>Текущие данные будут заменены!</b><br><br>"
                "Будет восстановлено:<br>  • " +
                "<br>  • ".join(items) +
                f"<br><br>Файлов в архиве: <b>{total_arc}</b> · "
                f"Размер: <b>{_fmt_size(arc_size)}</b><br><br>"
                "Продолжить?",
                config=self.config):
            return
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
        lbl_title = QLabel("Восстановление данных...")
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
                _qmb = QMessageBox(QMessageBox.Icon.Warning, "Отменено",
                                 "Восстановление отменено.\nЧасть данных могла быть восстановлена частично.",
                                 QMessageBox.StandardButton.Ok, self)
                _apply_msgbox_style(_qmb); _qmb.exec()
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
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                _apply_msgbox_style(msg)
                msg.button(QMessageBox.StandardButton.Ok).setIcon(QIcon())
                msg.button(QMessageBox.StandardButton.Ok).setText('OK')
                msg.exec()
                self.config.reload()
                init_lib_colors(self.config)
                self.apply_lib_theme(
                    self.config.get('library_theme_name', 'dark'),
                    self.config.get('library_theme_custom', None)
                )
                self._load_books()
            dlg.accept()
        def on_error(msg):
            dlg.accept()
            _qmb = QMessageBox(QMessageBox.Icon.Critical, "Ошибка восстановления",
                             f"Не удалось восстановить данные:\n{msg}",
                             QMessageBox.StandardButton.Ok, self)
            _apply_msgbox_style(_qmb); _qmb.exec()
        worker.progress_sig.connect(on_progress)
        worker.done_sig.connect(on_done)
        worker.error_sig.connect(on_error)
        worker.start()
        dlg.exec()
        cancel_flag[0] = True
        worker.wait()

    def _get_yandex_direct_link(self, url: str) -> str | None:
        """Делегирует получение прямой ссылки модулю cloud_download."""
        try:
            from cloud_download import get_direct_link, detect_service
            service = detect_service(url)
            if service:
                return get_direct_link(url)
        except ImportError:
            pass
        return None

    def restore_from_url(self):
        """Скачать ZIP-архив резервной копии по URL и восстановить из него."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QLabel, QLineEdit, QPushButton,
                                    QProgressDialog)
        from PyQt6.QtCore import Qt
        dlg = QDialog(self)
        dlg.setWindowTitle(_ls(self.config, 'restore_url_title'))
        dlg.setFixedWidth(520)
        dlg.setStyleSheet(
            f'QDialog{{background:{BG};color:{TEXT};}}'
            f'QLabel{{color:{TEXT};font-size:13px;}}'
            f'QLineEdit{{background:{SURFACE};color:{TEXT};'
            f'border:1px solid {BORDER};border-radius:6px;'
            f'padding:6px 10px;font-size:13px;}}'
            f'QLineEdit:focus{{border-color:{ACCENT};}}'
            f'QPushButton{{background:{SURFACE};color:{TEXT};'
            f'border:1px solid {BORDER};border-radius:6px;'
            f'padding:7px 18px;font-size:13px;min-width:0;}}'
            f'QPushButton:hover{{border-color:{ACCENT};'
            f'background:rgba(255,255,255,.08);}}'
            f'QPushButton:pressed{{background:{ACCENT};'
            f'color:#fff;border-color:{ACCENT};}}'
        )
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.addWidget(QLabel(_ls(self.config, 'restore_url_prompt')))
        url_edit = QLineEdit()
        url_edit.setPlaceholderText('https://...')
        lay.addWidget(url_edit)
        btn_row = QHBoxLayout()
        btn_ok     = QPushButton(_ls(self.config, 'yes'))
        btn_cancel = QPushButton(_ls(self.config, 'cancel'))
        btn_ok.setStyleSheet(
            f'QPushButton{{background:{ACCENT};color:#fff;'
            f'border:1px solid {ACCENT};border-radius:6px;'
            f'padding:7px 18px;font-size:13px;min-width:0;}}'
        )
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        url_edit.returnPressed.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        url = url_edit.text().strip()
        if not url:
            return
        prog = QProgressDialog(
            _ls(self.config, 'restore_url_download'),
            _ls(self.config, 'cancel'), 0, 0, self)
        prog.setWindowTitle(_ls(self.config, 'restore_url_title'))
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        prog.show()
        QApplication.processEvents()
        import tempfile, threading, os
        if sys.platform == 'win32':
            _base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
        else:
            _base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
        cache_dir = _base / 'NovaReader'
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            _test = cache_dir / '.write_test'
            _test.touch(); _test.unlink()
        except (PermissionError, OSError):
            cache_dir = Path.home()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip',
                                           prefix='novareader_restore_',
                                           dir=str(cache_dir))
        os.close(tmp_fd)
        print(f'[Restore] Временный файл: {tmp_path}')
        raw_url = url
        try:
            from cloud_download import get_direct_link, detect_service
            service = detect_service(raw_url)
        except ImportError:
            service = None
        if service:
            prog.setLabelText('Получаем прямую ссылку...')
            QApplication.processEvents()
            download_url = get_direct_link(raw_url)
            if not download_url:
                prog.close()
                Path(tmp_path).unlink(missing_ok=True)
                _qmb = QMessageBox(QMessageBox.Icon.Warning,
                                 'Не удалось получить ссылку',
                                 'Не удалось извлечь прямую ссылку для скачивания.\n\n'
                                 'Попробуйте: откройте ссылку в браузере, нажмите «Скачать»,\n'
                                 'остановите загрузку и скопируйте прямую ссылку.',
                                 QMessageBox.StandardButton.Ok, self)
                _apply_msgbox_style(_qmb); _qmb.exec()
                return
        else:
            download_url = raw_url
        prog.setLabelText(_ls(self.config, 'restore_url_download'))
        QApplication.processEvents()
        result  = [None]
        cancel  = [False]
        def _download():
            try:
                import requests as _req
                r = _req.get(download_url, stream=True, timeout=60,
                            headers={'User-Agent': 'Mozilla/5.0'})
                r.raise_for_status()
                ctype = r.headers.get('content-type', '')
                if 'text/html' in ctype:
                    result[0] = Exception('Сервер вернул HTML вместо файла.\n'
                                         'Возможно ссылка устарела или требует авторизации.')
                    return
                total = int(r.headers.get('content-length', 0))
                done  = 0
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if cancel[0]:
                            result[0] = 'cancel'
                            return
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            progress[0] = (done, total)
                result[0] = 'ok'
            except Exception as e:
                result[0] = e
        progress = [(0, 0)]
        t = threading.Thread(target=_download, daemon=True)
        t.start()
        from PyQt6.QtCore import QThread as _QThread
        prog.canceled.connect(lambda: cancel.__setitem__(0, True))
        while t.is_alive():
            QApplication.processEvents()
            done, total = progress[0]
            if total > 0:
                prog.setMaximum(total)
                prog.setValue(done)
            _QThread.msleep(100)
        prog.close()
        if result[0] != 'ok':
            Path(tmp_path).unlink(missing_ok=True)
            if result[0] != 'cancel' and result[0] is not None:
                _qmb = QMessageBox(QMessageBox.Icon.Critical,
                                 _ls(self.config, 'error'),
                                 _ls(self.config, 'restore_url_error', e=result[0]),
                                 QMessageBox.StandardButton.Ok, self)
                _apply_msgbox_style(_qmb); _qmb.exec()
            return
        self._restore_from_path(tmp_path)
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    def _auto_rescan_after_restore(self):
        """Автоматический скан папки после восстановления бэкапа."""
        folder = str(self.config.get_library_path())
        books = []
        for ext in ["*.epub", "*.fb2", "*.fb2.zip", "*.zip", "*.mobi", "*.azw3", "*.cbz", "*.cbr", "*.pdf"]:
            books.extend(Path(folder).rglob(ext))
        if books:
            if _styled_question(
                    self,
                    "Сканирование после восстановления",
                    f"Найдено {len(books)} книг в папке библиотеки.\n\nДобавить их в библиотеку?",
                    config=self.config):
                self._process_books([str(b) for b in books])
        else:
            self._load_books()

    _BOOK_EXTS = {'.epub', '.fb2', '.mobi', '.azw3', '.cbz', '.cbr', '.pdf',
                 '.zip', '.fb2.zip'}

    def _is_book_url(self, url):
        p = url.toLocalFile()
        if not p:
            return False
        from pathlib import Path as _P
        pl = _P(p)
        suffixes = ''.join(pl.suffixes).lower()
        return pl.is_dir() or pl.suffix.lower() in self._BOOK_EXTS or suffixes in self._BOOK_EXTS

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() and any(self._is_book_url(u) for u in md.urls()):
            e.acceptProposedAction()
            self._show_drop_overlay(True)
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._show_drop_overlay(False)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._show_drop_overlay(False)
        urls = e.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if self._is_book_url(u)]
        if paths:
            e.acceptProposedAction()
            self._process_books(paths)

    def _show_drop_overlay(self, show: bool):
        """Показывает/скрывает полупрозрачный оверлей при перетаскивании."""
        if show:
            if not hasattr(self, '_drop_overlay') or self._drop_overlay is None:
                from PyQt6.QtWidgets import QLabel as _QL
                from PyQt6.QtCore import Qt as _Qt
                ov = _QL(self._central_widget)
                ov.setAttribute(_Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                ov.setAlignment(_Qt.AlignmentFlag.AlignCenter)
                ov.setText(
                    f'<div style="color:{ACCENT};font-size:48px;font-family:Material Icons;">file_download</div>'
                    f'<div style="color:{TEXT};font-size:18px;margin-top:12px;">'
                    + (_ls(self.config, 'drop_to_add') if hasattr(self, 'config') else 'Перетащите книги сюда')
                    + '</div>'
                )
                ov.setStyleSheet(
                    f"background:rgba(0,0,0,0.55);"
                    f"border:3px solid {ACCENT};"
                    f"border-radius:12px;"
                )
                ov.setGeometry(self._central_widget.rect())
                ov.show()
                self._drop_overlay = ov
            else:
                self._drop_overlay.setGeometry(self._central_widget.rect())
                self._drop_overlay.show()
        else:
            if hasattr(self, '_drop_overlay') and self._drop_overlay:
                self._drop_overlay.hide()

    def closeEvent(self, e):
        if not self.isMaximized():
            self.config.set("library_width",  self.width())
            self.config.set("library_height", self.height())
        e.accept()
