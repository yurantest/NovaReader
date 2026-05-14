from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QComboBox, QGroupBox,
                             QTabWidget, QWidget, QGridLayout, QColorDialog,
                             QRadioButton, QButtonGroup, QCheckBox)
from PyQt6.QtCore import Qt
import json

from piper_voices_widget import PiperVoicesWidget


class SettingsWindow(QDialog):
    """Окно настроек — синхронизируется с JS через applySettingFromPython"""

    # Все строки интерфейса в двух языках
    _S = {
        'ru': {
            'title':          'Настройки',
            'close':          'Закрыть',
            'tab_font':       'Шрифт',
            'tab_layout':     'Макет',
            'tab_highlight':  'Подсветка',
            'tab_theme':      'Тема',
            'tab_tts':        'TTS голоса',
            'tab_lang':       'Язык',
            'tab_dev':        'Разработчик',
            'tab_screen':     'Экран',
            'screen_group':   'Подавление гашения экрана',
            'screen_inhibit': 'Не давать экрану гаснуть при чтении',
            'screen_timeout': 'Гасить через:',
            'screen_never':   'Никогда',
            'font_size':      'Размер шрифта',
            'line_height':    'Межстрочный интервал',
            'spread_mode':    'Режим страниц',
            'spread_auto':    'Авто',
            'spread_single':  'Одна страница',
            'spread_double':  'Две страницы',
            'page_margin':    'Поля страницы (px)',
            'hl_style':       'Стиль выделения по умолчанию',
            'hl_fill':        'Заливка',
            'hl_underline':   'Подчеркивание',
            'hl_squiggly':    'Волнистая',
            'tts_color':      'Цвет TTS-подсветки',
            'color_cyan':     'Голубой',
            'color_red':      'Красный',
            'color_green':    'Зелёный',
            'color_yellow':   'Жёлтый',
            'color_pink':     'Розовый',
            'themes':         'Готовые темы',
            'theme_light':    'Светлая',
            'theme_dark':     'Тёмная',
            'theme_sepia':    'Сепия',
            'theme_custom':   'Пользовательская',
            'custom_colors':  'Произвольные цвета',
            'bg_label':       'Фон:',
            'text_label':     'Текст:',
            'choose':         'Выбрать',
            'lang_group':     'Язык интерфейса',
            'lang_note':      'Изменение вступит в силу при следующем запуске.',
            'debug_group':    'Отладка',
            'debug_log':      'Записывать отладочный лог в файл',
            'log_path':       'Путь к лог-файлу:',
            # Тема библиотеки
            'tab_lib_theme':  'Библиотека',
            'lib_theme_title':'Тема библиотеки',
            'lib_dark':       'Тёмная',
            'lib_light':      'Светлая',
            'lib_custom':     'Пользовательская',
            'lib_copy_dark':  'Скопировать из тёмной',
            'lib_copy_light': 'Скопировать из светлой',
            'lib_copy_sys':   'Скопировать из системы',
            'lib_colors':     'Цвета интерфейса',
            'lib_bg':         'Фон',
            'lib_surface':    'Поверхность (карточки)',
            'lib_border':     'Рамки',
            'lib_accent':     'Акцент',
            'lib_text':       'Текст',
            'lib_sub':        'Второстепенный текст',
            'lib_series':     'Серия',
            'lib_toolbar':    'Панель инструментов',
            'lib_progress':   'Полоса прогресса',
        },
        'en': {
            'title':          'Settings',
            'close':          'Close',
            'tab_font':       'Font',
            'tab_layout':     'Layout',
            'tab_highlight':  'Highlight',
            'tab_theme':      'Theme',
            'tab_tts':        'TTS Voices',
            'tab_lang':       'Language',
            'tab_dev':        'Developer',
            'tab_screen':     'Screen',
            'screen_group':   'Screen sleep inhibit',
            'screen_inhibit': 'Keep screen on while reading',
            'screen_timeout': 'Turn off after:',
            'screen_never':   'Never',
            'font_size':      'Font size',
            'line_height':    'Line height',
            'spread_mode':    'Page mode',
            'spread_auto':    'Auto',
            'spread_single':  'Single page',
            'spread_double':  'Two pages',
            'page_margin':    'Page margin (px)',
            'hl_style':       'Default highlight style',
            'hl_fill':        'Fill',
            'hl_underline':   'Underline',
            'hl_squiggly':    'Squiggly',
            'tts_color':      'TTS highlight color',
            'color_cyan':     'Cyan',
            'color_red':      'Red',
            'color_green':    'Green',
            'color_yellow':   'Yellow',
            'color_pink':     'Pink',
            'themes':         'Preset themes',
            'theme_light':    'Light',
            'theme_dark':     'Dark',
            'theme_sepia':    'Sepia',
            'theme_custom':   'Custom',
            'custom_colors':  'Custom colors',
            'bg_label':       'Background:',
            'text_label':     'Text:',
            'choose':         'Choose',
            'lang_group':     'Interface language',
            'lang_note':      'Change takes effect on next launch.',
            'debug_group':    'Debug',
            'debug_log':      'Write debug log to file',
            'log_path':       'Log file path:',
            # Library theme
            'tab_lib_theme':  'Library',
            'lib_theme_title':'Library theme',
            'lib_dark':       'Dark',
            'lib_light':      'Light',
            'lib_custom':     'Custom',
            'lib_copy_dark':  'Copy from Dark',
            'lib_copy_light': 'Copy from Light',
            'lib_copy_sys':   'Copy from System',
            'lib_colors':     'Interface colors',
            'lib_bg':         'Background',
            'lib_surface':    'Surface (cards)',
            'lib_border':     'Borders',
            'lib_accent':     'Accent',
            'lib_text':       'Text',
            'lib_sub':        'Secondary text',
            'lib_series':     'Series',
            'lib_toolbar':    'Toolbar',
            'lib_progress':   'Progress bar',
        },
    }

    def __init__(self, config, reader_window=None, parent=None,
                 lib_theme_callback=None):
        super().__init__(parent if reader_window is None else reader_window)
        self.config = config
        self.reader_window = reader_window
        self._loading = False
        self._lib_theme_callback = lib_theme_callback  # callback: (name, custom_dict|None)

        self.setMinimumWidth(520)
        self.setModal(False)

        self._setup_ui()
        self._load_settings()
        self._apply_language()

    def _s(self, key):
        lang = self.config.get('language', 'ru')
        return self._S.get(lang, self._S['ru']).get(key, key)

    def _js(self, code):
        if self.reader_window and self.reader_window.web_view and self.reader_window.web_view.page():
            self.reader_window.web_view.page().runJavaScript(code)

    def _save(self, key, value):
        if self._loading:
            return
        self.config.set(key, value)
        self._js(f"window.applySettingFromPython && window.applySettingFromPython({json.dumps(key)}, {json.dumps(value)})")

    # ── Применение языка ──────────────────────────────────────────────────────

    def _apply_language(self):
        """Обновляет все тексты интерфейса по текущему языку из config."""
        self.setWindowTitle(self._s('title'))
        self._close_btn.setText(self._s('close'))

        # Вкладки
        self._tabs.setTabText(0, self._s('tab_font'))
        self._tabs.setTabText(1, self._s('tab_layout'))
        self._tabs.setTabText(2, self._s('tab_highlight'))
        self._tabs.setTabText(3, self._s('tab_theme'))
        self._tabs.setTabText(4, self._s('tab_tts'))
        self._tabs.setTabText(5, self._s('tab_lang'))
        self._tabs.setTabText(6, self._s('tab_lib_theme'))
        self._tabs.setTabText(7, self._s('tab_dev'))
        self._tabs.setTabText(8, self._s('tab_screen'))

        # Вкладка Шрифт
        self._font_size_group.setTitle(self._s('font_size'))
        self._line_height_group.setTitle(self._s('line_height'))

        # Вкладка Макет
        self._spread_group.setTitle(self._s('spread_mode'))
        self._margin_group.setTitle(self._s('page_margin'))
        # Перестраиваем spread combo с нужными строками, сохраняя значение
        spread = self.config.get('spread_mode', 'auto')
        self.spread_combo.blockSignals(True)
        self.spread_combo.clear()
        self.spread_combo.addItems([
            self._s('spread_auto'),
            self._s('spread_single'),
            self._s('spread_double'),
        ])
        spread_map = {
            'auto': self._s('spread_auto'),
            'none': self._s('spread_single'),
            'both': self._s('spread_double'),
        }
        self.spread_combo.setCurrentText(spread_map.get(spread, self._s('spread_auto')))
        self.spread_combo.blockSignals(False)

        # Вкладка Подсветка
        self._hl_style_group.setTitle(self._s('hl_style'))
        hl_style = self.config.get('default_highlight_style', 'highlight')
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItems([
            self._s('hl_fill'),
            self._s('hl_underline'),
            self._s('hl_squiggly'),
        ])
        style_map = {
            'highlight': self._s('hl_fill'),
            'underline': self._s('hl_underline'),
            'squiggly':  self._s('hl_squiggly'),
        }
        self.style_combo.setCurrentText(style_map.get(hl_style, self._s('hl_fill')))
        self.style_combo.blockSignals(False)

        self._tts_color_group.setTitle(self._s('tts_color'))
        color_keys = ['color_cyan', 'color_red', 'color_green', 'color_yellow', 'color_pink']
        for (btn, val), key in zip(self.tts_color_buttons, color_keys):
            btn.setText(self._s(key))

        # Вкладка Тема
        self._theme_group.setTitle(self._s('themes'))
        self.custom_group.setTitle(self._s('custom_colors'))
        theme_name = self.config.get('theme_name', None)
        bg = self.config.get('theme_bg', '#f4ecd8')
        preset_map_ru = {'#f4ecd8': 'Светлая', '#1a1a1a': 'Тёмная', '#fbf0d9': 'Сепия'}
        # Определяем текущую тему как внутренний ключ
        if theme_name in ('Светлая', 'Light', 'Тёмная', 'Dark', 'Сепия', 'Sepia',
                          'Пользовательская', 'Custom'):
            # Нормализуем к ключу
            _norm = {
                'Светлая': 'light', 'Light': 'light',
                'Тёмная':  'dark',  'Dark':  'dark',
                'Сепия':   'sepia', 'Sepia': 'sepia',
                'Пользовательская': 'custom', 'Custom': 'custom',
            }
            theme_key = _norm.get(theme_name, 'light')
        else:
            _rev = {'#f4ecd8': 'light', '#1a1a1a': 'dark', '#fbf0d9': 'sepia'}
            theme_key = _rev.get(bg, 'custom')

        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems([
            self._s('theme_light'),
            self._s('theme_dark'),
            self._s('theme_sepia'),
            self._s('theme_custom'),
        ])
        key_to_label = {
            'light':  self._s('theme_light'),
            'dark':   self._s('theme_dark'),
            'sepia':  self._s('theme_sepia'),
            'custom': self._s('theme_custom'),
        }
        self.theme_combo.setCurrentText(key_to_label.get(theme_key, self._s('theme_light')))
        self.theme_combo.blockSignals(False)
        self._update_custom_group_state(theme_key == 'custom')

        self._bg_label.setText(self._s('bg_label'))
        self._text_label.setText(self._s('text_label'))
        self.bg_btn.setText(self._s('choose'))
        self.text_btn.setText(self._s('choose'))

        # Вкладка Язык
        self._lang_group.setTitle(self._s('lang_group'))
        self._lang_note.setText(self._s('lang_note'))

        # Вкладка Разработчик
        self._debug_group.setTitle(self._s('debug_group'))
        self.debug_checkbox.setText(self._s('debug_log'))
        self._log_path_label.setText(
            self._s('log_path') + '\n' + str(self.config.config_dir / 'debug.log'))

        # Вкладка Тема библиотеки
        self._lib_theme_group.setTitle(self._s('lib_theme_title'))
        self._lib_rb_dark.setText(self._s('lib_dark'))
        self._lib_rb_light.setText(self._s('lib_light'))
        self._lib_rb_custom.setText(self._s('lib_custom'))
        self._lib_copy_dark_btn.setText(self._s('lib_copy_dark'))
        self._lib_copy_light_btn.setText(self._s('lib_copy_light'))
        self._lib_copy_sys_btn.setText(self._s('lib_copy_sys'))
        self._lib_colors_group.setTitle(self._s('lib_colors'))
        for key, s_key in self._lib_color_keys:
            lbl = self._lib_colors_group.findChild(QLabel, f"_lib_lbl_{key}")
            if lbl:
                lbl.setText(self._s(s_key))
            btn = self._lib_color_btns.get(key)
            if btn:
                btn.setText(self._s('choose'))

    # ── Построение UI ─────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_font_tab(),      '?')
        self._tabs.addTab(self._create_layout_tab(),    '?')
        self._tabs.addTab(self._create_highlight_tab(), '?')
        self._tabs.addTab(self._create_theme_tab(),     '?')
        self._tabs.addTab(self._create_tts_tab(),       '?')
        self._tabs.addTab(self._create_lang_tab(),      '?')
        self._tabs.addTab(self._create_lib_theme_tab(), '?')
        self._tabs.addTab(self._create_dev_tab(),       '?')
        self._tabs.addTab(self._create_screen_tab(),    '?')
        layout.addWidget(self._tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._close_btn = QPushButton()
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setFixedWidth(100)
        btn_layout.addWidget(self._close_btn)
        layout.addLayout(btn_layout)

    def _create_font_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._font_size_group = QGroupBox()
        h = QHBoxLayout(self._font_size_group)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(12, 36)
        self.font_size_label = QLabel('16px')
        self.font_size_label.setFixedWidth(45)
        self.font_size_slider.valueChanged.connect(self._on_font_size_changed)
        h.addWidget(self.font_size_slider)
        h.addWidget(self.font_size_label)
        layout.addWidget(self._font_size_group)

        self._line_height_group = QGroupBox()
        h2 = QHBoxLayout(self._line_height_group)
        self.line_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.line_height_slider.setRange(10, 30)
        self.line_height_label = QLabel('1.5')
        self.line_height_label.setFixedWidth(45)
        self.line_height_slider.valueChanged.connect(self._on_line_height_changed)
        h2.addWidget(self.line_height_slider)
        h2.addWidget(self.line_height_label)
        layout.addWidget(self._line_height_group)

        layout.addStretch()
        return tab

    def _create_layout_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._spread_group = QGroupBox()
        v = QVBoxLayout(self._spread_group)
        self.spread_combo = QComboBox()
        self.spread_combo.addItems(['Авто', 'Одна страница', 'Две страницы'])
        self.spread_combo.currentTextChanged.connect(self._on_spread_mode_changed)
        v.addWidget(self.spread_combo)
        layout.addWidget(self._spread_group)

        self._margin_group = QGroupBox()
        h = QHBoxLayout(self._margin_group)
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(0, 120)
        self.margin_label = QLabel('44px')
        self.margin_label.setFixedWidth(45)
        self.margin_slider.valueChanged.connect(self._on_margin_changed)
        h.addWidget(self.margin_slider)
        h.addWidget(self.margin_label)
        layout.addWidget(self._margin_group)

        layout.addStretch()
        return tab

    def _create_highlight_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._hl_style_group = QGroupBox()
        v = QVBoxLayout(self._hl_style_group)
        self.style_combo = QComboBox()
        self.style_combo.addItems(['Заливка', 'Подчеркивание', 'Волнистая'])
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        v.addWidget(self.style_combo)
        layout.addWidget(self._hl_style_group)

        self._tts_color_group = QGroupBox()
        tts_g = QGridLayout(self._tts_color_group)
        self._tts_color_defs = [
            ('Голубой',  '#00CED1', 'cyan'),
            ('Красный',  '#f28b82', 'red'),
            ('Зелёный',  '#81c995', 'green'),
            ('Жёлтый',   '#fdd66b', 'yellow'),
            ('Розовый',  '#ff8b8b', 'pink'),
        ]
        self.tts_color_buttons = []
        for i, (name, code, val) in enumerate(self._tts_color_defs):
            btn = QPushButton()
            btn.setFixedHeight(34)
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f'QPushButton{{background:{code};border-radius:6px;border:3px solid transparent;}}'
                f'QPushButton:checked{{border:2px solid #333;}}'
            )
            btn.clicked.connect(lambda checked, v=val: self._on_tts_color_selected(v))
            tts_g.addWidget(btn, i // 3, i % 3)
            self.tts_color_buttons.append((btn, val))
        layout.addWidget(self._tts_color_group)

        layout.addStretch()
        return tab

    def _create_theme_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._theme_group = QGroupBox()
        v = QVBoxLayout(self._theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['Светлая', 'Тёмная', 'Сепия', 'Пользовательская'])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        v.addWidget(self.theme_combo)
        layout.addWidget(self._theme_group)

        self.custom_group = QGroupBox()
        g = QGridLayout(self.custom_group)

        self._bg_label = QLabel()
        g.addWidget(self._bg_label, 0, 0)
        self.bg_btn = QPushButton()
        self.bg_btn.clicked.connect(self._on_bg_selected)
        self.bg_preview = QLabel()
        self.bg_preview.setFixedSize(24, 24)
        self.bg_preview.setStyleSheet('border:1px solid #888; border-radius:3px;')
        g.addWidget(self.bg_btn, 0, 1)
        g.addWidget(self.bg_preview, 0, 2)

        self._text_label = QLabel()
        g.addWidget(self._text_label, 1, 0)
        self.text_btn = QPushButton()
        self.text_btn.clicked.connect(self._on_text_selected)
        self.text_preview = QLabel()
        self.text_preview.setFixedSize(24, 24)
        self.text_preview.setStyleSheet('border:1px solid #888; border-radius:3px;')
        g.addWidget(self.text_btn, 1, 1)
        g.addWidget(self.text_preview, 1, 2)

        layout.addWidget(self.custom_group)
        layout.addStretch()
        return tab

    def _create_lib_theme_tab(self):
        """Вкладка «Тема библиотеки» — переключение тёмная/светлая/пользовательская
        с редактором цветов в стиле Calibre (7 цветовых пикеров)."""
        from library_window import DARK_THEME, LIGHT_THEME
        from PyQt6.QtWidgets import QScrollArea
        from PyQt6.QtGui import QColor

        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 8, 8, 8)

        # ── Переключатель темы ──────────────────────────────────────────────
        self._lib_theme_group = QGroupBox()
        theme_lay = QHBoxLayout(self._lib_theme_group)
        self._lib_rb_group = QButtonGroup(tab)

        self._lib_rb_dark   = QRadioButton()
        self._lib_rb_light  = QRadioButton()
        self._lib_rb_custom = QRadioButton()
        for rb in (self._lib_rb_dark, self._lib_rb_light, self._lib_rb_custom):
            self._lib_rb_group.addButton(rb)
            theme_lay.addWidget(rb)
        theme_lay.addStretch()
        outer.addWidget(self._lib_theme_group)

        # ── Кнопки «Скопировать из...» (Calibre-style) ─────────────────────
        copy_row = QHBoxLayout()
        self._lib_copy_dark_btn  = QPushButton()
        self._lib_copy_light_btn = QPushButton()
        self._lib_copy_sys_btn   = QPushButton()
        for btn in (self._lib_copy_dark_btn, self._lib_copy_light_btn,
                    self._lib_copy_sys_btn):
            btn.setFixedHeight(30)
            copy_row.addWidget(btn)
        copy_row.addStretch()
        outer.addLayout(copy_row)

        # ── Сетка цветовых пикеров ──────────────────────────────────────────
        self._lib_colors_group = QGroupBox()
        grid = QGridLayout(self._lib_colors_group)
        grid.setColumnStretch(1, 1)

        # (ключ, строка_в_._s)
        self._lib_color_keys = [
            ("BG",       "lib_bg"),
            ("SURFACE",  "lib_surface"),
            ("BORDER",   "lib_border"),
            ("ACCENT",   "lib_accent"),
            ("TEXT",     "lib_text"),
            ("SUB",      "lib_sub"),
            ("SERIES",   "lib_series"),
            ("TOOLBAR",  "lib_toolbar"),
            ("PROGRESS", "lib_progress"),
        ]
        self._lib_color_btns    = {}  # key -> QPushButton (пикер)
        self._lib_color_preview = {}  # key -> QLabel (цветной квадрат)
        self._lib_custom_colors  = {}  # key -> hex-строка

        for row, (key, s_key) in enumerate(self._lib_color_keys):
            lbl = QLabel()
            lbl.setObjectName(f"_lib_lbl_{key}")
            btn = QPushButton()
            btn.setFixedSize(90, 26)
            preview = QLabel()
            preview.setFixedSize(22, 22)
            preview.setStyleSheet("border:1px solid #888; border-radius:3px;")
            grid.addWidget(lbl,     row, 0)
            grid.addWidget(btn,     row, 1)
            grid.addWidget(preview, row, 2)
            self._lib_color_btns[key]    = btn
            self._lib_color_preview[key] = preview

            def _on_pick(checked, k=key):
                cur = self._lib_custom_colors.get(k, "#ffffff")
                c = QColorDialog.getColor(QColor(cur), self)
                if c.isValid():
                    self._lib_custom_colors[k] = c.name()
                    self._lib_color_preview[k].setStyleSheet(
                        f"background:{c.name()};border:1px solid #888;border-radius:3px;")
                    if self._lib_rb_custom.isChecked():
                        self._emit_lib_theme()

            btn.clicked.connect(_on_pick)

        outer.addWidget(self._lib_colors_group)
        outer.addStretch()

        # ── Подключение сигналов ────────────────────────────────────────────
        self._lib_rb_dark.toggled.connect(
            lambda on: on and self._on_lib_theme_radio("dark"))
        self._lib_rb_light.toggled.connect(
            lambda on: on and self._on_lib_theme_radio("light"))
        self._lib_rb_custom.toggled.connect(
            lambda on: on and self._on_lib_theme_radio("custom"))

        def _copy_from(src_theme):
            self._lib_custom_colors = dict(src_theme)
            self._update_lib_color_previews()
            if self._lib_rb_custom.isChecked():
                self._emit_lib_theme()
            else:
                self._lib_rb_custom.setChecked(True)  # переключит и вызовет _emit

        def _copy_from_system():
            """Читаем QPalette текущей системной темы (KDE/GNOME/etc.)."""
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPalette, QColor
            pal = QApplication.palette()

            def _hex(role, group=QPalette.ColorGroup.Normal):
                return pal.color(group, role).name()

            def _blend(c1: str, c2: str, ratio: float = 0.5) -> str:
                """Смешать два hex-цвета. ratio=0 → c1, ratio=1 → c2."""
                a = QColor(c1); b = QColor(c2)
                r = int(a.red()   * (1 - ratio) + b.red()   * ratio)
                g = int(a.green() * (1 - ratio) + b.green() * ratio)
                bv= int(a.blue()  * (1 - ratio) + b.blue()  * ratio)
                return QColor(r, g, bv).name()

            def _darken(c: str, factor: float = 0.85) -> str:
                col = QColor(c)
                return QColor(
                    int(col.red()   * factor),
                    int(col.green() * factor),
                    int(col.blue()  * factor)
                ).name()

            window  = _hex(QPalette.ColorRole.Window)
            button  = _hex(QPalette.ColorRole.Button)
            base    = _hex(QPalette.ColorRole.Base)
            mid     = _hex(QPalette.ColorRole.Mid)
            midlght = _hex(QPalette.ColorRole.Midlight)

            # TOOLBAR: Button обычно чуть темнее Window в KDE-темах.
            # Если Button == Window (одноцветная ОС), чуть затемняем.
            toolbar = button if button != window else _darken(window, 0.88)

            # BORDER: Mid или смесь Button+Window
            border = mid if mid not in ("#000000", "#ffffff") else _blend(window, base, 0.4)

            # SUB: PlaceholderText если доступен, иначе Dark
            if hasattr(QPalette.ColorRole, "PlaceholderText"):
                sub = _hex(QPalette.ColorRole.PlaceholderText)
                # PlaceholderText в некоторых темах = полностью чёрный/белый
                if sub in ("#000000", "#ffffff", "#ffffffff"):
                    sub = _hex(QPalette.ColorRole.Dark)
            else:
                sub = _hex(QPalette.ColorRole.Dark)

            colors = {
                "BG":       window,
                "SURFACE":  base,
                "BORDER":   border,
                "ACCENT":   _hex(QPalette.ColorRole.Highlight),
                "TEXT":     _hex(QPalette.ColorRole.WindowText),
                "SUB":      sub,
                "SERIES":   _hex(QPalette.ColorRole.Link),
                "TOOLBAR":  toolbar,
                "PROGRESS": _hex(QPalette.ColorRole.Highlight),
            }
            _copy_from(colors)

        self._lib_copy_dark_btn.clicked.connect(
            lambda: _copy_from(DARK_THEME))
        self._lib_copy_light_btn.clicked.connect(
            lambda: _copy_from(LIGHT_THEME))
        self._lib_copy_sys_btn.clicked.connect(_copy_from_system)

        return tab

    def _load_lib_settings(self):
        """Загрузить текущую тему библиотеки из конфига."""
        from library_window import DARK_THEME, LIGHT_THEME
        name = self.config.get("library_theme_name", "dark")
        custom = self.config.get("library_theme_custom", {})

        # Наполняем _lib_custom_colors из текущей темы
        if name == "light":
            self._lib_custom_colors = dict(LIGHT_THEME)
            self._lib_custom_colors.update(custom)
        elif name == "custom":
            self._lib_custom_colors = dict(DARK_THEME)
            self._lib_custom_colors.update(custom)
        else:
            self._lib_custom_colors = dict(DARK_THEME)

        self._update_lib_color_previews()

        # Выбираем нужный radio без лишних сигналов
        self._lib_rb_dark.blockSignals(True)
        self._lib_rb_light.blockSignals(True)
        self._lib_rb_custom.blockSignals(True)
        self._lib_rb_dark.setChecked(name == "dark")
        self._lib_rb_light.setChecked(name == "light")
        self._lib_rb_custom.setChecked(name == "custom")
        self._lib_rb_dark.blockSignals(False)
        self._lib_rb_light.blockSignals(False)
        self._lib_rb_custom.blockSignals(False)

        # Кнопки пикеров активны только в custom
        self._set_lib_pickers_enabled(name == "custom")

    def _update_lib_color_previews(self):
        for key, preview in self._lib_color_preview.items():
            col = self._lib_custom_colors.get(key, "#888888")
            preview.setStyleSheet(
                f"background:{col};border:1px solid #888;border-radius:3px;")

    def _set_lib_pickers_enabled(self, enabled: bool):
        for btn in self._lib_color_btns.values():
            btn.setEnabled(enabled)

    def _on_lib_theme_radio(self, name: str):
        from library_window import DARK_THEME, LIGHT_THEME
        self._set_lib_pickers_enabled(name == "custom")
        if name == "dark":
            self._lib_custom_colors = dict(DARK_THEME)
            self._update_lib_color_previews()
        elif name == "light":
            self._lib_custom_colors = dict(LIGHT_THEME)
            self._update_lib_color_previews()
        self._emit_lib_theme()

    def _emit_lib_theme(self):
        """Сохранить и передать тему библиотеки через callback."""
        name = ("dark"   if self._lib_rb_dark.isChecked()   else
                "light"  if self._lib_rb_light.isChecked()  else "custom")
        self.config.set("library_theme_name", name)
        if name == "custom":
            self.config.set("library_theme_custom", dict(self._lib_custom_colors))
        if self._lib_theme_callback:
            custom = self._lib_custom_colors if name == "custom" else None
            self._lib_theme_callback(name, custom)

    def _create_lang_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._lang_group = QGroupBox()
        g = QVBoxLayout(self._lang_group)

        self._lang_note = QLabel()
        self._lang_note.setStyleSheet('color: gray; font-size: 11px;')
        self._lang_note.setWordWrap(True)
        g.addWidget(self._lang_note)

        bg = QButtonGroup(tab)
        self._rb_ru = QRadioButton('Русский')
        self._rb_en = QRadioButton('English')
        bg.addButton(self._rb_ru)
        bg.addButton(self._rb_en)

        cur = self.config.get('language', 'ru')
        self._rb_ru.setChecked(cur == 'ru')
        self._rb_en.setChecked(cur == 'en')

        def _on_lang(code, on):
            if on:
                self.config.set('language', code)
                self._apply_language()

        self._rb_ru.toggled.connect(lambda on: _on_lang('ru', on))
        self._rb_en.toggled.connect(lambda on: _on_lang('en', on))

        g.addWidget(self._rb_ru)
        g.addWidget(self._rb_en)
        layout.addWidget(self._lang_group)
        layout.addStretch()
        return tab

    def _create_screen_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._screen_group = QGroupBox(self._s('screen_group'))
        v = QVBoxLayout(self._screen_group)

        # Включить/выключить подавление гашения экрана
        self.screen_inhibit_cb = QCheckBox(self._s('screen_inhibit'))
        self.screen_inhibit_cb.setChecked(self.config.get('screen_inhibit', False))
        self.screen_inhibit_cb.toggled.connect(self._on_screen_inhibit_toggled)
        v.addWidget(self.screen_inhibit_cb)

        # Таймаут: Никогда / N минут
        timeout_layout = QHBoxLayout()
        self._screen_timeout_label = QLabel(self._s('screen_timeout'))
        timeout_layout.addWidget(self._screen_timeout_label)

        from PyQt6.QtWidgets import QComboBox
        self.screen_timeout_combo = QComboBox()
        # (label, value_minutes)  0 = никогда
        self._screen_timeout_options = [
            ('∞',  0),
            ('10', 10),
            ('20', 20),
            ('30', 30),
            ('40', 40),
            ('50', 50),
        ]
        for label, _ in self._screen_timeout_options:
            self.screen_timeout_combo.addItem(label)

        saved_timeout = self.config.get('screen_inhibit_timeout', 0)
        idx = next((i for i, (_, v) in enumerate(self._screen_timeout_options)
                    if v == saved_timeout), 0)
        self.screen_timeout_combo.setCurrentIndex(idx)
        self.screen_timeout_combo.currentIndexChanged.connect(self._on_screen_timeout_changed)
        timeout_layout.addWidget(self.screen_timeout_combo)
        timeout_layout.addStretch()
        v.addLayout(timeout_layout)

        layout.addWidget(self._screen_group)
        layout.addStretch()
        return tab

    def _on_screen_inhibit_toggled(self, checked: bool):
        self.config.set('screen_inhibit', checked)
        # Уведомляем reader_window через сигнал если он слушает
        if hasattr(self, '_screen_inhibit_changed_cb') and self._screen_inhibit_changed_cb:
            self._screen_inhibit_changed_cb(checked)

    def _on_screen_timeout_changed(self, idx: int):
        _, minutes = self._screen_timeout_options[idx]
        self.config.set('screen_inhibit_timeout', minutes)
        if hasattr(self, '_screen_timeout_changed_cb') and self._screen_timeout_changed_cb:
            self._screen_timeout_changed_cb(minutes)

    def _create_dev_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._debug_group = QGroupBox()
        v = QVBoxLayout(self._debug_group)

        self.debug_checkbox = QCheckBox()
        self.debug_checkbox.setChecked(self.config.get('debug_log', False))
        self.debug_checkbox.toggled.connect(self._on_debug_toggled)
        v.addWidget(self.debug_checkbox)

        self._log_path_label = QLabel()
        self._log_path_label.setStyleSheet('color: gray; font-size: 11px;')
        self._log_path_label.setWordWrap(True)
        v.addWidget(self._log_path_label)

        layout.addWidget(self._debug_group)
        layout.addStretch()
        return tab

    def _create_tts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.piper_voices_widget = PiperVoicesWidget(self.config)
        self.piper_voices_widget.voicesChanged.connect(self._on_piper_voices_changed)
        layout.addWidget(self.piper_voices_widget)
        return tab

    # ── Загрузка настроек ─────────────────────────────────────────────────────

    def _load_settings(self):
        self._loading = True
        try:
            fs = int(self.config.get('font_size', 16))
            self.font_size_slider.setValue(fs)
            self.font_size_label.setText(f'{fs}px')

            lh = float(self.config.get('line_height', 1.5))
            self.line_height_slider.setValue(int(lh * 10))
            self.line_height_label.setText(f'{lh:.1f}')

            spread = self.config.get('spread_mode', 'auto')
            spread_map = {'auto': 'Авто', 'none': 'Одна страница', 'both': 'Две страницы'}
            self.spread_combo.setCurrentText(spread_map.get(spread, 'Авто'))

            margin = int(self.config.get('page_margin', 44))
            self.margin_slider.setValue(margin)
            self.margin_label.setText(f'{margin}px')

            style = self.config.get('default_highlight_style', 'highlight')
            style_map = {'highlight': 'Заливка', 'underline': 'Подчеркивание', 'squiggly': 'Волнистая'}
            self.style_combo.setCurrentText(style_map.get(style, 'Заливка'))

            saved_tts_color = self.config.get('tts_highlight_color', 'cyan')
            for btn, val in self.tts_color_buttons:
                btn.setChecked(val == saved_tts_color)

            bg   = self.config.get('theme_bg', '#f4ecd8')
            text = self.config.get('theme_text', '#5b4636')
            saved_theme = self.config.get('theme_name', None)
            preset_map = {'#f4ecd8': 'Светлая', '#1a1a1a': 'Тёмная', '#fbf0d9': 'Сепия'}
            if saved_theme in ('Светлая', 'Тёмная', 'Сепия', 'Пользовательская'):
                theme_name = saved_theme
            else:
                theme_name = preset_map.get(bg, 'Пользовательская')
            self.theme_combo.setCurrentText(theme_name)
            self._update_color_previews(bg, text)
            self._update_custom_group_state(theme_name == 'Пользовательская')
        finally:
            self._loading = False
        self._load_lib_settings()

    # ── Обработчики ───────────────────────────────────────────────────────────

    def _on_font_size_changed(self, v):
        self.font_size_label.setText(f'{v}px')
        self._save('font_size', v)

    def _on_line_height_changed(self, v):
        lh = v / 10.0
        self.line_height_label.setText(f'{lh:.1f}')
        self._save('line_height', lh)

    def _on_spread_mode_changed(self, mode):
        # mode может быть на любом языке — ищем по всем вариантам
        mapping = {}
        for lang_s in self._S.values():
            mapping[lang_s['spread_auto']]   = 'auto'
            mapping[lang_s['spread_single']] = 'none'
            mapping[lang_s['spread_double']] = 'both'
        self._save('spread_mode', mapping.get(mode, 'auto'))

    def _on_margin_changed(self, v):
        self.margin_label.setText(f'{v}px')
        self._save('page_margin', v)

    def _on_style_changed(self, s):
        mapping = {}
        for lang_s in self._S.values():
            mapping[lang_s['hl_fill']]      = 'highlight'
            mapping[lang_s['hl_underline']] = 'underline'
            mapping[lang_s['hl_squiggly']]  = 'squiggly'
        style_value = mapping.get(s, 'highlight')
        self._save('default_highlight_style', style_value)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('default_highlight_style', {json.dumps(style_value)})")

    def _on_tts_color_selected(self, color):
        for btn, val in self.tts_color_buttons:
            btn.setChecked(val == color)
        self._save('tts_highlight_color', color)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('tts_highlight_color', {json.dumps(color)})")

    def _update_color_previews(self, bg, text):
        self.bg_preview.setStyleSheet(f'background:{bg}; border:1px solid #888; border-radius:3px;')
        self.text_preview.setStyleSheet(f'background:{text}; border:1px solid #888; border-radius:3px;')

    def _update_custom_group_state(self, enabled: bool):
        self.bg_btn.setEnabled(enabled)
        self.text_btn.setEnabled(enabled)

    def _on_theme_changed(self, theme):
        # Нормализуем название темы к внутреннему ключу
        _norm = {}
        for lang_s in self._S.values():
            _norm[lang_s['theme_light']]  = 'light'
            _norm[lang_s['theme_dark']]   = 'dark'
            _norm[lang_s['theme_sepia']]  = 'sepia'
            _norm[lang_s['theme_custom']] = 'custom'
        theme_key = _norm.get(theme, 'light')

        # Сохраняем имя на русском (для обратной совместимости)
        name_ru = {'light': 'Светлая', 'dark': 'Тёмная', 'sepia': 'Сепия', 'custom': 'Пользовательская'}
        self.config.set('theme_name', name_ru.get(theme_key, 'Светлая'))
        self._update_custom_group_state(theme_key == 'custom')

        if theme_key == 'custom':
            bg   = self.config.get('custom_bg',  self.config.get('theme_bg',   '#f4ecd8'))
            text = self.config.get('custom_text', self.config.get('theme_text', '#5b4636'))
            self.config.set('theme_bg', bg)
            self.config.set('theme_text', text)
            self._update_color_previews(bg, text)
            if not self._loading:
                self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme', {{bg:{json.dumps(bg)},text:{json.dumps(text)}}})")
        else:
            presets = {
                'light': ('#f4ecd8', '#5b4636'),
                'dark':  ('#1a1a1a', '#e0e0e0'),
                'sepia': ('#fbf0d9', '#5f4b3a'),
            }
            bg, text = presets.get(theme_key, ('#f4ecd8', '#5b4636'))
            self.config.set('theme_bg', bg)
            self.config.set('theme_text', text)
            self._update_color_previews(bg, text)
            if not self._loading:
                self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme', {{bg:{json.dumps(bg)},text:{json.dumps(text)}}})")

    def _on_bg_selected(self):
        from PyQt6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self.config.get('custom_bg', self.config.get('theme_bg', '#f4ecd8'))), self)
        if c.isValid():
            self.config.set('custom_bg', c.name())
            self.config.set('theme_bg',  c.name())
            self._update_color_previews(c.name(), self.config.get('custom_text', self.config.get('theme_text', '#5b4636')))
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme_bg', {json.dumps(c.name())})")

    def _on_text_selected(self):
        from PyQt6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self.config.get('custom_text', self.config.get('theme_text', '#5b4636'))), self)
        if c.isValid():
            self.config.set('custom_text', c.name())
            self.config.set('theme_text',  c.name())
            self._update_color_previews(self.config.get('custom_bg', self.config.get('theme_bg', '#f4ecd8')), c.name())
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme_text', {json.dumps(c.name())})")

    def _on_debug_toggled(self, checked: bool):
        self.config.set('debug_log', checked)
        if checked:
            self._enable_debug_log()
        else:
            self._disable_debug_log()

    def _enable_debug_log(self):
        import sys
        log_path = self.config.config_dir / 'debug.log'
        try:
            f = open(log_path, 'a', encoding='utf-8', buffering=1)
            sys.stdout = f
            sys.stderr = f
        except Exception as e:
            print(f'[Debug] Ошибка открытия лога: {e}')

    def _disable_debug_log(self):
        import sys
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def _on_piper_voices_changed(self):
        installed = self.piper_voices_widget.get_installed_voices()
        self._js(f"""
            if (window._pushPiperVoices) {{
                window._pushPiperVoices({json.dumps(installed)});
            }}
        """)
