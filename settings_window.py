from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QComboBox, QGroupBox,
                             QTabWidget, QWidget, QGridLayout, QColorDialog)
from PyQt6.QtCore import Qt
import json

from piper_voices_widget import PiperVoicesWidget


class SettingsWindow(QDialog):
    """Окно настроек — синхронизируется с JS через applySettingFromPython"""

    def __init__(self, config, reader_window):
        super().__init__(reader_window)
        self.config = config
        self.reader_window = reader_window
        self._loading = False

        self.setWindowTitle("Настройки")
        self.setMinimumWidth(520)
        self.setModal(False)

        self._setup_ui()
        self._load_settings()

    def _js(self, code):
        if self.reader_window and self.reader_window.web_view and self.reader_window.web_view.page():
            self.reader_window.web_view.page().runJavaScript(code)

    def _save(self, key, value):
        if self._loading:
            return
        self.config.set(key, value)
        self._js(f"window.applySettingFromPython && window.applySettingFromPython({json.dumps(key)}, {json.dumps(value)})")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._create_font_tab(),      "Шрифт")
        tabs.addTab(self._create_layout_tab(),    "Макет")
        tabs.addTab(self._create_highlight_tab(), "Подсветка")
        tabs.addTab(self._create_theme_tab(),     "Тема")
        tabs.addTab(self._create_tts_tab(),       "TTS голоса")
        tabs.addTab(self._create_dev_tab(),       "Разработчик")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _create_font_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        size_group = QGroupBox("Размер шрифта")
        h = QHBoxLayout(size_group)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(12, 36)
        self.font_size_label = QLabel("16px")
        self.font_size_label.setFixedWidth(45)
        self.font_size_slider.valueChanged.connect(self._on_font_size_changed)
        h.addWidget(self.font_size_slider)
        h.addWidget(self.font_size_label)
        layout.addWidget(size_group)

        line_group = QGroupBox("Межстрочный интервал")
        h2 = QHBoxLayout(line_group)
        self.line_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.line_height_slider.setRange(10, 30)
        self.line_height_label = QLabel("1.5")
        self.line_height_label.setFixedWidth(45)
        self.line_height_slider.valueChanged.connect(self._on_line_height_changed)
        h2.addWidget(self.line_height_slider)
        h2.addWidget(self.line_height_label)
        layout.addWidget(line_group)

        layout.addStretch()
        return tab

    def _create_layout_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        spread_group = QGroupBox("Режим страниц")
        v = QVBoxLayout(spread_group)
        self.spread_combo = QComboBox()
        self.spread_combo.addItems(["Авто", "Одна страница", "Две страницы"])
        self.spread_combo.currentTextChanged.connect(self._on_spread_mode_changed)
        v.addWidget(self.spread_combo)
        layout.addWidget(spread_group)

        margin_group = QGroupBox("Поля страницы (px)")
        h = QHBoxLayout(margin_group)
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(0, 120)
        self.margin_label = QLabel("44px")
        self.margin_label.setFixedWidth(45)
        self.margin_slider.valueChanged.connect(self._on_margin_changed)
        h.addWidget(self.margin_slider)
        h.addWidget(self.margin_label)
        layout.addWidget(margin_group)

        layout.addStretch()
        return tab

    def _create_highlight_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        style_group = QGroupBox("Стиль выделения по умолчанию")
        v = QVBoxLayout(style_group)
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Заливка", "Подчеркивание", "Волнистая"])
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        v.addWidget(self.style_combo)
        layout.addWidget(style_group)

        # Настройка цвета TTS-подсветки
        tts_color_group = QGroupBox("Цвет TTS-подсветки")
        tts_g = QGridLayout(tts_color_group)
        self._tts_colors = [
            ("Голубой",    "#00CED1", "cyan"),
            ("Красный",    "#f28b82", "red"),
            ("Зелёный",    "#81c995", "green"),
            ("Жёлтый",     "#fdd66b", "yellow"),
            ("Розовый",    "#ff8b8b", "pink"),
        ]
        self.tts_color_buttons = []
        for i, (name, code, val) in enumerate(self._tts_colors):
            btn = QPushButton(name)
            btn.setFixedHeight(34)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton{{background:{code};border-radius:6px;border:2px solid transparent;}}"
                f"QPushButton:checked{{border:2px solid #333;}}"
            )
            btn.clicked.connect(lambda checked, v=val: self._on_tts_color_selected(v))
            tts_g.addWidget(btn, i // 3, i % 3)
            self.tts_color_buttons.append((btn, val))
        layout.addWidget(tts_color_group)

        layout.addStretch()
        return tab

    def _create_theme_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        theme_group = QGroupBox("Готовые темы")
        v = QVBoxLayout(theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Тёмная", "Сепия"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        v.addWidget(self.theme_combo)
        layout.addWidget(theme_group)

        custom_group = QGroupBox("Произвольные цвета")
        g = QGridLayout(custom_group)
        g.addWidget(QLabel("Фон:"), 0, 0)
        self.bg_btn = QPushButton("Выбрать")
        self.bg_btn.clicked.connect(self._on_bg_selected)
        g.addWidget(self.bg_btn, 0, 1)
        g.addWidget(QLabel("Текст:"), 1, 0)
        self.text_btn = QPushButton("Выбрать")
        self.text_btn.clicked.connect(self._on_text_selected)
        g.addWidget(self.text_btn, 1, 1)
        layout.addWidget(custom_group)

        layout.addStretch()
        return tab

    def _load_settings(self):
        self._loading = True
        try:
            fs = int(self.config.get('font_size', 16))
            self.font_size_slider.setValue(fs)
            self.font_size_label.setText(f"{fs}px")

            lh = float(self.config.get('line_height', 1.5))
            self.line_height_slider.setValue(int(lh * 10))
            self.line_height_label.setText(f"{lh:.1f}")

            spread = self.config.get('spread_mode', 'auto')
            spread_map = {'auto': 'Авто', 'none': 'Одна страница', 'both': 'Две страницы'}
            self.spread_combo.setCurrentText(spread_map.get(spread, 'Авто'))

            margin = int(self.config.get('page_margin', 44))
            self.margin_slider.setValue(margin)
            self.margin_label.setText(f"{margin}px")

            style = self.config.get('default_highlight_style', 'highlight')
            style_map = {'highlight': 'Заливка', 'underline': 'Подчеркивание', 'squiggly': 'Волнистая'}
            self.style_combo.setCurrentText(style_map.get(style, 'Заливка'))

            # Загрузка цвета TTS-подсветки
            saved_tts_color = self.config.get('tts_highlight_color', 'cyan')
            for btn, val in self.tts_color_buttons:
                btn.setChecked(val == saved_tts_color)

            bg = self.config.get('theme_bg', '#f4ecd8')
            theme_name = {'#f4ecd8': 'Светлая', '#1a1a1a': 'Тёмная'}.get(bg, 'Сепия')
            self.theme_combo.setCurrentText(theme_name)
        finally:
            self._loading = False

    def _on_font_size_changed(self, v):
        self.font_size_label.setText(f"{v}px")
        self._save('font_size', v)

    def _on_line_height_changed(self, v):
        lh = v / 10.0
        self.line_height_label.setText(f"{lh:.1f}")
        self._save('line_height', lh)

    def _on_spread_mode_changed(self, mode):
        self._save('spread_mode', {'Авто':'auto','Одна страница':'none','Две страницы':'both'}.get(mode,'auto'))

    def _on_margin_changed(self, v):
        self.margin_label.setText(f"{v}px")
        self._save('page_margin', v)

    def _on_style_changed(self, s):
        style_value = {'Заливка':'highlight','Подчеркивание':'underline','Волнистая':'squiggly'}.get(s,'highlight')
        self._save('default_highlight_style', style_value)
        # Отправляем в JS для немедленного применения
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('default_highlight_style', {json.dumps(style_value)})")

    def _on_tts_color_selected(self, color):
        """Выбор цвета TTS-подсветки"""
        for btn, val in self.tts_color_buttons:
            btn.setChecked(val == color)
        self._save('tts_highlight_color', color)
        # Отправляем в JS для немедленного применения
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('tts_highlight_color', {json.dumps(color)})")

    def _on_theme_changed(self, theme):
        themes = {'Светлая':('#f4ecd8','#5b4636'),'Тёмная':('#1a1a1a','#e0e0e0'),'Сепия':('#fbf0d9','#5f4b3a')}
        bg, text = themes.get(theme, ('#f4ecd8','#5b4636'))
        self.config.set('theme_bg', bg)
        self.config.set('theme_text', text)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme', {{bg:{json.dumps(bg)},text:{json.dumps(text)}}})")

    def _on_bg_selected(self):
        from PyQt6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self.config.get('theme_bg','#f4ecd8')), self)
        if c.isValid():
            self.config.set('theme_bg', c.name())
            self._js(f"window.applySettingFromPython('theme_bg', {json.dumps(c.name())})")

    def _on_text_selected(self):
        from PyQt6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self.config.get('theme_text','#5b4636')), self)
        if c.isValid():
            self.config.set('theme_text', c.name())
            self._js(f"window.applySettingFromPython('theme_text', {json.dumps(c.name())})")

    def _create_dev_tab(self):
        """Вкладка для разработчика — отладочные настройки."""
        from PyQt6.QtWidgets import QCheckBox
        tab = QWidget()
        layout = QVBoxLayout(tab)

        debug_group = QGroupBox("Отладка")
        v = QVBoxLayout(debug_group)

        self.debug_checkbox = QCheckBox("Записывать отладочный лог в файл")
        self.debug_checkbox.setToolTip(
            "Перенаправляет вывод программы в файл debug.log\n"
            "Файл создаётся в папке данных приложения.\n"
            "По умолчанию отключено."
        )
        self.debug_checkbox.setChecked(self.config.get('debug_log', False))
        self.debug_checkbox.toggled.connect(self._on_debug_toggled)
        v.addWidget(self.debug_checkbox)

        log_label = QLabel(
            "Путь к лог-файлу:\n"
            + str(self.config.config_dir / 'debug.log')
        )
        log_label.setStyleSheet("color: gray; font-size: 11px;")
        log_label.setWordWrap(True)
        v.addWidget(log_label)

        layout.addWidget(debug_group)
        layout.addStretch()
        return tab

    def _on_debug_toggled(self, checked: bool):
        """Включить/выключить запись лога."""
        self.config.set('debug_log', checked)
        if checked:
            self._enable_debug_log()
        else:
            self._disable_debug_log()

    def _enable_debug_log(self):
        """Перенаправить stdout/stderr в файл."""
        import sys
        log_path = self.config.config_dir / 'debug.log'
        try:
            f = open(log_path, 'a', encoding='utf-8', buffering=1)
            sys.stdout = f
            sys.stderr = f
            print(f"[Debug] Лог включён: {log_path}")
        except Exception as e:
            print(f"[Debug] Ошибка открытия лога: {e}")

    def _disable_debug_log(self):
        """Вернуть stdout/stderr в консоль."""
        import sys, io
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        print("[Debug] Лог отключён")

    def _create_tts_tab(self):
        """Вкладка TTS голосов"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Создаём виджет загрузки голосов Piper
        self.piper_voices_widget = PiperVoicesWidget(self.config)
        self.piper_voices_widget.voicesChanged.connect(self._on_piper_voices_changed)
        layout.addWidget(self.piper_voices_widget)
        
        return tab
    
    def _on_piper_voices_changed(self):
        """Вызывается при изменении списка голосов Piper"""
        # Обновляем VOICES в reader.html
        installed = self.piper_voices_widget.get_installed_voices()
        self._js(f"""
            if (window._pushPiperVoices) {{
                window._pushPiperVoices({json.dumps(installed)});
            }}
        """)
        print(f"[Settings] Piper voices updated: {len(installed)} installed")

