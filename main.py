#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════╗
# ║  КРИТИЧНО: os.environ для QtWebEngine устанавливаем ПЕРВЫМИ     ║
# ║  до любых импортов PyQt6 — иначе Chromium их игнорирует.        ║
# ╚══════════════════════════════════════════════════════════════════╝
import sys
import os
import json
import subprocess
from pathlib import Path

os.environ.setdefault('MALLOC_ARENA_MAX', '2')

# ── SSL-сертификаты: гарантируем рабочий CA bundle для requests ────────
# В standalone-сборке Nuitka пакет certifi не всегда утягивает cacert.pem
# как package-data — это не .py-модуль, а просто файл данных, и
# --include-package=requests сам по себе не гарантирует его копирование.
# На Linux это часто маскируется системным fallback (/etc/ssl/certs),
# на Windows такого fallback нет вообще — там requests/urllib3 просто
# падает с CERTIFICATE_VERIFY_FAILED на любой HTTPS-запрос (загрузка
# голосов Piper, облачные книги), и это может выглядеть как "загрузка
# вообще не работает" без явной причины на экране.
# Устанавливаем переменные окружения ДО запуска дочерних процессов
# (voice_download_worker и т.п.) — они наследуют окружение через QProcess.
try:
    import certifi
    _cacert_path = certifi.where()
    if Path(_cacert_path).exists():
        os.environ.setdefault('SSL_CERT_FILE', _cacert_path)
        os.environ.setdefault('REQUESTS_CA_BUNDLE', _cacert_path)
    else:
        print(f'[App] certifi.where() указывает на несуществующий файл: {_cacert_path}')
except Exception as _certifi_err:
    print(f'[App] Не удалось настроить certifi CA bundle: {_certifi_err}')


def _get_config_dir() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        xdg = os.environ.get('XDG_CONFIG_HOME', '')
        base = Path(xdg) if xdg else Path.home() / '.config'
    return base / 'NovaReader'


def _read_setting(key: str, default):
    try:
        settings_file = _get_config_dir() / 'settings.json'
        if settings_file.exists():
            data = json.loads(settings_file.read_text(encoding='utf-8'))
            return data.get(key, default)
    except Exception:
        pass
    return default


_APP_NAME = "NovaReader"


def _rebrand_webengine_process():
    """
    Копирует бинарник QtWebEngineProcess под именем программы и указывает
    Chromium использовать эту копию через QTWEBENGINE_PROCESS_PATH.

    Зачем: без этого все дочерние процессы Chromium (по одному на
    рендерер/GPU) видны в диспетчере задач/системном мониторе под именем
    "QtWebEngineProcess" - отдельно от главного процесса программы, и
    внешне непонятно, что они вообще относятся к этому приложению.
    Переименованная копия решает именно это: имя видимого процесса
    (Image Name в Task Manager -> Подробности, comm/argv0 в ps/top/htop/
    GNOME System Monitor) совпадает с именем программы, как это сделано,
    например, у Chrome/Electron-приложений с их "Helper"-процессами.

    Работает и для запуска из исходников (venv/pip), и для frozen-сборки -
    раньше подмена пути делалась только для frozen. Копия кладётся в
    кэш-папку и переиспользуется между запусками (копируем заново только
    если оригинал в установке Qt изменился).

    Важно для Windows: колонка "Имя образа" в диспетчере задач
    (вкладка "Подробности") покажет "NovaReader.exe" корректно сразу.
    А вот группировка по значку/описанию во вкладке "Процессы" зависит
    ещё и от VERSIONINFO-ресурса внутри exe (Компания/Продукт/Описание
    файла) - при простом копировании файла этот ресурс остаётся от Qt
    ("Qt WebEngine Process"), и для полной подмены там его нужно
    дополнительно патчить инструментом вроде rcedit на этапе сборки
    (см. build.py) - это отдельный шаг, сюда не включён.
    """
    exe_suffix = '.exe' if sys.platform == 'win32' else ''
    target_name = f'{_APP_NAME}{exe_suffix}'

    candidates = []
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
        for base_dir in [app_dir, app_dir / '_internal', app_dir / 'PyQt6', app_dir / 'PyQt6' / 'Qt6']:
            candidates.append(base_dir / 'libexec' / f'QtWebEngineProcess{exe_suffix}')
    else:
        # Запуск из исходников: ищем оригинал внутри установленного пакета
        # PyQt6-WebEngine (стандартный layout pip-колеса).
        try:
            import PyQt6
            pyqt_dir = Path(PyQt6.__file__).parent
            candidates.append(pyqt_dir / 'Qt6' / 'libexec' / f'QtWebEngineProcess{exe_suffix}')
            candidates.append(pyqt_dir / 'Qt6' / 'bin' / f'QtWebEngineProcess{exe_suffix}')
        except Exception:
            pass

    source = next((c for c in candidates if c.exists()), None)
    if source is None:
        return  # оригинал не нашли - остаётся штатное поведение Qt

    if sys.platform == 'win32':
        cache_base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        cache_base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    dest = cache_base / _APP_NAME / 'webengine-process' / target_name

    try:
        need_copy = (
            not dest.exists()
            or dest.stat().st_size != source.stat().st_size
            or dest.stat().st_mtime < source.stat().st_mtime
        )
        if need_copy:
            import shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            if sys.platform != 'win32':
                dest.chmod(0o755)
        os.environ['QTWEBENGINE_PROCESS_PATH'] = str(dest)
        if sys.platform == 'win32':
            import gpu_preference
            _gpu_pref = _read_setting('windows_gpu_preference', 'auto')
            if _gpu_pref in ('power_saving', 'high_performance'):
                # Явная настройка пользователя (Настройки -> GPU) -
                # применяем к обоим exe одинаково.
                gpu_preference.set_gpu_preference(_gpu_pref, [sys.executable, dest])
            else:
                # Настройка не задана - подхватываем то, что пользователь
                # мог включить вручную через NVIDIA/AMD панель для
                # главного exe, и синхронизируем на хелпер.
                gpu_preference.sync_gpu_preference(sys.executable, dest)
    except OSError as e:
        print(f'[App] Не удалось подготовить переименованный QtWebEngineProcess: {e}')



