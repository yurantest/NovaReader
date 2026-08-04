from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox,
                             QWidget, QFrame, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
import json


def _sys(role, group=QPalette.ColorGroup.Normal):
    return QApplication.palette().color(group, role).name()

def _blend(c1, c2, r=0.5):
    a, b = QColor(c1), QColor(c2)
    return QColor(int(a.red()*(1-r)+b.red()*r),
                  int(a.green()*(1-r)+b.green()*r),
                  int(a.blue()*(1-r)+b.blue()*r)).name()

def _build_style():
    bg      = _sys(QPalette.ColorRole.Window)
    surface = _sys(QPalette.ColorRole.Base)
    text    = _sys(QPalette.ColorRole.WindowText)
    border  = _sys(QPalette.ColorRole.Mid)
    accent  = _sys(QPalette.ColorRole.Highlight)
    sub     = _blend(text, bg, 0.45)
    hover   = _blend(bg, text, 0.06)
    sel_bg  = _sys(QPalette.ColorRole.Highlight)
    sel_txt = _sys(QPalette.ColorRole.HighlightedText)
    alt     = _blend(bg, surface, 0.5)

    return bg, f"""
QDialog {{
    background: {bg};
    color: {text};
    font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', sans-serif;
}}
QLabel {{ color: {text}; background: transparent; }}

/* Вкладки */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 6px;
    background: {surface};
}}
QTabBar::tab {{
    background: {bg};
    color: {sub};
    padding: 7px 20px;
    border: 1px solid {border};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: {surface};
    color: {text};
    font-weight: 600;
    border-bottom: 1px solid {surface};
}}
QTabBar::tab:hover:!selected {{ background: {hover}; color: {text}; }}

/* Таблица */
QTableWidget {{
    background: {surface};
    alternate-background-color: {alt};
    color: {text};
    gridline-color: {border};
    border: none;
    border-radius: 0;
    selection-background-color: {sel_bg};
    selection-color: {sel_txt};
    font-size: 13px;
    outline: none;
}}
QTableWidget::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:selected {{
    background: {sel_bg};
    color: {sel_txt};
}}
QHeaderView {{
    background: {bg};
    border: none;
}}
QHeaderView::section {{
    background: {bg};
    color: {sub};
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {border};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}}
QScrollBar:vertical {{
    width: 6px; background: transparent;
}}
QScrollBar::handle:vertical {{
    background: {border}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px; background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: {border}; border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* Кнопки */
QPushButton {{
    background: {_blend(bg, surface, 0.5)};
    border: 1px solid {border};
    border-radius: 6px;
    color: {text};
    padding: 6px 16px;
    font-size: 13px;
    min-width: 80px;
}}
QPushButton:hover {{ background: {hover}; border-color: {accent}; }}
QPushButton:pressed {{ background: {bg}; }}
QPushButton:default {{
    background: {accent};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton:default:hover {{ background: {_blend(accent, '#ffffff', 0.15)}; }}
QPushButton:disabled {{ color: {sub}; border-color: {border}; }}
"""


