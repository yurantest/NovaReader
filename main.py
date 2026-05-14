#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════╗
# ║  КРИТИЧНО: os.environ для QtWebEngine устанавливаем ПЕРВЫМИ     ║
# ║  до любых импортов PyQt6 — иначе Chromium их игнорирует.        ║
# ╚══════════════════════════════════════════════════════════════════╝
import sys
import os

# Флаги памяти Chromium — ОБЯЗАТЕЛЬНО до любого import PyQt6
# ВАЖНО: флаги должны быть в одной строке, разделенные пробелами
_JS_FLAGS = '--max-old-space-size=256 --expose-gc'
_MEMORY_FLAGS = (
    '--disable-background-networking '
    '--disable-background-timer-throttling '
    '--disable-backgrounding-occluded-windows '
    '--disable-breakpad '
    '--disable-client-side-phishing-detection '
    '--disable-component-update '
    '--disable-default-apps '
    '--disable-dev-shm-usage '
    '--disable-domain-reliability '
    '--disable-extensions '
    '--disable-features=TranslateUI,Prefetch,PreloadMediaEngagementData,AudioServiceOutOfProcess '
    '--disable-gpu-rasterization '
    '--disable-hang-monitor '
    '--disable-ipc-flooding-protection '
    '--disable-notifications '
    '--disable-offer-store-unmasked-wallet-cards '
    '--disable-popup-blocking '
    '--disable-print-preview '
    '--disable-prompt-on-repost '
    '--disable-renderer-backgrounding '
    '--disable-setuid-sandbox '
    '--disable-site-isolation-trials '
    '--disable-speech-api '
    '--disable-sync '
    '--disable-webgl '
    '--disk-cache-size=0 '
    '--media-cache-size=0 '
    # ── Кэши между сессиями: главная причина 1.4 ГБ при повторном запуске ──
    # GPU shader cache (~200-500 МБ): компилированные шейдеры накапливаются
    # на диске и жадно загружаются в память при каждом следующем запуске.
    '--disable-gpu-shader-disk-cache '
    # Code Cache: скомпилированный JS/WASM (reader.html + foliate-js)
    '--aggressive-cache-discard '
    '--disable-application-cache '
    '--disable-offline-load-stale-cache '
    f'--js-flags="{_JS_FLAGS}" '
    '--max_old_space_size=256 '
    '--renderer-process-limit=1 '
    '--single-process '  # Важно: уменьшает потребление памяти
    # ── Прямой доступ к файлам (file:// → fetch другого file://) ──────────
    # Позволяет reader.html загружать книги напрямую с диска через fetch(),
    # минуя base64-кодирование через Python-мост.
    # БЕЗОПАСНО: WebEngine используется как локальный рендерер,
    # доступ в интернет полностью отключён всеми флагами выше.
    '--disable-web-security '
    '--allow-file-access-from-files '
)

if sys.platform == 'win32':
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (
        f'--use-gl=angle --use-angle=d3d11 '
        f'--disable-gpu-sandbox '
        f'--disable-accelerated-2d-canvas '
        f'--disable-accelerated-video-decode '
        f'{_MEMORY_FLAGS}'
    )
    os.environ['ANGLE_FEATURE_OVERRIDES_ENABLED'] = 'force_d3d11'
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

elif sys.platform == 'linux':
    # ==================== VULKAN ====================
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (
        f'--use-gl=angle --use-angle=vulkan '      # ← WebEngine через Vulkan
        f'--disable-gpu-compositing '
        f'--disable-gpu-sandbox '
        f'{_MEMORY_FLAGS}'
    )
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'
    os.environ['QSG_RHI_BACKEND'] = 'vulkan'       # ← Qt Quick интерфейс на Vulkan

# Дополнительные оптимизации Qt WebEngine
os.environ['QTWEBENGINE_LOCALES_PATH'] = ''
os.environ['QT_FORCE_ASS_LOCALES'] = 'ru,en'

# Отключаем ненужные компоненты для уменьшения памяти
os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = ''  # Отключаем отладку