# CPU-оптимизация (2026-09): раньше --max-old-space-size=256 держал V8-кучу
# слишком тесной для перевёрстки книги -> частые GC-паузы жрали CPU при
# листании. 384 МБ — разумный компромисс: чуть больше памяти, заметно
# меньше сборок мусора.
_JS_FLAGS = '--max-old-space-size=384 --expose-gc'
_MEMORY_FLAGS = (
    '--disable-background-networking '
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
    '--disable-setuid-sandbox '
    '--disable-site-isolation-trials '
    '--disable-speech-api '
    '--disable-sync '
    '--disable-webgl '
    '--disk-cache-size=52428800 '
    '--media-cache-size=0 '
    '--aggressive-cache-discard '
    f'--js-flags="{_JS_FLAGS}" '
    '--renderer-process-limit=1 '
    '--disable-web-security '
    '--allow-file-access-from-files '
)
# ЯВНО убраны (были причиной высокой нагрузки на CPU, см. память проекта):
#   --single-process                     -> рендерер/GPU/браузер делят один
#                                            поток, конкурируя с Qt/Python;
#                                            без него нагрузка размазывается
#                                            по ядрам и падает на слабом CPU
#                                            (цена: +1 процесс, ~30-60 МБ).
#   --disable-background-timer-throttling
#   --disable-backgrounding-occluded-windows
#   --disable-renderer-backgrounding     -> запрещали Chromium снижать частоту
#                                            таймеров/рендера в свёрнутом/
#                                            неактивном окне - читалка грузила
#                                            CPU даже в фоне.
#   --disable-gpu-shader-disk-cache
#   --disable-application-cache
#   --disable-offline-load-stale-cache   -> вместе с NoCache гасили кэш
#                                            скомпилированного V8-байткода
#                                            движка ibc/*.js -> перекомпиляция
#                                            JS при каждом открытии книги.
#   --max_old_space_size=256 (без дефиса) -> несуществующий для Chromium флаг,
#                                            мёртвый код, ни на что не влиял.


# ── Гибридная графика (Linux) ───────────────────────────────────────
def _linux_detect_gpu_vendors() -> set:
    vendors = set()
    vendor_ids = {'0x8086': 'intel', '0x10de': 'nvidia', '0x1002': 'amd', '0x1022': 'amd'}
    try:
        drm_dir = Path('/sys/class/drm')
        if not drm_dir.exists():
            return vendors
        for card in sorted(drm_dir.glob('card[0-9]*')):
            if '-' in card.name:
                continue
            vendor_file = card / 'device' / 'vendor'
            try:
                vid = vendor_file.read_text().strip().lower()
                if vid in vendor_ids:
                    vendors.add(vendor_ids[vid])
            except Exception:
                continue
    except Exception:
        pass
    return vendors


def _linux_apply_hybrid_gpu_env(vendors: set):
    if 'nvidia' in vendors and 'intel' in vendors:
        os.environ.setdefault('__NV_PRIME_RENDER_OFFLOAD', '1')
        os.environ.setdefault('__GLX_VENDOR_LIBRARY_NAME', 'nvidia')
        os.environ.setdefault('__VK_LAYER_NV_optimus', 'NVIDIA_only')
        print('[GPU] Гибридная графика Intel+Nvidia — включён PRIME render offload.')
    elif 'amd' in vendors and 'intel' in vendors:
        os.environ.setdefault('DRI_PRIME', '1')
        print('[GPU] Гибридная графика Intel+AMD — включён DRI_PRIME offload.')


def _linux_primary_gpu_pci_id() -> str:
    try:
        drm_dir = Path('/sys/class/drm')
        if not drm_dir.exists():
            return ''
        for card in sorted(drm_dir.glob('card[0-9]*')):
            if '-' in card.name:
                continue
            dev_dir = card / 'device'
            try:
                vendor = dev_dir.joinpath('vendor').read_text().strip().lower()
                device = dev_dir.joinpath('device').read_text().strip().lower()
                if vendor.startswith('0x'):
                    vendor = vendor[2:]
                if device.startswith('0x'):
                    device = device[2:]
                if vendor and device:
                    return f'{vendor}:{device}'
            except Exception:
                continue
    except Exception:
        pass
    return ''


def _linux_force_vulkan_device_selection():
    if os.environ.get('MESA_VK_DEVICE_SELECT'):
        return
    pci_id = _linux_primary_gpu_pci_id()
    if pci_id:
        os.environ['MESA_VK_DEVICE_SELECT'] = pci_id
        print(f'[GPU] Закреплён Vulkan-девайс по умолчанию: {pci_id} (MESA_VK_DEVICE_SELECT)')


def _linux_has_vulkan() -> bool:
    try:
        import ctypes
        import ctypes.util
        lib_name = ctypes.util.find_library('vulkan') or 'libvulkan.so.1'
        ctypes.CDLL(lib_name)
        return True
    except Exception:
        return False


def _windows_has_d3d11() -> bool:
    try:
        import ctypes
        d3d11 = ctypes.WinDLL('d3d11.dll')
        d3d11.D3D11CreateDevice.restype = ctypes.HRESULT
        feature_levels = (ctypes.c_uint * 4)(0xc100, 0xb000, 0xa100, 0xa000)
        hr = d3d11.D3D11CreateDevice(
            None, 1, None, 0, feature_levels, 4, 7, None, None, None
        )
        if hr == 0 or hr == 1:
            print(f'[GPU] D3D11 поддерживается (HRESULT={hr})')
            return True
        else:
            print(f'[GPU] D3D11 не поддерживается (HRESULT=0x{hr & 0xFFFFFFFF:08X})')
            return False
    except Exception as e:
        print(f'[GPU] Ошибка проверки D3D11: {e}')
        return False


