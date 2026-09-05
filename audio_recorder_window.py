# -*- coding: utf-8 -*-
"""
audio_recorder_window.py — интерфейс записи глав книги в MP3 (NovaReader).

Открывается кнопкой рекордера в нижней панели reader.html. Позволяет
выбрать одну или несколько глав, голос из установленных TTS-движков и
папку сохранения — каждая выбранная глава записывается в СВОЙ MP3-файл
через AudiobookRecorder (audio_recorder.py). Все файлы кладутся в
подпапку с названием книги внутри выбранной папки сохранения. Синтез
идёт в фоновом QThread, чтобы не блокировать интерфейс читалки.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QProgressBar, QFrame,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QAbstractItemView, QFileDialog, QSlider,
                             QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPalette, QDesktopServices, QColor
from pathlib import Path

from audio_recorder import AudiobookRecorder, safe_filename
from tts_correction_window import _build_style, _sys, _blend


_ARW_S = {
    'ru': {
        'title':            'Запись глав в MP3',
        'desc':             'Выберите главы, голос диктора и папку — каждая глава '
                             'будет озвучена и сохранена отдельным MP3-файлом в '
                             'папке с названием книги.',
        'chapters':         'Главы',
        'select_all':       'Выбрать все',
        'select_none':      'Снять выбор',
        'engine':           'Движок TTS',
        'voice':            'Голос',
        'rate':             'Скорость',
        'output':           'Куда сохранить',
        'browse':           'Обзор…',
        'open_folder':      'Открыть папку',
        'save_path_hint':   'Файлы будут сохранены в: {path}',
        'title_merge_hint': 'В начало каждого файла (с паузой) будет добавлено название книги «{book}» — далее сразу идёт текст главы (её заголовок уже в тексте).',
        'record':           'Записать',
        'stop':             'Остановить',
        'close':            'Закрыть',
        'no_voices':        'Нет установленных голосов для этого движка',
        'no_engines':       'Нет доступных движков TTS',
        'no_chapters':      'Не удалось получить главы книги',
        'no_folder':        'Выберите папку для сохранения',
        'no_selection':     'Выберите хотя бы одну главу',
        'skip_hint':        'аннотация/сноски — обычно не нужно',
        'status_idle':      'Выберите главы, голос и папку для сохранения',
        'status_progress':  'Глава {chnum}/{chtotal} — предложение {done} из {total}',
        'status_done':      'Готово: записано глав — {count}',
        'status_stopped':   'Остановлено',
        'err_empty_text':   'В этой главе нет текста для озвучивания',
        'err_no_voice':     'Выбранный голос не найден на диске',
        'err_no_piper':     'Бинарник Piper не найден',
        'err_no_ffmpeg':    'ffmpeg не найден — установите его для записи в MP3',
        'err_no_edge_tts':  'Модуль edge-tts не установлен',
        'err_dir_title':    'Папка недоступна',
        'err_dir_not_found': 'Директория не найдена (возможно, отключён внешний диск или сетевая папка):\n{path}\n\nУкажите папку для сохранения заново.',
        'err_dir_permission': 'Нет прав на запись, либо каталог не существует:\n{path}\n\nВыберите другую папку.',
        'err_dir_other':    'Не удалось подготовить папку для сохранения:\n{path}\n\n{error}',
        'err_edge_error':   'Ошибка Edge TTS при синтезе речи',
        'err_ffmpeg_failed':'Ошибка ffmpeg при кодировании в MP3',
        'err_generic':      'Не удалось записать главу «{title}»',
    },
    'en': {
        'title':            'Record chapters to MP3',
        'desc':             'Choose chapters, a narrator voice and a folder — each '
                             'chapter is synthesized and saved as its own MP3 file '
                             'inside a folder named after the book.',
        'chapters':         'Chapters',
        'select_all':       'Select all',
        'select_none':      'Clear selection',
        'engine':           'TTS engine',
        'voice':            'Voice',
        'rate':             'Speed',
        'output':           'Save to',
        'browse':           'Browse…',
        'open_folder':      'Open folder',
        'save_path_hint':   'Files will be saved to: {path}',
        'title_merge_hint': 'The book title «{book}» will be added (with a pause) to the start of every file — the chapter text follows right after (its own heading is already in the text).',
        'record':           'Record',
        'stop':             'Stop',
        'close':            'Close',
        'no_voices':        'No installed voices for this engine',
        'no_engines':       'No TTS engines available',
        'no_chapters':      'Could not read the book chapters',
        'no_folder':        'Choose a folder to save to',
        'no_selection':     'Select at least one chapter',
        'skip_hint':        'annotation/footnotes — usually not needed',
        'status_idle':      'Choose chapters, voice and output folder',
        'status_progress':  'Chapter {chnum}/{chtotal} — sentence {done} of {total}',
        'status_done':      'Done: {count} chapter(s) recorded',
        'status_stopped':   'Stopped',
        'err_empty_text':   'This chapter has no text to read',
        'err_no_voice':     'Selected voice not found on disk',
        'err_no_piper':     'Piper binary not found',
        'err_no_ffmpeg':    'ffmpeg not found — install it to record MP3',
        'err_no_edge_tts':  'edge-tts module is not installed',
        'err_dir_title':    'Folder unavailable',
        'err_dir_not_found': 'Directory not found (an external drive or network share may be disconnected):\n{path}\n\nPlease choose the save folder again.',
        'err_dir_permission': 'No write permission, or the directory does not exist:\n{path}\n\nChoose a different folder.',
        'err_dir_other':    'Could not prepare the save folder:\n{path}\n\n{error}',
        'err_edge_error':   'Edge TTS error during synthesis',
        'err_ffmpeg_failed':'ffmpeg error while encoding MP3',
        'err_generic':      'Failed to record chapter "{title}"',
    },
}


def _pick_book_title(config, book_title_meta, book_path) -> str:
    """Название книги для озвучки/подпапки. Приоритет:
    1) библиотека (config.get_book_by_path) — title/author уже в нужном,
       вычищенном виде, как их видит пользователь в самом NovaReader;
    2) метаданные из файла книги (титульная страница), переданные JS;
    3) имя файла — только если ничего из вышеперечисленного нет."""
    if book_path:
        try:
            rec = config.get_book_by_path(str(book_path))
        except Exception:
            rec = None
        if rec:
            title = (rec.get('title') or '').strip()
            author = (rec.get('author') or '').strip()
            if title:
                return f'{title}. {author}' if author else title

    if isinstance(book_title_meta, dict):
        # На случай "языковой карты" {ru: "...", en: "..."} — берём первое
        # непустое значение (нормально JS уже разворачивает это в строку,
        # но подстраховываемся, чтобы в TTS не улетел сырой JSON-объект).
        book_title_meta = next((v for v in book_title_meta.values() if v), '')
    elif isinstance(book_title_meta, list):
        book_title_meta = next((v for v in book_title_meta if v), '')
    meta = str(book_title_meta or '').strip()
    if meta:
        return meta
    if not book_path:
        return 'Audiobook'
    return Path(str(book_path)).stem


class _RecordThread(QThread):
    """Фоновый поток записи выбранных глав — не блокирует UI читалки.

    Пишет главы одну за другой ОДНИМ recorder'ом (одна папка вывода на
    все главы), чтобы не пересоздавать AudiobookRecorder на каждую главу.
    """
    progress = pyqtSignal(int, int, int, int)   # chapter_num, chapter_total, done, total
    chapter_done = pyqtSignal(int, str)          # chapter_num, путь к mp3
    chapter_failed = pyqtSignal(int, str, str)   # chapter_num, title, код ошибки
    all_done = pyqtSignal(int)                   # сколько глав успешно записано
    stopped = pyqtSignal()

    def __init__(self, recorder: AudiobookRecorder, items):
        """items: список (index_1based, title, text, intro_text) — в
        порядке записи. intro_text озвучивается (с паузой) перед текстом
        КАЖДОЙ главы — только название книги, без "Глава N" (номер главы
        уже есть в тексте самой главы, повторять не нужно)."""
        super().__init__()
        self.recorder = recorder
        self.items = items
        self._was_stopped = False

    def run(self):
        total_chapters = len(self.items)
        recorded = 0
        for pos, (idx1, title, text, intro) in enumerate(self.items, start=1):
            if self.recorder._stop:
                self._was_stopped = True
                break
            try:
                path = self.recorder.record_chapter(
                    idx1, title, text,
                    progress_cb=lambda done, total, _pos=pos:
                        self.progress.emit(_pos, total_chapters, done, total),
                    intro_text=intro,
                )
            except Exception as e:
                self.chapter_failed.emit(pos, title, f'exception:{e}')
                continue
            if path:
                recorded += 1
                self.chapter_done.emit(pos, str(path))
            elif self.recorder.last_error == 'stopped':
                self._was_stopped = True
                break
            else:
                self.chapter_failed.emit(pos, title, self.recorder.last_error or 'unknown')
        if self._was_stopped:
            self.stopped.emit()
        else:
            self.all_done.emit(recorded)


class AudioRecorderWindow(QDialog):
    """Диалог записи одной или нескольких глав книги в MP3."""

    def __init__(self, config, reader_window, chapters,
                 current_section_index=None, book_title=''):
        # ВАЖНО: без родителя (parent=None) — иначе оконный менеджер
        # группирует диалог с окном читалки в один "объект" на панели
        # задач (нельзя свернуть/переключить по отдельности), даже если
        # заданы флаги Qt.WindowType.Window. Полностью независимое
        # top-level окно получается только когда у QDialog нет Qt-родителя.
        super().__init__(None)
        self.config = config
        self.reader_window = reader_window
        self.chapters = chapters or []
        self._thread = None
        self._stopping = False
        self._recorder = None
        self._chapter_numbers = {}
        self._book_title = _pick_book_title(
            config, book_title, getattr(reader_window, 'current_book', None))

        lang = config.get('language', 'ru')
        self._s = _ARW_S.get(lang, _ARW_S['ru'])

        self.setWindowTitle(self._t('title'))
        self.setMinimumWidth(520)
        self.setMinimumHeight(560)
        self.setModal(False)
        # Полноценное отдельное окно (со своей записью в диспетчере окон),
        # а не панель, "приклеенная" к окну читалки — можно независимо
        # свернуть/закрыть/переключить, не трогая ридер.
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        _bg, style = _build_style()
        self.setStyleSheet(style + self._extra_style())

        self._setup_ui()
        self._populate_chapters(current_section_index)
        self.title_merge_hint.setVisible(True)
        self.title_merge_hint.setText(self._t('title_merge_hint').format(book=self._book_title))
        self._populate_engines()
        self._update_save_path_hint()

    def _t(self, key):
        return self._s.get(key, key)

    def _extra_style(self):
        accent = _sys(QPalette.ColorRole.Highlight)
        border = _sys(QPalette.ColorRole.Mid)
        surface = _sys(QPalette.ColorRole.Base)
        text = _sys(QPalette.ColorRole.WindowText)
        return f"""
        QComboBox {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 10px;
            color: {text};
            font-size: 13px;
        }}
        QComboBox:hover {{ border-color: {accent}; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background: {surface};
            color: {text};
            selection-background-color: {accent};
            border: 1px solid {border};
            outline: none;
        }}
        QLineEdit {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 10px;
            color: {text};
            font-size: 13px;
        }}
        QListWidget {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            color: {text};
            font-size: 13px;
            outline: none;
        }}
        QListWidget::item {{ padding: 5px 6px; }}
        QListWidget::item:selected {{ background: transparent; }}
        QProgressBar {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            text-align: center;
            color: {text};
            font-size: 12px;
            height: 20px;
        }}
        QProgressBar::chunk {{
            background: {accent};
            border-radius: 5px;
        }}
        QSlider::groove:horizontal {{
            height: 4px; background: {border}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {accent}; width: 14px; height: 14px;
            margin: -5px 0; border-radius: 7px;
        }}
        """

    # ── UI ────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        desc = QLabel(self._t('desc'))
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; opacity: 0.7;")
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        border = _sys(QPalette.ColorRole.Mid)
        sep.setStyleSheet(f"background: {border}; max-height: 1px;")
        layout.addWidget(sep)

        # Главы (множественный выбор чекбоксами)
        chapters_header = QHBoxLayout()
        chapters_header.addWidget(self._label(self._t('chapters')))
        chapters_header.addStretch()
        select_all_btn = QPushButton(self._t('select_all'))
        select_all_btn.setFlat(True)
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.setStyleSheet("font-size: 11px; padding: 2px 6px; min-width: 0;")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        chapters_header.addWidget(select_all_btn)
        select_none_btn = QPushButton(self._t('select_none'))
        select_none_btn.setFlat(True)
        select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_none_btn.setStyleSheet("font-size: 11px; padding: 2px 6px; min-width: 0;")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        chapters_header.addWidget(select_none_btn)
        layout.addLayout(chapters_header)

        self.chapters_list = QListWidget()
        self.chapters_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.chapters_list, 1)

        self.title_merge_hint = QLabel("")
        self.title_merge_hint.setWordWrap(True)
        self.title_merge_hint.setStyleSheet("font-size: 11px; opacity: 0.7;")
        self.title_merge_hint.setVisible(False)
        layout.addWidget(self.title_merge_hint)

        # Движок + голос (в одну строку)
        row = QHBoxLayout()
        row.setSpacing(10)
        col_engine = QVBoxLayout()
        col_engine.addWidget(self._label(self._t('engine')))
        self.engine_combo = QComboBox()
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        col_engine.addWidget(self.engine_combo)
        row.addLayout(col_engine, 1)

        col_voice = QVBoxLayout()
        col_voice.addWidget(self._label(self._t('voice')))
        self.voice_combo = QComboBox()
        col_voice.addWidget(self.voice_combo)
        row.addLayout(col_voice, 1)
        layout.addLayout(row)

        # Скорость
        layout.addWidget(self._label(self._t('rate')))
        rate_row = QHBoxLayout()
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(50, 200)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self._on_rate_changed)
        rate_row.addWidget(self.rate_slider, 1)
        self.rate_label = QLabel("×1.0")
        self.rate_label.setFixedWidth(36)
        rate_row.addWidget(self.rate_label)
        layout.addLayout(rate_row)

        # Папка сохранения
        layout.addWidget(self._label(self._t('output')))
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        base_dir = self.config.get('audiobook_output_dir', '')
        if not base_dir:
            # По умолчанию — папка "audiobook" рядом с библиотекой книг
            # (там же, где программа хранит саму библиотеку), а не Downloads.
            try:
                base_dir = str(self.config.get_library_path() / 'audiobook')
            except Exception:
                try:
                    from config import Config
                    base_dir = str(Config._get_default_download_dir())
                except Exception:
                    base_dir = str(Path.home())
        self.output_edit.setText(base_dir)
        out_row.addWidget(self.output_edit, 1)
        browse_btn = QPushButton(self._t('browse'))
        browse_btn.clicked.connect(self._browse_folder)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        # Подсказка: итоговый путь с подпапкой книги
        self.save_path_hint = QLabel("")
        self.save_path_hint.setWordWrap(True)
        self.save_path_hint.setStyleSheet("font-size: 12px; opacity: 0.7;")
        layout.addWidget(self.save_path_hint)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self._t('status_idle'))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.status_label)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.open_folder_btn = QPushButton(self._t('open_folder'))
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.setVisible(False)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        close_btn = QPushButton(self._t('close'))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        self.record_btn = QPushButton(self._t('record'))
        self.record_btn.setDefault(True)
        self.record_btn.clicked.connect(self._on_record_clicked)
        btn_row.addWidget(self.record_btn)
        layout.addLayout(btn_row)

    def _label(self, text):
        lbl = QLabel(text.upper())
        sub = _blend(_sys(QPalette.ColorRole.WindowText),
                     _sys(QPalette.ColorRole.Window), 0.45)
        lbl.setStyleSheet(
            f"color:{sub}; font-size:11px; font-weight:700; "
            f"letter-spacing:0.6px; background:transparent;"
        )
        return lbl

    # ── Итоговая папка (с подпапкой книги) ───────────────────────
    def _target_dir(self):
        base = self.output_edit.text().strip()
        if not base:
            return None
        return Path(base) / safe_filename(self._book_title, max_len=120)

    def _update_save_path_hint(self):
        target = self._target_dir()
        if target:
            self.save_path_hint.setText(self._t('save_path_hint').format(path=str(target)))
        else:
            self.save_path_hint.setText("")

    # ── Наполнение списков ──────────────────────────────────────
    def _populate_chapters(self, current_section_index):
        self.chapters_list.clear()
        # Титульная секция («Название книги / Автор» на отдельной странице)
        # не показывается отдельной строкой — книга и так объявляется в
        # начале КАЖДОГО файла (только название, без номера главы),
        # отдельный файл под титульный лист не нужен.
        # Сквозная нумерация «настоящих» глав (без титульного листа,
        # аннотации и концевых сносок) — глава 1 всегда самый первый файл.
        self._chapter_numbers = {}
        n = 0
        for i, ch in enumerate(self.chapters):
            if ch.get('isTitlePage') or ch.get('skipByDefault') or ch.get('isPartHeading'):
                continue
            n += 1
            self._chapter_numbers[i] = n

        if not self.chapters:
            self.chapters_list.setEnabled(False)
            self.status_label.setText(self._t('no_chapters'))
            self.record_btn.setEnabled(False)
            return

        any_row = False
        for i, ch in enumerate(self.chapters):
            if ch.get('isTitlePage') or ch.get('isPartHeading'):
                continue  # отдельной строки нет — книга/часть объявляется в интро каждого файла
            any_row = True
            title = ch.get('title') or f"{i + 1}"
            skip_default = bool(ch.get('skipByDefault'))
            num = self._chapter_numbers.get(i)
            prefix = f"{num}." if num else "—"
            label = f"{prefix} {title}"
            if skip_default:
                label += f"  ({self._t('skip_hint')})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            is_current = (current_section_index is not None and
                          ch.get('sectionIndex') == current_section_index)
            # Аннотацию и концевые сноски-пояснения по умолчанию не отмечаем —
            # такие главы обычно не нужны в аудиокниге, но пользователь
            # может включить их вручную.
            checked = is_current and not skip_default
            item.setCheckState(Qt.CheckState.Checked if checked
                                else Qt.CheckState.Unchecked)
            if skip_default:
                sub = _blend(_sys(QPalette.ColorRole.WindowText),
                             _sys(QPalette.ColorRole.Window), 0.45)
                item.setForeground(QColor(sub))
            self.chapters_list.addItem(item)

        if not any_row:
            self.chapters_list.setEnabled(False)
            self.status_label.setText(self._t('no_chapters'))
            self.record_btn.setEnabled(False)
            return

        # Если ни одна глава не совпала с текущей позицией — отмечаем первую
        # обычную (не помеченную как «пропустить по умолчанию») главу, чтобы
        # список не открывался полностью пустым.
        if not any(self.chapters_list.item(i).checkState() == Qt.CheckState.Checked
                   for i in range(self.chapters_list.count())):
            for i in range(self.chapters_list.count()):
                idx = self.chapters_list.item(i).data(Qt.ItemDataRole.UserRole)
                if not self.chapters[idx].get('skipByDefault'):
                    self.chapters_list.item(i).setCheckState(Qt.CheckState.Checked)
                    break
            else:
                self.chapters_list.item(0).setCheckState(Qt.CheckState.Checked)

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.chapters_list.count()):
            self.chapters_list.item(i).setCheckState(state)

    def _checked_chapter_indexes(self):
        result = []
        for i in range(self.chapters_list.count()):
            item = self.chapters_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _populate_engines(self):
        self.engine_combo.clear()
        tts = getattr(self.reader_window, 'tts_controller', None)
        engines = tts.get_available_engines() if tts else []
        # Показываем только движки, для которых реально есть голоса —
        # иначе пользователь выберет движок и упрётся в пустой список голосов.
        usable = [e for e in engines if e.get('voice_count', 0) > 0]
        self._engines_data = {e['name']: e['voices'] for e in usable}

        if not usable:
            self.engine_combo.setEnabled(False)
            self.voice_combo.setEnabled(False)
            self.status_label.setText(self._t('no_engines'))
            self.record_btn.setEnabled(False)
            return

        for e in usable:
            self.engine_combo.addItem(e['name'], e['name'])
        # Предпочитаем Piper, если есть голоса — соответствует дефолту
        # AudiobookRecorder (engine='Piper').
        piper_idx = self.engine_combo.findData('Piper')
        self.engine_combo.setCurrentIndex(piper_idx if piper_idx >= 0 else 0)
        self._on_engine_changed()

    def _on_engine_changed(self):
        self.voice_combo.clear()
        engine_name = self.engine_combo.currentData()
        voices = self._engines_data.get(engine_name, [])
        if not voices:
            self.voice_combo.setEnabled(False)
            self.status_label.setText(self._t('no_voices'))
            self.record_btn.setEnabled(False)
            return
        self.voice_combo.setEnabled(True)
        self.record_btn.setEnabled(bool(self.chapters))
        for v in voices:
            self.voice_combo.addItem(v.get('name', v.get('id', '')), v.get('id'))
        if self.chapters:
            self.status_label.setText(self._t('status_idle'))

    def _on_rate_changed(self, value):
        self.rate_label.setText(f"×{value / 100:.1f}")

    # ── Папка вывода ─────────────────────────────────────────────
    def _browse_folder(self):
        from library_window import _make_styled_file_dialog, init_lib_colors
        # BG/SURFACE/TEXT/BORDER в library_window — глобальные переменные
        # модуля, которые обновляет init_lib_colors(config); без явного
        # вызова здесь они остаются на заводском значении по умолчанию и
        # не подхватывают тему, выбранную пользователем в настройках.
        init_lib_colors(self.config)
        start = self.output_edit.text() or str(Path.home())
        dlg = _make_styled_file_dialog(
            self, self._t('browse'), start, mode='folder', config=self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            files = dlg.selectedFiles()
            if files:
                folder = files[0]
                self.output_edit.setText(folder)
                self.config.set('audiobook_output_dir', folder)
                self.config.save()
                self._update_save_path_hint()

    def _open_output_folder(self):
        target = self._target_dir()
        if target and target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # ── Запись ────────────────────────────────────────────────
    def _on_record_clicked(self):
        if self._thread is not None and self._thread.isRunning():
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        indexes = self._checked_chapter_indexes()
        if not indexes:
            self.status_label.setText(self._t('no_selection'))
            return
        base_dir = self.output_edit.text().strip()
        if not base_dir:
            self.status_label.setText(self._t('no_folder'))
            return

        target_dir = self._target_dir()  # base_dir/<Название книги>
        engine_name = self.engine_combo.currentData()
        voice_id = self.voice_combo.currentData()
        rate = self.rate_slider.value() / 100.0

        # Заранее готовим папку сами (а не полагаемся на mkdir() внутри
        # AudiobookRecorder.__init__ без защиты) - если сама папка просто
        # отсутствует, создаём её как обычно. Но если пропала целая ветка
        # пути (например, отключили внешний диск/флешку или сетевую папку,
        # где раньше была настроена запись) - mkdir(parents=True) не может
        # создать несуществующий диск/точку монтирования и кидает
        # исключение. Раньше это ничем не ловилось и падало в терминал -
        # теперь показываем понятное окно вместо падения.
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            QMessageBox.warning(
                self, self._t('err_dir_title'),
                self._t('err_dir_permission').format(path=str(target_dir)))
            return
        except OSError as e:
            # Любая другая OSError при mkdir(parents=True) - на практике
            # почти всегда значит, что часть пути фундаментально
            # недоступна: не найден диск/точка монтирования (Windows -
            # отключили внешний диск), не смонтирована сетевая папка,
            # или часть пути на самом деле файл, а не директория. Раньше
            # это никак не ловилось и падало в терминал - теперь понятное
            # окно вместо падения.
            QMessageBox.warning(
                self, self._t('err_dir_title'),
                self._t('err_dir_not_found').format(path=str(target_dir)))
            return

        recorder = AudiobookRecorder(
            self.config, str(target_dir),
            engine=engine_name, voice=voice_id, rate=rate,
        )

        # Предварительные проверки — даём понятную причину сразу,
        # не дожидаясь запуска фонового потока.
        if engine_name == 'Piper':
            if not recorder.piper_bin:
                self.status_label.setText(self._t('err_no_piper'))
                return
            if not recorder.ffmpeg:
                self.status_label.setText(self._t('err_no_ffmpeg'))
                return
            if not recorder._voice_path():
                self.status_label.setText(self._t('err_no_voice'))
                return
        elif engine_name == 'Edge':
            try:
                import edge_tts  # noqa: F401
            except ImportError:
                self.status_label.setText(self._t('err_no_edge_tts'))
                return

        items = []
        # Нумерация — по порядку РЕАЛЬНО выбранных глав (аннотация/сноски,
        # если пользователь их всё же отметил вручную, тоже получают свой
        # порядковый номер и не наступают на номер другой главы — раньше
        # они могли совпасть с num обычной главы и файл перезаписывался).
        # Если в книге есть деление на части («Часть 1», «Часть 2»…) —
        # запоминаем текущую по ходу ПОЛНОГО списка глав (self.chapters,
        # а не только отмеченных) и добавляем её в интро вместе с
        # названием книги: «Книга. Автор. Часть N».
        current_part = None
        part_at = {}
        for i, ch in enumerate(self.chapters):
            if ch.get('isPartHeading'):
                current_part = (ch.get('title') or '').strip()
            part_at[i] = current_part

        for n, idx in enumerate(indexes, start=1):
            ch = self.chapters[idx]
            title = ch.get('title') or f"{idx + 1}"
            # Название книги (+ часть, если у книги есть деление на части) —
            # номер/название главы уже есть в тексте самой главы (заголовок),
            # повторять не нужно, иначе получается двойное произнесение.
            part = part_at.get(idx)
            intro = f'{self._book_title}. {part}' if part else self._book_title
            items.append((n, title, ch.get('text', ''), intro))

        self._recorder = recorder
        self._set_recording_state(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(
            self._t('status_progress').format(chnum=1, chtotal=len(items), done=0, total=1))

        self._thread = _RecordThread(recorder, items)
        self._thread.progress.connect(self._on_progress)
        self._thread.chapter_failed.connect(self._on_chapter_failed)
        self._thread.all_done.connect(self._on_all_done)
        self._thread.stopped.connect(self._on_stopped)
        self._thread.finished.connect(self._on_thread_finished)
        self._stopping = False
        self._thread.start()

    def _stop_record(self):
        if self._thread and self._thread.isRunning():
            self._stopping = True
            self._recorder.stop()
            self.record_btn.setEnabled(False)

    def _set_recording_state(self, recording: bool):
        self.chapters_list.setEnabled(not recording)
        self.engine_combo.setEnabled(not recording and self.engine_combo.count() > 0)
        self.voice_combo.setEnabled(not recording and self.voice_combo.count() > 0)
        self.rate_slider.setEnabled(not recording)
        self.record_btn.setEnabled(True)
        self.record_btn.setText(self._t('stop') if recording else self._t('record'))
        self.open_folder_btn.setVisible(False)

    def _on_progress(self, chnum, chtotal, done, total):
        # Общий процент: уже пройденные главы + доля текущей.
        overall = ((chnum - 1) + (done / total if total else 0)) / chtotal
        self.progress_bar.setValue(int(overall * 100))
        self.status_label.setText(
            self._t('status_progress').format(chnum=chnum, chtotal=chtotal, done=done, total=total))

    def _on_chapter_failed(self, pos, title, reason):
        if self._stopping:
            return
        key = f'err_{reason}' if not reason.startswith('exception:') else None
        if key and key in self._s:
            msg = self._t(key)
        else:
            msg = self._t('err_generic').format(title=title)
        self.status_label.setText(msg)

    def _on_all_done(self, count):
        self.progress_bar.setValue(100)
        self.status_label.setText(self._t('status_done').format(count=count))
        self.open_folder_btn.setVisible(count > 0)

    def _on_stopped(self):
        self.status_label.setText(self._t('status_stopped'))

    def _on_thread_finished(self):
        self._set_recording_state(False)
        self._thread = None
        self._stopping = False

    def closeEvent(self, event):
        if self._thread is not None and self._thread.isRunning():
            self._recorder.stop()
            self._thread.wait(5000)
        event.accept()
