from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QRadioButton, QGroupBox, QButtonGroup, QStackedWidget,
                             QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path

from library_window import (init_lib_colors, _mbtn, _styled_get_existing_directory,
                            BG, SURFACE, BORDER, ACCENT, TEXT, SUB, TOOLBAR)


class WelcomeWizard(QDialog):
    setup_completed = pyqtSignal(str)

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
            'next':           'Далее',
            'finish':         'Готово',
            'back':           'Назад',
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
            'next':           'Next',
            'finish':         'Done',
            'back':           'Back',
        },
    }

    def __init__(self, config):
        super().__init__()
        self.config = config
        init_lib_colors(config)
        self._lang = config.get('language', 'ru')

        from config import Config
        self.selected_path = str(Config._get_default_library_dir())

        self.setMinimumWidth(520)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint |
                            Qt.WindowType.WindowCloseButtonHint)

        self._build_ui()
        self._apply()

        # Общий стиль окна (не трогаем кнопки с иконками)
        self.setStyleSheet(f"""
            QDialog {{
                background: {BG};
                color: {TEXT};
                font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', sans-serif;
            }}
            QGroupBox {{
                border: 1px solid {BORDER};
                border-radius: 8px;
                margin-top: 14px;
                font-weight: 600;
                color: {SUB};
                font-size: 11px;
                letter-spacing: 0.8px;
                text-transform: uppercase;
                background: transparent;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                background: {BG};
            }}
            QRadioButton {{
                color: {TEXT};
                spacing: 8px;
                background: transparent;
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px; border-radius: 8px;
                border: 2px solid {BORDER}; background: {SURFACE};
            }}
            QRadioButton::indicator:checked {{
                background: {ACCENT}; border-color: {ACCENT};
            }}
            QLabel {{
                color: {TEXT};
                background: transparent;
            }}
            QLabel#desc {{
                color: {SUB};
            }}
        """)

    def _s(self, key: str) -> str:
        return self._STRINGS.get(self._lang, self._STRINGS['ru']).get(key, key)

    @staticmethod
    def _blend(c1, c2, ratio=0.5):
        from PyQt6.QtGui import QColor
        a, b = QColor(c1), QColor(c2)
        return QColor(
            int(a.red()   * (1-ratio) + b.red()   * ratio),
            int(a.green() * (1-ratio) + b.green() * ratio),
            int(a.blue()  * (1-ratio) + b.blue()  * ratio),
        ).name()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(20)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        outer.addWidget(self._stack)

        self._stack.addWidget(self._build_page_lang())
        self._stack.addWidget(self._build_page_folder())

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.cancel_btn = _mbtn("close", self._s('cancel'), sz=36)
        self.cancel_btn.setFixedSize(36, 36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.back_btn = _mbtn("arrow_back", self._s('back'), sz=36)
        self.back_btn.setFixedSize(36, 36)
        self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self._on_back)
        btn_row.addWidget(self.back_btn)

        # Кнопка "Далее" / "Готово" с иконкой и акцентным фоном
        self.next_btn = _mbtn("arrow_forward", self._s('next'), sz=36)
        self.next_btn.setFixedSize(36, 36)
        # Добавляем фон, но сохраняем шрифт из _mbtn
        self.next_btn.setStyleSheet(
            f"QPushButton{{"
            f"background:{ACCENT};color:white;border:none;border-radius:18px;padding:0;"
            f"font-family:'Material Icons';font-size:18px;}}"
            f"QPushButton:hover{{background:{self._blend(ACCENT, '#ffffff', 0.15)};}}"
            f"QPushButton:pressed{{background:{self._blend(ACCENT, '#000000', 0.1)};}}"
        )
        self.next_btn.clicked.connect(self._on_next)
        btn_row.addWidget(self.next_btn)

        outer.addLayout(btn_row)

    def _build_page_lang(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{BG};")
        lay = QVBoxLayout(page)
        lay.setSpacing(16)

        self._title_lbl = QLabel()
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        self._title_lbl.setFont(f)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setObjectName("desc")
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_lbl.setWordWrap(True)
        lay.addWidget(self._desc_lbl)

        self._lang_group = QGroupBox()
        g_lay = QVBoxLayout(self._lang_group)
        g_lay.setSpacing(8)
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
        page.setStyleSheet(f"background:{BG};")
        lay = QVBoxLayout(page)
        lay.setSpacing(16)

        self._title2_lbl = QLabel()
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        self._title2_lbl.setFont(f)
        self._title2_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title2_lbl)

        self._folder_group = QGroupBox()
        f_lay = QVBoxLayout(self._folder_group)
        f_lay.setSpacing(8)

        self.default_radio = QRadioButton()
        self.default_radio.setChecked(True)
        self.default_radio.toggled.connect(self._on_folder_toggle)
        f_lay.addWidget(self.default_radio)

        from config import Config
        self._def_path_lbl = QLabel(str(Config._get_default_library_dir()))
        self._def_path_lbl.setStyleSheet(f"color:{ACCENT};font-family:monospace;margin-left:20px;")
        f_lay.addWidget(self._def_path_lbl)

        self.custom_radio = QRadioButton()
        self.custom_radio.toggled.connect(self._on_folder_toggle)
        f_lay.addWidget(self.custom_radio)

        self.choose_btn = _mbtn("folder_open", self._s('choose_btn'), sz=36)
        self.choose_btn.setFixedSize(36, 36)
        self.choose_btn.setVisible(False)
        self.choose_btn.clicked.connect(self._choose_folder)
        f_lay.addWidget(self.choose_btn)

        self.chosen_lbl = QLabel()
        self.chosen_lbl.setStyleSheet(f"color:{ACCENT};font-family:monospace;margin-left:20px;")
        self.chosen_lbl.setVisible(False)
        f_lay.addWidget(self.chosen_lbl)

        lay.addWidget(self._folder_group)
        lay.addStretch()
        return page

    def _apply(self):
        self.setWindowTitle(self._s('window_title'))
        self._title_lbl.setText(self._s('title'))
        self._desc_lbl.setText(self._s('desc'))
        self._lang_group.setTitle(self._s('lang_group'))
        self._folder_group.setTitle(self._s('folder_group'))
        self.default_radio.setText(self._s('default_radio'))
        self.custom_radio.setText(self._s('custom_radio'))
        self.choose_btn.setToolTip(self._s('choose_btn'))
        self.cancel_btn.setToolTip(self._s('cancel'))
        self.back_btn.setToolTip(self._s('back'))

        if hasattr(self, '_title2_lbl'):
            self._title2_lbl.setText(self._s('title'))

        cur = self._stack.currentIndex()
        if cur == 0:
            self.next_btn.setToolTip(self._s('next'))
            self.next_btn.setText("arrow_forward")
            self.back_btn.setVisible(False)
        else:
            self.next_btn.setToolTip(self._s('finish'))
            self.next_btn.setText("check")  # иконка "готово"
            self.back_btn.setVisible(True)

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
        folder = _styled_get_existing_directory(
            self,
            self._s('choose_dialog'),
            str(Path.home()),
            config=self.config
        )
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

    def _on_back(self):
        if self._stack.currentIndex() == 1:
            self._stack.setCurrentIndex(0)
            self._apply()
