from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QFileDialog,
                             QGroupBox, QButtonGroup, QStackedWidget, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path


class WelcomeWizard(QDialog):
    """Окно приветствия при первом запуске.
    Страница 0 — выбор языка.
    Страница 1 — выбор папки библиотеки.
    """

    setup_completed = pyqtSignal(str)

    # Все строки в двух языках прямо здесь
    _STRINGS = {
        'ru': {
            'window_title':   'Добро пожаловать',
            'title':          ' Добро пожаловать!',
            'desc':           'Похоже, вы запускаете приложение впервые.\nДавайте настроим вашу библиотеку.',
            'lang_group':     'Язык интерфейса',
            'folder_group':   'Папка для хранения книг',
            'default_radio':  'Использовать папку по умолчанию',
            'custom_radio':   'Выбрать другую папку',
            'choose_btn':     ' Выбрать папку…',
            'choose_dialog':  'Выберите папку для библиотеки',
            'cancel':         'Отмена',
            'next':           'Далее →',
            'finish':         'Готово',
        },
        'en': {
            'window_title':   'Welcome',
            'title':          ' Welcome!',
            'desc':           'Looks like you are launching the app for the first time.\nLet\'s set up your library.',
            'lang_group':     'Interface language',
            'folder_group':   'Books library folder',
            'default_radio':  'Use default folder',
            'custom_radio':   'Choose another folder',
            'choose_btn':     ' Choose folder…',
            'choose_dialog':  'Select library folder',
            'cancel':         'Cancel',
            'next':           'Next →',
            'finish':         'Done',
        },
    }

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._lang = config.get('language', 'ru')

        from config import Config
        self.selected_path = str(Config._get_default_library_dir())

        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()
        self._apply()

    def _s(self, key: str) -> str:
        return self._STRINGS.get(self._lang, self._STRINGS['ru']).get(key, key)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(20)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        self._stack.addWidget(self._build_page_lang())
        self._stack.addWidget(self._build_page_folder())

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.next_btn = QPushButton()
        self.next_btn.setStyleSheet(
            "QPushButton{background:#1a73e8;color:white;border:none;"
            "padding:8px 16px;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#1765cc;}")
        self.next_btn.clicked.connect(self._on_next)
        btn_row.addWidget(self.next_btn)

        outer.addLayout(btn_row)

    def _build_page_lang(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)

        self._title_lbl = QLabel()
        f = QFont(); f.setPointSize(18); f.setBold(True)
        self._title_lbl.setFont(f)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_lbl.setStyleSheet("color:#666;")
        self._desc_lbl.setWordWrap(True)
        lay.addWidget(self._desc_lbl)

        self._lang_group = QGroupBox()
        g_lay = QVBoxLayout(self._lang_group)
        bg = QButtonGroup(self)

        self._rb_ru = QRadioButton('Русский')
        self._rb_en = QRadioButton('English')
        self._rb_ru.setChecked(self._lang == 'ru')
        self._rb_en.setChecked(self._lang == 'en')
        self._rb_ru.toggled.connect(lambda on: self._on_lang('ru') if on else None)
        self._rb_en.toggled.connect(lambda on: self._on_lang('en') if on else None)
        bg.addButton(self._rb_ru)
        bg.addButton(self._rb_en)
        g_lay.addWidget(self._rb_ru)
        g_lay.addWidget(self._rb_en)
        lay.addWidget(self._lang_group)
        lay.addStretch()
        return page

    def _build_page_folder(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)

        self._folder_group = QGroupBox()
        f_lay = QVBoxLayout(self._folder_group)

        self.default_radio = QRadioButton()
        self.default_radio.setChecked(True)
        self.default_radio.toggled.connect(self._on_folder_toggle)
        f_lay.addWidget(self.default_radio)

        from config import Config
        self._def_path_lbl = QLabel(str(Config._get_default_library_dir()))
        self._def_path_lbl.setStyleSheet("color:#1a73e8;font-family:monospace;margin-left:20px;")
        f_lay.addWidget(self._def_path_lbl)

        self.custom_radio = QRadioButton()
        self.custom_radio.toggled.connect(self._on_folder_toggle)
        f_lay.addWidget(self.custom_radio)

        self.choose_btn = QPushButton()
        self.choose_btn.setVisible(False)
        self.choose_btn.clicked.connect(self._choose_folder)
        f_lay.addWidget(self.choose_btn)

        self.chosen_lbl = QLabel()
        self.chosen_lbl.setStyleSheet("color:#1a73e8;font-family:monospace;margin-left:20px;")
        self.chosen_lbl.setVisible(False)
        f_lay.addWidget(self.chosen_lbl)

        lay.addWidget(self._folder_group)
        lay.addStretch()
        return page

    def _apply(self):
        """Применяет все строки по текущему языку."""
        self.setWindowTitle(self._s('window_title'))
        self._title_lbl.setText(self._s('title'))
        self._desc_lbl.setText(self._s('desc'))
        self._lang_group.setTitle(self._s('lang_group'))
        self._folder_group.setTitle(self._s('folder_group'))
        self.default_radio.setText(self._s('default_radio'))
        self.custom_radio.setText(self._s('custom_radio'))
        self.choose_btn.setText(self._s('choose_btn'))
        self.cancel_btn.setText(self._s('cancel'))
        cur = self._stack.currentIndex()
        self.next_btn.setText(self._s('finish') if cur == 1 else self._s('next'))

    def _on_lang(self, code: str):
        self._lang = code
        self.config.set('language', code)
        self._apply()

    def _on_folder_toggle(self):
        if self.default_radio.isChecked():
            from config import Config
            self.selected_path = str(Config._get_default_library_dir())
            self.choose_btn.setVisible(False)
            self.chosen_lbl.setVisible(False)
        else:
            self.choose_btn.setVisible(True)
            if self.selected_path:
                self.chosen_lbl.setText(self.selected_path)
                self.chosen_lbl.setVisible(True)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._s('choose_dialog'), str(Path.home()))
        if folder:
            self.selected_path = folder
            self.chosen_lbl.setText(folder)
            self.chosen_lbl.setVisible(True)

    def _on_next(self):
        if self._stack.currentIndex() == 0:
            self._stack.setCurrentIndex(1)
            self._apply()
            return
        self.config.set('library_path', self.selected_path)
        self.config.set('first_run', False)
        Path(self.selected_path).mkdir(parents=True, exist_ok=True)
        self.setup_completed.emit(self.selected_path)
        self.accept()
