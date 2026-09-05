#!/usr/bin/env python3
"""
NovaReader – скрипт сборки через Nuitka (двойной режим: Linux / Windows)
=========================================================================
Использование:
    python3 build.py                    # сборка для текущей платформы
    python3 build.py --target windows   # сборка под Windows (только на Windows)
    python3 build.py --target linux     # сборка под Linux
    python3 build.py --no-venv          # не создавать venv (использовать текущий Python)
    python3 build.py --clean            # очистить dist/ и build/ перед сборкой
    python3 build.py --no-strip         # не запускать strip (оставить отладочные символы)
    python3 build.py --no-cleanup       # не удалять мусор (numpy тесты, Qt локали и т.д.)
    python3 build.py --mingw64
    python3 build.py --docker           # сборка в Docker для обратной совместимости
                                          # с glibc (см. docker/Dockerfile.glibc239)
    python3 build.py --target linux --appimage        # + упаковать в AppImage
    python3 build.py --target linux --flatpak         # + упаковать в Flatpak
    python3 build.py --target linux --flatpak --flatpak-install  # + сразу установить

    # Сборка И упаковка ОДНОЙ командой, целиком внутри Docker (важно!):
    # --appimage/--flatpak, переданные ВМЕСТЕ с --docker, выполняются
    # тоже внутри контейнера — так package-build.sh ищет недостающие
    # библиотеки в /usr/lib контейнера (glibc 2.39), а не хоста. Если
    # собрать в Docker, а упаковать ОТДЕЛЬНО потом на хосте с более новым
    # glibc (например Arch) — в AppImage может незаметно просочиться
    # зависимость от glibc хоста, сводя на нет смысл сборки в контейнере.
    python3 build.py --docker --appimage --clean
    python3 build.py --docker --flatpak --flatpak-install --clean

Результат:
    dist/NovaReader/
        NovaReader (или NovaReader.exe)
        resources_bin.so / resources_bin.pyd  ← web/ и fonts/ встроены
        *.so / *.dll / *.pyd           ← все нативные библиотеки рядом
"""

import sys
import os
import subprocess
import shutil
import argparse
import hashlib
import struct
import zipfile
import platform
from pathlib import Path

# ─── Настройки ────────────────────────────────────────────────────────────────

APP_NAME        = "NovaReader"
MAIN_SCRIPT     = "main.py"
PYTHON_MIN      = (3, 10)
VENV_DIR        = ".venv-build"
DIST_DIR        = "dist"
BUILD_DIR       = "build"

# Папки копируемые рядом с exe после сборки
RESOURCE_DIRS = ["ibc"]

# Python-модули исключить из сборки (не нужны)
EXCLUDES = [
    "tkinter", "matplotlib", "PIL", "IPython",
    "jupyter", "distutils", "_tkinter", "test", "unittest",
    "pydoc", "doctest", "difflib", "ftplib", "telnetlib",
    # Не используются в проекте:
    "soundfile",  # Убран из проекта — используется sounddevice
    "onnxruntime", "pathvalidate",
    "sympy", "mypy", "coverage", "pytest",
    "pyaudio",   # убран из проекта — используется sounddevice

    # Дополнительные исключения для уменьшения размера:
    "pip", "setuptools", "pkg_resources",  # Не нужны в runtime
    "numpy.testing", "numpy.distutils",  # Тесты numpy
    "numpy.f2py", "numpy.doc",  # Документация numpy
    # numpy._typing НЕ исключаем — нужен внутри numpy.linalg при инициализации
    "onnx",  # ONNX не нужен
    "PIL", "pillow",  # Изображения не нужны
]

# Обязательные пакеты для сборки (в дополнение к requirements.txt)
BUILD_DEPS = ["nuitka", "ordered-set", "zstandard", "ziglang"]
# patchelf нужен на Linux: Nuitka требует 0.17.2, но в Arch уже 0.18+.
# Pip-версия фиксирована (0.17.2.x) и всегда совместима с Nuitka.
BUILD_DEPS_LINUX = ["patchelf==0.17.2"]

# Зависимости приложения (минимальный набор)
# PyQt6, PyQt6-WebEngine — GUI
# edge-tts — TTS через облако
# requests — загрузка голосов Piper
# pyaudio — воспроизведение аудио для Piper
# certifi, charset_normalizer — транзитивные зависимости requests

# ─── Глобальная переменная: целевая платформа ─────────────────────────────────
TARGET_PLATFORM = None  # Устанавливается в main() из аргументов

# ─── Цвета для вывода ─────────────────────────────────────────────────────────

def green(s):  return f"\033[92m{s}\033[0m" if sys.platform != "win32" else s
def yellow(s): return f"\033[93m{s}\033[0m" if sys.platform != "win32" else s
def red(s):    return f"\033[91m{s}\033[0m" if sys.platform != "win32" else s
def bold(s):   return f"\033[1m{s}\033[0m"  if sys.platform != "win32" else s

def info(msg):    print(f"  {green('✓')} {msg}")
def warn(msg):    print(f"  {yellow('!')} {msg}")
def error(msg):   print(f"  {red('✗')} {msg}"); sys.exit(1)
def step(msg):    print(f"\n{bold('▶')} {msg}")
def run(msg):     print(f"  → {msg}")



