from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
QPushButton, QSlider, QComboBox, QGroupBox,
QWidget, QGridLayout, QColorDialog,
QRadioButton, QButtonGroup, QCheckBox,
QStackedWidget, QFrame, QScrollArea,
QSizePolicy, QApplication, QFileDialog,
QMessageBox, QListWidget, QListWidgetItem,
QAbstractButton)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPalette, QPen, QPainterPath, QFontMetrics
import json
import shutil
import sys
from pathlib import Path
from piper_voices_widget import PiperVoicesWidget

def _sys_color(role, group=QPalette.ColorGroup.Normal):
    return QApplication.palette().color(group, role).name()

def _blend(c1, c2, ratio=0.5):
    a, b = QColor(c1), QColor(c2)
    return QColor(
        int(a.red()   * (1-ratio) + b.red()   * ratio),
        int(a.green() * (1-ratio) + b.green() * ratio),
        int(a.blue()  * (1-ratio) + b.blue()  * ratio),
    ).name()

def _is_dark():
    bg = QColor(_sys_color(QPalette.ColorRole.Window))
    return bg.lightness() < 128

def _contrast_color(bg_hex):
    """Чёрный или белый — какой даёт больше контраста с bg_hex.
    Не полагается на то, что цвета темы (в т.ч. пользовательские)
    вообще сочетаются друг с другом — считает яркость фона напрямую
    по формуле YIQ."""
    c = QColor(bg_hex)
    yiq = (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000
    return '#1a1a1a' if yiq >= 140 else '#ffffff'

_MATERIAL_ICONS_FAMILY = None

def _material_icons_family():
    """Регистрирует MaterialIcons-Regular.ttf (один раз на процесс) и
    возвращает имя семейства шрифта для рисования иконочных глифов
    напрямую через QPainter.drawText() — так глиф красится в любой
    цвет через обычный QPen, в отличие от растрового/SVG-изображения."""
    global _MATERIAL_ICONS_FAMILY
    if _MATERIAL_ICONS_FAMILY is not None:
        return _MATERIAL_ICONS_FAMILY
    from PyQt6.QtGui import QFontDatabase
    candidates = [
        Path(__file__).parent / 'ibc' / 'fonts' / 'MaterialIcons-Regular.ttf',
        Path(__file__).parent / 'ibc' / 'MaterialIcons-Regular.ttf',
    ]
    family = None
    for path in candidates:
        if path.exists():
            font_id = QFontDatabase.addApplicationFont(str(path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
                break
    _MATERIAL_ICONS_FAMILY = family or ''
    return _MATERIAL_ICONS_FAMILY

def _build_palette():
    win    = _sys_color(QPalette.ColorRole.Window)
    base   = _sys_color(QPalette.ColorRole.Base)
    btn    = _sys_color(QPalette.ColorRole.Button)
    text   = _sys_color(QPalette.ColorRole.WindowText)
    sub    = _sys_color(QPalette.ColorRole.PlaceholderText) if hasattr(QPalette.ColorRole, 'PlaceholderText') else _sys_color(QPalette.ColorRole.Dark)
    accent = _sys_color(QPalette.ColorRole.Highlight)
    mid    = _sys_color(QPalette.ColorRole.Mid)
    dark = _is_dark()
    surface = _blend(win, base, 0.5) if dark else base
    border  = mid if QColor(mid).lightness() not in (0, 255) else _blend(win, text, 0.15)
    hover   = _blend(win, text, 0.06)
    if QColor(sub).lightness() in (0, 255):
        sub = _blend(text, win, 0.45)
    return dict(
        S_BG      = win,
        S_SURFACE = surface,
        S_BORDER  = border,
        S_ACCENT  = accent,
        S_TEXT    = text,
        S_SUB     = sub,
        S_HOVER   = hover,
    )

_P = {}
S_BG = S_SURFACE = S_BORDER = S_ACCENT = S_TEXT = S_SUB = S_HOVER = "#000000"

def _refresh_palette():
    global _P, S_BG, S_SURFACE, S_BORDER, S_ACCENT, S_TEXT, S_SUB, S_HOVER
    _P = _build_palette()
    S_BG      = _P['S_BG']
    S_SURFACE = _P['S_SURFACE']
    S_BORDER  = _P['S_BORDER']
    S_ACCENT  = _P['S_ACCENT']
    S_TEXT    = _P['S_TEXT']
    S_SUB     = _P['S_SUB']
    S_HOVER   = _P['S_HOVER']

class QToggleSwitch(QAbstractButton):
    """Кастомный переключатель (toggle switch) вместо чекбокса.

    По умолчанию красится в палитру settings_window (S_ACCENT/S_BORDER) —
    так работали все существующие вызовы внутри самого settings_window.py,
    и трогать их не пришлось. Но если виджет используется в ДРУГОМ окне
    со своей собственной палитрой (например, диалог бэкапа в
    library_window.py, у которого свои ACCENT/BORDER, независимые от
    settings_window и не гарантированно даже инициализированные к этому
    моменту) — нужно передать цвета явно, иначе он до первого открытия
    окна настроек будет рисоваться чёрным (стартовое значение S_ACCENT/
    S_BORDER в settings_window — буквально "#000000").
    """
    def __init__(self, parent=None, accent=None, track_off=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 20)
        self._accent_override = accent
        self._track_off_override = track_off
        # Без фокуса клавиатуры Qt нечего обводить рамкой после клика мышью —
        # клик и toggled по-прежнему работают, фокус тут и не нужен.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_height = 20
        track_width = 36
        knob_size = 14
        margin = 3

        accent    = self._accent_override or S_ACCENT
        track_off = self._track_off_override or S_BORDER

        if self.isChecked():
            painter.setBrush(QColor(accent))
        else:
            painter.setBrush(QColor(track_off))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, track_width, track_height, 10, 10)

        painter.setBrush(QColor('#ffffff'))
        if self.isChecked():
            knob_x = track_width - knob_size - margin
        else:
            knob_x = margin

        painter.drawEllipse(int(knob_x), margin, knob_size, knob_size)


class CheckMark(QAbstractButton):
    """Чекбокс с иконкой-галочкой Material Design вместо стандартной
    закрашенной рамки Qt (некрасивый нативный QCheckBox::indicator).

    Глиф красится программно через _contrast_color() относительно
    фактического цвета фона плашки — а не хардкодится белым/чёрным —
    поэтому одинаково хорошо виден и на тёмном, и на светлом акценте,
    какой бы цвет темы ни выбрал пользователь.

    По умолчанию берёт S_ACCENT/S_BORDER/S_TEXT из settings_window
    (как и QToggleSwitch), но их можно переопределить параметрами
    accent=/border=/text_color= — для использования в других окнах
    со своей палитрой (см. QToggleSwitch и его accent=/track_off=)."""

    _CHECK_GLYPH = '\ue5ca'  # 'check' в MaterialIcons-Regular.ttf (codepoint из шрифта, проверено)

    def __init__(self, text='', parent=None, accent=None, border=None, text_color=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(text)
        self._accent_override = accent
        self._border_override = border
        self._text_color_override = text_color
        self._box = 18
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._icon_family = _material_icons_family()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self.text()) if self.text() else 0
        extra = (10 + text_w) if self.text() else 0
        h = max(self._box, fm.height()) + 6
        w = self._box + 4 + extra
        return QSize(w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        box = self._box
        y = (self.height() - box) // 2
        rect = QRectF(1, y, box, box)

        accent = self._accent_override or S_ACCENT
        border = self._border_override or S_BORDER

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(accent))
            painter.drawRoundedRect(rect, 5, 5)

            glyph_color = self._text_color_override or _contrast_color(accent)
            if self._icon_family:
                icon_font = QFont(self._icon_family)
                icon_font.setPixelSize(max(10, int(box * 0.78)))
                painter.setFont(icon_font)
                painter.setPen(QColor(glyph_color))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._CHECK_GLYPH)
            else:
                # Шрифт не нашёлся на диске — не оставляем пустую плашку без
                # признака "включено", рисуем простую галочку линиями
                pen = QPen(QColor(glyph_color))
                pen.setWidthF(2.0)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                path = QPainterPath()
                path.moveTo(rect.left() + 4, rect.top() + box * 0.55)
                path.lineTo(rect.left() + box * 0.42, rect.top() + box * 0.72)
                path.lineTo(rect.left() + box - 4, rect.top() + box * 0.3)
                painter.drawPath(path)
        else:
            pen = QPen(QColor(border))
            pen.setWidthF(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        if self.text():
            painter.setPen(QColor(self._text_color_override or S_TEXT))
            painter.setFont(self.font())
            text_rect = self.rect().adjusted(box + 10, 0, 0, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

class SettingsWindow(QDialog):
    """Окно настроек — современный тёмный дизайн с боковой навигацией."""
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
            'screen_inhibit':  'Не давать экрану гаснуть при чтении',
            'cursor_autohide': 'Скрывать курсор мыши при бездействии',
            'screen_timeout': 'Гасить через:',
            'screen_never':   'Никогда',
            'font_size':      'Размер шрифта',
            'line_height':    'Межстрочный интервал',
            'installed_fonts': 'Установленные шрифты',
            'import_font':    'Импортировать шрифт',
            'import_font_ok': 'Шрифт успешно импортирован',
            'import_font_exists': 'Шрифт уже установлен',
            'import_font_err': 'Ошибка при импорте шрифта',
            'import_font_filter': 'Файлы шрифтов (*.ttf *.otf *.woff *.woff2)',
            'reading_font':   'Шрифт чтения',
            'serif_fonts':    'С насечками',
            'sans_fonts':     'Без насечек',
            'spread_mode':    'Режим страниц',
            'spread_auto':    'Авто',
            'spread_single':  'Одна страница',
            'spread_double':  'Две страницы',
            'page_margin':    'Поля страницы',
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
            'bg_label':       'Фон',
            'text_label':     'Текст',
            'choose':         'Выбрать',
            'lang_group':     'Язык интерфейса',
            'lang_note':      'Изменение вступит в силу при следующем запуске.',
            'debug_group':    'Отладка',
            'debug_log':      'Записывать отладочный лог в файл',
            'log_path':       'Путь к лог-файлу:',
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
            'gfx_group':      'Графический backend (для разработчиков)',
            'gfx_backend_label': 'Рендеринг Qt WebEngine',
            'gfx_vulkan':     'Vulkan',
            'gfx_opengl':     'OpenGL',
            'gfx_d3d11':      'DirectX 11',
            'gfx_restart_note': 'Изменение применится при следующем открытии книги (читалка запускается отдельным процессом — перезапускать всю программу не нужно).',
            'gfx_active_now':   'Сейчас активен: {backend}',
            'gfx_fallback_warn': '⚠️ {preferred} недоступен на этой системе (нет поддержки видеокартой/драйвером) — временно используется {active}.',
            'gfx_auto_detect':   'Автоопределение поддержки GPU при запуске',
            'gfx_auto_detect_note': 'Если отключить — программа всегда использует ваш выбор выше, даже если видеокарта/драйвер его не поддерживают (для тестирования).',
            'online_search_toggle': 'Онлайн-поиск книг',
            'online_search_toggle_note': 'Показывает в тулбаре библиотеки кнопку поиска книг на внешних сайтах-агрегаторах.',
            'download_path_label': 'Папка для скачивания книг',
            'download_path_note': 'Книги, найденные через онлайн-поиск, сохраняются сюда автоматически, без диалога выбора файла.',
            'download_path_browse': 'Обзор…',
            'download_path_reset': 'По умолчанию',
            'download_path_dialog_title': 'Выберите папку для скачивания',
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
            'screen_inhibit':  'Keep screen on while reading',
            'cursor_autohide': 'Hide mouse cursor when idle',
            'screen_timeout': 'Turn off after:',
            'screen_never':   'Never',
            'font_size':      'Font size',
            'line_height':    'Line height',
            'installed_fonts': 'Installed fonts',
            'import_font':    'Import font',
            'import_font_ok': 'Font imported successfully',
            'import_font_exists': 'Font already installed',
            'import_font_err': 'Error importing font',
            'import_font_filter': 'Font files (*.ttf *.otf *.woff *.woff2)',
            'reading_font':   'Reading font',
            'serif_fonts':    'Serif (with serifs)',
            'sans_fonts':     'Sans-serif',
            'spread_mode':    'Page mode',
            'spread_auto':    'Auto',
            'spread_single':  'Single page',
            'spread_double':  'Two pages',
            'page_margin':    'Page margin',
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
            'bg_label':       'Background',
            'text_label':     'Text',
            'choose':         'Choose',
            'lang_group':     'Interface language',
            'lang_note':      'Change takes effect on next launch.',
            'debug_group':    'Debug',
            'debug_log':      'Write debug log to file',
            'log_path':       'Log file path:',
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
            'gfx_group':      'Graphics backend (developer)',
            'gfx_backend_label': 'Qt WebEngine rendering',
            'gfx_vulkan':     'Vulkan',
            'gfx_opengl':     'OpenGL',
            'gfx_d3d11':      'DirectX 11',
            'gfx_restart_note': 'Takes effect the next time you open a book (the reader runs as a separate process — no need to restart the whole app).',
            'gfx_active_now':   'Currently active: {backend}',
            'gfx_fallback_warn': '⚠️ {preferred} is not supported on this system (no GPU/driver support) — temporarily using {active}.',
            'gfx_auto_detect':   'Auto-detect GPU support on launch',
            'gfx_auto_detect_note': 'If disabled, the program always uses your selection above, even if the GPU/driver doesn\'t support it (for testing).',
            'online_search_toggle': 'Online book search',
            'online_search_toggle_note': 'Shows the online book search button (external aggregator sites) in the library toolbar.',
            'download_path_label': 'Book download folder',
            'download_path_note': 'Books found via online search are saved here automatically, without a file-choice dialog.',
            'download_path_browse': 'Browse…',
            'download_path_reset': 'Default',
            'download_path_dialog_title': 'Choose download folder',
        },
    }

    def __init__(self, config, reader_window=None, parent=None,
                 lib_theme_callback=None, online_search_changed_callback=None):
        super().__init__(parent if reader_window is None else reader_window)
        _refresh_palette()
        self._build_styles()
        self.config = config
        self.reader_window = reader_window
        self._loading = False
        self._lib_theme_callback = lib_theme_callback
        self._online_search_changed_cb = online_search_changed_callback
        self._nav_buttons = []
        self.setMinimumSize(680, 520)
        self.resize(870, 700)
        self.setModal(False)
        self.setWindowTitle('')
        lib_theme = self.config.get('library_theme_name', 'dark')
        self._sync_theme_to_lib(lib_theme)
        self.setStyleSheet(self._STYLE_MAIN)
        self._setup_ui()
        self._load_settings()
        self._restore_font_selection()
        self._apply_language()

    def _build_styles(self):
        """Строит все QSS-строки с актуальными цветами системной темы."""
        self._STYLE_MAIN = f"""
QDialog {{
    background: {S_BG};
    color: {S_TEXT};
    font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', sans-serif;
}}
QLabel {{ color: {S_TEXT}; background: transparent; outline: none; }}
QWidget:focus {{ outline: none; }}
QAbstractButton:focus {{ outline: none; border: none; }}
QGroupBox {{
    border: 1px solid {S_BORDER}; border-radius: 8px; margin-top: 14px;
    padding: 14px 12px 10px 12px; font-weight: 600; color: {S_SUB};
    font-size: 11px; letter-spacing: 0.8px;  text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px; background: {S_BG};
}}
QSlider::groove:horizontal {{ height: 4px; background: {S_BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {S_ACCENT}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
}}
QSlider::sub-page:horizontal {{ background: {S_ACCENT}; border-radius: 2px; }}
QComboBox {{
    background: {S_SURFACE}; border: 1px solid {S_BORDER}; border-radius: 6px;
    padding: 6px 12px; color: {S_TEXT}; min-width: 160px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {S_SUB}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {S_SURFACE}; border: 1px solid {S_BORDER}; color: {S_TEXT};
    selection-background-color: {S_ACCENT}; outline: none;
}}
QCheckBox {{
    color: {S_TEXT};
    spacing: 12px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {S_BORDER};
    background: {S_SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {S_ACCENT};
    border-color: {S_ACCENT};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNC41TDQuNSA4TDExIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4=);
}}
QCheckBox::indicator:hover {{
    border-color: {S_ACCENT};
}}
QRadioButton {{ color: {S_TEXT}; spacing: 8px; }}
QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 8px;
    border: 2px solid {S_BORDER}; background: {S_SURFACE};
}}
QRadioButton::indicator:checked {{ background: {S_ACCENT}; border-color: {S_ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical {{ background: {S_BORDER}; border-radius: 3px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
        self._BTN_STYLE = f"""
QPushButton {{
    background: {S_SURFACE}; border: 1px solid {S_BORDER}; border-radius: 6px;
    color: {S_TEXT}; padding: 6px 16px; font-size: 13px;
}}
QPushButton:hover {{ background: {S_HOVER}; border-color: {S_ACCENT}; }}
QPushButton:pressed {{ background: {S_BG}; }}
"""
        self._BTN_ACCENT_STYLE = f"""
QPushButton {{
    background: {S_ACCENT}; border: none; border-radius: 6px;
    color: white; padding: 8px 24px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: {_blend(S_ACCENT, '#ffffff', 0.15)}; }}
QPushButton:pressed {{ background: {_blend(S_ACCENT, '#000000', 0.1)}; }}
"""
        self._NAV_STYLE = f"""
QPushButton {{
    background: transparent; border: none; border-radius: 6px;
    color: {S_SUB}; padding: 9px 12px; font-size: 13px; text-align: left;
}}
QPushButton:hover {{ background: {S_HOVER}; color: {S_TEXT}; }}
"""
        self._NAV_ACTIVE_STYLE = f"""
QPushButton {{
    background: {_blend(S_ACCENT, S_BG, 0.85)};
    border: none; border-left: 3px solid {S_ACCENT};
    border-radius: 0px 6px 6px 0px;
    color: {S_ACCENT}; padding: 9px 12px 9px 9px;
    font-size: 13px; font-weight: 600; text-align: left;
}}
"""
        self._CARD_STYLE = f"""
QFrame#SettingsCard {{
    background: {S_SURFACE}; border: 1px solid {S_BORDER}; border-radius: 8px;
}}
"""

    def _card(self):
        w = QFrame()
        # objectName — ключевая часть фикса: без него селектор "QFrame { ... }"
        # каскадится на ВСЕ вложенные QFrame-наследники (включая QLabel и
        # QScrollArea — оба наследники QFrame в самом Qt), и каждая подпись
        # внутри карточки получала тот же фон+рамку, что и сама карточка.
        # С #SettingsCard стиль применяется только к виджету с этим именем.
        w.setObjectName("SettingsCard")
        w.setStyleSheet(self._CARD_STYLE)
        return w

    def _section_label(self, text):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"color:{S_SUB}; font-size:10px; font-weight:700; "
                          f"letter-spacing:1px; background:transparent;")
        return lbl

    @staticmethod
    def _contrast_color(bg_hex):
        return _contrast_color(bg_hex)

    def _value_label(self, text):
        lbl = QLabel(text)
        # Фон плашки — лёгкий акцентный оттенок поверх S_SURFACE, а не сам
        # S_ACCENT напрямую: так плашка всегда отличима от карточки, даже
        # если пользователь выберет ACCENT, совпадающий с фоном/текстом.
        pill_bg = _blend(S_SURFACE, S_ACCENT, 0.22)
        txt_color = self._contrast_color(pill_bg)
        lbl.setStyleSheet(
            f"color:{txt_color}; font-size:12px; font-weight:700; "
            f"background:{pill_bg}; border-radius:9px; padding:3px 10px; min-width:40px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

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

    def _switch_page(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.setStyleSheet(self._NAV_ACTIVE_STYLE if i == idx else self._NAV_STYLE)

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._nav_panel = QWidget()
        self._nav_panel.setFixedWidth(168)
        self._nav_panel.setStyleSheet(f"background:{S_BG}; border-right:1px solid {S_BORDER};")
        nav_layout = QVBoxLayout(self._nav_panel)
        nav_layout.setContentsMargins(8, 20, 8, 16)
        nav_layout.setSpacing(2)

        title_lbl = QLabel("NovaReader")
        title_lbl.setStyleSheet(f"color:{S_TEXT}; font-size:15px; font-weight:700; "
                                 f"padding:0 4px 16px 4px; background:transparent;")
        nav_layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{S_BORDER};")
        nav_layout.addWidget(sep)
        nav_layout.addSpacing(8)

        nav_items = [
            ('tab_font',      '\U0001D400  '),   # 𝐀  MATHEMATICAL BOLD CAPITAL A
            ('tab_layout',    '\u229E  '),        # ⊞  SQUARED PLUS
            ('tab_highlight', '\u270F\uFE0E  '),  # ✏  PENCIL (текстовый режим, не эмодзи)
            ('tab_theme',     '\u25D1  '),        # ◑  CIRCLE WITH RIGHT HALF BLACK
            ('tab_tts',       '\u25CE  '),        # ◎  BULLSEYE
            ('tab_screen',    '\u2299  '),        # ⊙  CIRCLED DOT OPERATOR
            ('tab_lang',      '\u2295  '),        # ⊕  CIRCLED PLUS
            ('tab_lib_theme', '\u25A6  '),        # ▦  SQUARE WITH ORTHOGONAL CROSSHATCH FILL
            ('tab_dev',       '\u2699\uFE0E  '),  # ⚙  GEAR (текстовый режим, не цветной эмодзи)
        ]
        self._nav_keys = [k for k, _ in nav_items]
        for i, (key, icon) in enumerate(nav_items):
            btn = QPushButton(icon + self._s(key))
            btn.setStyleSheet(self._NAV_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_page(idx))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            if key == 'tab_lib_theme' and self.reader_window is not None:
                btn.setVisible(False)

        nav_layout.addStretch()

        self._close_btn = QPushButton(self._s('close'))
        self._close_btn.setStyleSheet(self._BTN_ACCENT_STYLE)
        self._close_btn.clicked.connect(self.accept)
        nav_layout.addWidget(self._close_btn)

        root.addWidget(self._nav_panel)

        content_area = QWidget()
        content_area.setStyleSheet(f"background:{S_BG};")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._create_font_page())
        self._stack.addWidget(self._create_layout_page())
        self._stack.addWidget(self._create_highlight_page())
        self._stack.addWidget(self._create_theme_page())
        self._stack.addWidget(self._create_tts_page())
        self._stack.addWidget(self._create_screen_page())
        self._stack.addWidget(self._create_lang_page())
        self._stack.addWidget(self._create_lib_theme_page())
        self._stack.addWidget(self._create_dev_page())

        content_layout.addWidget(self._stack)
        root.addWidget(content_area, 1)

        self._switch_page(0)

    def _scroll_page(self, inner):
        sb = (f"background: transparent; border-radius: 3px; min-size: 20px;"
              f"background: {S_BORDER};")
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:{S_BG}; border:none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 4px 2px 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {S_BORDER}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {S_SUB}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{
                background: transparent; height: 6px; margin: 0 0 2px 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {S_BORDER}; border-radius: 3px; min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {S_SUB}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """)
        return scroll

    def _page_container(self, title_key):
        outer = QWidget()
        outer.setStyleSheet(f"background:{S_BG};")
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(28, 24, 28, 24)
        vbox.setSpacing(16)

        h = QLabel(self._s(title_key))
        h.setStyleSheet(f"color:{S_TEXT}; font-size:20px; font-weight:700; background:transparent;")
        setattr(self, f'_page_title_{title_key}', h)
        vbox.addWidget(h)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{S_BORDER}; max-height:1px;")
        vbox.addWidget(sep)

        return outer, vbox

    def _slider_row(self, label_text, slider, value_lbl, unit=''):
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
        lbl.setFixedWidth(160)
        h.addWidget(lbl)
        h.addWidget(slider, 1)
        h.addSpacing(8)
        h.addWidget(value_lbl)
        return row

    @staticmethod
    def _get_fonts_dir() -> Path:
        if getattr(sys, 'frozen', False):
            primary = Path(sys.executable).parent / 'ibc' / 'fonts'
        else:
            primary = Path(__file__).parent / 'ibc' / 'fonts'
        try:
            primary.mkdir(parents=True, exist_ok=True)
            test = primary / '.write_test'
            test.touch()
            test.unlink()
            return primary
        except (PermissionError, OSError):
            pass
        import os
        if sys.platform == 'win32':
            base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        else:
            base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        fallback = base / 'NovaReader' / 'fonts'
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _on_import_font(self):
        flt = self._s('import_font_filter')
        paths, _ = QFileDialog.getOpenFileNames(
            self, self._s('import_font'), '', flt)
        if not paths:
            return
        fonts_dir = self._get_fonts_dir()
        fonts_dir.mkdir(parents=True, exist_ok=True)
        from PyQt6.QtGui import QFontDatabase
        imported, skipped, errors = [], [], []
        for src_path in paths:
            src = Path(src_path)
            dst = fonts_dir / src.name
            if dst.exists():
                skipped.append(src.name)
                continue
            try:
                shutil.copy2(src, dst)
                fid = QFontDatabase.addApplicationFont(str(dst))
                if fid >= 0:
                    imported.append(src.name)
                else:
                    dst.unlink(missing_ok=True)
                    errors.append(src.name)
            except Exception as e:
                errors.append(f'{src.name}: {e}')
        parts = []
        if imported:
            parts.append(f"✓ {self._s('import_font_ok')}: {', '.join(imported)}")
        if skipped:
            parts.append(f"— {self._s('import_font_exists')}: {', '.join(skipped)}")
        if errors:
            parts.append(f"✗ {self._s('import_font_err')}: {', '.join(errors)}")
        if parts:
            QMessageBox.information(self, self._s('import_font'), '\n'.join(parts))
        if imported:
            self.config.invalidate_font_cache()
            self._rebuild_font_combos()

    def _rebuild_font_combos(self):
        if not hasattr(self, '_font_list_layout') or not hasattr(self, '_font_btns'):
            return
        from config import Config as _Cfg
        user_fonts = self.config.get_user_fonts()
        if not user_fonts:
            user_fonts = [self.config.DEFAULT_FONT, 'Noto Sans', 'Roboto']
        serif  = [f for f in user_fonts if _Cfg.classify_font(f) == 'serif']
        sans   = [f for f in user_fonts if _Cfg.classify_font(f) == 'sans']
        other  = [f for f in user_fonts
                  if _Cfg.classify_font(f) not in ('serif', 'sans', 'mono', 'skip')]
        all_fonts = serif + sans + other
        layout = self._font_list_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._font_btns.clear()
        self._font_btns = self._build_font_list(
            layout, all_fonts, 'reader_font_family',
            self.config.get('reader_font_family', self.config.DEFAULT_FONT))

    def _font_item_style(self, selected: bool) -> str:
        bg  = S_ACCENT  if selected else 'transparent'
        clr = '#ffffff' if selected else S_TEXT
        bdr = S_ACCENT  if selected else 'transparent'
        return (
            f'QPushButton {{ background:{bg}; border:1px solid {bdr}; '
            f'border-radius:6px; color:{clr}; padding:6px 12px; '
            f'text-align:left; }}'
            f'QPushButton:hover {{ background:{S_HOVER}; border-color:{S_ACCENT}; '
            f'color:{S_TEXT}; }}'
        )

    def _build_font_list(self, container_layout, fonts, config_key, default):
        btns = []
        cur = self.config.get(config_key, default)
        for fam in (fonts if fonts else [default]):
            btn = QPushButton(fam)
            btn.setCheckable(True)
            btn.setChecked(fam == cur)
            btn.setFont(QFont(fam, 12))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._font_item_style(fam == cur))
            btns.append(btn)
            def _click(checked, f=fam, b=btn):
                for ob in self._font_btns:
                    ob.setChecked(ob is b)
                    ob.setStyleSheet(self._font_item_style(ob is b))
                self._on_font_family_changed(f, config_key)
            btn.clicked.connect(_click)
            container_layout.addWidget(btn)
        container_layout.addStretch()
        return btns

    def _create_font_page(self):
        outer, vbox = self._page_container('tab_font')

        card = self._card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(16)

        self._font_size_sec = self._section_label(self._s('font_size'))
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(12, 36)
        self.font_size_label = self._value_label('16px')
        self.font_size_slider.valueChanged.connect(self._on_font_size_changed)
        cl.addWidget(self._font_size_sec)
        cl.addWidget(self._slider_row('', self.font_size_slider, self.font_size_label))
        cl.addSpacing(4)

        self._lh_sec_lbl = self._section_label(self._s('line_height'))
        self.line_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.line_height_slider.setRange(10, 30)
        self.line_height_label = self._value_label('1.5')
        self.line_height_slider.valueChanged.connect(self._on_line_height_changed)
        cl.addWidget(self._lh_sec_lbl)
        cl.addWidget(self._slider_row('', self.line_height_slider, self.line_height_label))

        vbox.addWidget(card)

        from config import Config as _Cfg
        user_fonts = self.config.get_user_fonts()
        if not user_fonts:
            user_fonts = [self.config.DEFAULT_FONT, 'Noto Sans', 'Roboto']

        serif  = [f for f in user_fonts if _Cfg.classify_font(f) == 'serif']
        sans   = [f for f in user_fonts if _Cfg.classify_font(f) == 'sans']
        other  = [f for f in user_fonts
                  if _Cfg.classify_font(f) not in ('serif', 'sans', 'mono', 'skip')]
        all_fonts = serif + sans + other

        font_card = self._card()
        fv = QVBoxLayout(font_card)
        fv.setContentsMargins(16, 16, 16, 16)
        fv.setSpacing(10)

        hdr = QWidget(); hdr.setStyleSheet('background:transparent;')
        hdr_h = QHBoxLayout(hdr); hdr_h.setContentsMargins(0, 0, 0, 0)
        self._font_reading_sec = self._section_label(self._s('reading_font'))
        hdr_h.addWidget(self._font_reading_sec, 1)
        self._import_font_btn = QPushButton('+ ' + self._s('import_font'))
        self._import_font_btn.setStyleSheet(self._BTN_STYLE)
        self._import_font_btn.setFixedHeight(28)
        self._import_font_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_font_btn.clicked.connect(self._on_import_font)
        hdr_h.addWidget(self._import_font_btn)
        fv.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {S_BG}; border: 1px solid {S_BORDER};
                          border-radius: 8px; }}
            QScrollBar:vertical {{ width: 5px; background: transparent; margin: 4px 0; }}
            QScrollBar::handle:vertical {{ background: {S_BORDER}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        inner = QWidget()
        inner.setStyleSheet(f'background: {S_BG};')
        self._font_list_layout = QVBoxLayout(inner)
        self._font_list_layout.setContentsMargins(6, 6, 6, 6)
        self._font_list_layout.setSpacing(2)
        self._font_btns = self._build_font_list(
            self._font_list_layout, all_fonts, 'reader_font_family',
            self.config.get('reader_font_family', self.config.DEFAULT_FONT))
        scroll.setWidget(inner)
        scroll.setFixedHeight(220)
        fv.addWidget(scroll)

        vbox.addWidget(font_card)
        vbox.addStretch()
        return self._scroll_page(outer)

    def _create_layout_page(self):
        outer, vbox = self._page_container('tab_layout')
        card = self._card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(16)

        self._spread_sec = self._section_label(self._s('spread_mode'))
        cl.addWidget(self._spread_sec)
        self.spread_combo = QComboBox()
        self.spread_combo.addItems(['Авто', 'Одна страница', 'Две страницы'])
        self.spread_combo.currentTextChanged.connect(self._on_spread_mode_changed)
        cl.addWidget(self.spread_combo)
        cl.addSpacing(4)

        self._margin_sec = self._section_label(self._s('page_margin'))
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(0, 120)
        self.margin_label = self._value_label('44px')
        self.margin_slider.valueChanged.connect(self._on_margin_changed)
        cl.addWidget(self._margin_sec)
        cl.addWidget(self._slider_row('', self.margin_slider, self.margin_label))

        vbox.addWidget(card)
        vbox.addStretch()
        return self._scroll_page(outer)

    def _create_highlight_page(self):
        outer, vbox = self._page_container('tab_highlight')

        card1 = self._card()
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(16, 16, 16, 16)
        c1.setSpacing(10)

        self._hl_sec = self._section_label(self._s('hl_style'))
        c1.addWidget(self._hl_sec)
        self.style_combo = QComboBox()
        self.style_combo.addItems(['Заливка', 'Подчеркивание', 'Волнистая'])
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        c1.addWidget(self.style_combo)
        vbox.addWidget(card1)

        card2 = self._card()
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(16, 16, 16, 16)
        c2.setSpacing(12)

        self._tts_sec = self._section_label(self._s('tts_color'))
        c2.addWidget(self._tts_sec)
        self._tts_color_defs = [
            ('Голубой',  '#00CED1', 'cyan'),
            ('Красный',  '#f28b82', 'red'),
            ('Зелёный',  '#81c995', 'green'),
            ('Жёлтый',   '#fdd66b', 'yellow'),
            ('Розовый',  '#ff8b8b', 'pink'),
        ]
        self.tts_color_buttons = []
        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_h = QHBoxLayout(row_w)
        row_h.setContentsMargins(0, 0, 0, 0)
        row_h.setSpacing(8)
        for name, code, val in self._tts_color_defs:
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f'QPushButton{{background:{code};border-radius:20px;border:3px solid transparent;}}'
                f'QPushButton:checked{{border:3px solid white;}}'
                f'QPushButton:hover{{border:3px solid rgba(255,255,255,0.6);}}'
            )
            btn.clicked.connect(lambda checked, v=val: self._on_tts_color_selected(v))
            row_h.addWidget(btn)
            self.tts_color_buttons.append((btn, val))
        row_h.addStretch()
        c2.addWidget(row_w)
        vbox.addWidget(card2)

        vbox.addStretch()
        return self._scroll_page(outer)

    def _create_theme_page(self):
        outer, vbox = self._page_container('tab_theme')

        card1 = self._card()
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(16, 16, 16, 16)
        c1.setSpacing(12)

        self._theme_sec = self._section_label(self._s('themes'))
        c1.addWidget(self._theme_sec)
        themes_row = QWidget()
        themes_row.setStyleSheet("background:transparent;")
        tr = QHBoxLayout(themes_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(8)
        self._theme_preset_btns = {}
        presets = [
            ('light', '#f4ecd8', '#5b4636', 'Светлая'),
            ('dark',  '#1a1a1a', '#e0e0e0', 'Тёмная'),
            ('sepia', '#fbf0d9', '#5f4b3a', 'Сепия'),
        ]
        for key, bg, fg, label in presets:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(52)
            btn.setStyleSheet(
                f'QPushButton{{background:{bg};color:{fg};border-radius:8px;'
                f'border:2px solid transparent;font-size:13px;font-weight:600;}}'
                f'QPushButton:checked{{border:2px solid {S_ACCENT};}}'
                f'QPushButton:hover{{border:2px solid rgba(79,142,247,0.5);}}'
            )
            btn.clicked.connect(lambda _, k=key: self._on_preset_theme(k))
            tr.addWidget(btn)
            self._theme_preset_btns[key] = btn

        btn_custom = QPushButton(self._s('theme_custom'))
        btn_custom.setCheckable(True)
        btn_custom.setFixedHeight(52)
        btn_custom.setStyleSheet(
            f'QPushButton{{background:{S_SURFACE};color:{S_TEXT};border-radius:8px;'
            f'border:2px solid transparent;font-size:13px;}}'
            f'QPushButton:checked{{border:2px solid {S_ACCENT};}}'
            f'QPushButton:hover{{border:2px solid rgba(79,142,247,0.5);}}'
        )
        btn_custom.clicked.connect(lambda _: self._on_preset_theme('custom'))
        tr.addWidget(btn_custom)
        self._theme_preset_btns['custom'] = btn_custom
        c1.addWidget(themes_row)
        vbox.addWidget(card1)

        self.custom_card = self._card()
        c2 = QVBoxLayout(self.custom_card)
        c2.setContentsMargins(16, 16, 16, 16)
        c2.setSpacing(12)

        self._custom_sec = self._section_label(self._s('custom_colors'))
        c2.addWidget(self._custom_sec)
        for attr, key in [('bg', 'bg_label'), ('text', 'text_label')]:
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(self._s(key))
            lbl.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent; min-width:60px;")
            setattr(self, f'_{attr}_label', lbl)
            preview = QLabel()
            preview.setFixedSize(28, 28)
            preview.setStyleSheet(f'background:#f4ecd8; border-radius:14px; border:2px solid {S_BORDER};')
            setattr(self, f'{attr}_preview', preview)
            btn = QPushButton(self._s('choose'))
            btn.setStyleSheet(self._BTN_STYLE)
            btn.setFixedHeight(32)
            setattr(self, f'{attr}_btn', btn)
            rh.addWidget(lbl)
            rh.addWidget(preview)
            rh.addSpacing(8)
            rh.addWidget(btn)
            rh.addStretch()
            c2.addWidget(row)
        self.bg_btn.clicked.connect(self._on_bg_selected)
        self.text_btn.clicked.connect(self._on_text_selected)
        vbox.addWidget(self.custom_card)

        vbox.addStretch()
        return self._scroll_page(outer)

    def _on_preset_theme(self, key):
        for k, b in self._theme_preset_btns.items():
            b.setChecked(k == key)
        name_ru = {'light': 'Светлая', 'dark': 'Тёмная', 'sepia': 'Сепия', 'custom': 'Пользовательская'}
        self.config.set('theme_name', name_ru.get(key, 'Светлая'))
        self.custom_card.setVisible(key == 'custom')
        if key == 'custom':
            bg   = self.config.get('custom_bg',  self.config.get('theme_bg',   '#f4ecd8'))
            text = self.config.get('custom_text', self.config.get('theme_text', '#5b4636'))
        else:
            presets = {'light': ('#f4ecd8','#5b4636'), 'dark': ('#1a1a1a','#e0e0e0'), 'sepia': ('#fbf0d9','#5f4b3a')}
            bg, text = presets[key]
        self.config.set('theme_bg', bg)
        self.config.set('theme_text', text)
        self._update_color_previews(bg, text)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme', {{bg:{json.dumps(bg)},text:{json.dumps(text)}}})")

    def _create_tts_page(self):
        outer = QWidget()
        outer.setStyleSheet(f"background:{S_BG};")
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(28, 24, 28, 24)
        vbox.setSpacing(0)

        h = QLabel(self._s('tab_tts'))
        h.setStyleSheet(f"color:{S_TEXT}; font-size:20px; font-weight:700; background:transparent;")
        vbox.addWidget(h)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{S_BORDER}; max-height:1px;")
        vbox.addWidget(sep)
        vbox.addSpacing(16)

        self.piper_voices_widget = PiperVoicesWidget(self.config)
        self.piper_voices_widget.voicesChanged.connect(self._on_piper_voices_changed)
        vbox.addWidget(self.piper_voices_widget, 1)
        return outer

    def _create_screen_page(self):
        outer, vbox = self._page_container('tab_screen')
        card = self._card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(14)

        # Переключатель (toggle switch)
        self.screen_inhibit_toggle = QToggleSwitch()
        self.screen_inhibit_toggle.setChecked(self.config.get('screen_inhibit', False))
        self.screen_inhibit_toggle.toggled.connect(self._on_screen_inhibit_toggled)

        row1 = QWidget()
        row1.setStyleSheet("background:transparent;")
        rh1 = QHBoxLayout(row1)
        rh1.setContentsMargins(0, 0, 0, 0)
        rh1.addWidget(self.screen_inhibit_toggle)
        self._screen_inhibit_label = QLabel(self._s('screen_inhibit'))
        self._screen_inhibit_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
        rh1.addWidget(self._screen_inhibit_label)
        rh1.addStretch()
        cl.addWidget(row1)

        # Переключатель (toggle switch)
        self.cursor_autohide_toggle = QToggleSwitch()
        self.cursor_autohide_toggle.setChecked(self.config.get('cursor_autohide', True))
        self.cursor_autohide_toggle.toggled.connect(self._on_cursor_autohide_toggled)

        row2 = QWidget()
        row2.setStyleSheet("background:transparent;")
        rh2 = QHBoxLayout(row2)
        rh2.setContentsMargins(0, 0, 0, 0)
        rh2.addWidget(self.cursor_autohide_toggle)
        self._cursor_autohide_label = QLabel(self._s('cursor_autohide'))
        self._cursor_autohide_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
        rh2.addWidget(self._cursor_autohide_label)
        rh2.addStretch()
        cl.addWidget(row2)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background:{S_BORDER};")
        cl.addWidget(sep2)

        timeout_row = QWidget(); timeout_row.setStyleSheet("background:transparent;")
        tr = QHBoxLayout(timeout_row); tr.setContentsMargins(0,0,0,0)
        self._screen_timeout_label = QLabel(self._s('screen_timeout'))
        self._screen_timeout_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
        tr.addWidget(self._screen_timeout_label)
        from PyQt6.QtWidgets import QComboBox as _CB
        self.screen_timeout_combo = _CB()
        self.screen_timeout_combo.setStyleSheet(self._STYLE_MAIN)
        self._screen_timeout_options = [('∞',0),('10',10),('20',20),('30',30),('40',40),('50',50)]
        for label, _ in self._screen_timeout_options:
            self.screen_timeout_combo.addItem(label)
        saved_timeout = self.config.get('screen_inhibit_timeout', 0)
        idx = next((i for i,(_, v) in enumerate(self._screen_timeout_options) if v == saved_timeout), 0)
        self.screen_timeout_combo.setCurrentIndex(idx)
        self.screen_timeout_combo.currentIndexChanged.connect(self._on_screen_timeout_changed)
        tr.addWidget(self.screen_timeout_combo)
        tr.addStretch()
        cl.addWidget(timeout_row)

        vbox.addWidget(card)
        vbox.addStretch()
        return self._scroll_page(outer)

    def _create_lang_page(self):
        outer, vbox = self._page_container('tab_lang')
        card = self._card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        note = QLabel(self._s('lang_note'))
        note.setStyleSheet(f"color:{S_SUB}; font-size:12px; background:transparent;")
        note.setWordWrap(True)
        cl.addWidget(note)
        self._lang_note = note

        bg = QButtonGroup(card)
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
                self._rebuild_pages()
                self._apply_language()

        self._rb_ru.toggled.connect(lambda on: _on_lang('ru', on))
        self._rb_en.toggled.connect(lambda on: _on_lang('en', on))
        cl.addWidget(self._rb_ru)
        cl.addWidget(self._rb_en)

        vbox.addWidget(card)
        vbox.addStretch()
        return self._scroll_page(outer)

    def _create_lib_theme_page(self):
        from library_window import DARK_THEME, LIGHT_THEME
        from PyQt6.QtGui import QColor
        outer, vbox = self._page_container('tab_lib_theme')

        card1 = self._card()
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(16, 16, 16, 16)
        c1.setSpacing(10)

        self._lib_theme_group = self._section_label(self._s('lib_theme_title'))
        c1.addWidget(self._lib_theme_group)

        # Превьюшки-плитки, как в «Готовых темах» ридера (не чекбоксы)
        from library_window import DARK_THEME as _LIB_DARK, LIGHT_THEME as _LIB_LIGHT
        lib_themes_row = QWidget()
        lib_themes_row.setStyleSheet("background:transparent;")
        ltr = QHBoxLayout(lib_themes_row)
        ltr.setContentsMargins(0, 0, 0, 0)
        ltr.setSpacing(8)

        lib_presets = [
            ('dark',  _LIB_DARK['BG'],  _LIB_DARK['TEXT'],  'lib_dark'),
            ('light', _LIB_LIGHT['BG'], _LIB_LIGHT['TEXT'], 'lib_light'),
        ]
        self._lib_theme_btns = {}
        for key, bg, fg, s_key in lib_presets:
            btn = QPushButton(self._s(s_key))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(52)
            btn.setStyleSheet(
                f'QPushButton{{background:{bg};color:{fg};border-radius:8px;'
                f'border:2px solid transparent;font-size:13px;font-weight:600;}}'
                f'QPushButton:checked{{border:2px solid {S_ACCENT};}}'
                f'QPushButton:hover{{border:2px solid rgba(79,142,247,0.5);}}'
            )
            ltr.addWidget(btn)
            self._lib_theme_btns[key] = btn

        btn_lib_custom = QPushButton(self._s('lib_custom'))
        btn_lib_custom.setCheckable(True)
        btn_lib_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_lib_custom.setFixedHeight(52)
        btn_lib_custom.setStyleSheet(
            f'QPushButton{{background:{S_SURFACE};color:{S_TEXT};border-radius:8px;'
            f'border:2px solid transparent;font-size:13px;}}'
            f'QPushButton:checked{{border:2px solid {S_ACCENT};}}'
            f'QPushButton:hover{{border:2px solid rgba(79,142,247,0.5);}}'
        )
        ltr.addWidget(btn_lib_custom)
        self._lib_theme_btns['custom'] = btn_lib_custom

        c1.addWidget(lib_themes_row)

        # Те же имена атрибутов, что и раньше у чекбоксов — весь остальной код
        # файла (_emit_lib_theme, _load_lib_settings и т.д.) работает с ними
        # через общий для QCheckBox/QPushButton API (isChecked/setChecked/toggled)
        # и трогать его не пришлось.
        self._lib_cb_dark   = self._lib_theme_btns['dark']
        self._lib_cb_light  = self._lib_theme_btns['light']
        self._lib_cb_custom = self._lib_theme_btns['custom']

        copy_row = QWidget(); copy_row.setStyleSheet("background:transparent;")
        crh = QHBoxLayout(copy_row); crh.setContentsMargins(0,0,0,0); crh.setSpacing(8)
        self._lib_copy_dark_btn  = QPushButton(); self._lib_copy_dark_btn.setStyleSheet(self._BTN_STYLE)
        self._lib_copy_light_btn = QPushButton(); self._lib_copy_light_btn.setStyleSheet(self._BTN_STYLE)
        self._lib_copy_sys_btn   = QPushButton(); self._lib_copy_sys_btn.setStyleSheet(self._BTN_STYLE)
        for btn in (self._lib_copy_dark_btn, self._lib_copy_light_btn, self._lib_copy_sys_btn):
            btn.setFixedHeight(30)
            crh.addWidget(btn)
        crh.addStretch()
        c1.addWidget(copy_row)
        vbox.addWidget(card1)

        card2 = self._card()
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(16, 16, 16, 16)
        c2.setSpacing(8)

        self._lib_colors_group_lbl = self._section_label(self._s('lib_colors'))
        c2.addWidget(self._lib_colors_group_lbl)
        self._lib_colors_group = card2
        self._lib_color_keys = [
            ("BG","lib_bg"),("SURFACE","lib_surface"),("BORDER","lib_border"),
            ("ACCENT","lib_accent"),("TEXT","lib_text"),("SUB","lib_sub"),
            ("SERIES","lib_series"),("TOOLBAR","lib_toolbar"),("PROGRESS","lib_progress"),
        ]
        self._lib_color_btns    = {}
        self._lib_color_preview = {}
        self._lib_custom_colors = {}
        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w); grid.setContentsMargins(0,0,0,0); grid.setSpacing(6)
        for row, (key, s_key) in enumerate(self._lib_color_keys):
            lbl = QLabel(self._s(s_key))
            lbl.setObjectName(f"_lib_lbl_{key}")
            lbl.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
            preview = QLabel()
            preview.setFixedSize(24, 24)
            preview.setStyleSheet(f"border-radius:12px; border:2px solid {S_BORDER};")
            btn = QPushButton(self._s('choose'))
            btn.setStyleSheet(self._BTN_STYLE)
            btn.setFixedHeight(28)
            grid.addWidget(lbl,     row, 0)
            grid.addWidget(preview, row, 1)
            grid.addWidget(btn,     row, 2)
            self._lib_color_btns[key]    = btn
            self._lib_color_preview[key] = preview
            def _on_pick(checked, k=key):
                cur = self._lib_custom_colors.get(k, "#ffffff")
                c = QColorDialog.getColor(QColor(cur), self)
                if c.isValid():
                    self._lib_custom_colors[k] = c.name()
                    self._lib_color_preview[k].setStyleSheet(
                        f"background:{c.name()};border-radius:12px;border:2px solid {S_BORDER};")
                    if self._lib_cb_custom.isChecked():
                        self._emit_lib_theme()
            btn.clicked.connect(_on_pick)
        c2.addWidget(grid_w)
        vbox.addWidget(card2)

        vbox.addStretch()

        def _on_theme_checkbox_changed(checked_cb):
            if checked_cb.isChecked():
                for cb in [self._lib_cb_dark, self._lib_cb_light, self._lib_cb_custom]:
                    if cb is not checked_cb:
                        cb.setChecked(False)
                self._emit_lib_theme()

        self._lib_cb_dark.toggled.connect(lambda: _on_theme_checkbox_changed(self._lib_cb_dark))
        self._lib_cb_light.toggled.connect(lambda: _on_theme_checkbox_changed(self._lib_cb_light))
        self._lib_cb_custom.toggled.connect(lambda: _on_theme_checkbox_changed(self._lib_cb_custom))

        def _copy_from(src):
            self._lib_custom_colors = dict(src)
            self._update_lib_color_previews()
            if self._lib_cb_custom.isChecked(): self._emit_lib_theme()
            else: self._lib_cb_custom.setChecked(True)

        def _copy_sys():
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPalette
            pal = QApplication.palette()
            def _hex(r): return pal.color(QPalette.ColorGroup.Normal, r).name()
            def _dk(c, f=0.85):
                col=QColor(c); return QColor(int(col.red()*f),int(col.green()*f),int(col.blue()*f)).name()
            win=_hex(QPalette.ColorRole.Window); btn_c=_hex(QPalette.ColorRole.Button)
            _copy_from({"BG":win,"SURFACE":_hex(QPalette.ColorRole.Base),
                "BORDER":_hex(QPalette.ColorRole.Mid),"ACCENT":_hex(QPalette.ColorRole.Highlight),
                "TEXT":_hex(QPalette.ColorRole.WindowText),"SUB":_hex(QPalette.ColorRole.Dark),
                "SERIES":_hex(QPalette.ColorRole.Link),"TOOLBAR":btn_c if btn_c!=win else _dk(win),
                "PROGRESS":_hex(QPalette.ColorRole.Highlight)})

        self._lib_copy_dark_btn.clicked.connect(lambda: _copy_from(DARK_THEME))
        self._lib_copy_light_btn.clicked.connect(lambda: _copy_from(LIGHT_THEME))
        self._lib_copy_sys_btn.clicked.connect(_copy_sys)

        return self._scroll_page(outer)

    def _create_dev_page(self):
        outer, vbox = self._page_container('tab_dev')
        card = self._card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        # Переключатель (toggle switch)
        self.debug_toggle = QToggleSwitch()
        self.debug_toggle.setChecked(self.config.get('debug_log', False))
        self.debug_toggle.toggled.connect(self._on_debug_toggled)

        row1 = QWidget()
        row1.setStyleSheet("background:transparent;")
        rh1 = QHBoxLayout(row1)
        rh1.setContentsMargins(0, 0, 0, 0)
        rh1.addWidget(self.debug_toggle)
        self._debug_log_label = QLabel(self._s('debug_log'))
        self._debug_log_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
        rh1.addWidget(self._debug_log_label)
        rh1.addStretch()
        cl.addWidget(row1)

        self._log_path_label = QLabel()
        self._log_path_label.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
        self._log_path_label.setWordWrap(True)
        cl.addWidget(self._log_path_label)

        vbox.addWidget(card)

        if self.reader_window is None:
            search_card = self._card()
            sl = QVBoxLayout(search_card)
            sl.setContentsMargins(16, 16, 16, 16)
            sl.setSpacing(10)

            self.online_search_toggle = QToggleSwitch()
            self.online_search_toggle.setChecked(self.config.get('online_search_enabled', False))
            self.online_search_toggle.toggled.connect(self._on_online_search_toggled)

            row3 = QWidget()
            row3.setStyleSheet("background:transparent;")
            rh3 = QHBoxLayout(row3)
            rh3.setContentsMargins(0, 0, 0, 0)
            rh3.addWidget(self.online_search_toggle)
            self._online_search_label = QLabel(self._s('online_search_toggle'))
            self._online_search_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
            rh3.addWidget(self._online_search_label)
            rh3.addStretch()
            sl.addWidget(row3)

            self._online_search_note = QLabel(self._s('online_search_toggle_note'))
            self._online_search_note.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
            self._online_search_note.setWordWrap(True)
            sl.addWidget(self._online_search_note)

            vbox.addWidget(search_card)

            dl_card = self._card()
            self._dl_card = dl_card
            dl_card.setVisible(self.config.get('online_search_enabled', False))
            dll = QVBoxLayout(dl_card)
            dll.setContentsMargins(16, 16, 16, 16)
            dll.setSpacing(10)

            self._download_path_sec = self._section_label(self._s('download_path_label'))
            dll.addWidget(self._download_path_sec)

            self._download_path_value = QLabel(str(self.config.get_download_path()))
            self._download_path_value.setStyleSheet(f'color:{S_TEXT}; font-size:12px; background:transparent;')
            self._download_path_value.setWordWrap(True)
            dll.addWidget(self._download_path_value)

            dl_btn_row = QHBoxLayout()
            dl_btn_row.setSpacing(8)
            self._download_path_browse_btn = QPushButton(self._s('download_path_browse'))
            self._download_path_browse_btn.setStyleSheet(self._BTN_STYLE)
            self._download_path_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._download_path_browse_btn.clicked.connect(self._on_browse_download_path)
            dl_btn_row.addWidget(self._download_path_browse_btn)

            self._download_path_reset_btn = QPushButton(self._s('download_path_reset'))
            self._download_path_reset_btn.setStyleSheet(self._BTN_STYLE)
            self._download_path_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._download_path_reset_btn.clicked.connect(self._on_reset_download_path)
            dl_btn_row.addWidget(self._download_path_reset_btn)
            dl_btn_row.addStretch()
            dll.addLayout(dl_btn_row)

            self._download_path_note = QLabel(self._s('download_path_note'))
            self._download_path_note.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
            self._download_path_note.setWordWrap(True)
            dll.addWidget(self._download_path_note)

            vbox.addWidget(dl_card)

        if self.reader_window is None:
            gfx_card = self._card()
            gl = QVBoxLayout(gfx_card)
            gl.setContentsMargins(16, 16, 16, 16)
            gl.setSpacing(10)

            self._gfx_sec = self._section_label(self._s('gfx_backend_label'))
            gl.addWidget(self._gfx_sec)
            self.gfx_combo = QComboBox()
            if sys.platform == 'win32':
                self._gfx_options = [('d3d11', self._s('gfx_d3d11')), ('opengl', self._s('gfx_opengl')), ('vulkan', self._s('gfx_vulkan'))]
                current = self.config.get('windows_graphics_backend', 'd3d11')
            else:
                self._gfx_options = [('vulkan', self._s('gfx_vulkan')), ('opengl', self._s('gfx_opengl'))]
                current = self.config.get('linux_graphics_backend', 'vulkan')
            self.gfx_combo.addItems([label for _, label in self._gfx_options])
            keys = [k for k, _ in self._gfx_options]
            try:
                self.gfx_combo.setCurrentIndex(keys.index(current))
            except ValueError:
                self.gfx_combo.setCurrentIndex(0)
            self.gfx_combo.currentIndexChanged.connect(self._on_gfx_backend_changed)
            gl.addWidget(self.gfx_combo)

            self._gfx_status = QLabel()
            self._gfx_status.setWordWrap(True)
            gl.addWidget(self._gfx_status)
            self._update_gfx_status()

            self._gfx_note = QLabel(self._s('gfx_restart_note'))
            self._gfx_note.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
            self._gfx_note.setWordWrap(True)
            gl.addWidget(self._gfx_note)

            # Переключатель (toggle switch)
            self.gfx_auto_toggle = QToggleSwitch()
            self.gfx_auto_toggle.setChecked(self.config.get('gfx_auto_detect', True))
            self.gfx_auto_toggle.toggled.connect(self._on_gfx_auto_detect_toggled)

            row2 = QWidget()
            row2.setStyleSheet("background:transparent;")
            rh2 = QHBoxLayout(row2)
            rh2.setContentsMargins(0, 0, 0, 0)
            rh2.addWidget(self.gfx_auto_toggle)
            self._gfx_auto_detect_label = QLabel(self._s('gfx_auto_detect'))
            self._gfx_auto_detect_label.setStyleSheet(f"color:{S_TEXT}; font-size:13px; background:transparent;")
            rh2.addWidget(self._gfx_auto_detect_label)
            rh2.addStretch()
            gl.addWidget(row2)

            self._gfx_auto_note = QLabel(self._s('gfx_auto_detect_note'))
            self._gfx_auto_note.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
            self._gfx_auto_note.setWordWrap(True)
            gl.addWidget(self._gfx_auto_note)

            vbox.addWidget(gfx_card)

        vbox.addStretch()
        return self._scroll_page(outer)

    def _apply_language(self):
        self.setWindowTitle(self._s('title'))
        self._close_btn.setText(self._s('close'))
        nav_keys = ['tab_font','tab_layout','tab_highlight','tab_theme','tab_tts',
                    'tab_screen','tab_lang','tab_lib_theme','tab_dev']
        icons = ['\U0001D400  ', '\u229E  ', '\u270F\uFE0E  ', '\u25D1  ',
                 '\u25CE  ', '\u2299  ', '\u2295  ', '\u25A6  ', '\u2699\uFE0E  ']
        for btn, key, icon in zip(self._nav_buttons, nav_keys, icons):
            cur = btn.styleSheet()
            btn.setText(icon + self._s(key))

        # Заголовки самих страниц ("Шрифт"/"Font", "Макет"/"Layout" и т.д.) —
        # раньше переводились только при первом построении страницы и никогда
        # не обновлялись при переключении языка на лету.
        for key in nav_keys:
            title_lbl = getattr(self, f'_page_title_{key}', None)
            if title_lbl is not None:
                title_lbl.setText(self._s(key))

        spread = self.config.get('spread_mode', 'auto')
        self.spread_combo.blockSignals(True)
        self.spread_combo.clear()
        self.spread_combo.addItems([self._s('spread_auto'),self._s('spread_single'),self._s('spread_double')])
        sm = {'auto':self._s('spread_auto'),'none':self._s('spread_single'),'both':self._s('spread_double')}
        self.spread_combo.setCurrentText(sm.get(spread, self._s('spread_auto')))
        self.spread_combo.blockSignals(False)

        hl = self.config.get('default_highlight_style', 'highlight')
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItems([self._s('hl_fill'),self._s('hl_underline'),self._s('hl_squiggly')])
        hlm = {'highlight':self._s('hl_fill'),'underline':self._s('hl_underline'),'squiggly':self._s('hl_squiggly')}
        self.style_combo.setCurrentText(hlm.get(hl, self._s('hl_fill')))
        self.style_combo.blockSignals(False)

        if hasattr(self, '_screen_inhibit_label'):
            self._screen_inhibit_label.setText(self._s('screen_inhibit'))
        if hasattr(self, '_cursor_autohide_label'):
            self._cursor_autohide_label.setText(self._s('cursor_autohide'))
        self._screen_timeout_label.setText(self._s('screen_timeout'))
        self._lang_note.setText(self._s('lang_note'))
        if hasattr(self, '_debug_log_label'):
            self._debug_log_label.setText(self._s('debug_log'))
        self._log_path_label.setText(
            self._s('log_path') + '\n' + str(self.config.config_dir / 'debug.log'))

        if hasattr(self, '_gfx_sec'):
            self._gfx_sec.setText(self._s('gfx_backend_label'))
        if hasattr(self, '_gfx_note'):
            self._gfx_note.setText(self._s('gfx_restart_note'))
        if hasattr(self, '_gfx_auto_detect_label'):
            self._gfx_auto_detect_label.setText(self._s('gfx_auto_detect'))
        if hasattr(self, '_gfx_auto_note'):
            self._gfx_auto_note.setText(self._s('gfx_auto_detect_note'))
        if hasattr(self, '_online_search_label'):
            self._online_search_label.setText(self._s('online_search_toggle'))
        if hasattr(self, '_online_search_note'):
            self._online_search_note.setText(self._s('online_search_toggle_note'))
        if hasattr(self, '_download_path_sec'):
            self._download_path_sec.setText(self._s('download_path_label'))
        if hasattr(self, '_download_path_browse_btn'):
            self._download_path_browse_btn.setText(self._s('download_path_browse'))
        if hasattr(self, '_download_path_reset_btn'):
            self._download_path_reset_btn.setText(self._s('download_path_reset'))
        if hasattr(self, '_download_path_note'):
            self._download_path_note.setText(self._s('download_path_note'))

        if hasattr(self, 'gfx_combo') and hasattr(self, '_gfx_options'):
            current_index = self.gfx_combo.currentIndex()
            self.gfx_combo.blockSignals(True)
            self.gfx_combo.clear()
            key_map = dict(self._gfx_options)
            keys = list(key_map.keys())
            labels = {'vulkan': self._s('gfx_vulkan'), 'opengl': self._s('gfx_opengl'), 'd3d11': self._s('gfx_d3d11')}
            self._gfx_options = [(k, labels[k]) for k in keys]
            self.gfx_combo.addItems([label for _, label in self._gfx_options])
            self.gfx_combo.setCurrentIndex(current_index)
            self.gfx_combo.blockSignals(False)
            self._update_gfx_status()

        if hasattr(self, '_import_font_btn'):
            self._import_font_btn.setText('+ ' + self._s('import_font'))
        if hasattr(self, '_font_reading_sec'):
            self._font_reading_sec.setText(self._s('reading_font').upper())

        self._bg_label.setText(self._s('bg_label'))
        self._text_label.setText(self._s('text_label'))
        self.bg_btn.setText(self._s('choose'))
        self.text_btn.setText(self._s('choose'))

        if hasattr(self, '_lib_cb_dark'):
            self._lib_cb_dark.setText(self._s('lib_dark'))
            self._lib_cb_light.setText(self._s('lib_light'))
            self._lib_cb_custom.setText(self._s('lib_custom'))
        if hasattr(self, '_lib_copy_dark_btn'):
            self._lib_copy_dark_btn.setText(self._s('lib_copy_dark'))
            self._lib_copy_light_btn.setText(self._s('lib_copy_light'))
            self._lib_copy_sys_btn.setText(self._s('lib_copy_sys'))
        for key, s_key in self._lib_color_keys:
            lbl = self._lib_colors_group.findChild(QLabel, f"_lib_lbl_{key}")
            if lbl: lbl.setText(self._s(s_key))
            btn = self._lib_color_btns.get(key)
            if btn: btn.setText(self._s('choose'))

    def _restore_font_selection(self):
        saved = self.config.get('reader_font_family', '')
        if not saved or not hasattr(self, '_font_btns'):
            return
        for btn in self._font_btns:
            is_sel = (btn.text() == saved)
            btn.setChecked(is_sel)
            btn.setStyleSheet(self._font_item_style(is_sel))

    def _load_settings(self):
        self._loading = True
        try:
            fs = int(self.config.get('font_size', 16))
            self.font_size_slider.setValue(fs)
            self.font_size_label.setText(f'{fs}px')
            lh = float(self.config.get('line_height', 1.5))
            self.line_height_slider.setValue(int(lh * 10))
            self.line_height_label.setText(f'{lh:.1f}')
            margin = int(self.config.get('page_margin', 44))
            self.margin_slider.setValue(margin)
            self.margin_label.setText(f'{margin}px')
            saved_tts_color = self.config.get('tts_highlight_color', 'cyan')
            for btn, val in self.tts_color_buttons:
                btn.setChecked(val == saved_tts_color)
            bg   = self.config.get('theme_bg', '#f4ecd8')
            text = self.config.get('theme_text', '#5b4636')
            self._update_color_previews(bg, text)
            saved_theme = self.config.get('theme_name', None)
            _rev = {'Светлая':'light','Light':'light','Тёмная':'dark','Dark':'dark',
                    'Сепия':'sepia','Sepia':'sepia','Пользовательская':'custom','Custom':'custom'}
            _bg_rev = {'#f4ecd8':'light','#1a1a1a':'dark','#fbf0d9':'sepia'}
            theme_key = _rev.get(saved_theme, _bg_rev.get(bg, 'custom'))
            for k, b in self._theme_preset_btns.items():
                b.setChecked(k == theme_key)
            self.custom_card.setVisible(theme_key == 'custom')
        finally:
            self._loading = False
        self._load_lib_settings()

    def _on_font_family_changed(self, family: str, key: str = 'reader_font_family'):
        self._save(key, family)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython({__import__('json').dumps(key)}, {__import__('json').dumps(family)})")

    def _on_font_size_changed(self, v):
        self.font_size_label.setText(f'{v}px')
        self._save('font_size', v)

    def _on_line_height_changed(self, v):
        lh = v / 10.0
        self.line_height_label.setText(f'{lh:.1f}')
        self._save('line_height', lh)

    def _on_spread_mode_changed(self, mode):
        mapping = {}
        for ls in self._S.values():
            mapping[ls['spread_auto']]='auto'; mapping[ls['spread_single']]='none'; mapping[ls['spread_double']]='both'
        self._save('spread_mode', mapping.get(mode, 'auto'))

    def _on_margin_changed(self, v):
        self.margin_label.setText(f'{v}px')
        self._save('page_margin', v)

    def _on_style_changed(self, s):
        mapping = {}
        for ls in self._S.values():
            mapping[ls['hl_fill']]='highlight'; mapping[ls['hl_underline']]='underline'; mapping[ls['hl_squiggly']]='squiggly'
        val = mapping.get(s, 'highlight')
        self._save('default_highlight_style', val)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('default_highlight_style', {json.dumps(val)})")

    def _on_tts_color_selected(self, color):
        for btn, val in self.tts_color_buttons:
            btn.setChecked(val == color)
        self._save('tts_highlight_color', color)
        if not self._loading:
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('tts_highlight_color', {json.dumps(color)})")

    def _update_color_previews(self, bg, text):
        self.bg_preview.setStyleSheet(f'background:{bg}; border-radius:14px; border:2px solid {S_BORDER};')
        self.text_preview.setStyleSheet(f'background:{text}; border-radius:14px; border:2px solid {S_BORDER};')

    def _on_theme_changed(self, theme): pass

    def _on_bg_selected(self):
        c = QColorDialog.getColor(QColor(self.config.get('custom_bg', self.config.get('theme_bg','#f4ecd8'))), self)
        if c.isValid():
            self.config.set('custom_bg', c.name()); self.config.set('theme_bg', c.name())
            self._update_color_previews(c.name(), self.config.get('custom_text', self.config.get('theme_text','#5b4636')))
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme_bg', {json.dumps(c.name())})")

    def _on_text_selected(self):
        c = QColorDialog.getColor(QColor(self.config.get('custom_text', self.config.get('theme_text','#5b4636'))), self)
        if c.isValid():
            self.config.set('custom_text', c.name()); self.config.set('theme_text', c.name())
            self._update_color_previews(self.config.get('custom_bg', self.config.get('theme_bg','#f4ecd8')), c.name())
            self._js(f"window.applySettingFromPython && window.applySettingFromPython('theme_text', {json.dumps(c.name())})")

    def _on_cursor_autohide_toggled(self, checked):
        self.config.set('cursor_autohide', checked)
        if hasattr(self,'_cursor_autohide_changed_cb') and self._cursor_autohide_changed_cb:
            self._cursor_autohide_changed_cb(checked)

    def _on_screen_inhibit_toggled(self, checked):
        self.config.set('screen_inhibit', checked)
        if hasattr(self,'_screen_inhibit_changed_cb') and self._screen_inhibit_changed_cb:
            self._screen_inhibit_changed_cb(checked)

    def _on_screen_timeout_changed(self, idx):
        _, minutes = self._screen_timeout_options[idx]
        self.config.set('screen_inhibit_timeout', minutes)
        if hasattr(self,'_screen_timeout_changed_cb') and self._screen_timeout_changed_cb:
            self._screen_timeout_changed_cb(minutes)

    def _gfx_label_for(self, key: str) -> str:
        labels = {'vulkan': self._s('gfx_vulkan'), 'opengl': self._s('gfx_opengl'), 'd3d11': self._s('gfx_d3d11')}
        return labels.get(key, key)

    def _update_gfx_status(self):
        if not hasattr(self, '_gfx_status') or not hasattr(self, '_gfx_options'):
            return
        keys = [k for k, _ in self._gfx_options]
        idx = self.gfx_combo.currentIndex()
        preferred = keys[idx] if 0 <= idx < len(keys) else keys[0]
        active = self.config.get('_active_graphics_backend', preferred)
        if active != preferred:
            self._gfx_status.setStyleSheet(f'color:#e0a030; font-size:11px; background:transparent;')
            self._gfx_status.setText(self._s('gfx_fallback_warn').format(
                preferred=self._gfx_label_for(preferred), active=self._gfx_label_for(active)))
        else:
            self._gfx_status.setStyleSheet(f'color:{S_SUB}; font-size:11px; background:transparent;')
            self._gfx_status.setText(self._s('gfx_active_now').format(backend=self._gfx_label_for(active)))

    def _on_gfx_auto_detect_toggled(self, checked):
        self.config.set('gfx_auto_detect', checked)

    def _on_gfx_backend_changed(self, index):
        keys = [k for k, _ in self._gfx_options]
        if index < 0 or index >= len(keys):
            return
        value = keys[index]
        if sys.platform == 'win32':
            self.config.set('windows_graphics_backend', value)
        else:
            self.config.set('linux_graphics_backend', value)
        self._update_gfx_status()

    def _on_debug_toggled(self, checked):
        self.config.set('debug_log', checked)
        if checked: self._enable_debug_log()
        else: self._disable_debug_log()
        if hasattr(self,'_dev_mode_changed_cb') and self._dev_mode_changed_cb:
            self._dev_mode_changed_cb(checked)

    def _on_online_search_toggled(self, checked):
        self.config.set('online_search_enabled', checked)
        if hasattr(self, '_dl_card'):
            self._dl_card.setVisible(checked)
        if self._online_search_changed_cb:
            self._online_search_changed_cb(checked)

    def _on_browse_download_path(self):
        from library_window import _styled_get_existing_directory
        current = str(self.config.get_download_path())
        chosen = _styled_get_existing_directory(
            self, self._s('download_path_dialog_title'), current, config=self.config)
        if chosen:
            self.config.set('download_path', chosen)
            self._download_path_value.setText(str(self.config.get_download_path()))

    def _on_reset_download_path(self):
        from config import Config as _Cfg
        default_path = str(_Cfg._get_default_download_dir())
        self.config.set('download_path', default_path)
        self._download_path_value.setText(str(self.config.get_download_path()))

    def _enable_debug_log(self):
        import sys, os
        log_path = self.config.config_dir / 'debug.log'
        try:
            log_fd = os.open(str(log_path), os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o644)
            os.dup2(log_fd, 1); os.dup2(log_fd, 2); os.close(log_fd)
            f = open(str(log_path), 'a', encoding='utf-8', buffering=1)
            sys.stdout = f; sys.stderr = f
            print('[Debug] === Лог включён ===', flush=True)
        except Exception as e:
            sys.__stdout__.write(f'[Debug] Ошибка открытия лога: {e}\n')

    def _disable_debug_log(self):
        import sys, os
        try:
            devnull_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull_fd, 1); os.dup2(devnull_fd, 2); os.close(devnull_fd)
        except Exception: pass
        devnull = open(os.devnull, 'w')
        sys.stdout = devnull; sys.stderr = devnull

    def _on_piper_voices_changed(self):
        installed = self.piper_voices_widget.get_installed_voices()
        self._js(f"if(window._pushPiperVoices){{window._pushPiperVoices({json.dumps(installed)});}}")

    def _load_lib_settings(self):
        from library_window import DARK_THEME, LIGHT_THEME
        name = self.config.get("library_theme_name", "dark")
        custom = self.config.get("library_theme_custom", {})
        if name == "light":
            self._lib_custom_colors = dict(LIGHT_THEME)
        elif name == "custom":
            self._lib_custom_colors = dict(DARK_THEME)
            self._lib_custom_colors.update(custom)
        else:
            self._lib_custom_colors = dict(DARK_THEME)
        self._update_lib_color_previews()
        if hasattr(self, '_lib_cb_dark'):
            self._lib_cb_dark.blockSignals(True)
            self._lib_cb_light.blockSignals(True)
            self._lib_cb_custom.blockSignals(True)
            self._lib_cb_dark.setChecked(name == "dark")
            self._lib_cb_light.setChecked(name == "light")
            self._lib_cb_custom.setChecked(name == "custom")
            self._lib_cb_dark.blockSignals(False)
            self._lib_cb_light.blockSignals(False)
            self._lib_cb_custom.blockSignals(False)
        self._set_lib_pickers_enabled(name == "custom")

    def _update_lib_color_previews(self):
        for key, preview in self._lib_color_preview.items():
            col = self._lib_custom_colors.get(key, "#888888")
            preview.setStyleSheet(f"background:{col};border-radius:12px;border:2px solid {S_BORDER};")

    def _set_lib_pickers_enabled(self, enabled):
        for btn in self._lib_color_btns.values():
            btn.setEnabled(enabled)

    def _rebuild_pages(self):
        """Полностью пересобирает все страницы _stack — так гарантированно
        подхватываются актуальные S_* цвета (при смене темы) и актуальный
        язык (при смене языка), включая все подписи/заголовки, которые
        _apply_language() point-by-point не обновляет (их слишком много,
        разбросаны по 9 страницам, и точечно гоняться за каждой — не
        валидная стратегия, легко что-то забыть, как уже случалось)."""
        if not hasattr(self, '_stack'):
            return
        cur_idx = self._stack.currentIndex()
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
            w.deleteLater()
        self._stack.addWidget(self._create_font_page())
        self._stack.addWidget(self._create_layout_page())
        self._stack.addWidget(self._create_highlight_page())
        self._stack.addWidget(self._create_theme_page())
        self._stack.addWidget(self._create_tts_page())
        self._stack.addWidget(self._create_screen_page())
        self._stack.addWidget(self._create_lang_page())
        self._stack.addWidget(self._create_lib_theme_page())
        self._stack.addWidget(self._create_dev_page())
        self._stack.setCurrentIndex(cur_idx)
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False
        self._restore_font_selection()
        self._load_lib_settings()

    def _sync_theme_to_lib(self, theme_name: str):
        from library_window import DARK_THEME, LIGHT_THEME
        if theme_name == 'light':
            colors = LIGHT_THEME
        elif theme_name == 'custom':
            colors = dict(DARK_THEME)
            colors.update(self.config.get('library_theme_custom', {}))
        else:
            colors = DARK_THEME
        global S_BG, S_SURFACE, S_BORDER, S_ACCENT, S_TEXT, S_SUB, S_HOVER, _P
        bg      = colors.get('BG',      DARK_THEME['BG'])
        surface = colors.get('SURFACE', DARK_THEME['SURFACE'])
        border  = colors.get('BORDER',  DARK_THEME['BORDER'])
        accent  = colors.get('ACCENT',  DARK_THEME['ACCENT'])
        text    = colors.get('TEXT',    DARK_THEME['TEXT'])
        sub     = colors.get('SUB',     DARK_THEME['SUB'])
        hover   = _blend(bg, text, 0.06)
        S_BG      = bg
        S_SURFACE = surface
        S_BORDER  = border
        S_ACCENT  = accent
        S_TEXT    = text
        S_SUB     = sub
        S_HOVER   = hover
        _P = dict(S_BG=bg, S_SURFACE=surface, S_BORDER=border,
                  S_ACCENT=accent, S_TEXT=text, S_SUB=sub, S_HOVER=hover)
        self._build_styles()
        self.setStyleSheet(self._STYLE_MAIN)
        if hasattr(self, '_nav_panel'):
            self._nav_panel.setStyleSheet(
                f"background:{S_BG}; border-right:1px solid {S_BORDER};")
        if hasattr(self, '_nav_buttons'):
            for btn in self._nav_buttons:
                btn.setStyleSheet(self._NAV_STYLE)
        if hasattr(self, '_close_btn'):
            self._close_btn.setStyleSheet(self._BTN_ACCENT_STYLE)
        if hasattr(self, '_stack'):
            self._rebuild_pages()
            self._apply_language()

    def _on_lib_theme_radio(self, name):
        from library_window import DARK_THEME, LIGHT_THEME
        self._set_lib_pickers_enabled(name == "custom")
        if name == "dark":   self._lib_custom_colors = dict(DARK_THEME);  self._update_lib_color_previews()
        elif name == "light": self._lib_custom_colors = dict(LIGHT_THEME); self._update_lib_color_previews()
        self._emit_lib_theme()

    def _emit_lib_theme(self):
        name = ("dark" if (hasattr(self, '_lib_cb_dark') and self._lib_cb_dark.isChecked()) else
                "light" if (hasattr(self, '_lib_cb_light') and self._lib_cb_light.isChecked()) else "custom")
        self.config.set("library_theme_name", name)
        if name == "custom":
            self.config.set("library_theme_custom", dict(self._lib_custom_colors))
        if self._lib_theme_callback:
            self._lib_theme_callback(name, self._lib_custom_colors if name=="custom" else None)
        self._sync_theme_to_lib(name)