# ── Настройки отключения GPU-композитинга для каждого бэкенда ──────
_disable_vulkan = _read_setting('disable_gpu_compositing_vulkan', True)
_disable_opengl = _read_setting('disable_gpu_compositing_opengl', False)
_disable_d3d11   = _read_setting('disable_gpu_compositing_d3d11', False)

# Экспериментально: развести два независимых потребителя Vulkan в Chromium.
#   --use-angle=vulkan     -> ANGLE (эмуляция GL/GLES) сидит на Vulkan
#   --enable-features=Vulkan --use-vulkan=native -> Skia/композитор Chromium
#                              сидит на Vulkan напрямую, без участия ANGLE
# По умолчанию Chromium сажает оба на один и тот же VkDevice/очередь - на
# некоторых связках драйвер+GPU (напр. AMD RADV) это приводит к конфликту
# за очередь ("device busy") и краху GPU-процесса. Раз WebGL и так выключен
# (--disable-webgl), ANGLE вообще не обязан использовать Vulkan - можно
# оставить его на обычном GL, а композитор Skia посадить на Vulkan отдельно.
_vulkan_direct_native = _read_setting('vulkan_direct_native', False)


def _vulkan_gl_flags() -> str:
    if _vulkan_direct_native:
        return '--use-gl=angle --use-angle=gl --enable-features=Vulkan --use-vulkan=native '
    return '--use-gl=angle --use-angle=vulkan '


if sys.platform == 'win32':
    _gfx_backend = _read_setting('windows_graphics_backend', 'd3d11')
    _gfx_auto_detect = _read_setting('gfx_auto_detect', True)
    if _gfx_auto_detect and _gfx_backend == 'd3d11' and not _windows_has_d3d11():
        print('[GPU] D3D11 не поддерживается — переключаюсь на OpenGL.')
        _gfx_backend = 'opengl'
    if _gfx_backend == 'auto':
        # Экспериментально (2026-09): подход Calibre - вообще не форсировать
        # ANGLE-бэкенд (--use-gl/--use-angle) и не выключать отдельные
        # функции (2D canvas, video decode). Chromium сам выбирает лучший
        # доступный вариант под конкретную видеокарту/драйвер, как в
        # обычном Chrome. Из наших флагов остаются только общие
        # memory/CPU-оптимизации (_MEMORY_FLAGS), которые к выбору
        # GPU-бэкенда отношения не имеют.
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = _MEMORY_FLAGS
        os.environ.pop('ANGLE_FEATURE_OVERRIDES_ENABLED', None)
        os.environ.pop('QSG_RHI_BACKEND', None)
    elif _gfx_backend == 'opengl':
        flags = (
            f'--use-gl=angle --use-angle=gl '
            f'--max-frame-rate=60 '
            f'--disable-accelerated-2d-canvas '
            f'--disable-accelerated-video-decode '
            f'{_MEMORY_FLAGS}'
        )
        if _disable_opengl:
            flags = '--disable-gpu-compositing ' + flags
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
        os.environ.pop('ANGLE_FEATURE_OVERRIDES_ENABLED', None)
        os.environ['QSG_RHI_BACKEND'] = 'opengl'
    elif _gfx_backend == 'vulkan':
        flags = (
            f'{_vulkan_gl_flags()}'
            f'--max-frame-rate=60 '
            f'--disable-accelerated-2d-canvas '
            f'--disable-accelerated-video-decode '
            f'{_MEMORY_FLAGS}'
        )
        if _disable_vulkan:
            flags = '--disable-gpu-compositing ' + flags
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
        os.environ.pop('ANGLE_FEATURE_OVERRIDES_ENABLED', None)
        os.environ['QSG_RHI_BACKEND'] = 'vulkan'
    else:
        flags = (
            f'--use-gl=angle --use-angle=d3d11 '
            f'--max-frame-rate=60 '
            f'--disable-accelerated-2d-canvas '
            f'--disable-accelerated-video-decode '
            f'{_MEMORY_FLAGS}'
        )
        if _disable_d3d11:
            flags = '--disable-gpu-compositing ' + flags
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
        os.environ['ANGLE_FEATURE_OVERRIDES_ENABLED'] = 'force_d3d11'
        os.environ['QSG_RHI_BACKEND'] = 'd3d11'
    # QTWEBENGINE_DISABLE_SANDBOX оставлен как есть (нужен для AppImage/
    # портативных сборок - без него Chromium может отказаться стартовать
    # из-за setuid-прав chrome-sandbox). --disable-gpu-sandbox же убран
    # (2026-09) в рамках теста: с ним GPU у Chromium уходил в тот же
    # процесс (--in-process-gpu), и потеря контекста (см. крэши с Vulkan-
    # композитингом) валила рендеринг без возможности изолированного
    # восстановления. Без --disable-gpu-sandbox GPU остаётся в отдельном
    # процессе - должно быть чуть больше памяти, но устойчивее к сбоям GPU.
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

