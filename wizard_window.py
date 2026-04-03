from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QFileDialog,
                             QGroupBox, QButtonGroup, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path


class WelcomeWizard(QDialog):
    """Окно приветствия при первом запуске"""

    setup_completed = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        from config import Config
        self.selected_path = str(Config._get_default_library_dir())

        self.setWindowTitle("Добро пожаловать")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("📚 Добро пожаловать!")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Описание
        desc = QLabel(
            "Похоже, вы запускаете приложение впервые.\n"
            "Давайте настроим вашу библиотеку."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; margin-bottom: 20px;")
        layout.addWidget(desc)

        # Группа выбора папки
        folder_group = QGroupBox("Папка для хранения книг")
        folder_layout = QVBoxLayout(folder_group)

        # Вариант 1: Папка по умолчанию
        self.default_radio = QRadioButton("Использовать папку по умолчанию")
        self.default_radio.setChecked(True)
        self.default_radio.toggled.connect(self._on_radio_toggled)
        folder_layout.addWidget(self.default_radio)

        from config import Config
        _def_lib = Config._get_default_library_dir()
        default_path_label = QLabel(str(_def_lib))
        default_path_label.setStyleSheet("color: #1a73e8; font-family: monospace; margin-left: 20px;")
        folder_layout.addWidget(default_path_label)

        # Вариант 2: Выбрать другую папку
        self.custom_radio = QRadioButton("Выбрать другую папку")
        self.custom_radio.toggled.connect(self._on_radio_toggled)
        folder_layout.addWidget(self.custom_radio)

        # Кнопка выбора папки (изначально скрыта)
        self.choose_folder_btn = QPushButton("📁 Выбрать папку...")
        self.choose_folder_btn.setVisible(False)
        self.choose_folder_btn.clicked.connect(self._choose_folder)
        folder_layout.addWidget(self.choose_folder_btn)

        # Метка с выбранным путем
        self.selected_path_label = QLabel("")
        self.selected_path_label.setStyleSheet("color: #1a73e8; font-family: monospace; margin-left: 20px;")
        self.selected_path_label.setVisible(False)
        folder_layout.addWidget(self.selected_path_label)

        layout.addWidget(folder_group)

        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.next_btn = QPushButton("Далее →")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1765cc;
            }
        """)
        self.next_btn.clicked.connect(self._on_next)
        button_layout.addWidget(self.next_btn)

        layout.addLayout(button_layout)

    def _on_radio_toggled(self):
        if self.default_radio.isChecked():
            from config import Config
            self.selected_path = str(Config._get_default_library_dir())
            self.choose_folder_btn.setVisible(False)
            self.selected_path_label.setVisible(False)
        else:
            self.choose_folder_btn.setVisible(True)
            if self.selected_path:
                self.selected_path_label.setText(self.selected_path)
                self.selected_path_label.setVisible(True)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для библиотеки",
            str(Path.home())
        )

        if folder:
            self.selected_path = folder
            self.selected_path_label.setText(folder)
            self.selected_path_label.setVisible(True)

    def _on_next(self):
        # Сохраняем настройки
        self.config.set('library_path', self.selected_path)
        self.config.set('first_run', False)

        # Создаем папку если её нет
        Path(self.selected_path).mkdir(parents=True, exist_ok=True)

        self.setup_completed.emit(self.selected_path)
        self.accept()
