# -*- coding: utf-8 -*-
"""
Виджет загрузки голосов Piper TTS для окна настроек.
Загрузка идёт через QProcess (отдельный процесс) — полная изоляция от UI.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QProgressBar, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QProcess, QTimer
from PyQt6.QtGui import QFont
from pathlib import Path
import json
import sys
import time
from piper_voice_downloader import PiperVoiceDownloader


def _palette():
    """Ленивый импорт палитры из settings_window."""
    import settings_window as sw
    return dict(
        BG=sw.S_BG, SURFACE=sw.S_SURFACE, BORDER=sw.S_BORDER,
        ACCENT=sw.S_ACCENT, TEXT=sw.S_TEXT, SUB=sw.S_SUB, HOVER=sw.S_HOVER,
    )


_ICON_DOWNLOAD = '\u2193'
_ICON_CHECK = '\u2713'

_PW_S = {
    'ru': {
        'title': 'Голоса Piper TTS',
        'hint': 'Нажмите {arrow} для загрузки голоса. После загрузки голос станет доступен в читалке.',
        'quality': 'Качество',
        'download': '{arrow} Загрузить',
        'downloading': '{arrow} Загрузка...',
        'retrying': '{arrow} Повтор...',
        'installed': '{check} Установлен',
        'delete': 'Удалить',
    },
    'en': {
        'title': 'Piper TTS Voices',
        'hint': 'Click {arrow} to download a voice. Once downloaded, it will be available in the reader.',
        'quality': 'Quality',
        'download': '{arrow} Download',
        'downloading': '{arrow} Downloading...',
        'retrying': '{arrow} Retrying...',
        'installed': '{check} Installed',
        'delete': 'Delete',
    },
}


def _pw_s(config, key):
    lang = config.get('language', 'ru')
    template = _PW_S.get(lang, _PW_S['ru']).get(key, key)
    return template.format(arrow=_ICON_DOWNLOAD, check=_ICON_CHECK)


class PiperVoicesWidget(QWidget):
    voicesChanged = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.voices_dir = config.voices_dir
        self.downloader = PiperVoiceDownloader(self.voices_dir)
        self.download_processes = {}      # voice_id -> QProcess
        self._process_buffers = {}        # voice_id -> str (буфер частичных строк)
        self._download_retries = {}       # voice_id -> int (счётчик попыток)
        self._progress_bar_cache = {}     # voice_id -> QProgressBar (чтобы не дёргать findChild на каждый % )
        self._last_progress_update = {}   # voice_id -> (время последнего обновления, последний %)
        self._cancelled_voices = set()    # voice_id, намеренно отменённые (удаление во время загрузки) —
                                           # чтобы _handle_process_failure не запускал для них автоповтор
        self._colors = _palette()
        self._init_ui()
        self._load_voices()

    def _t(self, key):
        return _pw_s(self.config, key)

    def _init_ui(self):
        c = self._colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(self._t('title').upper())
        title.setStyleSheet(
            f"color:{c['SUB']}; font-size:11px; font-weight:700; "
            f"letter-spacing:0.8px; background:transparent;"
        )
        layout.addWidget(title)

        hint = QLabel(self._t('hint'))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{c['SUB']}; font-size:11px; background:transparent;")
        layout.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: {c['BORDER']}; border-radius: 3px; min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self.voices_container = QWidget()
        self.voices_container.setStyleSheet("background:transparent;")
        self.voices_layout = QVBoxLayout(self.voices_container)
        self.voices_layout.setContentsMargins(0, 0, 0, 0)
        self.voices_layout.setSpacing(8)
        self.voices_layout.addStretch()

        self.scroll.setWidget(self.voices_container)
        layout.addWidget(self.scroll)

    def _load_voices(self):
        while self.voices_layout.count() > 1:
            item = self.voices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for voice_data in self.downloader.RUSSIAN_VOICES:
            voice_id = voice_data["name"]
            voice_name = voice_data["display_name"]
            voice_quality = voice_data["quality"]
            installed = self.downloader.check_voice_exists(voice_id)
            widget = self._create_voice_widget(voice_id, voice_name, voice_quality, installed)
            self.voices_layout.insertWidget(self.voices_layout.count() - 1, widget)

    def _create_voice_widget(self, voice_id, voice_name, quality, installed):
        c = self._colors
        frame = QFrame()
        frame.setObjectName("VoiceCard")
        frame.setStyleSheet(f"""
            QFrame#VoiceCard {{
                background: {c['SURFACE']};
                border: 1px solid {c['BORDER']};
                border-radius: 8px;
            }}
            QFrame#VoiceCard:hover {{ border-color: {c['ACCENT']}; }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(f"<b>{voice_name}</b>")
        name_label.setStyleSheet(f"color:{c['TEXT']}; font-size:14px; background:transparent;")
        info_layout.addWidget(name_label)

        quality_label = QLabel(f"{self._t('quality')}: <span style='color:{c['ACCENT']};'>{quality}</span>")
        quality_label.setStyleSheet(f"color:{c['SUB']}; font-size:12px; background:transparent;")
        info_layout.addWidget(quality_label)

        layout.addLayout(info_layout, 1)

        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if installed:
            row = QHBoxLayout()
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.setSpacing(6)

            status_label = QLabel(self._t('installed'))
            status_label.setStyleSheet(
                f"color:#4caf50; font-size:12px; font-weight:600; "
                f"background: rgba(76,175,80,0.12); border-radius:6px; padding:4px 10px;"
            )
            row.addWidget(status_label)

            delete_btn = QPushButton(self._t('delete'))
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: #e57373;
                    border: 1px solid #e57373; border-radius: 6px;
                    padding: 4px 10px; font-size: 12px;
                }}
                QPushButton:hover {{ background: rgba(229,115,115,0.15); }}
            """)
            delete_btn.clicked.connect(lambda checked, vid=voice_id: self._delete_voice(vid))
            row.addWidget(delete_btn)

            status_layout.addLayout(row)
        else:
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            download_btn = QPushButton(self._t('download'))
            download_btn.setObjectName(f"download_btn_{voice_id}")
            download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            download_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['ACCENT']}; color: white; border: none;
                    border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {c['ACCENT']}; }}
                QPushButton:disabled {{ background: {c['BORDER']}; color: {c['SUB']}; }}
            """)
            download_btn.clicked.connect(lambda checked, vid=voice_id: self._download_voice(vid))
            btn_layout.addWidget(download_btn)

            status_layout.addLayout(btn_layout)

            progress = QProgressBar()
            progress.setObjectName(f"progress_{voice_id}")
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(True)
            progress.setFormat("%p%")
            progress.setFixedWidth(120)
            progress.setStyleSheet(f"""
                QProgressBar {{
                    background: {c['BG']}; border: 1px solid {c['BORDER']};
                    border-radius: 3px; height: 16px; text-align: center; color: {c['TEXT']};
                }}
                QProgressBar::chunk {{ background: {c['ACCENT']}; border-radius: 2px; }}
            """)
            progress.hide()
            status_layout.addWidget(progress)

        layout.addLayout(status_layout)
        return frame

    def _delete_voice(self, voice_id):
        # Если для этого голоса ещё идёт активная загрузка — сначала
        # останавливаем её, иначе после повторного нажатия "Загрузить"
        # получим два параллельных процесса, пишущих в один и тот же файл.
        process = self.download_processes.get(voice_id)
        if process is not None:
            print(f"[PiperVoices] Останавливаем активную загрузку {voice_id} перед удалением...")
            self._cancelled_voices.add(voice_id)
            try:
                process.kill()
                process.waitForFinished(2000)
            except Exception as e:
                print(f"[PiperVoices] Ошибка остановки процесса {voice_id}: {e}")
            self.download_processes.pop(voice_id, None)
            self._process_buffers.pop(voice_id, None)
            self._download_retries.pop(voice_id, None)
            self._progress_bar_cache.pop(voice_id, None)
            self._last_progress_update.pop(voice_id, None)

        try:
            success = self.downloader.delete_voice(voice_id)
            print(f"[PiperVoices] Удаление {voice_id}: {'успех' if success else 'голос не найден'}")
        except Exception as e:
            print(f"[PiperVoices] Ошибка удаления {voice_id}: {e}")
        self._load_voices()
        self.voicesChanged.emit()

    def _download_voice(self, voice_id, retry_count=0):
        """Запускает загрузку в ОТДЕЛЬНОМ ПРОЦЕССЕ через QProcess с проверкой и перезапуском."""
        try:
            # Не даём запустить второй процесс для того же голоса, пока первый
            # ещё жив — иначе оба параллельно пишут в один и тот же файл.
            if voice_id in self.download_processes:
                print(f"[PiperVoices] Загрузка {voice_id} уже выполняется — игнорируем повторный запуск")
                return

            # Сохраняем счётчик попыток
            self._download_retries[voice_id] = retry_count

            voice_info = None
            for v in self.downloader.RUSSIAN_VOICES:
                if v["name"] == voice_id:
                    voice_info = v
                    break

            if not voice_info:
                print(f"[PiperVoices] Голос не найден: {voice_id}")
                return

            progress_bar = self.findChild(QProgressBar, f"progress_{voice_id}")
            if not progress_bar:
                print(f"[PiperVoices] Не найден progress_bar для {voice_id}")
                return

            btn = self.findChild(QPushButton, f"download_btn_{voice_id}")
            if btn:
                btn.setEnabled(False)
                btn.setText(self._t('retrying') if retry_count > 0 else self._t('downloading'))

            progress_bar.show()
            progress_bar.setValue(0)
            self._progress_bar_cache[voice_id] = progress_bar
            self._last_progress_update[voice_id] = (0.0, -1)

            # Команда запуска воркера — та же логика, что и для читалки
            # (--reader): в собранном виде системного Python нет и
            # voice_download_worker.py не лежит рядом с exe отдельным файлом
            # (он вкомпилирован внутрь), поэтому запускаем сам исполняемый
            # файл программы с флагом --piper-worker, а не sys.executable +
            # путь к .py. В dev-режиме (python main.py) это по-прежнему
            # обычный python3 + voice_download_worker.py.
            try:
                from main import _build_piper_worker_cmd
                worker_cmd = _build_piper_worker_cmd(
                    voice_info["name"], voice_info["onnx"], voice_info["json"],
                    str(self.voices_dir)
                )
            except Exception as e:
                print(f"[PiperVoices] КРИТИЧЕСКАЯ ОШИБКА: не удалось построить команду воркера: {e}")
                self._reset_voice_button(voice_id)
                return

            print(f"[PiperVoices] Команда воркера: {worker_cmd}")
            print(f"[PiperVoices] Голос: {voice_info['name']}")

            # Создаём QProcess
            process = QProcess(self)
            process.setProgram(worker_cmd[0])
            process.setArguments(worker_cmd[1:])

            # Устанавливаем кодировку UTF-8 для stdout/stderr
            env = process.processEnvironment()
            env.insert('PYTHONIOENCODING', 'utf-8')
            env.insert('PYTHONUNBUFFERED', '1')
            process.setProcessEnvironment(env)

            # Буфер для накопления частичных строк
            self._process_buffers[voice_id] = ""

            # Подключаем сигналы
            process.readyReadStandardOutput.connect(
                lambda pid=voice_id: self._on_process_output(pid)
            )
            process.readyReadStandardError.connect(
                lambda pid=voice_id: self._on_process_error(pid)
            )
            process.finished.connect(
                lambda exit_code, exit_status, pid=voice_id: self._on_process_finished(pid, exit_code, exit_status)
            )
            # errorOccurred — асинхронный сигнал, не блокирует UI. Заменяет
            # прежний waitForStarted(3000), который замораживал интерфейс на
            # срок до 3 секунд (а при повторных попытках — кратно дольше),
            # потому что вызывался прямо из обработчика клика в главном потоке.
            process.errorOccurred.connect(
                lambda err, pid=voice_id, rc=retry_count: self._on_process_error_occurred(pid, err, rc)
            )

            self.download_processes[voice_id] = process

            print(f"[PiperVoices] Запуск процесса...")
            process.start()
            print(f"[PiperVoices] process.start() вызван (попытка {retry_count + 1}) — "
                  f"дальнейшая судьба процесса придёт асинхронно через сигналы")

        except Exception as e:
            print(f"[PiperVoices] ИСКЛЮЧЕНИЕ при запуске загрузки {voice_id}: {e}")
            import traceback
            traceback.print_exc()
            self._handle_process_failure(voice_id, retry_count, str(e))

    def _on_process_error_occurred(self, voice_id, error, retry_count):
        """QProcess.errorOccurred — асинхронный аналог проверки, которую раньше
        делал блокирующий waitForStarted(). Сработает, например, если системе
        не удалось запустить процесс (QProcess.ProcessError.FailedToStart)."""
        from PyQt6.QtCore import QProcess as _QP
        error_names = {
            _QP.ProcessError.FailedToStart: "FailedToStart (не удалось запустить)",
            _QP.ProcessError.Crashed: "Crashed",
            _QP.ProcessError.Timedout: "Timedout",
            _QP.ProcessError.ReadError: "ReadError",
            _QP.ProcessError.WriteError: "WriteError",
            _QP.ProcessError.UnknownError: "UnknownError",
        }
        error_name = error_names.get(error, str(error))
        print(f"[PiperVoices] errorOccurred для {voice_id}: {error_name}")
        if error == _QP.ProcessError.FailedToStart:
            self._handle_process_failure(voice_id, retry_count, error_name)

    def _handle_process_failure(self, voice_id, retry_count, error_msg):
        """Обрабатывает сбой запуска и решает, делать ли повторную попытку."""
        if voice_id in self._cancelled_voices:
            self._cancelled_voices.discard(voice_id)
            print(f"[PiperVoices] {voice_id} был отменён пользователем — автоповтор не запускаем")
            self._reset_voice_button(voice_id)
            return

        # Очищаем старый процесс, если он есть
        process = self.download_processes.pop(voice_id, None)
        if process:
            try:
                process.readyReadStandardOutput.disconnect()
                process.readyReadStandardError.disconnect()
                process.finished.disconnect()
            except Exception:
                pass
            # НЕ вызываем deleteLater() — это причина крашей!

        max_retries = 2  # Всего будет 3 попытки: 0, 1, 2
        if retry_count < max_retries:
            print(f"[PiperVoices] Планируется повторная попытка через 1.5 сек...")
            # Меняем текст кнопки, чтобы пользователь видел, что идёт повтор
            btn = self.findChild(QPushButton, f"download_btn_{voice_id}")
            if btn:
                btn.setText(self._t('retrying'))

            # Отложенный перезапуск через QTimer
            QTimer.singleShot(1500, lambda vid=voice_id, rc=retry_count + 1: self._download_voice(vid, rc))
        else:
            print(f"[PiperVoices] КРИТИЧЕСКИЙ СБОЙ: Не удалось загрузить {voice_id} после {max_retries + 1} попыток. Причина: {error_msg}")
            self._reset_voice_button(voice_id)

    def _on_process_output(self, voice_id):
        """Читает stdout дочернего процесса с буферизацией."""
        process = self.download_processes.get(voice_id)
        if not process:
            return

        # ЗАЩИТА: если объект уже удалён, но сигнал ещё в очереди
        try:
            data = bytes(process.readAllStandardOutput()).decode('utf-8', errors='replace')
        except RuntimeError:
            return  # Игнорируем запоздалый сигнал

        self._process_buffers[voice_id] += data

        buffer = self._process_buffers[voice_id]
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            line = line.strip()
            if line:
                self._process_json_line(voice_id, line)

        self._process_buffers[voice_id] = buffer

    def _on_process_error(self, voice_id):
        """Читает stderr дочернего процесса."""
        process = self.download_processes.get(voice_id)
        if not process:
            return

        try:
            data = bytes(process.readAllStandardError()).decode('utf-8', errors='replace')
            if data.strip():
                print(f"[PiperVoices] STDERR {voice_id}: {data.strip()}")
        except RuntimeError:
            pass

    def _process_json_line(self, voice_id, line):
        """Обрабатывает одну JSON-строку от процесса."""
        try:
            event = json.loads(line)
            event_type = event.get("type")

            if event_type == "progress":
                percent = event.get("percent", 0)

                # Троттлинг: воркер может слать события прогресса очень часто
                # (десятки раз в секунду). Каждое обновление QProgressBar —
                # это событие в очереди главного GUI-потока; при активной
                # закачке они могут забить очередь и задерживать/"съедать"
                # другие события интерфейса (например, клик по обложке книги
                # в библиотеке). Обновляем UI не чаще раза в ~120 мс, кроме
                # финальных значений (0% и 100%), которые пропускаем всегда.
                now = time.monotonic()
                last_time, last_percent = self._last_progress_update.get(voice_id, (0.0, -1))
                if percent not in (0, 100) and percent == last_percent:
                    return
                if percent not in (0, 100) and (now - last_time) < 0.12:
                    return
                self._last_progress_update[voice_id] = (now, percent)

                progress_bar = self._progress_bar_cache.get(voice_id)
                if not progress_bar:
                    progress_bar = self.findChild(QProgressBar, f"progress_{voice_id}")
                    if progress_bar:
                        self._progress_bar_cache[voice_id] = progress_bar
                if progress_bar:
                    progress_bar.setValue(percent)

            elif event_type == "status":
                message = event.get("message", "")
                print(f"[PiperVoices] {voice_id}: {message}")

            elif event_type == "error":
                message = event.get("message", "")
                print(f"[PiperVoices] Ошибка {voice_id}: {message}")

            elif event_type == "finished":
                success = event.get("success", False)
                if success:
                    self._download_retries.pop(voice_id, None)  # Сброс счётчика при успехе
                    # _load_voices() пересоздаёт все виджеты голосов —
                    # закэшированная ссылка на progress_bar станет невалидной.
                    self._progress_bar_cache.pop(voice_id, None)
                    self._last_progress_update.pop(voice_id, None)
                    self._load_voices()
                    self.voicesChanged.emit()
                else:
                    # Если процесс сам сообщил о неудаче
                    retry_count = self._download_retries.get(voice_id, 0)
                    self._handle_process_failure(voice_id, retry_count, "Процесс сообщил о неудаче")

        except json.JSONDecodeError:
            print(f"[PiperVoices] Некорректный JSON от процесса: {line}")

    def _on_process_finished(self, voice_id, exit_code, exit_status):
        """Дочерний процесс завершился."""
        # 1. Обрабатываем остаток буфера
        buffer = self._process_buffers.pop(voice_id, "")
        if buffer.strip():
            self._process_json_line(voice_id, buffer.strip())

        # 2. Извлекаем процесс из словаря
        process = self.download_processes.pop(voice_id, None)
        if process:
            # ВАЖНО: НЕ вызываем deleteLater()!
            # deleteLater() + queued-сигналы = гонка состояний и RuntimeError.
            # Простого удаления из словаря достаточно: GC Python
            # безопасно уничтожит объект, когда на него не останется ссылок.

            # На всякий случай отключаем сигналы
            try:
                process.readyReadStandardOutput.disconnect()
                process.readyReadStandardError.disconnect()
                process.finished.disconnect()
            except Exception:
                pass

        # 3. Проверяем код завершения
        if exit_code != 0:
            print(f"[PiperVoices] Процесс {voice_id} завершился с кодом ошибки {exit_code}")
            retry_count = self._download_retries.get(voice_id, 0)
            self._handle_process_failure(voice_id, retry_count, f"Код завершения {exit_code}")
        else:
            print(f"[PiperVoices] Процесс {voice_id} успешно завершён")

    def _reset_voice_button(self, voice_id):
        try:
            progress_bar = self.findChild(QProgressBar, f"progress_{voice_id}")
            if progress_bar:
                progress_bar.hide()
        except RuntimeError:
            pass

        try:
            btn = self.findChild(QPushButton, f"download_btn_{voice_id}")
            if btn:
                btn.setText(self._t('download'))
                btn.setEnabled(True)
        except RuntimeError:
            pass

        # Очищаем счётчик попыток при полном сбросе
        self._download_retries.pop(voice_id, None)
        self._progress_bar_cache.pop(voice_id, None)
        self._last_progress_update.pop(voice_id, None)

    def refresh_theme(self):
        self._colors = _palette()
        self._init_ui()
        # _init_ui() пересоздаёт все виджеты — старые ссылки на progress_bar
        # больше не действительны (даже если загрузка сейчас идёт).
        self._progress_bar_cache.clear()
        self._load_voices()

    def get_installed_voices(self):
        voices = []
        for voice_data in self.downloader.RUSSIAN_VOICES:
            voice_id = voice_data["name"]
            installed = self.downloader.check_voice_exists(voice_id)
            if installed:
                voices.append({
                    'id': voice_id,
                    'name': voice_data["display_name"],
                })
        return voices
