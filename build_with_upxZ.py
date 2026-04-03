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
RESOURCE_DIRS = ["web", "fonts"]

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

def _res_should_exclude(path: Path) -> bool:
    """Проверяет, нужно ли исключить файл из упаковки."""
    name = path.name
    for pattern in RESOURCE_EXCLUDES:
        if pattern.startswith('*.'):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    parts = path.parts
    if any(p in parts for p in ['.git', '.github', '__pycache__']):
        return True
    return False


    """
    Кодирует web/ и fonts/ в base64 и генерирует resources_bin.py.
    Аналог build_resources.py, встроенный в build.py.
    """
    import base64 as _b64

    step("Упаковка " + ", ".join(f"{d}/" for d in RESOURCE_DIRS) + " → resources_bin.py")

    fonts_files: dict[str, str] = {}
    fonts_dir = root / "fonts"
    if "fonts" in RESOURCE_DIRS and fonts_dir.exists():
        for f in sorted(fonts_dir.glob("*")):
            if f.is_file() and not _res_should_exclude(f):
                fonts_files[f.name] = _b64.b64encode(f.read_bytes()).decode("ascii")
                run(f"fonts/{f.name}  ({len(fonts_files[f.name])} b64-байт)")

    web_files: dict[str, str] = {}
    web_dir = root / "web"
    if "web" in RESOURCE_DIRS and web_dir.exists():
        for f in sorted(web_dir.rglob("*")):
            if f.is_file() and not _res_should_exclude(f):
                rel = str(f.relative_to(web_dir)).replace("\\", "/")
                web_files[rel] = _b64.b64encode(f.read_bytes()).decode("ascii")
                run(f"web/{rel}  ({len(web_files[rel])} b64-байт)")

    info(f"Шрифты: {len(fonts_files)}, web-файлы: {len(web_files)}")

    fonts_str = ",\n    ".join(f"'{k}': b'{v}'" for k, v in fonts_files.items())
    web_str   = ",\n    ".join(f"'{k}': b'{v}'" for k, v in web_files.items())

    code = (
        '# -*- coding: utf-8 -*-\n'
        '"""Бинарные ресурсы (web, fonts) — автогенерировано build.py. НЕ РЕДАКТИРОВАТЬ."""\n'
        'import base64, tempfile, os, hashlib, shutil, atexit, glob\n'
        'from pathlib import Path\n\n'
        f'FONTS = {{\n    {fonts_str if fonts_str else "# нет файлов"}\n}}\n\n'
        f'WEB_FILES = {{\n    {web_str if web_str else "# нет файлов"}\n}}\n\n'
        '_web_temp_dir: str | None = None\n\n'
        'def _get_web_temp_dir() -> str:\n'
        '    global _web_temp_dir\n'
        '    if _web_temp_dir and Path(_web_temp_dir, "reader.html").exists():\n'
        '        return _web_temp_dir\n'
        '    h = hashlib.md5(str(sorted(WEB_FILES.keys())).encode()).hexdigest()[:8]\n'
        '    d = Path(tempfile.gettempdir()) / f"novareader_{h}"\n'
        '    if d.exists():\n'
        '        shutil.rmtree(d)\n'
        '    d.mkdir(parents=True)\n'
        '    for name, b64 in WEB_FILES.items():\n'
        '        p = d / name\n'
        '        p.parent.mkdir(parents=True, exist_ok=True)\n'
        '        p.write_bytes(base64.b64decode(b64))\n'
        '    _web_temp_dir = str(d)\n'
        '    return _web_temp_dir\n\n'
        'def get_web_dir() -> Path:\n'
        '    """Возвращает Path к временной папке web/ со всеми файлами."""\n'
        '    return Path(_get_web_temp_dir())\n\n'
        'def get_font_path(font_name: str) -> str:\n'
        '    """Создаёт временный файл шрифта и возвращает путь к нему."""\n'
        '    if font_name not in FONTS:\n'
        '        raise ValueError(f"Unknown font: {font_name}")\n'
        '    fd, path = tempfile.mkstemp(suffix=".ttf")\n'
        '    os.write(fd, base64.b64decode(FONTS[font_name]))\n'
        '    os.close(fd)\n'
        '    return path\n\n'
        'def _cleanup():\n'
        '    tmp = Path(tempfile.gettempdir())\n'
        '    for d in tmp.glob("novareader_*"):\n'
        '        try: shutil.rmtree(d)\n'
        '        except: pass\n'
        '    for f in glob.glob(str(tmp / "*.ttf")):\n'
        '        try: os.unlink(f)\n'
        '        except: pass\n\n'
        'atexit.register(_cleanup)\n'
    )

    out_py.write_text(code, encoding="utf-8")
    size_kb = out_py.stat().st_size / 1024
    info(f"resources_bin.py готов ({size_kb:.1f} KB) → {out_py.name}")


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

