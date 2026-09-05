#!/usr/bin/env python3
"""
Управление GPU-предпочтением процессов на Windows.

Windows назначает "высокая производительность" / "энергосбережение"
отдельно на каждый exe-файл через один и тот же реестровый механизм DXGI
(HKCU\\SOFTWARE\\Microsoft\\DirectX\\UserGpuPreferences), которым пользуются
и "Параметры графики" Windows, и панели NVIDIA/AMD.

Раньше (--single-process) весь Chromium был одним и тем же exe -
программой - поэтому одна настройка GPU покрывала всё. Теперь отдельный
хелпер-процесс (переименованная копия QtWebEngineProcess) - это другой
файл по другому пути, и драйвер может назначить ему другой физический
адаптер, чем главному процессу. Рассинхронизация адаптеров между главным
процессом (панели/UI) и хелпером (содержимое книги) - вероятная причина
чёрного экрана вместо текста при ручном включении "высокой
производительности" только для одного из двух exe.

На Linux/macOS все функции - no-op (там нет этого реестрового механизма;
гибридная графика на Linux управляется отдельно, через PRIME/DRI_PRIME -
см. _linux_apply_hybrid_gpu_env в main.py).
"""

import sys
from pathlib import Path

_KEY_PATH = r'SOFTWARE\Microsoft\DirectX\UserGpuPreferences'
_LEVELS = {'power_saving': 1, 'high_performance': 2}


def is_supported() -> bool:
    return sys.platform == 'win32'


def get_gpu_preference(exe_path) -> str:
    """
    Возвращает текущее предпочтение для exe_path: 'auto' (не задано),
    'power_saving' или 'high_performance'. На не-Windows всегда 'auto'.
    """
    if not is_supported():
        return 'auto'
    try:
        import winreg
        exe = str(Path(exe_path).resolve())
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, exe)
        for name, num in _LEVELS.items():
            if f'GpuPreference={num}' in value:
                return name
    except OSError:
        pass
    return 'auto'


def set_gpu_preference(level: str, exe_paths):
    """
    Явно задаёт предпочтение GPU для списка exe-путей. level: 'auto'
    (сбросить/не задавать), 'power_saving' или 'high_performance'.
    На не-Windows ничего не делает.
    """
    if not is_supported():
        return
    if level not in ('auto',) and level not in _LEVELS:
        raise ValueError(f'Неизвестный уровень GPU-предпочтения: {level}')
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _KEY_PATH) as key:
            for exe_path in exe_paths:
                exe = str(Path(exe_path).resolve())
                if level == 'auto':
                    try:
                        winreg.DeleteValue(key, exe)
                        print(f'[GPU] Сброшено предпочтение для {exe}')
                    except FileNotFoundError:
                        pass
                else:
                    value = f'GpuPreference={_LEVELS[level]};'
                    try:
                        current, _ = winreg.QueryValueEx(key, exe)
                    except FileNotFoundError:
                        current = None
                    if current != value:
                        winreg.SetValueEx(key, exe, 0, winreg.REG_SZ, value)
                        print(f'[GPU] Установлено предпочтение для {exe}: {value}')
    except OSError as e:
        print(f'[GPU] Не удалось установить GPU-предпочтение: {e}')


def sync_gpu_preference(main_exe_path, other_exe_path):
    """
    Копирует предпочтение GPU с main_exe_path на other_exe_path, если оно
    там задано (например, пользователь вручную включил "высокую
    производительность" в панели NVIDIA только для главного exe). Если у
    главного exe предпочтение не задано - ничего не навязывает.
    """
    level = get_gpu_preference(main_exe_path)
    if level == 'auto':
        return
    if get_gpu_preference(other_exe_path) != level:
        set_gpu_preference(level, [other_exe_path])