elif sys.platform == 'linux':
    _gpu_vendors = _linux_detect_gpu_vendors()
    if len(_gpu_vendors) > 1:
        print(f'[GPU] Обнаружена гибридная видеосистема: {", ".join(sorted(_gpu_vendors))}.')
        _linux_apply_hybrid_gpu_env(_gpu_vendors)
    _linux_force_vulkan_device_selection()

    _gfx_backend = _read_setting('linux_graphics_backend', 'opengl')
    _gfx_auto_detect = _read_setting('gfx_auto_detect', True)
    if _gfx_auto_detect and _gfx_backend == 'vulkan' and not _linux_has_vulkan():
        print('[GPU] Vulkan не поддерживается — переключаюсь на OpenGL.')
        _gfx_backend = 'opengl'
    if _gfx_backend == 'auto':
        # См. комментарий в ветке Windows выше - тот же подход Calibre.
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = _MEMORY_FLAGS
        os.environ.pop('QSG_RHI_BACKEND', None)
    elif _gfx_backend == 'opengl':
        flags = (
            f'--use-gl=angle --use-angle=gl '
            f'--max-frame-rate=60 '
            f'{_MEMORY_FLAGS}'
        )
        if _disable_opengl:
            flags = '--disable-gpu-compositing ' + flags
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
        os.environ['QSG_RHI_BACKEND'] = 'opengl'
    else:
        flags = (
            f'{_vulkan_gl_flags()}'
            f'--max-frame-rate=60 '
            f'{_MEMORY_FLAGS}'
        )
        if _disable_vulkan:
            flags = '--disable-gpu-compositing ' + flags
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
        os.environ['QSG_RHI_BACKEND'] = 'vulkan'
    os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

# Дополнительные оптимизации
os.environ['QTWEBENGINE_LOCALES_PATH'] = ''
os.environ['QT_FORCE_ASS_LOCALES'] = 'ru,en'
os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = ''
os.environ['QT_QUICK_CONTROLS_MOBILE'] = '0'


def _load_flags_from_file():
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
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f"{content} {current}".strip()
        print(f"[App] Загружены дополнительные флаги из {flags_file.name}")
        return True
    except Exception as e:
        print(f"[App] Ошибка чтения {flags_file.name}: {e}")
        return False


_load_flags_from_file()

if sys.platform != 'win32':
    os.environ.setdefault('ALSA_PCM_CARD', 'default')
    os.environ.setdefault('LIBASOUND_DEBUG', '0')
    try:
        import ctypes
        asound = ctypes.cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(None)
    except Exception:
        pass

_rebrand_webengine_process()

_active_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(не установлены!)')
# Обновлено вместе с CPU-оптимизацией _MEMORY_FLAGS: --single-process,
# --disable-gpu-shader-disk-cache и --disk-cache-size=0 больше не
# выставляются намеренно (см. комментарии у _MEMORY_FLAGS выше).
_key_flags = ['--disable-web-security', '--disk-cache-size=52428800',
              '--renderer-process-limit=1']
_missing = [f for f in _key_flags if f not in _active_flags]
_startup_diag = []
if _missing:
    _startup_diag.append(f"[App] ОТСУТСТВУЮТ ключевые флаги: {', '.join(_missing)}")
_startup_diag.append(f"[App] Chromium флаги: {_active_flags[:140]}{'...' if len(_active_flags) > 140 else ''}")


# ── Проверка системных зависимостей X11 ────────────────────────────────────
_SO_TO_APT_PACKAGE = {
    'libxcb-cursor.so.0':      'libxcb-cursor0',
    'libxcb-icccm.so.4':       'libxcb-icccm4',
    'libxcb-image.so.0':       'libxcb-image0',
    'libxcb-keysyms.so.1':     'libxcb-keysyms1',
    'libxcb-randr.so.0':       'libxcb-randr0',
    'libxcb-render-util.so.0': 'libxcb-render-util0',
    'libxcb-shape.so.0':       'libxcb-shape0',
    'libxcb-shm.so.0':         'libxcb-shm0',
    'libxcb-sync.so.1':        'libxcb-sync1',
    'libxcb-xfixes.so.0':      'libxcb-xfixes0',
    'libxcb-xinerama.so.0':    'libxcb-xinerama0',
    'libxcb-glx.so.0':         'libxcb-glx0',
    'libxkbcommon-x11.so.0':   'libxkbcommon-x11-0',
    'libxkbcommon.so.0':       'libxkbcommon0',
    'libGL.so.1':              'libgl1',
    'libEGL.so.1':             'libegl1',
    'libdbus-1.so.3':          'libdbus-1-3',
    'libfontconfig.so.1':      'libfontconfig1',
}