def find_python() -> Path:
    """Ищет Python 3.10+ в системе."""
    candidates = ["python3.14", "python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"]
    for name in candidates:
        p = shutil.which(name)
        if p:
            result = subprocess.run(
                [p, "-c", "import sys; print(sys.version_info[:2])"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                ver = eval(result.stdout.strip())
                if ver >= PYTHON_MIN:
                    return Path(p)
    error(f"Python {'.'.join(map(str, PYTHON_MIN))}+ не найден в системе.")


def setup_venv(root: Path, explicit_python: str | None = None) -> Path:
    """Создаёт venv и возвращает путь к python внутри него."""
    venv_path = root / VENV_DIR
    is_win = sys.platform == "win32"

    if is_win:
        venv_python = venv_path / "Scripts" / "python.exe"
    else:
        venv_python = venv_path / "bin" / "python3"

    if not venv_python.exists():
        step("Создание виртуального окружения")
        if explicit_python:
            sys_python = Path(explicit_python)
            if not sys_python.exists():
                error(f"Python не найден: {explicit_python}")
        else:
            sys_python = find_python()
        run(f"Используем Python: {sys_python}")
        # Проверяем версию
        r = subprocess.run([str(sys_python), "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
            capture_output=True, text=True)
        info(f"Python версия: {r.stdout.strip()}")
        subprocess.run([str(sys_python), "-m", "venv", str(venv_path)], check=True)
        # На некоторых сборках python3-venv (замечено в Docker на Ubuntu)
        # generic-симлинк bin/python3 внутри venv не создаётся — venv module
        # завершается с кодом 0, но реально существует только версионный
        # bin/python3.X. Ищем его как фолбэк, иначе ниже упадёт с
        # FileNotFoundError на несуществующий bin/python3.
        if not venv_python.exists():
            bin_dir = venv_path / ("Scripts" if is_win else "bin")
            pattern = "python3.*.exe" if is_win else "python3.*"
            candidates = sorted(bin_dir.glob(pattern))
            # Отфильтровываем *-config и подобные не-исполняемые скрипты
            candidates = [c for c in candidates if c.is_file() and os.access(c, os.X_OK)]
            if candidates:
                venv_python = candidates[0]
                info(f"bin/python3 не создан venv-модулем — использую {venv_python.name}")
            else:
                error(f"venv создан, но ни один python-исполняемый файл не найден в {bin_dir}")
        info(f"venv создан: {venv_path}")
    else:
        step("Виртуальное окружение уже существует")
        # Показываем версию Python в venv
        r = subprocess.run([str(venv_python), "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
            capture_output=True, text=True)
        info(f"venv Python: {r.stdout.strip()} ({venv_path})")
        # Если версия не та что нужна — предупреждаем
        if explicit_python and r.stdout.strip():
            pass  # пользователь сам указал путь, доверяем

    return venv_python


def install_dependencies(venv_python: Path, root: Path):
    """Устанавливает зависимости из requirements.txt + build-зависимости."""
    step("Установка зависимостей")
    pip = [str(venv_python), "-m", "pip"]

    # Обновляем pip (на Windows может блокироваться файл — не падаем)
    run("Обновление pip...")
    try:
        r = subprocess.run([*pip, "install", "--upgrade", "pip"], capture_output=True, text=True)
        if r.returncode != 0:
            info("pip не обновлён (продолжаем с текущей версией)")
        else:
            info("pip обновлён")
    except Exception as e:
        info(f"pip upgrade пропущен: {e}")

    # Зависимости приложения
    req_file = root / "requirements.txt"
    if req_file.exists():
        run("Установка requirements.txt...")
        # На Windows pip читает файл в cp1251 — перекодируем во временный utf-8 файл
        import tempfile, shutil as _shutil
        try:
            req_text = req_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            req_text = req_file.read_text(encoding='cp1251')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         suffix='.txt', delete=False) as tmp:
            tmp.write(req_text)
            tmp_req = tmp.name
        try:
            subprocess.run([*pip, "install", "-r", tmp_req], check=True)
        finally:
            os.unlink(tmp_req)
        info("requirements.txt установлен")

    # Зависимости сборки
    run(f"Установка зависимостей сборки: {', '.join(BUILD_DEPS)}...")
    subprocess.run([*pip, "install", *BUILD_DEPS], check=True)
    info("Зависимости сборки установлены")

    # Linux: устанавливаем patchelf из pip с фиксированной версией.
    # Nuitka рассчитана на patchelf 0.17.2 — но версия из apt/pacman
    # СИЛЬНО зависит от дистрибутива и НИКОГДА ей не совпадает:
    #   Ubuntu 22.04 (apt): 0.14.3 — старая, ломает RPATH standalone-сборки
    #     (бинарник собирается без ошибок, но не находит собственные .so/
    #     ресурсы при запуске — выглядит как "программа не запускается",
    #     хотя дело не в GCC/компиляторе, а именно в этом инструменте)
    #   Ubuntu 24.04 (apt): 0.18.0 — новее, для этой раскладки обычно
    #     работает терпимо, но тоже не тот же 0.17.2, что ждёт Nuitka
    #   Arch (pacman): 0.18+ — тоже не совпадает
    # Раньше здесь был только warn() при неудаче pip-установки — сборка
    # молча продолжалась на системном patchelf, и ошибка (сломанные пути)
    # проявлялась только при ЗАПУСКЕ готового бинарника, а не при сборке,
    # что сильно затрудняло диагностику. Теперь версия проверяется по
    # факту (через тот же venv/bin-приоритет, что использует сама Nuitka),
    # и при несовпадении сборка останавливается сразу же.
    if sys.platform != "win32":
        run("Установка pip-версии patchelf (Linux)...")
        result = subprocess.run(
            [*pip, "install", *BUILD_DEPS_LINUX],
            capture_output=True, text=True)
        if result.returncode != 0:
            error(f"Не удалось установить pip-версию patchelf: "
                  f"{result.stderr.strip()[:300]}\n"
                  f"Без неё сборка на системном patchelf может дать "
                  f"бинарник, который собирается без ошибок, но не "
                  f"находит свои файлы при запуске.")

        expected_version = BUILD_DEPS_LINUX[0].split("==")[1]
        check_env = _get_build_env(venv_python)
        try:
            ver_result = subprocess.run(
                ["patchelf", "--version"],
                capture_output=True, text=True, env=check_env, timeout=10)
            actual_version = ver_result.stdout.strip().split()[-1] if ver_result.stdout.strip() else "?"
        except Exception as e:
            actual_version = f"ошибка проверки: {e}"

        if actual_version != expected_version:
            error(
                f"patchelf в PATH — версия {actual_version}, а не "
                f"{expected_version} (venv/bin должен был перекрыть "
                f"системный через PATH — см. _get_build_env). Это "
                f"типичная причина, когда сборка проходит без ошибок, но "
                f"готовый бинарник потом не находит собственные .so-файлы "
                f"и не запускается — версия patchelf, отличная от "
                f"{expected_version}, может неверно прописать RPATH."
            )
        info(f"patchelf {actual_version} — версия подтверждена, приоритет над системным есть")


# ─── Сборка Nuitka ────────────────────────────────────────────────────────────

def get_nuitka_version(venv_python: Path) -> tuple:
    """Возвращает версию Nuitka как (major, minor, patch)."""
    try:
        r = subprocess.run(
            [str(venv_python), "-m", "nuitka", "--version"],
            capture_output=True, text=True, timeout=10
        )
        # Вывод вида: "2.4.8" или "Nuitka 2.4.8 ..."
        import re
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", r.stdout + r.stderr)
        if m:
            ver = tuple(int(x) for x in m.groups())
            info(f"Nuitka версия: {'.'.join(map(str, ver))}")
            return ver
    except Exception:
        pass
    return (1, 0, 0)  # fallback для старых версий


def find_zig_compiler(root: Path) -> str | None:
    """
    Ищет Zig-компилятор для Windows-сборки.
    Сначала проверяет корень проекта (zig.exe / zig),
    затем системный PATH.
    Zig используется как drop-in C-компилятор для Nuitka на Windows.
    """
    # 1. Проект/корень: zig.exe (Windows) или zig (Linux)
    for name in ["zig.exe", "zig"]:
        local = root / name
        if local.exists():
            info(f"Zig найден в корне проекта: {local}")
            return str(local)
    # 2. Системный PATH
    p = shutil.which("zig")
    if p:
        info(f"Zig найден в PATH: {p}")
        return p
    return None



    """
    Проверяет наличие MinGW64.
    
    Args:
        cross_compile: Если True, ищем для кросс-компиляции (Linux → Windows)
                       Если False, ищем для нативной сборки (Windows → Windows)
    """
    if cross_compile:
        # Для кросс-компиляции ищем x86_64-w64-mingw32-gcc
        candidates = ["x86_64-w64-mingw32-gcc"]
    else:
        # Для нативной сборки на Windows ищем gcc в PATH
        candidates = ["gcc", "mingw32-make", "mingw64-make"]
    
    for cc in candidates:
        result = subprocess.run([cc, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            if not cross_compile:
                info(f"MinGW64 найден: {cc}")
            return cc
    
    if cross_compile:
        warn("MinGW64 не найден. Установите: sudo apt install mingw-w64")
    else:
        warn("MinGW64 не найден в PATH. Установите MSYS2 или WinLibs")
    return None


# ─── Strip + очистка мусора ───────────────────────────────────────────────────

# Паттерны путей которые безопасно удалять из dist
# (Qt переводы для лишних языков, numpy тестовые бинарники, WebEngine dev-ресурсы)
CLEANUP_PATTERNS = [
    # Qt переводы — оставляем только ru, en; остальные 50+ языков не нужны
    'PyQt6/Qt6/translations',
    # numpy тестовые .so (несколько МБ, никогда не нужны в продакшне)
    'numpy/_core/_multiarray_tests',
    'numpy/_core/_operand_flag_tests',
    'numpy/_core/_rational_tests',
    'numpy/_core/_struct_ufunc_tests',
    'numpy/_core/_umath_tests',
    'numpy/_core/_simd',
    'numpy/random/_bounded_integers',
    'numpy/linalg/lapack_lite',
    # Qt WebEngine devtools (только для отладки)
    'PyQt6/Qt6/resources/qtwebengine_devtools_resources.pak',
]

# Паттерны переводов которые ОСТАВЛЯЕМ — ru + en
# Переводы которые ОСТАВЛЯЕМ — только ru и en нужных модулей
KEEP_TRANSLATIONS = (
    'qt_ru', 'qt_en',
    'qtbase_ru', 'qtbase_en',
    'qtwebengine_ru', 'qtwebengine_en',
    'qtwebengine_locales/ru', 'qtwebengine_locales/en',
)

# Модули Qt которые удаляем ПОЛНОСТЬЮ независимо от языка
# (не используются в проекте — qt_help, multimedia, serial, websockets и др.)
DELETE_QT_MODULES = (
    'qt_help_',       # справочная система Qt
    'qtmultimedia_',  # Qt Multimedia
    'qtserialport_',  # Qt Serial Port
    'qtwebsockets_',  # Qt WebSockets
    'qtconnectivity_',# Qt Bluetooth/NFC
    'qtdeclarative_', # Qt QML/Quick
    'qtlocation_',    # Qt Location
    'qtquick',        # Qt Quick
    'qtsensors_',     # Qt Sensors
    'qtscript_',      # Qt Script
    'qtxmlpatterns_', # Qt XML Patterns
)



def hide_console_window(exe_dir: Path):
    """Скрывает консольное окно в готовом .exe через патч PE-заголовка.
    Работает без перекомпиляции — просто меняет subsystem CUI→GUI.
    """
    if sys.platform != "win32":
        return
    exe = exe_dir / "NovaReader.exe"
    if not exe.exists():
        warn(f"hide_console: {exe.name} не найден")
        return
    step("hide_console: скрываем консольное окно в exe")
    try:
        with open(exe, "r+b") as f:
            f.seek(0)
            if f.read(2) != b"MZ":
                warn("hide_console: не PE-файл, пропускаем")
                return
            f.seek(0x3c)
            pe_offset = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_offset)
            if f.read(4) != b"PE\x00\x00":
                warn("hide_console: неверная PE-подпись")
                return
            opt_header_offset = pe_offset + 24
            f.seek(opt_header_offset)
            magic = struct.unpack("<H", f.read(2))[0]
            subsystem_offset = opt_header_offset + 68
            f.seek(subsystem_offset)
            subsystem = struct.unpack("<H", f.read(2))[0]
            # subsystem 2 = Windows GUI (без консоли)
            # subsystem 3 = Windows CUI (с консолью)
            if subsystem == 2:
                info("hide_console: уже GUI-приложение (консоль отключена)")
                return
            f.seek(subsystem_offset)
            f.write(struct.pack("<H", 2))  # 2 = Windows GUI, без консоли
            info(f"hide_console: консоль скрыта (subsystem {subsystem} → 2 GUI)")
    except Exception as e:
        warn(f"hide_console: ошибка: {e}")

def run_strip(exe_dir: Path):
    """
    Запускает strip на всех .so и главном бинарнике (Linux only).
    strip удаляет отладочные символы — обычно -30..50% от каждого .so.
    На Windows strip не нужен — Nuitka сам не включает debug-символы.
    """
    if sys.platform == 'win32':
        return

    strip = shutil.which('strip')
    if not strip:
        warn("strip не найден — пропускаем. Установите: sudo apt install binutils")
        return

    step("strip: удаление отладочных символов")

    targets = []
    # Главный бинарник
    for name in [APP_NAME, APP_NAME.lower()]:
        f = exe_dir / name
        if f.exists() and f.is_file():
            targets.append(f)
            break
    # Все .so
    targets += [f for f in exe_dir.rglob('*.so') if f.is_file()]
    targets += [f for f in exe_dir.rglob('*.so.*') if f.is_file()]

    total_before = sum(f.stat().st_size for f in targets)
    ok = failed = 0

    for f in sorted(targets):
        result = subprocess.run(
            [strip, '--strip-unneeded', str(f)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok += 1
        else:
            # Некоторые .so защищены — не страшно
            failed += 1

    total_after = sum(f.stat().st_size for f in targets)
    saved_mb = (total_before - total_after) / 1024 / 1024
    pct      = (1 - total_after / total_before) * 100 if total_before else 0
    info(f"strip: обработано {ok} файлов, пропущено {failed}")
    info(f"strip: сэкономлено {saved_mb:.1f} MB ({pct:.0f}%) "
         f"[{total_before//1024//1024} MB → {total_after//1024//1024} MB]")


def run_upx(exe_dir: Path, args=None):
    """
    Сжимает все бинарники через UPX (уменьшает размер на 30-40%).
    UPX ищется в корне проекта: ./upx (Linux) или ./upx.exe (Windows)
    """
    if args and args.no_upx:
        info("UPX отключен пользователем")
        return

    root = Path(__file__).parent.resolve()
    
    # Ищем UPX в корне проекта
    if sys.platform == 'win32':
        upx_path = root / 'upx.exe'
    else:
        upx_path = root / 'upx'
    
    if not upx_path.exists():
        # Пробуем найти в системном PATH
        upx = shutil.which('upx')
        if not upx:
            warn("UPX не найден в корне проекта и в PATH.")
            warn(f"Положите upx{'x' if sys.platform == 'win32' else ''} в корень проекта: {root}")
            warn("Скачать: https://github.com/upx/upx/releases")
            warn("UPX уменьшает размер сборки на 30-40%!")
            return
    else:
        upx = str(upx_path)
        info(f"UPX найден: {upx_path}")

    step("UPX: сжатие бинарников")

    targets = []
    # Главный бинарник
    for name in [APP_NAME, APP_NAME.lower(), APP_NAME + ".exe"]:
        f = exe_dir / name
        if f.exists() and f.is_file():
            targets.append(f)
            break
    # Все .so / .dll / .pyd
    targets += [f for f in exe_dir.rglob('*.so') if f.is_file()]
    targets += [f for f in exe_dir.rglob('*.so.*') if f.is_file()]
    targets += [f for f in exe_dir.rglob('*.dll') if f.is_file()]
    targets += [f for f in exe_dir.rglob('*.pyd') if f.is_file()]

    # BLAS/LAPACK-реализации (OpenBLAS, MKL, ATLAS — тянутся numpy/scipy)
    # используют нестандартное, чувствительное к выравниванию расположение
    # ELF-сегментов (под производительность). UPX их успешно "сжимает"
    # (exit code 0, без предупреждений), но ломает выравнивание — при
    # запуске падает ImportError: "ELF load command address/offset not
    # page-aligned". Известная, задокументированная несовместимость UPX
    # именно с такими библиотеками — исключаем их из сжатия целиком.
    UPX_EXCLUDE_PATTERNS = ('openblas', 'scipy_openblas', 'mkl_', 'libmkl',
                            'lapack', 'libatlas', 'libblas')
    excluded = [f for f in targets
                if any(pat in f.name.lower() for pat in UPX_EXCLUDE_PATTERNS)]
    if excluded:
        targets = [f for f in targets if f not in excluded]
        info(f"UPX: пропущено {len(excluded)} BLAS/LAPACK-библиотек "
             f"(известная несовместимость с UPX — ломает ELF-выравнивание):")
        for f in excluded:
            info(f"  • {f.name}")

    # QtWebEngineCore — огромный файл (~197 МБ), сжимаем первым с увеличенным таймаутом
    # На Windows Qt6WebEngineCore.dll защищён CFG — UPX его сломает, пропускаем.
    webengine_names = [
        'libQt6WebEngineCore.so.6',
        'libQt6WebEngineCore.so',
    ]
    if sys.platform != 'win32':
        webengine_names.append('Qt6WebEngineCore.dll')
    webengine_files = []
    for name in webengine_names:
        for f in exe_dir.rglob(name):
            if f.is_file() and f not in webengine_files:
                webengine_files.append(f)

    total_before = sum(f.stat().st_size for f in targets)
    ok = failed = 0

    for f in webengine_files:
        if f in targets:
            targets.remove(f)
        size_mb = f.stat().st_size // 1024 // 1024
        info(f"UPX: сжимаем {f.name} ({size_mb} МБ) — может занять несколько минут...")
        # Убеждаемся что файл исполняемый — UPX требует этого на Linux
        if sys.platform != 'win32':
            f.chmod(f.stat().st_mode | 0o111)
        result = subprocess.run(
            [upx, '--best', str(f)],
            capture_output=True, text=True,
            timeout=600  # 10 минут для огромного файла
        )
        if result.returncode == 0:
            ok += 1
            new_mb = f.stat().st_size // 1024 // 1024
            info(f"UPX: {f.name} {size_mb} МБ → {new_mb} МБ")
        else:
            # Показываем полную ошибку для диагностики
            warn(f"UPX: не удалось сжать {f.name}")
            warn(f"  stdout: {result.stdout.strip()[:200]}")
            warn(f"  stderr: {result.stderr.strip()[:200]}")
            failed += 1

    for f in sorted(targets):
        result = subprocess.run(
            [upx, '-9', '--best', str(f)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok += 1
        else:
            failed += 1

    total_after = sum(f.stat().st_size for f in targets)
    saved_mb = (total_before - total_after) / 1024 / 1024
    pct      = (1 - total_after / total_before) * 100 if total_before else 0
    info(f"UPX: обработано {ok} файлов, пропущено {failed}")
    info(f"UPX: сэкономлено {saved_mb:.1f} MB ({pct:.0f}%) "
         f"[{total_before//1024//1024} MB → {total_after//1024//1024} MB]")


def run_cleanup(exe_dir: Path):
    """
    Удаляет из dist мусор: лишние Qt-переводы, numpy тестовые бинарники,
    WebEngine devtools и прочее что никогда не нужно в продакшне.
    """
    step("Очистка мусора из dist")

    saved_bytes = 0

    # ── Qt переводы: оставляем только ru + en ──────────────────────────────
    # Nuitka 4.x кладёт .qm файлы прямо в корень dist
    # Старые версии — в PyQt6/Qt6/translations
    _trans_dirs = [
        exe_dir,  # Nuitka 4.x — корень
        exe_dir / 'PyQt6' / 'Qt6' / 'translations',  # старая структура
    ]
    removed = kept = 0
    for trans_dir in _trans_dirs:
        if not trans_dir.exists():
            continue
        # Ищем .qm файлы только в этой папке (не рекурсивно для корня)
        pattern = trans_dir.glob('*.qm') if trans_dir == exe_dir else trans_dir.rglob('*.qm')
        for f in list(pattern):
            if not f.is_file():
                continue
            rel = f.name  # просто имя файла
            # Удаляем модули которые не нужны вообще
            delete_module = any(rel.startswith(d) for d in DELETE_QT_MODULES)
            if delete_module:
                saved_bytes += f.stat().st_size
                f.unlink()
                removed += 1
                continue
            # Из оставшихся — только ru и en
            keep = any(k in rel for k in KEEP_TRANSLATIONS)
            if not keep:
                saved_bytes += f.stat().st_size
                f.unlink()
                removed += 1
            else:
                kept += 1
    info(f"Qt переводы: удалено {removed}, оставлено {kept} (ru/en)")

    # ── Qt WebEngine переводы: оставляем только ru + en ────────────────────
    we_locales_dir = exe_dir / 'qtwebengine_locales'
    if we_locales_dir.exists():
        removed = kept = 0
        for f in list(we_locales_dir.glob('*.pak')):
            # Оставляем только ru.pak и en-US.pak, en-GB.pak
            if f.stem in ['ru', 'en-US', 'en-GB']:
                kept += 1
            else:
                saved_bytes += f.stat().st_size
                f.unlink()
                removed += 1
        info(f"Qt WebEngine переводы: удалено {removed}, оставлено {kept} (ru/en)")

    # ── Паттерны: numpy тесты, WebEngine devtools ──────────────────────────
    for pattern in CLEANUP_PATTERNS:
        if 'translations' in pattern:
            continue  # уже обработали выше
        target = exe_dir / pattern.replace('/', os.sep)
        if target.exists():
            sz = target.stat().st_size if target.is_file() else \
                 sum(f.stat().st_size for f in target.rglob('*') if f.is_file())
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
            saved_bytes += sz
            info(f"Удалено: {pattern} ({sz//1024} KB)")

    # ── Удаление .dist-info директорий (метаданные пакетов, не нужны) ────────
    dist_info_dirs = list(exe_dir.rglob('*.dist-info'))
    for d in dist_info_dirs:
        if d.is_dir():
            sz = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            shutil.rmtree(d)
            saved_bytes += sz
    if dist_info_dirs:
        info(f"Удалено .dist-info директорий: {len(dist_info_dirs)}")

    # ── Удаление __pycache__ директорий ──────────────────────────────────────
    pycache_dirs = list(exe_dir.rglob('__pycache__'))
    for d in pycache_dirs:
        if d.is_dir():
            sz = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            shutil.rmtree(d)
            saved_bytes += sz
    if pycache_dirs:
        info(f"Удалено __pycache__ директорий: {len(pycache_dirs)}")

    # ── Удаление тестовых папок из пакетов ───────────────────────────────────
    test_dirs = []
    for pattern in ['*/tests', '*/test', '*/testing']:
        test_dirs += list(exe_dir.glob(pattern))
    for d in test_dirs:
        if d.is_dir():
            sz = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            shutil.rmtree(d)
            saved_bytes += sz
    if test_dirs:
        info(f"Удалено тестовых папок: {len(test_dirs)}")

    # ── Удаление документации из пакетов (.txt, .rst, .md, .html в пакетах) ─
    doc_exts = {'.txt', '.rst', '.md', '.html', '.htm'}
    doc_files = []
    for ext in doc_exts:
        doc_files += [f for f in exe_dir.rglob(f'*{ext}')
                      if f.is_file() and any(p in f.parts for p in ['aiohttp', 'charset_normalizer', 'certifi', 'requests', 'numpy', 'edge_tts'])]
    for f in doc_files:
        try:
            saved_bytes += f.stat().st_size
            f.unlink()
        except Exception:
            pass
    if doc_files:
        info(f"Удалено doc-файлов из пакетов: {len(doc_files)}")

    # ── Удаление onnxruntime (если вдруг попал) ───────────────────────────────
    for pattern in ['libonnxruntime*.so*', 'onnxruntime*.dll']:
        for lib in exe_dir.glob(pattern):
            if lib.exists():
                sz = lib.stat().st_size
                lib.unlink()
                saved_bytes += sz
                info(f"Удалено: {lib.name} ({sz//1024//1024} MB)")

    info(f"Очистка: освобождено {saved_bytes//1024//1024} MB")
    
    # ── Удаление onnxruntime (если вдруг попал) ───────────────────────────
    onnx_libs = list(exe_dir.glob('libonnxruntime*.so*'))
    for lib in onnx_libs:
        if lib.exists():
            sz = lib.stat().st_size
            lib.unlink()
            saved_bytes += sz
            info(f"Удалено: {lib.name} ({sz//1024//1024} MB)")
    
    # ── Удаление WebEngine devtools (отладка, не нужна в продакшне) ───────
    devtools_pak = exe_dir / 'qtwebengine_devtools_resources.pak'
    if devtools_pak.exists():
        sz = devtools_pak.stat().st_size
        devtools_pak.unlink()
        saved_bytes += sz
        info(f"Удалено: qtwebengine_devtools_resources.pak ({sz//1024//1024} MB)")


def check_mingw64_windows() -> str | None:
    """Проверяет наличие MinGW64 на Windows (MSYS2/WinLibs)."""
    # Проверяем стандартные пути установки
    mingw_paths = [
        r"C:\msys64\mingw64\bin\gcc.exe",
        r"C:\mingw64\bin\gcc.exe",
        r"C:\Program Files\mingw-w64\bin\gcc.exe",
    ]
    
    # Проверяем PATH
    result = subprocess.run(["gcc", "--version"], capture_output=True, text=True)
    if result.returncode == 0 and "mingw" in result.stdout.lower():
        info(f"MinGW64 найден в PATH: gcc")
        return "gcc"
    
    # Проверяем стандартные пути
    for gcc_path in mingw_paths:
        if Path(gcc_path).exists():
            info(f"MinGW64 найден: {gcc_path}")
            return gcc_path
    
    warn("MinGW64 не найден. Установите MSYS2 (https://www.msys2.org/) или WinLibs (https://winlibs.com/)")
    return None




def _get_build_env(venv_python: Path) -> dict:
    """
    Возвращает os.environ с venv/bin в НАЧАЛЕ PATH.
    Это гарантирует что pip-версия patchelf (venv/bin/patchelf)
    получает приоритет над системной (/usr/bin/patchelf).
    Nuitka ищет patchelf через PATH — первый найденный побеждает.
    """
    env = os.environ.copy()
    venv_bin = str(venv_python.parent)
    current_path = env.get('PATH', '')
    if venv_bin not in current_path.split(os.pathsep):
        env['PATH'] = venv_bin + os.pathsep + current_path
    return env


def build_nuitka(venv_python: Path, root: Path, dist_dir: Path, args=None):
    """Запускает Nuitka для компиляции приложения."""
    step("Сборка через Nuitka")
    
    # Определяем целевую платформу
    host_platform = sys.platform
    target_win = (TARGET_PLATFORM == "windows") or (TARGET_PLATFORM is None and host_platform == "win32")
    
    out_name = APP_NAME + (".exe" if target_win else "")
    nuitka_ver = get_nuitka_version(venv_python)

    # fb2c — вычисляем аргумент до формирования cmd
    _fb2c_dir = root / "tools" / "fb2c"
    _fb2c_bin = _fb2c_dir / ("fb2c.exe" if target_win else "fb2c")
    _fb2c_dst = "tools/fb2c/fb2c.exe" if target_win else "tools/fb2c/fb2c"
    if _fb2c_bin.exists():
        _fb2c_args = [f"--include-data-file={_fb2c_bin}={_fb2c_dst}"]
        info(f"Включаем конвертер: {_fb2c_dst}")
    else:
        _fb2c_args = []
        warn(f"fb2c не найден: {_fb2c_bin} — конвертация FB2→EPUB недоступна")

    # Nuitka на Anaconda/conda по умолчанию требует статическую libpython
    # (libpython-static из conda-forge), которая в conda-окружениях обычно
    # не установлена ("FATAL: Automatic detection of static libpython
    # failed"). Раз мы теперь умеем собирать прямо из активной conda-среды
    # (см. detect в main()), не требуем от пользователя дополнительно
    # ставить conda-forge пакет - просто просим Nuitka линковаться
    # динамически. Разделяемая libpython всё равно копируется в дистрибутив
    # отдельно (см. _copy_libpython ниже), так что на портативность сборки
    # это не влияет.
    _static_libpython_args = ["--static-libpython=no"] if os.environ.get("CONDA_PREFIX") else []

    # Базовые флаги Nuitka
    cmd = [
        str(venv_python), "-m", "nuitka",
        "--standalone",                        # все зависимости рядом с exe
        f"--output-dir={dist_dir}",
        f"--output-filename={out_name}",
        "--assume-yes-for-downloads",          # авто-скачать gcc/MinGW если нужно
        *_static_libpython_args,

        # GUI-приложение: на Windows без консоли
        # --windows-console-mode=disable — актуальный флаг (Nuitka >= 1.9 / 4.x)
        *( ["--windows-console-mode=disable"] if target_win else [] ),

        # Название приложения (поддерживается в Nuitka >= 1.5)
        *([ f"--product-name={APP_NAME}",
            f"--product-version=1.0.0" ] if nuitka_ver >= (1, 5) else []),

        # Оптимизация
        "--lto=auto",     # auto: использовать LTO если компилятор поддерживает
        "--jobs=4",

        # Кросс-компиляция для Windows из-под Linux
        # В Nuitka 4.x флаги --target-arch и --target-platform удалены
        # Вместо этого используется переменная окружения CC/CXX
    ]

    # ─── Настройка компилятора ───────────────────────────────────────────────
    #
    # Windows (нативная): Zig в корне проекта → Zig в PATH → MinGW64 → авто
    # Linux (нативная):   системный gcc/cc → Zig (запасной вариант)
    # Кросс-компиляция Linux→Windows: не поддерживается

    if target_win and host_platform != "win32":
        error(
            "Кросс-компиляция Linux → Windows не поддерживается.\n"
            "  Запустите build.py на Windows: python build.py\n"
            "  Или используйте Wine с Windows-версией Python."
        )

    elif target_win and host_platform == "win32":
        # Windows: НЕ устанавливаем CC/CXX — Nuitka сама найдёт кэшированный Zig
        info("Компилятор Windows: Nuitka использует Zig автоматически")

    else:
        # Linux: системный gcc в приоритете → Zig только как запасной вариант.
        # Раньше было наоборот (Zig первым) — но Nuitka не всегда корректно
        # находит/использует Zig как C-компилятор на некоторых системах,
        # из-за чего сборка либо падает, либо использует что-то не то.
        # gcc почти всегда уже стоит на Linux (build-essential) и не даёт
        # сюрпризов, поэтому теперь он в приоритете.
        gcc = shutil.which("gcc") or shutil.which("cc")
        if gcc:
            os.environ.setdefault("CC", gcc)
            os.environ.setdefault("CXX", shutil.which("g++") or shutil.which("c++") or gcc)
            info(f"Компилятор Linux: {gcc}")
        else:
            zig = find_zig_compiler(root)
            if zig:
                os.environ.setdefault("CC",  f"{zig} cc")
                os.environ.setdefault("CXX", f"{zig} c++")
                info(f"gcc/cc не найден — использую Zig ({zig})")
            else:
                error("Ни gcc/cc, ни Zig не найдены. Установите: sudo apt install build-essential")

    # PyQt6 + WebEngine
    cmd.append("--enable-plugin=pyqt6")
    
    # Qt WebEngine
    if target_win:
        info("Qt WebEngine: DirectX 11 (ANGLE) включен")
    else:
        info("Qt WebEngine: EGL включен")

    # Включаем все модули приложения
    cmd.extend([
        "--include-package=tts",
        "--include-package=tts.clients",



        # Включаем папки с бинарниками Piper: только нужную платформу
        *( ["--include-data-dir=tts/piper-win=tts/piper-win"]
           if target_win else
           ["--include-data-dir=tts/piper=tts/piper"] ),

        *_fb2c_args,

        # Исходные файлы (все .py рядом с main.py)
        "--include-module=config",
        "--include-module=book_parser",
        "--include-module=library_window",
        "--include-module=reader_window",
        "--include-module=wizard_window",
        "--include-module=settings_window",
        "--include-module=tts_correction_window",
        "--include-module=piper_voice_downloader",
        "--include-module=piper_voices_widget",
        "--include-module=audio_player",
        "--include-module=screen_inhibit",
        "--include-module=cloud_download",
         "--include-module=voice_download_worker",
         "--include-module=book_search_window",
          "--include-module=translator_engine",
           "--include-module=translator_window",
            "--include-module=process_monitor",
        # PyQt6.QtDBus нужен для screen_inhibit (кофеин-режим) на Linux
        *(["--include-module=PyQt6.QtDBus"] if sys.platform != "win32" else []),
        # Сетевые пакеты (edge-tts + requests)
        "--include-package=edge_tts",
        "--include-package=requests",
        "--include-package=certifi",
        # cacert.pem — файл ДАННЫХ (не .py), --include-package его не
        # гарантирует; без него requests не может проверить TLS-сертификат
        # на Windows (там нет системного CA bundle как fallback на Linux),
        # и любая HTTPS-загрузка (голоса Piper, облачные книги) молча
        # падает с CERTIFICATE_VERIFY_FAILED. См. main.py/voice_download_worker.py.
        "--include-package-data=certifi",
        # charset_normalizer подтягивается через requests автоматически
        
        # Аудио
        "--include-package=sounddevice",
        "--include-package=numpy",
        # aiohttp и его зависимости (yarl, frozenlist, multidict и др.)
        # подтягиваются автоматически через edge_tts — не дублируем
        
        # Пакеты для морфологического анализа (исправлено!)
        "--include-package=pymorphy3",
        "--include-package=pymorphy3_dicts_ru",  # правильное имя (с дефисом)
    ])

    # ─── Добавляем data-директорию словарей pymorphy3 (обязательно!) ──────
    # Словари лежат в site-packages/pymorphy3_dicts_ru/data
    # Используем venv_python для поиска правильного пути
    import site
    venv_site_packages = Path(venv_python).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    # Проверяем, есть ли там папка pymorphy3_dicts_ru
    data_src = venv_site_packages / "pymorphy3_dicts_ru" / "data"
    if not data_src.exists():
        # Запасной вариант – через site.getsitepackages()
        for sp in site.getsitepackages():
            candidate = Path(sp) / "pymorphy3_dicts_ru" / "data"
            if candidate.exists():
                data_src = candidate
                break
    if data_src.exists():
        cmd.append(f"--include-data-dir={data_src}=pymorphy3_dicts_ru/data")
        info(f"Словари pymorphy3 включены из: {data_src}")
    else:
        warn("Папка с данными pymorphy3 не найдена — морфологический разбор не будет работать")
        warn(f"Искали в: {venv_site_packages / 'pymorphy3_dicts_ru/data'}")
    # ─────────────────────────────────────────────────────────────────────────

    # Исключения — не следовать за импортами ненужных модулей
    for excl in EXCLUDES:
        cmd.append(f"--nofollow-import-to={excl}")
    
    # Минимальные исключения — только то что точно не нужно в runtime
    # numpy._typing и linalg НЕ трогаем — они нужны при инициализации numpy
    cmd.extend([
        "--nofollow-import-to=onnxruntime",
        # aiohttp тестовые
        "--nofollow-import-to=aiohttp.test_utils",
        "--nofollow-import-to=aiohttp.pytest_plugin",
        # requests
    ])

    # Иконка (если есть)
    # Приоритет: NovaReader_Windows.ico / NovaReader_Linux.png, затем стандартные имена
    # Nuitka принимает PNG напрямую и сам создаёт многоразмерный ICO
    # Порядок поиска: сначала платформо-специфичные, потом общие
    win_icon_names = ["NovaReader_Windows.ico", "NovaReader_Windows.png",
                      "icon.ico", f"{APP_NAME}.ico", f"{APP_NAME}.png", "icon.png"]
    lin_icon_names = ["NovaReader_Linux.png", "NovaReader_Linux.svg",
                      "icon.png", f"{APP_NAME}.png"]

    if target_win:
        for icon_name in win_icon_names:
            icon_path = root / icon_name
            if icon_path.exists():
                # Nuitka принимает и .ico и .png через --windows-icon-from-ico
                cmd.append(f"--windows-icon-from-ico={icon_path}")
                info(f"Иконка Windows: {icon_path.name}")
                break
    else:
        for icon_name in lin_icon_names:
            icon_path = root / icon_name
            if icon_path.exists():
                cmd.append(f"--linux-icon={icon_path}")
                info(f"Иконка Linux: {icon_path.name}")
                break

    # Главный скрипт
    cmd.append(str(root / MAIN_SCRIPT))

    run("Команда Nuitka:")
    run("  " + " ".join(cmd[:8]) + " ...")
    print()

    result = subprocess.run(cmd, cwd=str(root), env=_get_build_env(venv_python))
    if result.returncode != 0:
        error("Nuitka завершился с ошибкой!")

    info("Компиляция завершена")


# ─── Постобработка ────────────────────────────────────────────────────────────

def _copy_python_interpreter(venv_python: Path, exe_dir: Path):
    """Копирует python3 интерпретатор рядом с exe для запуска piper как subprocess."""
    if not venv_python or not venv_python.exists():
        return

    dst_name = venv_python.name  # python3 или python3.14
    dst = exe_dir / dst_name
    if dst.exists():
        info(f"Python интерпретатор уже есть: {dst_name}")
        return

    try:
        shutil.copy2(str(venv_python), str(dst))
        dst.chmod(0o755)
        info(f"Скопирован Python: {dst_name} → {exe_dir.name}/")
        # Также симлинк python3 → python3.14 если нужно
        symlink = exe_dir / "python3"
        if not symlink.exists() and dst_name != "python3":
            symlink.symlink_to(dst_name)
            info(f"Симлинк: python3 → {dst_name}")
    except Exception as e:
        warn(f"Не удалось скопировать Python: {e}")


def _copy_libpython(venv_python: Path | None, exe_dir: Path, root: Path):
    """Копирует libpython3.x.so рядом с exe и создаёт run.sh с LD_LIBRARY_PATH."""
    # Ищем libpython от venv
    candidates = []
    if venv_python:
        # В venv Python линкован против конкретной libpython
        import subprocess
        r = subprocess.run(
            ["ldd", str(venv_python)],
            capture_output=True, text=True
        )
        import re
        for line in r.stdout.splitlines():
            m = re.search(r'libpython[\d.]+\.so[\d.]*\s+=>\s+(\S+)', line)
            if m:
                candidates.append(Path(m.group(1)))

    # Ищем в стандартных местах
    import glob
    # Ищем libpython любой версии 3.x
    import sys as _sys
    pyver = f"{_sys.version_info.major}.{_sys.version_info.minor}"
    for pattern in [
        f"/usr/lib/libpython{pyver}*.so*",
        f"/usr/lib/x86_64-linux-gnu/libpython{pyver}*.so*",
        f"/usr/lib/libpython3*.so*",
        str(root / f".venv-build/lib/libpython{pyver}*.so*"),
    ]:
        candidates.extend(Path(p) for p in glob.glob(pattern))

    copied = False
    for lib in candidates:
        if lib.exists() and lib.is_file():
            dst = exe_dir / lib.name
            if not dst.exists():
                shutil.copy2(str(lib), str(dst))
                info(f"Скопирована: {lib.name} → {exe_dir.name}/")
            else:
                info(f"Уже есть: {lib.name}")
            copied = True
            break

    if not copied:
        warn(f"libpython{pyver} не найдена — добавлен LD_LIBRARY_PATH в run.sh")


def create_linux_launcher(exe_dir: Path):
    """Создаёт run.sh с правильными путями для Nuitka 4.x."""
    launcher = exe_dir / "run.sh"
    exe_name = APP_NAME
    
    # Проверяем, где находится QtWebEngineProcess
    qtwebengineprocess = exe_dir / "QtWebEngineProcess"
    if qtwebengineprocess.exists():
        # В Nuitka 4.x QtWebEngineProcess лежит в корне
        we_process_path = f'$SCRIPT_DIR/QtWebEngineProcess'
        plugins_path = f'$SCRIPT_DIR/PyQt6/Qt6/plugins'
        resources_path = f'$SCRIPT_DIR/PyQt6/Qt6/resources'
        locales_path = f'$SCRIPT_DIR/PyQt6/Qt6/translations/qtwebengine_locales'
    else:
        # Старая структура
        we_process_path = f'$SCRIPT_DIR/PyQt6/Qt6/libexec/QtWebEngineProcess'
        plugins_path = f'$SCRIPT_DIR/PyQt6/Qt6/plugins'
        resources_path = f'$SCRIPT_DIR/PyQt6/Qt6/resources'
        locales_path = f'$SCRIPT_DIR/PyQt6/Qt6/translations/qtwebengine_locales'
    
    script = (
        "#!/bin/bash\n"
        f"# {APP_NAME} launcher\n"
        "\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        f'EXE="$SCRIPT_DIR/{APP_NAME}"\n'
        "\n"
        'export LD_LIBRARY_PATH="$SCRIPT_DIR:${LD_LIBRARY_PATH:-}"\n'
        f'export QTWEBENGINEPROCESS_PATH="{we_process_path}"\n'
        f'export QT_PLUGIN_PATH="{plugins_path}"\n'
        f'export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGIN_PATH/platforms"\n'
        f'export QTWEBENGINE_RESOURCES_PATH="{resources_path}"\n'
        f'export QTWEBENGINE_LOCALES_PATH="{locales_path}"\n'
        "\n"
        'exec "$EXE" "$@"\n'
    )
    launcher.write_text(script, encoding="utf-8")
    launcher.chmod(0o755)
    info(f"Создан launcher: {launcher.name}")


def create_windows_launcher(exe_dir: Path):
    """Создаёт .bat файл с настройками Qt WebEngine для Windows."""
    launcher = exe_dir / "run.bat"
    
    script = (
        "@echo off\n"
        f"REM {APP_NAME} launcher for Windows\n"
        "\n"
        'set SCRIPT_DIR=%~dp0\n'
        f'set EXE=%SCRIPT_DIR%{APP_NAME}.exe\n'
        "\n"
        'start "" "%EXE%" %*\n'
    )
    launcher.write_text(script, encoding="utf-8")
    info(f"Создан launcher: {launcher.name}")


def post_process(root: Path, dist_dir: Path,
                 venv_python: Path | None = None) -> Path:
    """
    После сборки:
    1. Копирует web/ и fonts/ рядом с exe
    2. Копирует папки Piper (бинарники)
    3. Linux: копирует libpython, python3, создаёт run.sh
    """
    step("Постобработка: копирование ресурсов")

    # Определяем целевую платформу
    host_platform = sys.platform
    target_win = (TARGET_PLATFORM == "windows") or (TARGET_PLATFORM is None and host_platform == "win32")

    # Находим папку с exe (Nuitka кладёт в dist/main.dist/)
    exe_dir = None
    for candidate in [
        dist_dir / f"{MAIN_SCRIPT.replace('.py', '')}.dist",
        dist_dir / f"{APP_NAME}.dist",
        dist_dir,
    ]:
        if candidate.exists() and candidate.is_dir():
            exe_dir = candidate
            break
    if not exe_dir:
        exe_dir = dist_dir
    run(f"Папка с exe: {exe_dir}")

    # Nuitka называет папку по имени входного скрипта (dist/main.dist), а не
    # по имени программы — скрипты упаковки (package-build.sh, Flatpak-
    # манифест) ищут её строго как dist/<APP_NAME> (например dist/NovaReader).
    # Переименовываем/переносим сюда сразу же, чтобы не делать это руками
    # перед каждой упаковкой.
    target_dir = dist_dir / APP_NAME
    if exe_dir.resolve() == dist_dir.resolve():
        # Nuitka положила файлы прямо в dist_dir (без своей подпапки) —
        # переместить саму dist_dir в себя же нельзя, просто оставляем как
        # есть в этом редком случае (обычно Nuitka всегда создаёт <name>.dist).
        pass
    elif exe_dir.resolve() != target_dir.resolve():
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(exe_dir), str(target_dir))
        exe_dir = target_dir
        run(f"Папка переименована в: {exe_dir}")

    # web/ и fonts/ будут скопированы ниже

    # Копируем web/ и fonts/ рядом с exe
    for dir_name in RESOURCE_DIRS:
        src = root / dir_name
        if src.exists():
            dst = exe_dir / dir_name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(str(src), str(dst))
            file_count = sum(1 for _ in dst.rglob('*') if _.is_file())
            info(f"{dir_name}/ скопирован ({file_count} файлов) → {exe_dir.name}/{dir_name}/")
        else:
            warn(f"Папка {dir_name}/ не найдена в корне проекта")

    # Копируем иконку рядом с exe (нужна для QApplication.setWindowIcon() в runtime)
    icon_copied = False
    if target_win:
        icon_candidates = ["NovaReader_Windows.ico", "NovaReader_Windows.png",
                           "NovaReader_Linux.png", "icon.ico", "icon.png"]
    else:
        icon_candidates = ["NovaReader_Linux.png", "NovaReader_Linux.svg",
                           "icon.png", "icon.ico"]
    for icon_name in icon_candidates:
        icon_src = root / icon_name
        if icon_src.exists():
            shutil.copy2(str(icon_src), str(exe_dir / icon_name))
            info(f"Иконка скопирована: {icon_name} → {exe_dir.name}/")
            icon_copied = True
            break
    if not icon_copied:
        warn("Иконка не найдена — в программе будет стандартный значок Windows")

    # Копируем папки с бинарниками Piper (только для текущей платформы!)
    if not target_win:
        # Linux: копируем только tts/piper
        src = root / 'tts/piper'
        if src.exists():
            dst = exe_dir / 'tts/piper'
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(str(src), str(dst))
            file_count = sum(1 for _ in dst.rglob('*') if _.is_file())
            info(f"tts/piper/ скопирована ({file_count} файлов) → {exe_dir.name}/tts/piper/")
            # Явный chmod +x — исходный бит исполняемости мог быть уже
            # потерян ДО этого шага (например, при упаковке/распаковке
            # через zip, который не всегда сохраняет unix-права). Делаем
            # это здесь, а не полагаемся только на самолечение в
            # tts/clients/piper.py — там chmod падает молча, если бинарник
            # окажется на файловой системе только для чтения (AppImage).
            piper_bin = dst / 'piper'
            if piper_bin.exists():
                piper_bin.chmod(piper_bin.stat().st_mode | 0o111)
                info(f"tts/piper/piper: chmod +x применён")
            else:
                warn("tts/piper/piper не найден внутри скопированной папки — TTS через Piper не будет работать")
        else:
            warn("Папка tts/piper/ не найдена, пропускаем")
    else:
        # Windows: копируем только tts/piper-win
        src = root / 'tts/piper-win'
        if src.exists():
            dst = exe_dir / 'tts/piper-win'
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(str(src), str(dst))
            file_count = sum(1 for _ in dst.rglob('*') if _.is_file())
            info(f"tts/piper-win/ скопирована ({file_count} файлов) → {exe_dir.name}/tts/piper-win/")
        else:
            warn("Папка tts/piper-win/ не найдена, пропускаем")

    # Копируем ffmpeg рядом с exe (нужен для Edge TTS: декодирование MP3 → PCM)
    # Windows: ffmpeg.exe в корне проекта
    # Linux:   ffmpeg системный (не копируем, он уже в PATH)
    if target_win:
        ffmpeg_src = root / 'ffmpeg.exe'
        if ffmpeg_src.exists():
            ffmpeg_dst = exe_dir / 'ffmpeg.exe'
            shutil.copy2(str(ffmpeg_src), str(ffmpeg_dst))
            size_mb = ffmpeg_src.stat().st_size / 1024 / 1024
            info(f"ffmpeg.exe скопирован → {exe_dir.name}/ ({size_mb:.1f} MB)")
        else:
            warn("ffmpeg.exe не найден в корне проекта!")
            warn("Edge TTS не будет работать без ffmpeg.")
            warn("Скачай: https://www.gyan.dev/ffmpeg/builds/")
            warn(f"Положи ffmpeg.exe в: {root}")

    # Linux: копируем libpython и python3 интерпретатор
    if not target_win:
        _copy_libpython(venv_python, exe_dir, root)
        _copy_python_interpreter(venv_python, exe_dir)
    # run.sh / run.bat не создаём — запуск напрямую через exe

    info("Постобработка завершена")
    return exe_dir


def print_summary(exe_dir: Path):
    """Выводит итоговую информацию о сборке."""
    # Определяем целевую платформу
    host_platform = sys.platform
    target_win = (TARGET_PLATFORM == "windows") or (TARGET_PLATFORM is None and host_platform == "win32")
    
    exe = exe_dir / (APP_NAME + (".exe" if target_win else ""))

    step("Готово!")
    print()
    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        info(f"Исполняемый файл: {exe} ({size_mb:.1f} MB)")

    # Список файлов в папке
    print(f"\n  Содержимое {exe_dir}:")
    total_size = 0
    files = sorted(exe_dir.iterdir(), key=lambda p: (p.is_dir(), p.name))
    shown = 0
    for f in files:
        if f.is_file():
            sz = f.stat().st_size
            total_size += sz
            if shown < 15 or f.suffix in (".bin", ".exe", "") and f.stem == APP_NAME:
                print(f"    {f.name:<40} {sz/1024:>8.1f} KB")
            shown += 1
    if shown > 15:
        remaining = shown - 15
        print(f"    ... и ещё {remaining} файлов ...")
    for d in exe_dir.iterdir():
        if d.is_dir():
            count = sum(1 for _ in d.rglob("*") if _.is_file())
            print(f"    {d.name}/ ({count} файлов)")

    total_mb = sum(f.stat().st_size for f in exe_dir.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"\n  Общий размер: {total_mb:.1f} MB")
    print()
    print(green(f"  Запуск: {exe}"))
    print()
    if not target_win:
        print(f"  {yellow('Если не запускается — проверь:')}")
        print(f"    ldd {exe} | grep 'not found'")
        print(f"    {exe}  # запустить напрямую из терминала")
    print()


# ─── Главная функция ──────────────────────────────────────────────────────────

# ─── Сборка внутри Docker (обратная совместимость с glibc) ──────────────────

def _run_docker_build(args):
    """Собирает проект внутри Docker-контейнера со старым glibc, чтобы
    итоговый бинарник запускался на системах старее сборочной машины.

    Nuitka линкует результат против glibc ТОЙ машины, где идёт сборка —
    это свойство динамической линковки Linux, а не параметр build.py.
    Единственный надёжный способ получить бинарник, совместимый со старым
    glibc (в этом проекте — 2.39, Ubuntu 24.04), — собрать его внутри
    окружения, где установлена именно эта версия (тот же принцип, что
    manylinux-образы для Python-пакетов)."""
    if sys.platform == "win32":
        error("--docker актуален только для Linux-сборки (glibc — Linux-специфика)")

    docker_bin = shutil.which("docker")
    if not docker_bin:
        error("Docker не найден в PATH. Установите Docker: https://docs.docker.com/engine/install/")

    root = Path(__file__).parent.resolve()
    dockerfile = root / "docker" / "Dockerfile.glibc239"
    if not dockerfile.exists():
        error(f"Не найден {dockerfile}")

    image_tag = "novareader-build:glibc239"
    if args.docker_python:
        image_tag += f"-py{args.docker_python.replace('.', '')}"

    build_args = []
    if args.docker_python:
        build_args = ["--build-arg", f"PYTHON_VERSION={args.docker_python}"]

    step(f"Сборка Docker-образа (glibc 2.39"
         f"{f', Python {args.docker_python}' if args.docker_python else ''}) — "
         f"это может занять пару минут при первом запуске")
    run(f"docker build -f {dockerfile.relative_to(root)} "
        f"{' '.join(build_args)} -t {image_tag} .")
    r = subprocess.run(
        [docker_bin, "build", "-f", str(dockerfile), *build_args, "-t", image_tag, str(root)],
    )
    if r.returncode != 0:
        error("Сборка Docker-образа не удалась (см. вывод выше)")
    info(f"Образ готов: {image_tag}")

    # Прокидываем дальше все флаги, кроме --docker/--docker-python (иначе
    # рекурсия или неизвестный build.py-внутри-контейнера флаг) — то есть
    # --clean, --target, --no-strip и т.п. работают и через --docker.
    passthrough = []
    skip_next = False
    raw_args = sys.argv[1:]
    for i, a in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if a == "--docker":
            continue
        if a == "--docker-python":
            skip_next = True  # пропускаем и сам флаг, и его значение
            continue
        if a.startswith("--docker-python="):
            continue
        passthrough.append(a)

    step(f"Запуск сборки внутри контейнера ({image_tag})")

    # ─── ЗАПУСК С ФЛАГОМ --user ──────────────────────────────────────────────
    # Важно: все файлы, создаваемые внутри контейнера (dist/, build/,
    # .venv-build/ и прочие), должны принадлежать пользователю хоста,
    # а не root. Иначе после сборки их нельзя будет удалить/перезаписать
    # без sudo, что крайне неудобно.
    #
    # user_id = os.getuid() — UID текущего пользователя на хосте.
    # Docker пробрасывает его внутрь контейнера через --user, и все
    # процессы внутри (включая Nuitka) будут создавать файлы с этим UID.
    # Это работает даже если в контейнере нет такого пользователя в
    # /etc/passwd — Docker просто подменяет UID на уровне ядра.
    user_id = os.getuid()
    run(f"Запуск с --user {user_id} (файлы будут принадлежать текущему пользователю)")

    r = subprocess.run([
        docker_bin, "run", "--rm",
        "-u", str(user_id),  # ⬅️ КЛЮЧЕВОЙ ФЛАГ
        "-v", f"{root}:/build",
        image_tag,
        *(passthrough or ["--target", "linux"]),
    ])
    if r.returncode != 0:
        error("Сборка внутри контейнера завершилась с ошибкой (см. вывод выше)")

    print()
    info(f"Готово — бинарник совместим с glibc 2.39+ (см. {DIST_DIR}/)")
    print(f"  {yellow('Проверить минимальную версию glibc итогового бинарника:')}")
    print(f"    objdump -T {DIST_DIR}/{APP_NAME}/{APP_NAME} | grep GLIBC_ | sed 's/.*GLIBC_//' | sort -V | tail -1")
    print()


# ─── AppImage ────────────────────────────────────────────────────────────

def _warn_if_packaging_outside_docker(dist_dir: Path):
    """Если упаковка (AppImage/Flatpak) идёт НЕ внутри Docker-контейнера
    (см. ENV NOVAREADER_IN_DOCKER=1 в Dockerfile.glibc239) — предупреждаем.

    package-build.sh при нехватке какой-то библиотеки в dist/NovaReader
    ищёт её в /usr/lib ТОЙ машины, где сейчас реально выполняется. Если
    сама программа собрана внутри Docker (glibc 2.39), а упаковка в
    AppImage/Flatpak запущена ОТДЕЛЬНО на хосте с более новым glibc
    (например, на Arch с 2.43) — скрипт найдёт и подложит библиотеки
    хоста, и в итоговый пакет незаметно просочится зависимость от более
    новой glibc, сводя на нет весь смысл сборки в контейнере.

    Для чисто нативной сборки (без --docker вообще, всё на одной машине)
    предупреждение ложное — там glibc хоста и так один и тот же на всех
    этапах, поэтому это просто info(), а не warn()."""
    if os.environ.get("NOVAREADER_IN_DOCKER") == "1":
        return  # упаковка идёт внутри контейнера — всё безопасно, тихо продолжаем
    info("Упаковка идёт вне Docker. Если dist/NovaReader собрана через "
         "--docker, а упаковываете вы сейчас на ДРУГОЙ (хостовой) машине — "
         "лучше передать --appimage/--flatpak ВМЕСТЕ с --docker в одной "
         "команде, иначе package-build.sh может подложить библиотеки "
         "хоста и протащить в пакет более новую glibc хоста.")


def _run_appimage_packaging(root: Path, dist_dir: Path):
    """Упаковывает уже собранный dist/NovaReader в AppImage — запускает
    package-build.sh (см. этот файл в корне проекта). Скрипт сам проверяет
    наличие dist/NovaReader, докачивает appimagetool при первом запуске,
    подхватывает Qt-плагины/ресурсы и упаковывает результат в
    NovaReader-<дата>.AppImage в корне проекта."""
    script = root / "package-build.sh"
    if not script.exists():
        warn(f"--appimage пропущен: не найден {script}")
        return
    if not (dist_dir / APP_NAME).exists():
        warn(f"--appimage пропущен: не найдена сборка {dist_dir / APP_NAME}")
        return
    if shutil.which("bash") is None:
        warn("--appimage пропущен: bash не найден в PATH")
        return

    _warn_if_packaging_outside_docker(dist_dir)

    step("AppImage: упаковка через package-build.sh")
    r = subprocess.run(["bash", str(script)], cwd=str(root))
    if r.returncode != 0:
        warn("package-build.sh завершился с ошибкой (см. вывод выше) — "
             "AppImage не создан, но основная сборка в dist/ не пострадала")
    else:
        info("AppImage готов — см. NovaReader-*.AppImage в корне проекта")


# ─── Flatpak ─────────────────────────────────────────────────────────────

def _run_flatpak_packaging(root: Path, dist_dir: Path, install: bool = False):
    """Упаковывает уже собранный dist/NovaReader в Flatpak по манифесту
    flatpak/com.novareader.NovaReader.yml. Манифест не пересобирает
    приложение из исходников — как и AppImage-скрипт, он берёт готовый
    Nuitka-standalone dist/NovaReader и просто кладёт его файлы в песочницу
    Flatpak (buildsystem: simple + cp). Это надёжнее, чем пытаться собрать
    PyQt6-WebEngine из исходников силами flatpak-builder — там своя, более
    сложная и хрупкая цепочка зависимостей."""
    if shutil.which("flatpak-builder") is None:
        warn("--flatpak пропущен: flatpak-builder не найден. Установите:\n"
             "    sudo apt install flatpak-builder\n"
             "    flatpak install flathub org.freedesktop.Platform//23.08 "
             "org.freedesktop.Sdk//23.08")
        return
    if not (dist_dir / APP_NAME).exists():
        warn(f"--flatpak пропущен: не найдена сборка {dist_dir / APP_NAME}")
        return

    _warn_if_packaging_outside_docker(dist_dir)

    manifest = root / "flatpak" / "com.novareader.NovaReader.yml"
    if not manifest.exists():
        warn(f"--flatpak пропущен: не найден манифест {manifest}")
        return

    build_dir = root / "flatpak-build"
    repo_dir = root / "flatpak-repo"

    step("Flatpak: сборка через flatpak-builder")
    cmd = [
        "flatpak-builder", "--force-clean",
        f"--repo={repo_dir}",
        str(build_dir), str(manifest),
    ]
    r = subprocess.run(cmd, cwd=str(root))
    if r.returncode != 0:
        warn("flatpak-builder завершился с ошибкой (см. вывод выше) — "
             "Flatpak не создан, но основная сборка в dist/ не пострадала")
        return
    info(f"Flatpak-репозиторий готов: {repo_dir}")

    if install:
        step("Flatpak: локальная установка (--user)")
        r = subprocess.run(
            ["flatpak-builder", "--user", "--install", "--force-clean",
             str(build_dir), str(manifest)],
            cwd=str(root),
        )
        if r.returncode != 0:
            warn("Установка Flatpak не удалась (см. вывод выше)")
        else:
            info("Flatpak установлен — запуск: flatpak run com.novareader.NovaReader")
    else:
        print(f"  {yellow('Собрать .flatpak-пакет для распространения:')}")
        print(f"    flatpak build-bundle {repo_dir} NovaReader.flatpak "
              f"com.novareader.NovaReader")
        print(f"  {yellow('Или установить локально сразу же в следующий раз:')}")
        print(f"    python3 build.py --target linux --flatpak --flatpak-install")


def main():
    parser = argparse.ArgumentParser(
        description=f"Сборка {APP_NAME} через Nuitka",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--target",      choices=["linux", "windows"], default=None,
                        help="Целевая платформа (по умолчанию: текущая)")
    parser.add_argument("--python",      default=None,        help="Путь к Python (по умолчанию: авто)")
    parser.add_argument("--no-venv",     action="store_true", help="Не создавать venv")
    parser.add_argument("--no-install",  action="store_true", help="Не устанавливать зависимости")
    parser.add_argument("--no-compile",  action="store_true", help="Только шифрование ресурсов")
    parser.add_argument("--clean",       action="store_true", help="Очистить dist/ и build/")
    parser.add_argument("--dist-dir",    default=DIST_DIR,     help="Папка для результата")
    parser.add_argument("--no-strip",    action="store_true",
                        help="Не запускать strip (оставить отладочные символы в .so)")
    parser.add_argument("--no-cleanup",  action="store_true",
                        help="Не удалять мусор (Qt переводы, numpy тесты, WebEngine devtools)")
    parser.add_argument("--no-upx",      action="store_true",
                        help="Не сжимать UPX (по умолчанию UPX включен)")
    parser.add_argument("--docker",      action="store_true",
                        help="Собрать внутри Docker (Ubuntu 24.04, glibc 2.39) для "
                             "обратной совместимости — см. docker/Dockerfile.glibc239. "
                             "Без этого флага бинарник линкуется против glibc ХОСТА, "
                             "на котором идёт сборка, и не запустится на системах "
                             "со старым glibc.")
    parser.add_argument("--docker-python", default=None, metavar="X.Y",
                        help="Версия Python внутри --docker образа (например 3.14). "
                             "Ставится из PPA deadsnakes, если её нет в стандартных "
                             "репозиториях базового образа Ubuntu. По умолчанию — "
                             "минимум, который требует build.py (3.10).")
    parser.add_argument("--appimage",    action="store_true",
                        help="После сборки упаковать dist/NovaReader в AppImage "
                             "(запускает package-build.sh; только Linux).")
    parser.add_argument("--flatpak",     action="store_true",
                        help="После сборки упаковать dist/NovaReader в Flatpak "
                             "(запускает flatpak-builder по манифесту "
                             "flatpak/com.novareader.NovaReader.yml; только Linux).")
    parser.add_argument("--flatpak-install", action="store_true",
                        help="С --flatpak: сразу установить собранный Flatpak "
                             "локально (--user), не только собрать .flatpak-repo.")
    args = parser.parse_args()

    if args.docker:
        _run_docker_build(args)
        return

    # Устанавливаем целевую платформу
    global TARGET_PLATFORM
    TARGET_PLATFORM = args.target

    root     = Path(__file__).parent.resolve()
    dist_dir = root / args.dist_dir

    # ─── ПРОВЕРКА НА КИРИЛЛИЦУ В ПУТИ ──────────────────────────────────────
    # Nuitka не работает с путями, содержащими кириллицу!
    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in str(root))
    if has_cyrillic:
        print(f"\n{red('═' * 70)}")
        print(red("⚠️  ОБНАРУЖЕНА КИРИЛЛИЦА В ПУТИ К ПРОЕКТУ!"))
        print(red("═" * 70))
        print(f"\n  Путь: {root}")
        print(f"\n  Nuitka не работает с путями, содержащими кириллицу!")
        print(f"\n  {yellow('Решение:')} Переместите проект в путь с латиницей:")
        print(f"    mv \"{root}\" /home/user/Downloads/NovaReader")
        print(f"    cd /home/user/Downloads/NovaReader")
        print(f"\n  {green('Правильные пути:')}")
        print(f"    /home/user/Downloads/")
        print(f"    /opt/novareader/")
        print(f"    /home/user/projects/my_app/")
        print(f"\n{red('═' * 70)}\n")
        sys.exit(1)
    # ────────────────────────────────────────────────────────────────────────

    # Определяем целевую платформу для отображения
    host_platform = f"{platform.system()} {platform.machine()}"
    target_desc = TARGET_PLATFORM if TARGET_PLATFORM else host_platform

    print(bold(f"\n{'='*60}"))
    print(bold(f"  {APP_NAME} — сборка через Nuitka"))
    print(bold(f"  Хост-платформа: {host_platform}"))
    print(bold(f"  Целевая платформа: {target_desc}"))
    print(bold(f"  Python: {sys.version.split()[0]}"))
    print(bold(f"{'='*60}\n"))

    # Очистка
    if args.clean:
        step("Очистка старых сборок")
        for d in [dist_dir, root / BUILD_DIR, root / f"{APP_NAME}.build",
                  root / f"{APP_NAME}.dist", root / f"{APP_NAME}.onefile-build"]:
            if d.exists():
                shutil.rmtree(d)
                info(f"Удалено: {d}")

    # Проверяем что main.py существует
    if not (root / MAIN_SCRIPT).exists():
        error(f"{MAIN_SCRIPT} не найден в {root}")



    # venv
    # Если уже запущены внутри venv или conda-окружения — не создаём новый,
    # используем текущий. conda не ставит VIRTUAL_ENV и не меняет
    # sys.base_prefix/sys.prefix (каждое conda-окружение - полноценная
    # отдельная установка Python, а не надстройка над базовым
    # интерпретатором, как обычный venv) - поэтому проверяем отдельно
    # через CONDA_PREFIX, который conda всегда выставляет при активации
    # любого окружения, включая base.
    #
    # Без этой проверки скрипт считал, что окружения нет, и создавал venv
    # через find_python() -> shutil.which(), который при активной conda
    # находит именно conda-питон (она подставляет себя первой в PATH).
    # venv, созданный ОТ conda-питона, обычно нерабочий: он линкуется на
    # библиотеки (libpython3.x.so, openssl, libffi), которые физически
    # лежат внутри conda-окружения, а обычная активация venv не
    # воспроизводит трюки с путями, которые делает conda при своей
    # активации.
    in_conda_env = os.environ.get("CONDA_PREFIX") is not None
    already_in_venv = (
        os.environ.get("VIRTUAL_ENV") is not None or
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix) or
        in_conda_env
    )

    if args.no_venv or already_in_venv:
        venv_python = Path(args.python) if args.python else Path(sys.executable)
        if already_in_venv and not args.no_venv:
            if in_conda_env:
                env_name = os.environ.get("CONDA_DEFAULT_ENV", "base")
                info(f"Обнаружено активное conda-окружение: {env_name}")
            else:
                venv_name = Path(os.environ.get("VIRTUAL_ENV", sys.prefix)).name
                info(f"Обнаружен активный venv: {venv_name}")
        info(f"Используем Python: {venv_python} ({sys.version.split()[0]})")
    else:
        venv_python = setup_venv(root, explicit_python=args.python)

    # Зависимости
    if not args.no_install and not args.no_venv:
        install_dependencies(venv_python, root)
    elif args.no_install:
        warn("Установка зависимостей пропущена (--no-install)")


    # Компиляция
    if not args.no_compile:

        build_nuitka(venv_python, root, dist_dir, args)

    # Постобработка
    exe_dir = post_process(root, dist_dir, venv_python)

    # Скрываем консоль в готовом exe (Windows)
    hide_console_window(exe_dir)
    # Strip + очистка мусора + UPX
    if not args.no_strip:
        run_strip(exe_dir)
    if not args.no_upx:
        run_upx(exe_dir, args)
    if not args.no_cleanup:
        run_cleanup(exe_dir)

    # Итог
    print_summary(exe_dir)

    # ─── Опциональная упаковка (только Linux) ──────────────────────────
    target_is_linux = (TARGET_PLATFORM == "linux") or \
                       (TARGET_PLATFORM is None and platform.system() != "Windows")

    if args.appimage:
        if not target_is_linux:
            warn("--appimage пропущен: доступен только для Linux-сборки")
        else:
            _run_appimage_packaging(root, dist_dir)

    if args.flatpak:
        if not target_is_linux:
            warn("--flatpak пропущен: доступен только для Linux-сборки")
        else:
            _run_flatpak_packaging(root, dist_dir, install=args.flatpak_install)


if __name__ == "__main__":
    main()