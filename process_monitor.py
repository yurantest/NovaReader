#!/usr/bin/env python3
"""
Агрегированный мониторинг памяти приложения.

Зачем: без флага --single-process Chromium (QtWebEngine) запускает
render/GPU-процессы отдельными строками в диспетчере задач, и по ним
неудобно следить за общим потреблением памяти. --single-process решал
это ценой CPU (все роли Chromium делят один поток с Qt/Python).

Вместо этого здесь мы сами суммируем RSS главного процесса и всех его
дочерних (QtWebEngineProcess и т.п.) через psutil — процессы остаются
раздельными для ОС (и для распределения нагрузки по ядрам), но
приложение видит и может показать одну общую цифру.
"""

import os

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


def get_app_memory_report():
    """
    Возвращает dict с суммарной памятью приложения (главный процесс +
    все дочерние, рекурсивно) или None, если psutil недоступен / процесс
    уже не существует.

    {
        'total_bytes': int,
        'total_mb': float,
        'process_count': int,           # включая главный процесс
        'processes': [(name, pid, rss_bytes), ...],
    }
    """
    if not _PSUTIL_OK:
        return None
    try:
        root = psutil.Process(os.getpid())
    except psutil.Error:
        return None

    try:
        children = root.children(recursive=True)
    except psutil.Error:
        children = []
    all_procs = [root] + children

    total = 0
    parts = []
    for p in all_procs:
        try:
            rss = p.memory_info().rss
            name = p.name()
            pid = p.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        total += rss
        parts.append((name, pid, rss))

    return {
        'total_bytes': total,
        'total_mb': total / (1024 * 1024),
        'process_count': len(parts),
        'processes': parts,
    }


def format_app_memory_report() -> str:
    """Однострочная сводка для логов/debug.log в стиле остальных [Memory]-строк."""
    report = get_app_memory_report()
    if report is None:
        return '[Memory] psutil недоступен либо процесс завершён — сводка недоступна'

    # Схлопываем несколько процессов с одинаковым именем (например,
    # QtWebEngineProcess x2-3) в одну запись с count, чтобы строка не
    # растягивалась на десяток пунктов.
    by_name = {}
    for name, _pid, rss in report['processes']:
        entry = by_name.setdefault(name, {'count': 0, 'rss': 0})
        entry['count'] += 1
        entry['rss'] += rss

    breakdown = ', '.join(
        f"{name}" + (f" x{info['count']}" if info['count'] > 1 else '')
        + f": {info['rss'] / (1024 * 1024):.0f} МБ"
        for name, info in by_name.items()
    )
    return (f"[Memory] Приложение суммарно: {report['total_mb']:.0f} МБ "
            f"({report['process_count']} процессов — {breakdown})")