def _find_qxcb_plugin_path():
    try:
        import importlib.util
        spec = importlib.util.find_spec('PyQt6')
        if spec is None or not spec.submodule_search_locations:
            return None
        pyqt6_dir = Path(list(spec.submodule_search_locations)[0])
        for rel in ('Qt6/plugins/platforms/libqxcb.so', 'Qt/plugins/platforms/libqxcb.so'):
            p = pyqt6_dir / rel
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _check_linux_x11_missing_libs():
    if sys.platform != 'linux':
        return []
    plugin_path = _find_qxcb_plugin_path()
    if plugin_path is None:
        return []
    try:
        result = subprocess.run(['ldd', str(plugin_path)], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    missing = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if '=> not found' in line:
            missing.append(line.split('=>')[0].strip())
    return missing


def _show_missing_deps_message(missing_libs=None, missing_pip_pkgs=None):
    lines = []
    apt_packages = []
    if missing_libs:
        apt_packages = sorted({_SO_TO_APT_PACKAGE.get(lib, lib) for lib in missing_libs})
        lines.append("Не хватает системных библиотек для запуска под X11:")
        lines.extend(f"  • {lib}" for lib in missing_libs)
        lines.append("")
        lines.append("Установите пакеты (Debian/Ubuntu):")
        lines.append("  sudo apt install " + ' '.join(apt_packages))
        lines.append("")
        lines.append("На Fedora/RHEL названия пакетов могут отличаться —")
        lines.append("ищите по имени библиотеки в 'dnf provides <имя>.so'.")
    if missing_pip_pkgs:
        if lines:
            lines.append("")
        lines.append("Не хватает Python-пакетов:")
        lines.extend(f"  • {pkg}" for pkg in missing_pip_pkgs)
        lines.append("")
        lines.append("Установите их командой:")
        lines.append("  pip install " + ' '.join(missing_pip_pkgs))
    message = "NovaReader не может запуститься.\n" + "\n".join(lines)
    print(f"\n{'='*70}\n{message}\n{'='*70}\n", file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showerror("NovaReader — не хватает зависимостей", message)
        root.destroy()
    except Exception:
        pass


_missing_x11_libs = _check_linux_x11_missing_libs()
if _missing_x11_libs:
    _show_missing_deps_message(missing_libs=_missing_x11_libs)
    sys.exit(1)

try:
    from PyQt6.QtWidgets import QApplication, QSplashScreen
except ImportError as _pyqt_err:
    _missing_pip = ['PyQt6']
    if 'WebEngine' in str(_pyqt_err) or 'QtWebEngine' in str(_pyqt_err):
        _missing_pip = ['PyQt6-WebEngine']
    _show_missing_deps_message(missing_pip_pkgs=_missing_pip)
    sys.exit(1)

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFontDatabase, QPixmap, QPainter, QColor, QFont
import time
import subprocess


def _setup_logging(config):
    import os as _os
    debug_enabled = config.get('debug_log', False)
    if sys.platform == 'win32':
        if debug_enabled:
            try:
                log_path = config.config_dir / 'debug.log'
                log_fd = _os.open(str(log_path),
                                  _os.O_WRONLY | _os.O_CREAT | _os.O_APPEND, 0o644)
                _os.dup2(log_fd, 1)
                _os.dup2(log_fd, 2)
                _os.close(log_fd)
                f = _os.fdopen(_os.dup(1), 'w', encoding='utf-8', errors='replace')
                sys.stdout = f
                sys.stderr = f
                print("[Debug] === Запуск приложения ===", flush=True)
                for line in _startup_diag:
                    print(line, flush=True)
            except Exception as e:
                print(f"[Warning] Не удалось открыть лог-файл: {e}", flush=True)
        else:
            print("[Setup] Windows: подавление вывода ОТКЛЮЧЕНО", flush=True)
            return
    if debug_enabled:
        log_path = config.config_dir / 'debug.log'
        try:
            log_fd = _os.open(str(log_path),
                              _os.O_WRONLY | _os.O_CREAT | _os.O_APPEND, 0o644)
            _os.dup2(log_fd, 1)
            _os.dup2(log_fd, 2)
            _os.close(log_fd)
            f = _os.fdopen(_os.dup(1), 'w', encoding='utf-8', errors='replace')
            sys.stdout = f
            sys.stderr = f
            print("[Debug] === Запуск приложения ===", flush=True)
            for line in _startup_diag:
                print(line, flush=True)
        except Exception:
            pass
    else:
        try:
            devnull_fd = _os.open(_os.devnull, _os.O_WRONLY)
            _os.dup2(devnull_fd, 1)
            _os.dup2(devnull_fd, 2)
            _os.close(devnull_fd)
        except Exception:
            pass
        _devnull = open(_os.devnull, 'w')
        sys.stdout = _devnull
        sys.stderr = _devnull


from config import Config
from library_window import LibraryWindow
from reader_window import ReaderWindow
from wizard_window import WelcomeWizard


def _get_pid_file() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_RUNTIME_DIR', Path(os.environ.get('TMPDIR', '/tmp'))))
    return base / 'novareader.pid'


def _is_process_running(pid: int) -> bool:
    try:
        if sys.platform == 'win32':
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x400, False, pid)
            if handle == 0:
                return False
            exit_code = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == 259
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False


def _wait_for_previous_instance():
    pid_file = _get_pid_file()
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            old_pid = None
        if old_pid and old_pid != os.getpid() and _is_process_running(old_pid):
            print(f"[App] Предыдущий экземпляр (PID {old_pid}) ещё работает, ждём...")
            import time as _time
            deadline = _time.monotonic() + 8.0
            while _time.monotonic() < deadline and _is_process_running(old_pid):
                _time.sleep(0.25)
            if _is_process_running(old_pid):
                print(f"[App] Предыдущий экземпляр не завершился за 8 с, продолжаем")
            else:
                print(f"[App] Предыдущий экземпляр завершился")
    try:
        pid_file.write_text(str(os.getpid()))
    except OSError as e:
        print(f"[App] Не удалось записать PID-файл: {e}")


def _remove_pid_file():
    try:
        _get_pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def _get_webengine_cache_dir() -> Path:
    app_name = "NovaReader"
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / app_name / 'QtWebEngine' / 'Default'


def _clear_webengine_cache():
    import shutil
    cache_root = _get_webengine_cache_dir()
    targets = [
        cache_root / 'GPUCache',
        cache_root / 'Code Cache',
        cache_root / 'Cache',
        cache_root / 'ShaderCache',
        cache_root / 'blob_storage',
        cache_root / 'DawnCache',
    ]
    cleared = []
    for target in targets:
        if target.exists():
            try:
                shutil.rmtree(target)
                cleared.append(target.name)
            except Exception as e:
                print(f"[Cache] Не удалось очистить {target.name}: {e}")
    if cleared:
        print(f"[Cache] Очищено: {', '.join(cleared)}")
    else:
        print("[Cache] Кэш WebEngine чист")


def _trim_memory_once():
    try:
        import ctypes
        if sys.platform == 'win32':
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            result = psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
            print(f'[Memory] EmptyWorkingSet -> {"OK" if result else "FAILED"}')
        else:
            libc = ctypes.CDLL('libc.so.6', use_errno=True)
            result = libc.malloc_trim(0)
            print(f'[Memory] malloc_trim(0) -> {result} (1=OK, страницы возвращены ОС)')
    except Exception as e:
        print(f"[Memory] trim ошибка: {e}")


def _configure_webengine_profile():
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    profile = QWebEngineProfile.defaultProfile()
    try:
        # DiskHttpCache (было NoCache): небольшой дисковый кэш даёт Chromium
        # хранить скомпилированный V8-байткод движка читалки (ibc/*.js) между
        # запусками/открытиями книг вместо перекомпиляции JS каждый раз -
        # экономит CPU на старте и при открытии книги ценой ~50 МБ на диске
        # (не в RAM).
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    except AttributeError:
        pass
    profile.setHttpCacheMaximumSize(50 * 1024 * 1024)
    try:
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    except AttributeError:
        pass
    cache_dir = _get_webengine_cache_dir()
    try:
        profile.setCachePath(str(cache_dir))
    except AttributeError:
        pass
    print(f"[Profile] WebEngine профиль настроен (cache→{cache_dir.name}, storage→tmp)")


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
    from PyQt6.QtGui import QIcon
    p = _find_icon_path()
    if p:
        app.setWindowIcon(QIcon(str(p)))
        print(f"[App] Иконка: {p.name}")
    else:
        print("[App] Иконка не найдена")


def _load_fonts():
    if getattr(sys, 'frozen', False):
        ibc_dir = Path(sys.executable).parent / 'ibc'
    else:
        ibc_dir = Path(__file__).parent / 'ibc'
    import os
    if sys.platform == 'win32':
        cfg_base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        cfg_base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    user_fonts_dir = cfg_base / 'NovaReader' / 'fonts'
    dirs_to_scan = [ibc_dir, ibc_dir / 'fonts', user_fonts_dir]
    for fonts_dir in dirs_to_scan:
        if not fonts_dir.exists():
            continue
        pattern = '*.ttf' if fonts_dir == ibc_dir else '**/*.ttf'
        for ttf in sorted(fonts_dir.glob(pattern)):
            fid = QFontDatabase.addApplicationFont(str(ttf))
            if fid >= 0:
                print(f"[Font] {ttf.name}: {QFontDatabase.applicationFontFamilies(fid)}")
            else:
                print(f"[Font] Ошибка загрузки: {ttf.name}")


def _make_splash_pixmap(icon_path: Path | None, w: int = 400, h: int = 260) -> QPixmap:
    px = QPixmap(w, h)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QColor(28, 28, 32)
    painter.setBrush(bg)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, w, h, 16, 16)
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
            icon_h = size + 16
    title_font = QFont()
    title_font.setPointSize(22)
    title_font.setWeight(QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.setPen(QColor(232, 232, 240))
    ty = 28 + icon_h
    painter.drawText(0, ty, w, 38, Qt.AlignmentFlag.AlignHCenter, "NovaReader")
    sub_font = QFont()
    sub_font.setPointSize(11)
    painter.setFont(sub_font)
    painter.setPen(QColor(130, 130, 150))
    painter.drawText(0, ty + 42, w, 24, Qt.AlignmentFlag.AlignHCenter,
                     "Инициализация…")
    painter.end()
    return px


def _build_reader_cmd(book_path: str) -> list:
    exe_dir = Path(sys.executable).parent
    for app_name in ('NovaReader', 'NovaReader.exe', 'main', 'main.exe'):
        app_bin = exe_dir / app_name
        if app_bin.exists():
            return [str(app_bin), '--reader', book_path]
    return [sys.executable, str(Path(__file__).resolve()), '--reader', book_path]


def _build_search_cmd() -> list:
    exe_dir = Path(sys.executable).parent
    for app_name in ('NovaReader', 'NovaReader.exe', 'main', 'main.exe'):
        app_bin = exe_dir / app_name
        if app_bin.exists():
            return [str(app_bin), '--search']
    return [sys.executable, str(Path(__file__).resolve()), '--search']


class _SubprocessAppInstance:
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


def _ask_book_action(app, parent_window, book_path: str, config) -> str:
    from pathlib import Path as _P
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                 QPushButton, QLabel)
    from PyQt6.QtGui import QFont as _QF
    from PyQt6.QtCore import Qt as _Qt
    lang = config.get('language', 'ru')
    if lang == 'ru':
        t_title = 'Открыть книгу'
        t_open = 'Открыть'
        t_addopen = 'Добавить и открыть'
        t_add = 'Только добавить'
        t_cancel = 'Отмена'
    else:
        t_title = 'Open book'
        t_open = 'Open'
        t_addopen = 'Add and open'
        t_add = 'Add to library'
        t_cancel = 'Cancel'
    try:
        from library_window import init_lib_colors
        init_lib_colors(config)
        from library_window import BG, SURFACE, BORDER, ACCENT, TEXT, SUB
    except Exception:
        BG = '#1e1e2e'; SURFACE = '#2a2a3a'; BORDER = '#3a3a4a'
        ACCENT = '#7c5cbf'; TEXT = '#e0e0e0'; SUB = '#888888'
    result = ['cancel']
    dlg = QDialog(parent_window if parent_window else None)
    dlg.setWindowTitle('NovaReader')
    dlg.setModal(True)
    dlg.setFixedWidth(420)
    dlg.setStyleSheet(
        f'QDialog{{background:{BG};color:{TEXT};}}'
        f'QLabel{{color:{TEXT};}}'
        f'QPushButton{{background:{SURFACE};color:{TEXT};'
        f'border:1px solid {BORDER};border-radius:6px;'
        f'padding:8px 14px;font-size:13px;min-width:0;}}'
        f'QPushButton:hover{{border-color:{ACCENT};'
        f'background:rgba(255,255,255,.08);}}'
        f'QPushButton:pressed{{background:{ACCENT};'
        f'color:#fff;border-color:{ACCENT};}}'
    )
    lay = QVBoxLayout(dlg)
    lay.setSpacing(14)
    lay.setContentsMargins(24, 22, 24, 20)
    lbl_title = QLabel(t_title)
    f = _QF(); f.setPointSize(13); f.setBold(True)
    lbl_title.setFont(f)
    lay.addWidget(lbl_title)
    lbl_name = QLabel(_P(book_path).name)
    lbl_name.setWordWrap(True)
    lbl_name.setStyleSheet(f'color:{SUB};font-size:12px;')
    lay.addWidget(lbl_name)
    lay.addSpacing(4)
    btn_open = QPushButton(t_open)
    btn_addopen = QPushButton(t_addopen)
    btn_add = QPushButton(t_add)
    btn_cancel = QPushButton(t_cancel)
    btn_addopen.setStyleSheet(
        f'QPushButton{{background:{ACCENT};color:#fff;'
        f'border:1px solid {ACCENT};border-radius:6px;'
        f'padding:8px 14px;font-size:13px;min-width:0;}}'
        f'QPushButton:hover{{background:{ACCENT};opacity:.9;}}'
    )
    row = QHBoxLayout()
    row.setSpacing(8)
    for b in (btn_open, btn_addopen, btn_add, btn_cancel):
        row.addWidget(b)
    lay.addLayout(row)
    btn_open.clicked.connect(lambda: (result.__setitem__(0, 'open'), dlg.accept()))
    btn_addopen.clicked.connect(lambda: (result.__setitem__(0, 'add_open'), dlg.accept()))
    btn_add.clicked.connect(lambda: (result.__setitem__(0, 'add_only'), dlg.accept()))
    btn_cancel.clicked.connect(dlg.reject)
    dlg.exec()
    return result[0]