class TTSCorrectionWindow(QDialog):
    """Окно коррекции произношения TTS — глобальные и книжные замены"""

    def __init__(self, config, reader_window):
        super().__init__(reader_window)
        self.config = config
        self.reader_window = reader_window
        self._loading = False
        self._book_path = getattr(reader_window, 'current_book', None)

        self.setWindowTitle("Исправление произношения TTS")
        self.setMinimumSize(560, 480)
        self.setModal(False)

        # Применяем системную тему
        bg, style = _build_style()
        self.setStyleSheet(style)

        self._setup_ui()
        self._load_corrections()

    def _js(self, code):
        if self.reader_window and self.reader_window.web_view:
            self.reader_window.web_view.page().runJavaScript(code)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        # Описание
        desc = QLabel(
            "Добавьте слова или фразы, которые TTS читает неправильно.\n"
            "Глобальные замены применяются ко всем книгам, "
            "книжные — только к текущей."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; opacity: 0.7;")
        layout.addWidget(desc)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        bg  = QApplication.palette().color(QPalette.ColorGroup.Normal, QPalette.ColorRole.Mid).name()
        sep.setStyleSheet(f"background: {bg}; max-height: 1px;")
        layout.addWidget(sep)

        # Вкладки
        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_table_tab('global'), "Глобальные")
        book_label = "Эта книга" if self._book_path else "Эта книга (нет)"
        self.tabs.addTab(self._make_table_tab('book'), book_label)
        if not self._book_path:
            self.tabs.setTabEnabled(1, False)
        layout.addWidget(self.tabs, 1)

        # Нижняя панель
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 12px;")
        btn_layout.addWidget(self.info_label)
        btn_layout.addStretch()

        add_btn = QPushButton("+ Добавить")
        add_btn.clicked.connect(self._add_row)
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(del_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self._save_corrections)
        self.save_btn.setDefault(True)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        self.tabs.currentChanged.connect(self._update_info)

    def _make_table_tab(self, scope: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Неправильно", "Правильно", "Без регистра"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 90)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.verticalHeader().setDefaultSectionSize(34)

        layout.addWidget(table)
        setattr(self, f'_{scope}_table', table)
        return widget

    def _current_table(self) -> QTableWidget:
        scope = 'global' if self.tabs.currentIndex() == 0 else 'book'
        return getattr(self, f'_{scope}_table')

    def _add_row(self, wrong="", correct="", case_insensitive=True, table=None):
        t = table or self._current_table()
        row = t.rowCount()
        t.insertRow(row)
        t.setItem(row, 0, QTableWidgetItem(wrong))
        t.setItem(row, 1, QTableWidgetItem(correct))

        from settings_window import CheckMark  # тот же виджет, что и в остальном приложении
        accent = _sys(QPalette.ColorRole.Highlight)
        border = _sys(QPalette.ColorRole.Mid)
        cb = CheckMark(accent=accent, border=border)
        cb.setChecked(case_insensitive)
        cb.setToolTip("Без учёта регистра")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        h = QHBoxLayout(container)
        h.addWidget(cb)
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.setContentsMargins(0, 0, 0, 0)
        t.setCellWidget(row, 2, container)
        self._update_info()

    def _delete_selected(self):
        t = self._current_table()
        rows = sorted(set(i.row() for i in t.selectedItems()), reverse=True)
        if not rows:
            QMessageBox.information(self, "Удаление", "Выберите строку для удаления")
            return
        for row in rows:
            t.removeRow(row)
        self._update_info()

    def _load_corrections(self):
        self._loading = True
        try:
            for item in self.config.get_corrections_global():
                self._add_row(item.get('wrong',''), item.get('correct',''),
                               item.get('case_insensitive', True), self._global_table)
            if self._book_path:
                for item in self.config.get_corrections_for_book(self._book_path):
                    self._add_row(item.get('wrong',''), item.get('correct',''),
                                   item.get('case_insensitive', True), self._book_table)
        finally:
            self._loading = False
        self._update_info()

    def _read_table(self, table: QTableWidget) -> list:
        result = []
        for row in range(table.rowCount()):
            wrong   = (table.item(row, 0) or QTableWidgetItem()).text().strip()
            correct = (table.item(row, 1) or QTableWidgetItem()).text().strip()
            if not wrong:
                continue
            container = table.cellWidget(row, 2)
            from settings_window import CheckMark
            cb = container.findChild(CheckMark) if container else None
            result.append({'wrong': wrong, 'correct': correct,
                           'case_insensitive': cb.isChecked() if cb else True})
        return result

    def _save_corrections(self):
        global_list = self._read_table(self._global_table)
        self.config.set_corrections_global(global_list)
        if self._book_path:
            book_list = self._read_table(self._book_table)
            self.config.set_corrections_for_book(self._book_path, book_list)

        all_corrections = global_list + (
            self._read_table(self._book_table) if self._book_path else [])
        self._js(f"if(window.updateTTSCorrections){{window.updateTTSCorrections({json.dumps(all_corrections)});}}")

        orig = self.save_btn.text()
        self.save_btn.setText("✓ Сохранено")
        self.save_btn.setEnabled(False)
        QTimer.singleShot(1500, lambda: (
            self.save_btn.setText(orig),
            self.save_btn.setEnabled(True)
        ))
        self._update_info()

    def _update_info(self):
        t = self._current_table()
        count = t.rowCount()
        scope = "глобальных" if self.tabs.currentIndex() == 0 else "книжных"
        self.info_label.setText(f"{count} {scope} замен")

    def closeEvent(self, event):
        self._save_corrections()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._save_corrections()
        else:
            super().keyPressEvent(event)
