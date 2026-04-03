#!/usr/bin/env python3
"""
Автоматический выбор графического backend для Qt WebEngine в PyQt6.
Работает на Windows и Linux.
"""

import os
import platform


def configure_qt_graphics():
    """
    Настраивает графический backend для Qt WebEngine до создания QApplication.
    
    Linux: OpenGL (desktop) → fallback на software если не работает
    Windows: DirectX через ANGLE (d3d11)
    """
    system = platform.system()
    
    if system == "Linux":
        # Linux: пробуем OpenGL, но с fallback на software
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ["QT_OPENGL"] = "software"
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer"
    
    elif system == "Windows":
        # Windows: используем DirectX через ANGLE
        os.environ["QT_OPENGL"] = "angle"
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-angle=d3d11"
        os.environ.pop("QT_QUICK_BACKEND", None)