def _run_reader_mode(book_path: str, from_association: bool = False):
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import QWebEngineProfile
    if not Path(book_path).exists():
        print(f"[ReaderMode] Файл не найден: {book_path}")
        sys.exit(1)
    # AA_ShareOpenGLContexts ОБЯЗАН быть выставлен до создания QApplication
    # при использовании QWebEngineView (задокументированное требование Qt,
    # не специфично для платформы/видеокарты - так же делает Calibre в
    # calibre/gui2/__init__.py). Раньше у нас reader_window (а с ним и
    # QWebEngineWidgets) импортировался ПОСЛЕ QApplication(...) - Qt в
    # такой ситуации сам пытается восстановиться, но не гарантированно на
    # всех платформах/драйверах. Явная установка убирает эту гонку.
    QApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("NovaReader")
    _load_fonts()
    _set_app_icon(app)
    profile = QWebEngineProfile.defaultProfile()
    try:
        # DiskHttpCache (было NoCache): небольшой дисковый кэш даёт Chromium
        # хранить скомпилированный V8-байткод движка читалки (ibc/*.js) между
        # запусками/открытиями книг вместо перекомпиляции JS каждый раз -
        # экономит CPU на старте и при открытии книги ценой ~50 МБ на диске
        # (не в RAM).
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    except AttributeError:
        pass
    profile.setHttpCacheMaximumSize(50 * 1024 * 1024)
    try:
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    except AttributeError:
        pass
    from config import Config
    from reader_window import ReaderWindow
    config = Config()
    _setup_logging(config)
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
    if from_association:
        action = _ask_book_action(app, None, book_path, config)
        if action == 'cancel':
            sys.exit(0)
        if action in ('add_open', 'add_only'):
            try:
                from book_parser import BookParser
                meta = BookParser.parse_meta(book_path)
                if meta:
                    config.add_book(meta)
                    print(f'[Assoc] Книга добавлена: {book_path}')
            except Exception as e:
                print(f'[Assoc] Ошибка добавления: {e}')
        if action == 'add_only':
            sys.exit(0)
        window.load_book(book_path)
        window.show()
    else:
        window.load_book(book_path)
        window.show()
    exit_code = app.exec()
    _window_ref[0] = None
    sys.exit(exit_code)


