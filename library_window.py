from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QScrollArea, QGridLayout, QLabel,
                             QFileDialog, QMessageBox, QProgressDialog,
                             QFrame, QLineEdit, QMenu, QComboBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QAction
from pathlib import Path
import shutil, json, re
from book_parser import BookParser
from zip_handler import ZipHandler
from book_normalizer import normalize_book, SUPPORTED as NORMALIZER_SUPPORTED
from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal as _Signal

BG      = "#1e1e2e"
SURFACE = "#282838"
BORDER  = "#3a3a50"
ACCENT  = "#1a73e8"
TEXT    = "#e8eaed"
SUB     = "#9aa0a6"
SERIES  = "#7ecfff"
TOOLBAR = "#252535"
CARD_W  = 170
CARD_H  = 280
CARD_S  = 14


# Unicode fallback symbols if Material Icons not available
_ICON_FALLBACK = {
    'add':          '+',
    'folder_open':  '⊞',
    'delete_sweep': '⌫',
    'refresh':      '↻',
    'search':       '⌕',
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

    def __init__(self, book_info):
        super().__init__()
        self.book_info = book_info
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
            self.clicked.emit(self.book_info)

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
                open_menu = menu.addMenu("📖 Открыть в...")
                
                # Приоритет форматов: FB2 > EPUB > остальные
                priority = ['fb2', 'epub', 'mobi', 'azw3', 'pdf', 'cbz', 'cbr']
                for fmt in priority:
                    if fmt in book_formats:
                        fpath = book_formats[fmt]
                        act = QAction(f"{'✅ ' if fmt == 'fb2' else ''}{fmt.upper()} — {fpath.name}", self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._open_book_format(fp))
                        open_menu.addAction(act)
                
                menu.addSeparator()

                # Нормализовать для TTS (подменю по форматам)
                norm_formats = {fmt: fp for fmt, fp in book_formats.items()
                                if ('.' + fmt) in NORMALIZER_SUPPORTED}
                if norm_formats:
                    if len(norm_formats) == 1:
                        fmt, fpath = next(iter(norm_formats.items()))
                        act = QAction(f"🔧 Нормализовать для TTS ({fmt.upper()})", self)
                        act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                        menu.addAction(act)
                    else:
                        norm_menu = menu.addMenu("🔧 Нормализовать для TTS")
                        for fmt, fpath in norm_formats.items():
                            act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                            act.triggered.connect(lambda checked, fp=str(fpath): self._normalize_book(fp))
                            norm_menu.addAction(act)

                menu.addSeparator()
                
                # Подменю "Удалить формат"
                delete_menu = menu.addMenu("🗑️ Удалить формат")
                for fmt, fpath in sorted(book_formats.items()):
                    act = QAction(f"{fmt.upper()} — {fpath.name}", self)
                    act.triggered.connect(lambda checked, fp=str(fpath), fm=fmt: self._delete_format(fp, fm))
                    delete_menu.addAction(act)
            else:
                # Один формат
                src_path = str(book_path)
                ext = book_path.suffix.lower()
                if ext in NORMALIZER_SUPPORTED:
                    act = QAction("🔧 Нормализовать для TTS", self)
                    act.triggered.connect(lambda checked, fp=src_path: self._normalize_book(fp))
                    menu.addAction(act)
                    menu.addSeparator()
                act = QAction("🗑️ Удалить книгу", self)
                act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
                menu.addAction(act)
        else:
            act = QAction("🗑️ Удалить книгу", self)
            act.triggered.connect(lambda: self.delete_req.emit(self.book_info))
            menu.addAction(act)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _open_book_format(self, file_path):
        """Открыть книгу в указанном формате."""
        self.clicked.emit(file_path)
    
    def _delete_format(self, file_path, format_name):
        """Удалить конкретный формат книги."""
        title = self.book_info.get("title", "Книга")[:40]
        r = QMessageBox.question(
            self, f"Удалить формат {format_name.upper()}",
            f'Удалить "{title}" в формате {format_name.upper()}?\n\nФайл будет удалён с диска.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        
        try:
            fp = Path(file_path)
            if fp.exists():
                fp.unlink()
                print(f"[Library] Удалён формат {format_name}: {fp}")
                
                # Удаляем запись из библиотеки
                self.config._library = [b for b in self.config.get_books()
                                        if b.get("file_path") != str(fp)]
                self.config.save_library()
                
                # Если папка пуста — удаляем её
                book_dir = fp.parent
                if book_dir.exists() and not any(book_dir.iterdir()):
                    # Удаляем также обложку если есть
                    cover = book_dir / "cover.jpg"
                    if cover.exists():
                        cover.unlink()
                    # Пытаемся удалить папку автора если пуста
                    author_dir = book_dir.parent
                    lib_root = self.config.get_library_path()
                    if author_dir != lib_root and not any(author_dir.iterdir()):
                        author_dir.rmdir()
        except Exception as e:
            print(f"[Library] Delete format error: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить файл:\n{e}")
        
        # Обновляем библиотеку
        if hasattr(self.parent(), '_on_library_updated'):
            self.parent()._on_library_updated()

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
        dlg.setWindowTitle("🔧 Нормализация книги")
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
        open_btn  = QPushButton("📂 Открыть папку")
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
                log_box.append(f"✅ Готово! Файл сохранён: {dst}")
                open_btn.setEnabled(True)
                open_btn.clicked.connect(lambda: __import__('subprocess').Popen(
                    ['xdg-open' if __import__('sys').platform != 'win32' else 'explorer',
                     str(dst.parent)]))
            else:
                log_box.append("")
                log_box.append("❌ Нормализация завершилась с ошибкой")

        worker.log_line.connect(on_log)
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
            fill.setStyleSheet(f"background:{ACCENT};border-radius:2px;")
            lay.addWidget(bg)


class LibraryWindow(QMainWindow):
    book_selected = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
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
        cw = QWidget()
        cw.setStyleSheet(f"background:{BG};")
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._make_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
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
        scroll.setWidget(self.books_container)
        root.addWidget(scroll)

        self.statusBar().setStyleSheet(
            f"QStatusBar{{background:{TOOLBAR};color:{SUB};"
            f"font-size:12px;padding:2px 8px;}}")
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet(f"color:{SUB};")
        self.statusBar().addWidget(self.status_label)

    def _make_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            f"QWidget{{background:{TOOLBAR};border-bottom:1px solid {BORDER};}}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0); lay.setSpacing(4)

        self.add_btn     = _mbtn("add",          "Добавить книги")
        self.scan_btn    = _mbtn("folder_open",  "Сканировать папку")
        self.cleanup_btn = _mbtn("delete_sweep", "Очистить несуществующие записи")
        self.export_btn  = _mbtn("content_copy", "Экспорт заметок")
        self.refresh_btn = _mbtn("refresh",      "Обновить")

        self.add_btn.clicked.connect(self.add_books)
        self.scan_btn.clicked.connect(self.scan_folder)
        self.cleanup_btn.clicked.connect(self.cleanup_library)
        self.export_btn.clicked.connect(self.export_notes)
        self.refresh_btn.clicked.connect(self._load_books)

        for btn in (self.add_btn, self.scan_btn, self.cleanup_btn):
            lay.addWidget(btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"color:{BORDER};")
        lay.addWidget(sep)
        lay.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Поиск по названию, автору, серии...")
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
        self.sort_combo.addItems(["По последнему чтению", "По дате добавления", "По названию", "По автору"])
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
        self.format_filter.addItems(["Все форматы", "EPUB", "FB2", "PDF", "MOBI", "CBZ", "Комиксы"])
        self.format_filter.setFixedSize(140, 34)
        self.format_filter.setStyleSheet(
            f"QComboBox{{background:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:17px;"
            f"padding:0 14px;font-size:13px;}}"
            f"QComboBox:focus{{border:1px solid {ACCENT};}}")
        self.format_filter.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.format_filter)
        
        lay.addWidget(self.refresh_btn)
        return bar

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
        valid = [b for b in books
                 if b.get("file_path") and Path(b["file_path"]).exists()]
        if len(valid) != len(books):
            self.config._library = valid
            self.config.save_library()
        # Сортировка по умолчанию - по последнему чтению
        self._all_books = self._sort_books(valid)
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        self._display(self._filter(self._all_books, q))

    def _filter(self, books, q):
        q = q.strip().lower()
        if not q: return books
        return [b for b in books
                if q in " ".join([b.get("title", ""), b.get("author", ""),
                                   b.get("series", "") or ""]).lower()]

    def _sort_books(self, books):
        """Сортировка книг по выбранному критерию."""
        sort_type = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "По последнему чтению"
        
        if sort_type == "По последнему чтению":
            # Сортируем по last_read, а если его нет — по added
            # Самые последние открытые книги — первые
            def sort_key(book):
                # Используем last_read если есть, иначе added
                return book.get("last_read") or book.get("added") or ""
            return sorted(books, key=sort_key, reverse=True)
        
        elif sort_type == "По дате добавления":
            return sorted(books, key=lambda x: x.get("added", ""), reverse=True)
        
        elif sort_type == "По названию":
            return sorted(books, key=lambda x: x.get("title", "").lower())
        
        elif sort_type == "По автору":
            return sorted(books, key=lambda x: (x.get("author", "") or "").lower())
        
        return books

    def _on_sort_changed(self):
        """Изменение типа сортировки."""
        self._display(self._filter(self._all_books, self.search_box.text() if hasattr(self, "search_box") else ""))

    def _on_library_updated(self):
        """Обновление списка книг при изменении библиотеки (real-time)."""
        # Защита от рекурсивного вызова
        if hasattr(self, '_updating') and self._updating:
            print("[Library] ⚠️ Защита от рекурсивного _on_library_updated()")
            return
        
        self._updating = True
        try:
            # Перезагружаем книги с сохранением текущей позиции прокрутки
            # Находим QScrollArea через books_container
            scroll_area = self.books_container.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()

            pos = scroll_area.verticalScrollBar().value() if scroll_area else 0

            books = self.config.get_books()
            valid = [b for b in books
                     if b.get("file_path") and Path(b["file_path"]).exists()]
            self._all_books = self._sort_books(valid)
            self._display(self._filter(self._all_books, self.search_box.text() if hasattr(self, "search_box") else ""))

            # Восстанавливаем позицию прокрутки
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
            card = BookCard(book)
            card.clicked.connect(self._on_book_clicked)
            card.delete_req.connect(self._on_delete_book)
            self.books_layout.addWidget(card, idx // cols, idx % cols)
        n, shown = len(self._all_books), len(books)
        self.status_label.setText(
            f"Показано: {shown} из {n}" if shown != n else f"Книг: {n}")

    def _on_search(self, q):
        self._display(self._filter(self._all_books, q))

    def _on_filter_changed(self, format_name):
        """Фильтрация по формату книги."""
        q = self.search_box.text() if hasattr(self, "search_box") else ""
        books = self._filter(self._all_books, q)
        
        if format_name != "Все форматы":
            if format_name == "Комиксы":
                # Комиксы и манга = CBZ + CBR
                books = [b for b in books if b.get('format', '').lower() in ('cbz', 'cbr', 'comic')]
            else:
                books = [b for b in books if b.get('format', '').upper() == format_name.upper()]
        
        self._display(books)

    def _on_book_clicked(self, book_info):
        """Открытие книги с приоритетом FB2 > EPUB > остальные."""
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
        """Удаление книги (всех форматов в папке)."""
        title = book_info.get("title", "Книга")[:60]
        r = QMessageBox.question(
            self, "Удалить книгу",
            f'Удалить "{title}"?\n\nВсе форматы книги и папка будут удалены с диска.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return

        fp = Path(book_info.get("file_path", ""))
        book_dir = fp.parent if fp.exists() else None
        
        # Находим все записи этой книги в библиотеке (все форматы)
        book_key = self._get_book_key(book_info)
        books_to_remove = []
        for book in self.config.get_books():
            if self._get_book_key(book) == book_key:
                books_to_remove.append(book)
        
        # Удаляем записи из библиотеки
        self.config._library = [b for b in self.config.get_books()
                                if b not in books_to_remove]
        self.config.save_library()

        # Удаляем файлы
        try:
            if book_dir and book_dir.exists():
                # Находим все файлы книг в папке
                book_files = []
                for f in book_dir.iterdir():
                    if f.suffix.lower() in ['.epub', '.fb2', '.mobi', '.azw3', '.pdf', '.cbz', '.cbr']:
                        book_files.append(f)
                
                if book_files:
                    # Удаляем все файлы книг
                    for bf in book_files:
                        bf.unlink()
                        print(f"[Library] Удалён файл: {bf}")
                    
                    # Удаляем обложку
                    cover = book_dir / "cover.jpg"
                    if cover.exists():
                        cover.unlink()
                    
                    # Удаляем metadata.json
                    metadata = book_dir / "metadata.json"
                    if metadata.exists():
                        metadata.unlink()
                    
                    # Пытаемся удалить папку книги
                    try:
                        book_dir.rmdir()
                        print(f"[Library] Удалена папка: {book_dir}")
                    except OSError:
                        # Папка не пуста — оставляем
                        pass
                    
                    # Пытаемся удалить папку автора если пуста
                    author_dir = book_dir.parent
                    lib_root = self.config.get_library_path()
                    if author_dir != lib_root and author_dir.exists() and not any(author_dir.iterdir()):
                        try:
                            author_dir.rmdir()
                            print(f"[Library] Удалена папка автора: {author_dir}")
                        except OSError:
                            pass
            elif fp.exists():
                fp.unlink()
        except Exception as e:
            print(f"[Library] Delete error: {e}")
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось удалить файлы:\n{e}")

        # Удаляем обложку из кэша
        cp = book_info.get("cover_path")
        if cp:
            try: Path(cp).unlink(missing_ok=True)
            except Exception: pass
        
        self._load_books()

    # ── добавление ────────────────────────────────────────────
    def add_books(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите книги", str(self.config.get_library_path()),
            "Книги (*.epub *.fb2 *.fb2.zip *.zip *.mobi *.azw3 *.cbz *.pdf);;Комиксы (*.cbz *.cbr);;Манга (*.cbz *.cbr);;PDF (*.pdf);;Все файлы (*)")
        if files: self._process_books(files)

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Папка", str(self.config.get_library_path()))
        if not folder: return
        books = []
        for ext in ["*.epub", "*.fb2", "*.fb2.zip", "*.zip", "*.mobi", "*.cbz", "*.pdf"]:
            books.extend(Path(folder).rglob(ext))
        if not books:
            QMessageBox.information(self, "Информация", "Книги не найдены"); return
        r = QMessageBox.question(
            self, "Сканирование", f"Найдено {len(books)} книг. Добавить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._process_books([str(b) for b in books])

    def cleanup_library(self):
        books = self.config.get_books()
        miss  = [b for b in books
                 if not (b.get("file_path") and Path(b["file_path"]).exists())]
        if not miss:
            QMessageBox.information(self, "Очистка", "Все записи актуальны."); return
        r = QMessageBox.question(
            self, "Очистка", f"Удалить {len(miss)} несуществующих записей?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.config._library = [b for b in books if b not in miss]
            self.config.save_library(); self._load_books()

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
        
        self.txt_radio = QRadioButton("📄 TXT — простой текст")
        self.txt_radio.setChecked(True)
        layout.addWidget(self.txt_radio)
        
        self.md_radio = QRadioButton("📝 Markdown — с форматированием")
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
                f"✅ Заметки успешно экспортированы!\n\n"
                f"📊 Экспортировано книг: {count}\n"
                f"📁 Файл сохранён:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"❌ Не удалось экспортировать заметки:\n{e}"
            )

    def _process_books(self, file_paths):
        expanded = []
        for fp in file_paths: expanded.extend(self._expand_file(fp))
        if not expanded:
            QMessageBox.warning(self, "Нет книг", "Книги не найдены."); return
        prog = QProgressDialog(
            "Добавление книг...", "Отмена", 0, len(expanded), self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        added = skipped = 0
        for i, (src_path, tmp_cleanup) in enumerate(expanded):
            if prog.wasCanceled(): break
            prog.setValue(i)
            prog.setLabelText(f"Обработка: {Path(src_path).name}")
            try:
                meta = self.parser.extract_metadata(src_path) or {}
                meta.setdefault("title", Path(src_path).stem)
                meta.setdefault("author", "Неизвестен")
                
                # Проверяем, есть ли уже книга с такими же метаданными
                book_key = self._get_book_key(meta)
                existing_book = self._find_existing_book(book_key)
                
                dest = self._copy_structured(src_path, meta, existing_book)
                if not dest: skipped += 1; continue
                cover_data = self.parser.extract_cover(src_path)
                cover_path = None
                if cover_data:
                    cover_path = dest.parent / "cover.jpg"
                    cover_path.write_bytes(cover_data)
                    (self.config.covers_dir / f"{dest.stem}.jpg").write_bytes(cover_data)
                (dest.parent / "metadata.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                meta["file_path"]  = str(dest)
                meta["format"]     = dest.suffix.lower().lstrip(".")
                meta["cover_path"] = str(cover_path) if cover_path else ""
                self.config.add_book(meta); added += 1
            except Exception as e:
                print(f"[Library] error: {e}"); skipped += 1
            finally:
                if tmp_cleanup and Path(tmp_cleanup).exists():
                    shutil.rmtree(tmp_cleanup, ignore_errors=True)
        prog.setValue(len(expanded))
        QMessageBox.information(
            self, "Готово", f"Добавлено: {added}\nПропущено: {skipped}")
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
            except Exception as e: print(f"[Library] zip: {e}")
            return results
        # CBR (RAR archives) - requires rarfile or unrar
        if p.suffix.lower() == ".cbr":
            print(f"[Library] CBR format requires unrar: {p}")
            return [(str(p), None)]
        return [(str(p), None)]

    @staticmethod
    def _safe_name(name, max_len=60):
        return re.sub(r'[<>:"/\\|?*]', "_", name).strip(". ")[:max_len] or "Без_названия"

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
                # Используем существующую папку книги
                existing_path = Path(existing_book.get("file_path", ""))
                book_dir = existing_path.parent
            else:
                # Создаём новую папку
                lib = self.config.get_library_path()
                author = self._safe_name(meta.get("author") or "Неизвестен")
                title  = meta.get("title") or src.stem
                series = meta.get("series"); snum = meta.get("series_number")
                if series:
                    n = ""
                    if snum is not None:
                        try:
                            v = float(snum)
                            n = f" #{int(v) if v == int(v) else v}"
                        except Exception: n = f" #{snum}"
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

    def closeEvent(self, e):
        self.config.set("library_width",  self.width())
        self.config.set("library_height", self.height())
        e.accept()
