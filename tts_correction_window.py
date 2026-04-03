from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt
import json


class TTSCorrectionWindow(QDialog):
    """Окно коррекции произношения TTS — список пар (неправильно → правильно)"""

    def __init__(self, config, reader_window):
        super().__init__(reader_window)
        self.config = config
        self.reader_window = reader_window
        self._loading = False

        self.setWindowTitle("Исправление произношения TTS")
        self.setMinimumSize(500, 400)
        self.setModal(False)

        self._setup_ui()
        self._load_corrections()

    def _js(self, code):
        """Выполнить JavaScript в reader"""
        if self.reader_window and self.reader_window.web_view and self.reader_window.web_view.page():
            self.reader_window.web_view.page().runJavaScript(code)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Описание
        desc_group = QGroupBox("Как это работает")
        desc_layout = QVBoxLayout(desc_group)
        desc_label = QLabel(
            "Добавьте слова или фразы, которые TTS читает неправильно.\n"
            "TTS заменит их на правильный вариант перед чтением.\n\n"
            "Пример: О,О → ОКЕЙ (чтобы читалось как «ОКЕЙ», а не «О запятая О»)"
        )
        desc_label.setWordWrap(True)
        desc_layout.addWidget(desc_label)
        layout.addWidget(desc_group)

        # Таблица пар
        table_group = QGroupBox("Список замен")
        table_layout = QVBoxLayout(table_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Неправильно", "Правильно", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 50)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: rgba(0,0,0,0.1);
                border: 1px solid rgba(0,0,0,0.15);
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background: rgba(0,0,0,0.05);
                padding: 8px;
                border: none;
                font-weight: 600;
            }
        """)
        table_layout.addWidget(self.table)

        # Кнопки управления таблицей
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("+ Добавить пару")
        self.add_btn.clicked.connect(self._add_row)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #1a73e8;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #1557b0; }
        """)
        btn_layout.addWidget(self.add_btn)
        
        btn_layout.addStretch()
        
        self.delete_btn = QPushButton("Удалить выбранное")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #d93025;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #b31412; }
        """)
        btn_layout.addWidget(self.delete_btn)
        
        table_layout.addLayout(btn_layout)
        layout.addWidget(table_group)

        # Кнопки внизу
        bottom_layout = QHBoxLayout()
        
        self.info_label = QLabel("0 пар")
        self.info_label.setStyleSheet("color: #666; font-size: 12px;")
        bottom_layout.addWidget(self.info_label)
        
        bottom_layout.addStretch()
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self._save_corrections)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #1a73e8;
                color: white;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 500;
            }
            QPushButton:hover { background: #1557b0; }
            QPushButton:disabled {
                background: #3c4043;
                color: #666;
            }
        """)
        bottom_layout.addWidget(self.save_btn)
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.2); }
        """)
        bottom_layout.addWidget(self.close_btn)
        
        layout.addLayout(bottom_layout)

    def _add_row(self, wrong="", correct=""):
        """Добавить новую строку в таблицу"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        wrong_item = QTableWidgetItem(wrong)
        wrong_item.setFlags(wrong_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, wrong_item)
        
        correct_item = QTableWidgetItem(correct)
        correct_item.setFlags(correct_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 1, correct_item)
        
        # Кнопка удаления
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(32, 32)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #999;
                border-radius: 16px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(217, 48, 37, 0.15);
                color: #d93025;
            }
        """)
        del_btn.clicked.connect(lambda: self._delete_row(row))
        self.table.setCellWidget(row, 2, del_btn)
        
        self._update_info()

    def _delete_row(self, row):
        """Удалить строку по индексу"""
        self.table.removeRow(row)
        self._update_info()

    def _delete_selected(self):
        """Удалить выбранную строку"""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            QMessageBox.information(self, "Удаление", "Выберите строку для удаления")
            return
        
        row = selected_rows[0].row()
        self._delete_row(row)

    def _load_corrections(self):
        """Загрузить список коррекций из конфига"""
        self._loading = True
        try:
            corrections = self.config.get('tts_corrections', [])
            self.table.setRowCount(0)
            for item in corrections:
                self._add_row(item.get('wrong', ''), item.get('correct', ''))
        finally:
            self._loading = False

    def _save_corrections(self):
        """Сохранить список коррекций в конфиг и отправить в JS"""
        corrections = []
        for row in range(self.table.rowCount()):
            wrong_item = self.table.item(row, 0)
            correct_item = self.table.item(row, 1)
            wrong = wrong_item.text().strip() if wrong_item else ''
            correct = correct_item.text().strip() if correct_item else ''
            if wrong and correct:
                corrections.append({'wrong': wrong, 'correct': correct})
        
        self.config.set('tts_corrections', corrections)
        
        # Отправить в JS для обновления
        self._js(f"""
            if (window.updateTTSCorrections) {{
                window.updateTTSCorrections({json.dumps(corrections)});
            }}
        """)
        
        # Визуальное подтверждение
        orig_text = self.save_btn.text()
        self.save_btn.setText("✓ Сохранено")
        self.save_btn.setEnabled(False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (
            self.save_btn.setText(orig_text),
            self.save_btn.setEnabled(True)
        ))
        
        self._update_info()

    def _update_info(self):
        """Обновить информацию о количестве пар"""
        count = self.table.rowCount()
        self.info_label.setText(f"{count} {self._plural(count, 'пара', 'пары', 'пар')}")

    @staticmethod
    def _plural(n, one, two, five):
        """Склонение слов: n пара/пары/пар"""
        n = abs(n) % 100
        n1 = n % 10
        if n > 10 and n < 20:
            return five
        if n1 > 1 and n1 < 5:
            return two
        if n1 == 1:
            return one
        return five