class EbookReader:
    def __init__(self):
        from PyQt6.QtCore import Qt as _Qt
        # См. комментарий в _run_reader_mode - тот же самый фикс.
        QApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
        self.app = QApplication(sys.argv)
        from PyQt6.QtGui import QFont
        self.app.setDesktopSettingsAware(False)
        default_font = self.app.font()
        default_font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias |
            QFont.StyleStrategy.PreferQuality
        )
        self.app.setFont(default_font)
        self.app.setApplicationName("NovaReader")
        self.app.setQuitOnLastWindowClosed(False)
        _load_fonts()
        self.config = Config()
        _setup_logging(self.config)
        try:
            self.config.set('_active_graphics_backend', _gfx_backend)
        except Exception:
            pass
        _set_app_icon(self.app)
        try:
            self.config.get_font_file_map()
        except Exception:
            pass
        self.library_window = None
        self.settings_window = None
        self.reader_windows = []
        self._reader_procs: list[tuple[str, subprocess.Popen]] = []
        self._webengine_ready = True
        self._initialized = False
        self._proc_watchdog = QTimer()
        self._proc_watchdog.setInterval(1000)
        self._proc_watchdog.timeout.connect(self._check_reader_procs)
        self._proc_watchdog.start()
        _wait_for_previous_instance()
        _clear_webengine_cache()
        icon_path = _find_icon_path()
        splash_px = _make_splash_pixmap(icon_path)
        self._splash = QSplashScreen(splash_px,
                                     Qt.WindowType.WindowStaysOnTopHint |
                                     Qt.WindowType.FramelessWindowHint)
        self._splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._splash.show()
        self.app.processEvents()
        self._splash_shown_at = time.monotonic()
        if self.config.is_first_run():
            self._show_wizard()
        else:
            self._open_library_when_ready()

    def _open_library_when_ready(self):
        if self._webengine_ready:
            self._finish_show_library()
        else:
            self._library_pending = True
            print("[App] Библиотека отложена — ждём WebEngine…")

    def _schedule_post_startup_cleanup(self):
        def _cleanup():
            import gc
            gc.collect()
            _trim_memory_once()
            QTimer.singleShot(30000, _cleanup)
        QTimer.singleShot(2000, _cleanup)

    def _finish_show_library(self):
        min_splash_ms = 900
        elapsed = int((time.monotonic() - getattr(self, '_splash_shown_at', 0)) * 1000)
        remaining = max(0, min_splash_ms - elapsed)

        def _close_and_show():
            if hasattr(self, '_splash') and self._splash:
                self._splash.close()
                self._splash = None
                print("[App] Сплэш закрыт")
            self.show_library()
            self._schedule_post_startup_cleanup()

        if remaining > 0:
            QTimer.singleShot(remaining, _close_and_show)
        else:
            _close_and_show()

    def _show_wizard(self):
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
        self._open_library_when_ready()

    def show_library(self):
        if hasattr(self, '_showing_library') and self._showing_library:
            print("[App] Защита от рекурсивного show_library()")
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
                self.library_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self.library_window.book_selected.connect(self.open_book)
                self.library_window.destroyed.connect(self._on_library_closed)
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
            print("[App] Защита от рекурсивного open_book()")
            return
        self._opening_book = True
        try:
            print(f"[App] Opening book: {book_path}")
            for bp, proc in list(self._reader_procs):
                if bp == book_path and proc.poll() is None:
                    print(f"[App] Книга уже открыта в процессе PID={proc.pid}, пропускаем")
                    return
            self.config._positions = self.config._load_positions()
            self.config.mark_as_read(book_path)
            if self.library_window:
                def _refresh_one():
                    if not self.library_window.update_single_book_progress(book_path):
                        self.library_window._on_library_updated()
                QTimer.singleShot(0, _refresh_one)
            cmd = _build_reader_cmd(book_path)
            proc = subprocess.Popen(cmd, env=os.environ.copy())
            self._reader_procs.append((book_path, proc))
            print(f"[App] Читалка запущена, PID={proc.pid}")
        finally:
            self._opening_book = False

    def _check_reader_procs(self):
        if not self._initialized:
            return
        before = len(self._reader_procs)
        finished_paths = [bp for bp, p in self._reader_procs if p.poll() is not None]
        self._reader_procs = [(bp, p) for bp, p in self._reader_procs if p.poll() is None]
        finished = before - len(self._reader_procs)
        if finished:
            print(f"[App] Читалок завершилось: {finished}, осталось: {len(self._reader_procs)}")
            try:
                self.config.reload()
            except Exception as e:
                print(f"[App] config.reload() ошибка: {e}")
            self.config._positions = self.config._load_positions()
            if self.library_window and self.library_window.isVisible():
                all_found = True
                for bp in finished_paths:
                    if not self.library_window.update_single_book_progress(bp):
                        all_found = False
                if not all_found:
                    self.library_window._on_library_updated()
        if not self._reader_procs and not self.library_window:
            print("[App] Все читалки закрыты и библиотека закрыта — выход")
            self._proc_watchdog.stop()
            self.app.quit()

    def run(self):
        def _on_quit():
            _remove_pid_file()
            try:
                self.config.reload()
            except Exception:
                pass
            for _, proc in self._reader_procs:
                if proc.poll() is None:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
        self.app.aboutToQuit.connect(_on_quit)
        return self.app.exec()