# Важно: устанавливаем максимальный размер памяти до импорта PyQt6
os.environ['QT_QUICK_CONTROLS_MOBILE'] = '0'  # Отключаем мобильные контролы


# ─── ЗАГРУЗКА ФЛАГОВ ИЗ ФАЙЛА NovaReader.flags (как в Chromium) ───
def _load_flags_from_file():
    """
    Загружает дополнительные флаги из файла NovaReader.flags,
    расположенного рядом с исполняемым файлом.
    Формат файла: одна строка с флагами через пробел.
    Аналог chrome-flags.conf в Chromium.
    """
    if not getattr(sys, 'frozen', False):
        return False

    flags_file = Path(sys.executable).parent / 'NovaReader.flags'
    if not flags_file.exists():
        return False

    try:
        with open(flags_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return False

        current = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
        # Добавляем флаги из файла в начало (чтобы их можно было переопределить)
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f"{content} {current}".strip()
        print(f"[App]  Загружены дополнительные флаги из {flags_file.name}")
        return True
    except Exception as e:
        print(f"[App]  Ошибка чтения {flags_file.name}: {e}")
        return False


# Загружаем флаги из файла (если есть)
from pathlib import Path
_load_flags_from_file()


# Теперь можно импортировать остальное
# Подавляем шум ALSA на Linux
if sys.platform != 'win32':
    os.environ.setdefault('ALSA_PCM_CARD', 'default')
    os.environ.setdefault('LIBASOUND_DEBUG', '0')
    try:
        import ctypes
        asound = ctypes.cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(None)
    except Exception:
        pass

if sys.platform == 'win32':
    pass  # рендерер настроен выше через env flags
elif sys.platform == 'linux':
    pass  # рендерер настроен выше через env flags

# Настройка путей Qt WebEngine для скомпилированной версии
if getattr(sys, 'frozen', False):
    app_dir = Path(sys.executable).parent

    # Ищем QtWebEngineProcess
    for base_dir in [app_dir, app_dir / '_internal', app_dir / 'PyQt6', app_dir / 'PyQt6' / 'Qt6']:
        if not base_dir.exists():
            continue
        proc_path = base_dir / 'libexec' / 'QtWebEngineProcess.exe'
        if proc_path.exists():
            os.environ['QTWEBENGINE_PROCESS_PATH'] = str(proc_path)
            break
        proc_path = base_dir / 'libexec' / 'QtWebEngineProcess'
        if proc_path.exists():
            os.environ['QTWEBENGINE_PROCESS_PATH'] = str(proc_path)
            break

# ── Диагностика флагов (только в debug-режиме, буферизируем) ───────────────
_active_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(не установлены!)')
_key_flags = ['--single-process', '--disable-gpu-shader-disk-cache',
              '--disable-web-security', '--disk-cache-size=0',
              '--max-old-space-size=256']
_missing = [f for f in _key_flags if f not in _active_flags]
# Сохраняем диагностику — выведем только если debug_log=True
_startup_diag = []
if _missing:
    _startup_diag.append(f"[App]   ОТСУТСТВУЮТ ключевые флаги: {', '.join(_missing)}")
_startup_diag.append(f"[App]  Chromium флаги: {_active_flags[:140]}{'...' if len(_active_flags) > 140 else ''}")

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFontDatabase, QPixmap, QPainter, QColor, QFont
import time
import subprocess


def _setup_logging(config):
    """Настройка логирования.
    debug_log=True  → все print() и ошибки пишутся в файл debug.log.
    debug_log=False → stdout подавляется, stderr остаётся (реальные ошибки видны).
    """
    import io
    debug_enabled = config.get('debug_log', False)

    if debug_enabled:
        log_path = config.config_dir / 'debug.log'
        try:
            f = open(log_path, 'a', encoding='utf-8', buffering=1)
            sys.stdout = f
            sys.stderr = f
            print(f"[Debug] === Запуск приложения ===")
            for line in _startup_diag:
                print(line)
        except Exception:
            pass
    else:
        # Подавляем только stdout — stderr оставляем для реальных ошибок
        # (ImportError, missing libs, traceback и т.п. будут видны в терминале)
        sys.stdout = io.StringIO()
from config import Config
from library_window import LibraryWindow
from reader_window import ReaderWindow
from wizard_window import WelcomeWizard


def _get_pid_file() -> Path:
    """Путь к PID-файлу текущего экземпляра."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_RUNTIME_DIR', Path(os.environ.get('TMPDIR', '/tmp'))))
    return base / 'novareader.pid'


def _is_process_running(pid: int) -> bool:
    """Проверяет, жив ли процесс с данным PID."""
    try:
        if sys.platform == 'win32':
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x400, False, pid)  # PROCESS_QUERY_INFORMATION
            if handle == 0:
                return False
            exit_code = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == 259  # STILL_ACTIVE
        else:
            os.kill(pid, 0)   # сигнал 0 — только проверка существования
            return True
    except (OSError, ProcessLookupError):
        return False


def _wait_for_previous_instance():
    """
    Ждёт завершения предыдущего экземпляра NovaReader.

    Проблема без этого:
      Старый процесс ещё пишет GPU shader cache → новый стартует,
      _clear_webengine_cache() удаляет файлы → старый дописывает новые →
      Chromium нового экземпляра находит свежие файлы и загружает в RAM → 1.3 ГБ.

    Решение: читаем PID предыдущего запуска. Если процесс жив — ждём до 8 секунд.
    После ожидания (или если процесс уже мёртв) — чистим кэш и запускаем Chromium.
    """
    pid_file = _get_pid_file()
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            old_pid = None

        if old_pid and old_pid != os.getpid() and _is_process_running(old_pid):
            print(f"[App]  Предыдущий экземпляр (PID {old_pid}) ещё работает, ждём...")
            import time as _time
            deadline = _time.monotonic() + 8.0
            while _time.monotonic() < deadline and _is_process_running(old_pid):
                _time.sleep(0.25)
            if _is_process_running(old_pid):
                print(f"[App]  Предыдущий экземпляр не завершился за 8 с, продолжаем")
            else:
                print(f"[App]  Предыдущий экземпляр завершился")

    # Записываем свой PID
    try:
        pid_file.write_text(str(os.getpid()))
    except OSError as e:
        print(f"[App]  Не удалось записать PID-файл: {e}")


def _remove_pid_file():
    """Удаляет PID-файл при завершении."""
    try:
        _get_pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def _get_webengine_cache_dir() -> Path:
    """
    Возвращает путь к директории кэша WebEngine.
    Qt хранит данные в ~/.cache/<AppName>/QtWebEngine/Default/ (Linux)
    или %LOCALAPPDATA%/<AppName>/QtWebEngine/Default/ (Windows).
    """
    import os
    app_name = "NovaReader"
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / app_name / 'QtWebEngine' / 'Default'


def _clear_webengine_cache():
    """
    Удаляет накопившийся GPU shader cache и Code Cache между сессиями.
    Именно эти папки при повторном запуске дают +700-900 МБ к RAM:
    Chromium загружает их целиком в память на старте.

    Безопасно: кэши полностью пересоздаются при следующем запуске.
    Пользовательские данные (закладки, позиции) хранятся в config.json
    и этой очисткой не затрагиваются.
    """
    import shutil
    cache_root = _get_webengine_cache_dir()
    # Удаляем только кэши — не трогаем LocalStorage и IndexedDB
    targets = [
        cache_root / 'GPUCache',        # скомпилированные шейдеры GPU
        cache_root / 'Code Cache',      # скомпилированный JS/WASM
        cache_root / 'Cache',           # HTTP-кэш (уже отключён флагом, но на диске есть)
        cache_root / 'ShaderCache',     # альтернативное имя в некоторых версиях Qt
        cache_root / 'blob_storage',    # временные Blob-объекты
        cache_root / 'DawnCache',       # Dawn GPU shader cache (Qt 6.5+)
    ]
    cleared = []
    for target in targets:
        if target.exists():
            try:
                shutil.rmtree(target)
                cleared.append(target.name)
            except Exception as e:
                print(f"[Cache]  Не удалось очистить {target.name}: {e}")
    if cleared:
        print(f"[Cache]  Очищено: {', '.join(cleared)}")
    else:
        print("[Cache]  Кэш WebEngine чист")


def _configure_webengine_profile():
    """
    Настраивает профиль WebEngine ДО создания любого QWebEngineView.

    Порядок критичен: если вызвать после создания вида — часть кэшей
    уже загружена в память и настройки не имеют эффекта.

    Что делаем:
    - Отключаем HTTP-кэш (NoCache)
    - Направляем persistent storage в temp-директорию (очищается при перезапуске)
    - Отключаем persistent cookies
    - Устанавливаем кастомный cache path → туда пойдёт GPUCache при следующем
      запуске (мы его очищаем в _clear_webengine_cache при старте)
    """
    from PyQt6.QtWebEngineCore import QWebEngineProfile

    profile = QWebEngineProfile.defaultProfile()

    # HTTP-кэш — полностью отключаем
    try:
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
    except AttributeError:
        pass
    profile.setHttpCacheMaximumSize(0)

    # Persistent cookies — не нужны читалке
    try:
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    except AttributeError:
        pass

    # Кастомный cache path — туда Qt запишет GPUCache при этом сеансе.
    # Мы очищаем эту директорию при следующем запуске (_clear_webengine_cache).
    # Нельзя ставить пустую строку — Qt откатится к дефолтному пути.
    cache_dir = _get_webengine_cache_dir()
    try:
        profile.setCachePath(str(cache_dir))
    except AttributeError:
        pass

    # Persistent storage (localStorage с TTS-настройками, IndexedDB).
    # ВАЖНО: нельзя использовать /tmp — localStorage теряется после ребута.
    # НЕЛЬЗЯ использовать /dev/shm — это RAM-диск, увеличивает потребление памяти.
    # Кладём в ~/.config/NovaReader/webengine_storage — рядом с config.json.
    import os
    if sys.platform == 'win32':
        config_base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        config_base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    we_storage = config_base / 'NovaReader' / 'webengine_storage'
    we_storage.mkdir(parents=True, exist_ok=True)
    try:
        profile.setPersistentStoragePath(str(we_storage))
    except AttributeError:
        pass

    print(f"[Profile]  WebEngine профиль настроен (cache→{cache_dir.name}, storage→tmp)")




# ── Иконки/пути ──────────────────────────────────────────────────────────────
_ICON_NAMES_WIN = ["NovaReader_Windows.ico", "NovaReader.ico", "icon.ico",
                   "NovaReader_Linux.png", "NovaReader.png", "icon.png"]
_ICON_NAMES_LIN = ["NovaReader_Linux.png", "NovaReader.png", "icon.png",
                   "NovaReader_Windows.ico", "NovaReader.ico", "icon.ico"]


def _find_icon_path() -> Path | None:
    names = _ICON_NAMES_WIN if sys.platform == 'win32' else _ICON_NAMES_LIN
    if getattr(sys, 'frozen', False):
        roots = [Path(sys.executable).parent]
    else:
        roots = [Path(__file__).parent]
    for root in roots:
        for name in names:
            p = root / name
            if p.exists():
                return p
    return None


def _set_app_icon(app):
    """Устанавливает иконку приложения."""
    from PyQt6.QtGui import QIcon
    p = _find_icon_path()
    if p:
        app.setWindowIcon(QIcon(str(p)))
        print(f"[App] Иконка: {p.name}")
    else:
        print("[App]  Иконка не найдена")


def _load_fonts():
    if getattr(sys, 'frozen', False):
        fonts_dir = Path(sys.executable).parent / 'fonts'
    else:
        fonts_dir = Path(__file__).parent / 'fonts'
    if not fonts_dir.exists():
        print(f"[Font]  Папка fonts/ не найдена: {fonts_dir}")
        return
    for ttf in sorted(fonts_dir.glob('*.ttf')):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            print(f"[Font]  {ttf.name}: {QFontDatabase.applicationFontFamilies(fid)}")
        else:
            print(f"[Font]  Ошибка загрузки: {ttf.name}")


def _make_splash_pixmap(icon_path: Path | None, w: int = 400, h: int = 260) -> QPixmap:
    """
    Рисует сплэш-экран: тёмный фон, иконка (если есть), название и статус.
    Возвращает QPixmap для QSplashScreen.
    """
    px = QPixmap(w, h)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Фон — скруглённый тёмный прямоугольник
    bg = QColor(28, 28, 32)
    painter.setBrush(bg)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, w, h, 16, 16)

    # Тонкая рамка
    painter.setPen(QColor(70, 70, 85))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(1, 1, w - 2, h - 2, 15, 15)

    icon_h = 0
    if icon_path and icon_path.exists():
        icon_px = QPixmap(str(icon_path))
        if not icon_px.isNull():
            size = 80
            icon_px = icon_px.scaled(size, size,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            ix = (w - size) // 2
            painter.drawPixmap(ix, 28, icon_px)
            icon_h = size + 16   # отступ после иконки

    # Название
    title_font = QFont()
    title_font.setPointSize(22)
    title_font.setWeight(QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.setPen(QColor(232, 232, 240))
    ty = 28 + icon_h
    painter.drawText(0, ty, w, 38, Qt.AlignmentFlag.AlignHCenter, "NovaReader")

    # Подпись
    sub_font = QFont()
    sub_font.setPointSize(11)
    painter.setFont(sub_font)
    painter.setPen(QColor(130, 130, 150))
    painter.drawText(0, ty + 42, w, 24, Qt.AlignmentFlag.AlignHCenter,
                     "Инициализация…")

    painter.end()
    return px


def _build_reader_cmd(book_path: str) -> list:
    """
    Возвращает команду для запуска читалки в subprocess.

    Nuitka копирует python3 интерпретатор в dist/ рядом с NovaReader,
    и sys.executable указывает на него — поэтому нельзя определять режим
    по имени exe (python3 есть и в source и в compiled).

    Надёжный способ: ищем NovaReader бинарник рядом с sys.executable.
    Если найден — compiled, запускаем его с --reader.
    Если нет — source, запускаем интерпретатор + скрипт.
    """
    exe_dir = Path(sys.executable).parent
    for app_name in ('NovaReader', 'NovaReader.exe', 'main', 'main.exe'):
        app_bin = exe_dir / app_name
        if app_bin.exists():
            return [str(app_bin), '--reader', book_path]
    # Source-режим
    return [sys.executable, str(Path(__file__).resolve()), '--reader', book_path]


class _SubprocessAppInstance:
    """
    Заглушка app_instance для ReaderWindow запущенного в --reader режиме.
    ReaderWindow ожидает объект с reader_windows и show_library().
    В subprocess библиотека недоступна — show_library() просто закрывает окно.
    """
    def __init__(self, window_ref_holder):
        self._holder = window_ref_holder
        self.library_window = None

    @property
    def reader_windows(self):
        w = self._holder()
        return [w] if w is not None else []

    def show_library(self):
        w = self._holder()
        if w is not None:
            w.close()


def _run_reader_mode(book_path: str):
    """
    Режим читалки: запускается когда NovaReader вызван с флагом --reader.
    Полностью изолированный процесс — при закрытии память освобождается.
    Chromium-флаги уже выставлены вверху main.py до любых импортов PyQt6.
    """
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import QWebEngineProfile

    if not Path(book_path).exists():
        print(f"[ReaderMode] Файл не найден: {book_path}")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("NovaReader")
    _set_app_icon(app)  # иначе Wayland/X11 показывает дефолтный значок

    # Настраиваем WebEngine профиль до создания QWebEngineView
    profile = QWebEngineProfile.defaultProfile()
    try:
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
    except AttributeError:
        pass
    profile.setHttpCacheMaximumSize(0)
    try:
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    except AttributeError:
        pass

    from config import Config
    from reader_window import ReaderWindow

    config = Config()

    _window_ref = [None]
    app_instance = _SubprocessAppInstance(lambda: _window_ref[0])

    window = ReaderWindow(
        config,
        tts_controller=None,
        parent=None,
        app_instance=app_instance,
    )
    _window_ref[0] = window
    window.destroyed.connect(lambda: _window_ref.__setitem__(0, None))

    window.load_book(book_path)
    window.show()

    exit_code = app.exec()
    _window_ref[0] = None
    sys.exit(exit_code)


class EbookReader:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("NovaReader")
        # Отключаем авто-выход при закрытии последнего окна.
        # Иначе закрытие библиотеки убивает все читалки-subprocess через _on_quit.
        # Выход управляется вручную через _check_reader_procs и _on_library_closed.
        self.app.setQuitOnLastWindowClosed(False)
        _load_fonts()

        self.config = Config()
        _setup_logging(self.config)
        _set_app_icon(self.app)

        self.library_window = None
        self.reader_windows = []   # оставляем для обратной совместимости с closeEvent
        self._reader_procs: list[tuple[str, subprocess.Popen]] = []
        self._webengine_ready = False

        # Watchdog: каждую секунду проверяем живые subprocess-читалки.
        # Запускается только после полной инициализации (_initialized=True),
        # иначе срабатывает до создания library_window и вызывает app.quit().
        self._initialized = False
        self._proc_watchdog = QTimer()
        self._proc_watchdog.setInterval(1000)
        self._proc_watchdog.timeout.connect(self._check_reader_procs)
        self._proc_watchdog.start()

        # ── Подготовка WebEngine ──────────────────────────────────────────────
        # 0. Ждём завершения предыдущего экземпляра — иначе старый процесс
        #    успевает записать GPU shader cache ПОСЛЕ нашей очистки.
        _wait_for_previous_instance()
        # 1. Очищаем GPU shader cache и Code Cache с прошлого сеанса.
        #    Именно они дают +700-900 МБ при повторном запуске: Chromium
        #    загружает их целиком в RAM на старте.
        # 2. Настраиваем профиль ДО создания любого QWebEngineView —
        #    если сделать после, часть кэшей уже в памяти.
        _clear_webengine_cache()
        _configure_webengine_profile()

        # ── Сплэш-экран ──────────────────────────────────────────────────────
        # Показываем ДО открытия библиотеки: пока WebEngine инициализируется
        # (компилирует шейдеры, поднимает Chromium), пользователь видит сплэш
        # и не может открыть книгу раньше времени.  Это предотвращает сценарий
        # «открыл книгу до готовности WebEngine → 1.3 ГБ вместо 600–800 МБ».
        icon_path = _find_icon_path()
        splash_px = _make_splash_pixmap(icon_path)
        self._splash = QSplashScreen(splash_px,
                                     Qt.WindowType.WindowStaysOnTopHint |
                                     Qt.WindowType.FramelessWindowHint)
        self._splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._splash.show()
        self.app.processEvents()   # даём Qt отрисовать сплэш немедленно

        # ── Прогрев WebEngine ─────────────────────────────────────────────────
        # Создаём скрытый QWebEngineView — Chromium инициализируется при первом
        # создании экземпляра.  loadFinished сигнализирует о готовности движка:
        # шейдеры скомпилированы, процесс рендерера поднят.
        self._warmup_view = None
        self._start_webengine_warmup()

        # Первый запуск: сразу показываем визард (без ожидания WebEngine —
        # визард не использует WebEngine, блокировки нет).
        if self.config.is_first_run():
            self._show_wizard()
        else:
            # Обычный запуск: ждём готовности WebEngine, потом открываем библиотеку
            self._open_library_when_ready()

    # ── Прогрев WebEngine ─────────────────────────────────────────────────────

    def _start_webengine_warmup(self):
        """
        Прогрев WebEngine: about:blank + фиксированная пауза 3 секунды.

        Почему НЕ reader.html:
          reader.html в скрытом вью = вторая копия в памяти. Когда пользователь
          открывает книгу → новый ReaderWindow грузит ещё одну копию reader.html.
          Два экземпляра одновременно → 1.5 ГБ вместо 850 МБ.
          Плюс reader.html ждёт WebChannel (которого нет в warmup-вью) → 94 секунды.

        Почему about:blank + пауза:
          about:blank запускает Chromium процесс и компилирует базовые GPU шейдеры.
          Пауза 3 с даёт движку время завершить инициализацию до того как пользователь
          сможет открыть книгу. Один экземпляр reader.html → нормальное потребление.
        """
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl

        self._warmup_view = QWebEngineView()
        self._warmup_view.hide()
        self._warmup_view.resize(1, 1)

        def _on_blank_loaded(_ok):
            # about:blank загружен — Chromium поднят, базовые шейдеры компилируются.
            # Ждём ещё 3 секунды чтобы инициализация завершилась.
            elapsed_blank = int((time.monotonic() - self._warmup_start) * 1000)
            print(f"[App]  Chromium запущен ({elapsed_blank} мс), ждём 3 с...")

            def _on_ready():
                if self._webengine_ready:
                    return
                self._webengine_ready = True
                elapsed = int((time.monotonic() - self._warmup_start) * 1000)
                print(f"[App]  WebEngine готов ({elapsed} мс)")
                self._warmup_view.deleteLater()
                self._warmup_view = None
                if getattr(self, '_library_pending', False):
                    self._library_pending = False
                    self._finish_show_library()

            QTimer.singleShot(3000, _on_ready)

        self._warmup_view.loadFinished.connect(_on_blank_loaded)
        self._warmup_view.load(QUrl("about:blank"))
        self._warmup_start = time.monotonic()

        # Жёсткий таймаут 10 с на случай если loadFinished не придёт
        def _timeout():
            if not self._webengine_ready:
                print("[App]  WebEngine warmup timeout — продолжаем")
                if hasattr(self, '_warmup_view') and self._warmup_view:
                    self._warmup_view.deleteLater()
                    self._warmup_view = None
                self._webengine_ready = True
                if getattr(self, '_library_pending', False):
                    self._library_pending = False
                    self._finish_show_library()

        QTimer.singleShot(10000, _timeout)
        print("[App]  Инициализация WebEngine...")
    def _open_library_when_ready(self):
        """Открывает библиотеку: сразу если WebEngine готов, иначе — отложенно."""
        if self._webengine_ready:
            self._finish_show_library()
        else:
            # Поднимем флаг — _on_ready откроет библиотеку сам
            self._library_pending = True
            print("[App]  Библиотека отложена — ждём WebEngine…")

    def _finish_show_library(self):
        """Закрывает сплэш и открывает окно библиотеки."""
        if hasattr(self, '_splash') and self._splash:
            self._splash.close()
            self._splash = None
            print("[App]  Сплэш закрыт")
        self.show_library()

    def _show_wizard(self):
        # Визард не использует WebEngine → показываем сразу, сплэш закрываем
        if hasattr(self, '_splash') and self._splash:
            self._splash.close()
            self._splash = None
        wizard = WelcomeWizard(self.config)
        wizard.setup_completed.connect(self._on_wizard_completed)
        result = wizard.exec()
        if result == 0:
            print("[App] Настройка отменена, выход")
            sys.exit(0)

    def _on_wizard_completed(self, library_path):
        print(f"[App] Библиотека настроена: {library_path}")
        # После визарда WebEngine может быть ещё не готов — ждём
        self._open_library_when_ready()

    def show_library(self):
        if hasattr(self, '_showing_library') and self._showing_library:
            print("[App]  Защита от рекурсивного show_library()")
            return
        if self.library_window and self.library_window.isVisible():
            print("[App] Библиотека уже открыта")
            self.library_window.raise_()
            self.library_window.activateWindow()
            return

        self._showing_library = True
        try:
            if not self.library_window:
                print("[App] Создаём новое окно библиотеки")
                self.library_window = LibraryWindow(self.config)
                # WA_DeleteOnClose: Qt удаляет объект при закрытии окна,
                # а не просто скрывает. Без этого флага destroyed не срабатывает
                # и self.library_window остаётся не-None → app никогда не завершается.
                self.library_window.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self.library_window.book_selected.connect(self.open_book)
                self.library_window.destroyed.connect(self._on_library_closed)
            else:
                print("[App] Показываем существующее окно библиотеки")

            self.library_window.show()
            self._initialized = True
            self.library_window.raise_()
            self.library_window.activateWindow()
        finally:
            self._showing_library = False

    def _on_library_closed(self):
        self.library_window = None
        alive = [p for _, p in self._reader_procs if p.poll() is None]
        if not alive:
            self.app.quit()

    def open_book(self, book_path):
        if hasattr(self, '_opening_book') and self._opening_book:
            print("[App]  Защита от рекурсивного open_book()")
            return

        self._opening_book = True
        try:
            print(f"[App] Opening book: {book_path}")

            # Если эта книга уже открыта в живом subprocess — не запускаем повторно
            for bp, proc in list(self._reader_procs):
                if bp == book_path and proc.poll() is None:
                    print(f"[App] Книга уже открыта в процессе PID={proc.pid}, пропускаем")
                    return

            # Сначала перечитываем positions.json с диска — subprocess мог записать
            # свежий прогресс после последнего тика watchdog'а (раз в секунду).
            # Только потом mark_as_read — иначе setdefault создаст пустую запись
            # и save_positions() сотрёт прогресс ещё до запуска нового subprocess'а.
            self.config._positions = self.config._load_positions()
            self.config.mark_as_read(book_path)

            if self.library_window:
                self.library_window._on_library_updated()

            # Запускаем читалку в отдельном процессе
            cmd = _build_reader_cmd(book_path)
            proc = subprocess.Popen(cmd, env=os.environ.copy())
            self._reader_procs.append((book_path, proc))
            print(f"[App] Читалка запущена, PID={proc.pid}")
        finally:
            self._opening_book = False

    def _check_reader_procs(self):
        """
        Вызывается каждую секунду. Убирает завершившиеся subprocess'ы.
        Если библиотека закрыта и читалок не осталось — выходим.
        """
        if not self._initialized:
            return
        before = len(self._reader_procs)
        self._reader_procs = [(bp, p) for bp, p in self._reader_procs
                              if p.poll() is None]
        finished = before - len(self._reader_procs)
        if finished:
            print(f"[App] Читалок завершилось: {finished}, осталось: {len(self._reader_procs)}")
            # Subprocess записал позицию в positions.json — перечитываем с диска.
            # Без этого главный процесс показывает устаревший прогресс из памяти.
            self.config._positions = self.config._load_positions()
            # Обновляем библиотеку только если она видима — иначе лишний reflow
            if self.library_window and self.library_window.isVisible():
                self.library_window._on_library_updated()

        if not self._reader_procs and not self.library_window:
            print("[App] Все читалки закрыты и библиотека закрыта — выход")
            self._proc_watchdog.stop()
            self.app.quit()

    def run(self):
        def _on_quit():
            _remove_pid_file()
            # Завершаем все живые читалки при закрытии главного процесса
            for _, proc in self._reader_procs:
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except OSError:
                        pass

        self.app.aboutToQuit.connect(_on_quit)
        return self.app.exec()


def main():
    # --reader <book_path> — режим читалки (запускается как subprocess)
    if '--reader' in sys.argv:
        idx = sys.argv.index('--reader')
        if idx + 1 < len(sys.argv):
            _run_reader_mode(sys.argv[idx + 1])
        else:
            print("Использование: NovaReader --reader <book_path>")
            sys.exit(1)
    else:
        app = EbookReader()
        sys.exit(app.run())


if __name__ == "__main__":
    main()
