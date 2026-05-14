"""
screen_inhibit.py — предотвращает отключение экрана / спящий режим.

Принцип caffeine-ng:
  Linux  — D-Bus org.freedesktop.ScreenSaver.Inhibit() через PyQt6.QtDBus.
           Inhibit cookie держится живым пока объект жив в памяти процесса.
           Fallback: org.freedesktop.portal.Inhibit (Wayland portal),
                     затем xset dpms off (X11).
  Windows — SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED).

Использование:
    inhibitor = ScreenInhibitor()
    inhibitor.inhibit()       # запретить гашение экрана
    inhibitor.uninhibit()     # снять запрет
    inhibitor.is_active       # True если запрет активен
"""

import sys
import subprocess


class ScreenInhibitor:
    def __init__(self):
        self._active  = False
        self._cookie  = None   # D-Bus cookie (int) — должен жить в памяти!
        self._iface   = None   # QDBusInterface — держим живым намеренно
        self._method  = None   # 'dbus_screensaver' | 'dbus_portal' | 'xset' | 'windows'

    @property
    def is_active(self) -> bool:
        return self._active

    # ── Публичное API ────────────────────────────────────────────────────────

    def inhibit(self) -> bool:
        """Запрещает гашение экрана. Возвращает True если успешно."""
        if self._active:
            return True
        if sys.platform == 'win32':
            return self._inhibit_windows()
        return self._inhibit_linux()

    def uninhibit(self):
        """Снимает запрет."""
        if not self._active:
            return
        if sys.platform == 'win32':
            self._uninhibit_windows()
        else:
            self._uninhibit_linux()

    # ── Windows ──────────────────────────────────────────────────────────────

    def _inhibit_windows(self) -> bool:
        try:
            import ctypes
            ES_CONTINUOUS       = 0x80000000
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_DISPLAY_REQUIRED)
            self._active = True
            self._method = 'windows'
            print("[ScreenInhibit] Windows: экран не будет гаснуть")
            return True
        except Exception as e:
            print(f"[ScreenInhibit] Windows ошибка: {e}")
            return False

    def _uninhibit_windows(self):
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print("[ScreenInhibit] Windows: запрет снят")
        except Exception as e:
            print(f"[ScreenInhibit] Windows uninhibit ошибка: {e}")
        self._active = False
        self._method = None

    # ── Linux ─────────────────────────────────────────────────────────────────

    def _inhibit_linux(self) -> bool:
        # 1. org.freedesktop.ScreenSaver (GNOME, KDE, XFCE, X11+Wayland)
        if self._try_dbus_screensaver():
            return True
        # 2. org.freedesktop.portal.Inhibit (Wayland portal)
        if self._try_dbus_portal():
            return True
        # 3. xset (X11 last resort)
        if self._try_xset():
            return True
        print("[ScreenInhibit] Не удалось подавить гашение экрана")
        return False

    def _uninhibit_linux(self):
        m = self._method
        if m == 'dbus_screensaver':
            self._dbus_screensaver_uninhibit()
        elif m == 'dbus_portal':
            self._dbus_portal_uninhibit()
        elif m == 'xset':
            self._xset_uninhibit()
        self._active = False
        self._method = None

    # ── D-Bus: org.freedesktop.ScreenSaver ───────────────────────────────────
    # Это основной метод caffeine-ng — работает на GNOME, KDE, XFCE, Wayland.
    # ВАЖНО: self._iface и self._cookie должны оставаться живыми в памяти —
    # D-Bus автоматически снимает inhibit когда объект уничтожается.

    def _try_dbus_screensaver(self) -> bool:
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
            bus = QDBusConnection.sessionBus()
            if not bus.isConnected():
                return False

            # Перебираем все известные пути для разных DE
            # KDE Wayland/X11, GNOME, XFCE используют разные пути
            candidates = [
                ('org.freedesktop.ScreenSaver',
                 '/org/freedesktop/ScreenSaver',
                 'org.freedesktop.ScreenSaver'),
                ('org.freedesktop.ScreenSaver',
                 '/ScreenSaver',
                 'org.freedesktop.ScreenSaver'),
                ('org.gnome.SessionManager',
                 '/org/gnome/SessionManager',
                 'org.gnome.SessionManager'),
                ('org.kde.PowerManagement.Inhibit',
                 '/org/kde/PowerManagement/Inhibit',
                 'org.kde.PowerManagement.Inhibit'),
            ]
            iface = None
            for service, path, interface in candidates:
                candidate = QDBusInterface(service, path, interface, bus)
                if candidate.isValid():
                    iface = candidate
                    print(f"[ScreenInhibit] D-Bus сервис найден: {service}")
                    break
            if iface is None:
                print("[ScreenInhibit] ScreenSaver D-Bus: ни один сервис не найден")
                return False

            # Разные DE используют разные сигнатуры Inhibit
            reply = iface.call('Inhibit', 'NovaReader', 'Чтение книги')
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                # Fallback: некоторые DE требуют дополнительные аргументы
                reply = iface.call('Inhibit', 'NovaReader', 0, 'Чтение книги', 8)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                print(f"[ScreenInhibit] ScreenSaver D-Bus ошибка: {reply.errorMessage()}")
                return False

            args = reply.arguments()
            if not args:
                return False

            self._cookie = args[0]   # uint — держим живым!
            self._iface  = iface     # держим живым!
            self._active = True
            self._method = 'dbus_screensaver'
            print(f"[ScreenInhibit] ScreenSaver inhibit OK (cookie={self._cookie})")
            return True

        except ImportError:
            print("[ScreenInhibit] PyQt6.QtDBus недоступен")
        except Exception as e:
            print(f"[ScreenInhibit] ScreenSaver D-Bus: {e}")
        return False

    def _dbus_screensaver_uninhibit(self):
        try:
            if self._iface and self._cookie is not None:
                self._iface.call('UnInhibit', self._cookie)
                print("[ScreenInhibit] ScreenSaver uninhibit OK")
        except Exception as e:
            print(f"[ScreenInhibit] ScreenSaver uninhibit ошибка: {e}")
        finally:
            self._cookie = None
            self._iface  = None

    # ── D-Bus: org.freedesktop.portal.Inhibit (Wayland portal) ───────────────

    def _try_dbus_portal(self) -> bool:
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
            bus = QDBusConnection.sessionBus()
            if not bus.isConnected():
                return False

            iface = QDBusInterface(
                'org.freedesktop.portal.Desktop',
                '/org/freedesktop/portal/desktop',
                'org.freedesktop.portal.Inhibit',
                bus
            )
            if not iface.isValid():
                return False

            # flags: 8 = inhibit idle/suspend
            reply = iface.call('Inhibit', '', 8, {'reason': 'Чтение книги'})
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                return False

            self._iface  = iface
            self._active = True
            self._method = 'dbus_portal'
            print("[ScreenInhibit] Wayland portal inhibit OK")
            return True

        except Exception as e:
            print(f"[ScreenInhibit] Portal D-Bus: {e}")
        return False

    def _dbus_portal_uninhibit(self):
        # Portal inhibit снимается автоматически при закрытии соединения
        self._iface = None
        print("[ScreenInhibit] Wayland portal uninhibit")

    # ── xset (X11 fallback) ───────────────────────────────────────────────────

    def _try_xset(self) -> bool:
        try:
            r1 = subprocess.run(['xset', 's', 'off'],   capture_output=True, timeout=3)
            r2 = subprocess.run(['xset', '-dpms'],      capture_output=True, timeout=3)
            if r1.returncode == 0 or r2.returncode == 0:
                self._active = True
                self._method = 'xset'
                print("[ScreenInhibit] xset: экран не будет гаснуть")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False

    def _xset_uninhibit(self):
        try:
            subprocess.run(['xset', 's', 'on'],  capture_output=True, timeout=3)
            subprocess.run(['xset', '+dpms'],    capture_output=True, timeout=3)
            print("[ScreenInhibit] xset: запрет снят")
        except Exception as e:
            print(f"[ScreenInhibit] xset uninhibit: {e}")