def _build_piper_worker_cmd(voice_name: str, onnx_url: str, json_url: str, voices_dir: str) -> list:
    exe_dir = Path(sys.executable).parent
    for app_name in ('NovaReader', 'NovaReader.exe', 'main', 'main.exe'):
        app_bin = exe_dir / app_name
        if app_bin.exists():
            return [str(app_bin), '--piper-worker', voice_name, onnx_url, json_url, voices_dir]
    worker_script = Path(__file__).resolve().parent / 'voice_download_worker.py'
    return [sys.executable, str(worker_script), voice_name, onnx_url, json_url, voices_dir]


def _run_search_mode():
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtWidgets import QApplication
    # См. комментарий в _run_reader_mode. Тут WebEngine не используется, но
    # ставим для единообразия со всеми остальными QApplication программы.
    QApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("NovaReader")
    app.setStyle('Fusion')
    from config import Config
    import library_window as _lw
    config = Config()
    _lw.init_lib_colors(config)
    from book_search_window import BookSearchWindow, _apply_search_style
    _apply_search_style(app)
    _load_fonts()
    _set_app_icon(app)
    _setup_logging(config)
    pid_file = None
    try:
        if sys.platform == 'win32':
            base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
        else:
            base = Path(os.environ.get('XDG_RUNTIME_DIR',
                                       Path(os.environ.get('TMPDIR', '/tmp'))))
        pid_file = base / 'novareader_search.pid'
        pid_file.write_text(str(os.getpid()))
    except OSError:
        pid_file = None

    def _remove_pid():
        try:
            if pid_file:
                pid_file.unlink(missing_ok=True)
        except OSError:
            pass
    app.aboutToQuit.connect(_remove_pid)

    window = BookSearchWindow(config, None)
    window.setWindowFlags(
        Qt.WindowType.Window |
        Qt.WindowType.WindowTitleHint |
        Qt.WindowType.WindowSystemMenuHint |
        Qt.WindowType.WindowMinimizeButtonHint |
        Qt.WindowType.WindowCloseButtonHint)
    window.show()
    sys.exit(app.exec())


def main():
    if '--piper-worker' in sys.argv:
        idx = sys.argv.index('--piper-worker')
        worker_args = sys.argv[idx + 1:]
        sys.argv = [sys.argv[0]] + worker_args
        import voice_download_worker
        voice_download_worker.main()
        return
    if '--search' in sys.argv:
        _run_search_mode()
        return
    if '--reader' in sys.argv:
        idx = sys.argv.index('--reader')
        if idx + 1 < len(sys.argv):
            _run_reader_mode(sys.argv[idx + 1])
        else:
            print("Использование: NovaReader --reader <book_path>")
            sys.exit(1)
    elif len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        _run_reader_mode(sys.argv[1], from_association=True)
    else:
        app = EbookReader()
        sys.exit(app.run())


if __name__ == "__main__":
    main()