# Паттерны переводов которые ОСТАВЛЯЕМ (ru + en)
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

    total_before = sum(f.stat().st_size for f in targets)
    ok = failed = 0

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


def build_nuitka(venv_python: Path, root: Path, dist_dir: Path, args=None):
    """Запускает Nuitka для компиляции приложения."""
    step("Сборка через Nuitka")
    
    # Определяем целевую платформу
    host_platform = sys.platform
    target_win = (TARGET_PLATFORM == "windows") or (TARGET_PLATFORM is None and host_platform == "win32")
    
    out_name = APP_NAME + (".exe" if target_win else "")
    nuitka_ver = get_nuitka_version(venv_python)

    # Базовые флаги Nuitka
    cmd = [
        str(venv_python), "-m", "nuitka",
        "--standalone",                        # все зависимости рядом с exe
        f"--output-dir={dist_dir}",
        f"--output-filename={out_name}",
        "--assume-yes-for-downloads",          # авто-скачать gcc/MinGW если нужно

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
    # Linux (нативная):   Zig в корне проекта → системный gcc/cc
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
        # Linux: Zig (если есть в корне) → системный gcc
        zig = find_zig_compiler(root)
        if zig:
            os.environ.setdefault("CC",  f"{zig} cc")
            os.environ.setdefault("CXX", f"{zig} c++")
            info(f"Компилятор Linux: Zig ({zig})")
        else:
            gcc = shutil.which("gcc") or shutil.which("cc")
            if gcc:
                info(f"Компилятор Linux: {gcc}")
            else:
                error("gcc/cc не найден. Установите: sudo apt install build-essential")

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

        # web/ и fonts/ встроены в resources_bin.so/pyd

        # Включаем папки с бинарниками Piper: только нужную платформу
        *( ["--include-data-dir=tts/piper-win=tts/piper-win"]
           if target_win else
           ["--include-data-dir=tts/piper=tts/piper"] ),

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
        "--include-module=graphics_backend",
        "--include-module=audio_player",
        # Сетевые пакеты (edge-tts + requests)
        "--include-package=edge_tts",
        "--include-package=requests",
        # certifi и charset_normalizer подтягиваются через requests автоматически
        
        # Аудио
        "--include-package=sounddevice",
        "--include-package=numpy",
        # aiohttp и его зависимости (yarl, frozenlist, multidict и др.)
        # подтягиваются автоматически через edge_tts — не дублируем
    ])

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

    result = subprocess.run(cmd, cwd=str(root))
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
        "# Флаги памяти WebEngine — устанавливаем здесь т.к. main.py использует setdefault\n"
        "# (setdefault не перезапишет переменную если она уже задана лаунчером)\n"
        'export QTWEBENGINE_CHROMIUM_FLAGS="--use-gl=egl --disable-gpu-compositing --js-flags=--max-old-space-size=192 --renderer-process-limit=1 --disable-background-networking --disable-dev-shm-usage --disk-cache-size=1 --media-cache-size=1 --disable-gpu-rasterization --blink-settings=maximumDecodedImageSize=33554432 --disable-features=Prefetch,PreloadMediaEngagementData"\n'
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
        "REM Оптимизация Qt WebEngine: используем DirectX 11 через ANGLE\n"
        "\n"
        'set SCRIPT_DIR=%~dp0\n'
        f'set EXE=%SCRIPT_DIR%{APP_NAME}.exe\n'
        "\n"
        "REM Флаги памяти WebEngine\n"
        'set QTWEBENGINE_CHROMIUM_FLAGS=--use-gl=angle --use-angle=d3d11 --js-flags=--max-old-space-size=192 --renderer-process-limit=1 --disable-background-networking --disable-dev-shm-usage --disk-cache-size=1 --media-cache-size=1 --disable-gpu-rasterization --blink-settings=maximumDecodedImageSize=33554432 --disable-features=Prefetch,PreloadMediaEngagementData\n'
        'set ANGLE_FEATURE_OVERRIDES_ENABLED=force_d3d11\n'
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
    args = parser.parse_args()

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
    # Если уже запущены внутри venv — не создаём новый, используем текущий
    already_in_venv = (
        os.environ.get("VIRTUAL_ENV") is not None or
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

    if args.no_venv or already_in_venv:
        venv_python = Path(args.python) if args.python else Path(sys.executable)
        if already_in_venv and not args.no_venv:
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
        # Упаковываем web/ и fonts/ → resources_bin.py → .so/.pyd
        resources_py = root / "resources_bin.py"

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


if __name__ == "__main__":
    main()
