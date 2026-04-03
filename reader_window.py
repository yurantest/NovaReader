from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import QUrl, pyqtSlot, QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from PyQt6.QtWebChannel import QWebChannel
from pathlib import Path
import json
from tts.controller import TTSController
import base64
import uuid
from datetime import datetime
import sys


class ReaderBridge(QObject):
    ttsFinished = pyqtSignal()
    piperProgress = pyqtSignal(str, int)
    piperFinished = pyqtSignal(str, bool)
    piperError = pyqtSignal(str, str)

    def __init__(self, reader):
        super().__init__()
        self.reader = reader
        # Кешируем config — он никогда не меняется, но reader может стать None
        self._config = reader.config
        self.piperProgress.connect(self._on_piper_progress)
        self.piperFinished.connect(self._on_piper_finished)
        self.piperError.connect(self._on_piper_error)

    # ── Безопасные аксессоры ─────────────────────────────────────────────
    # closeEvent обнуляет self.reader чтобы оборвать все callbacks.
    # Любой JS-callback может прилететь чуть позже — guard это перехватывает.

    @property
    def _r(self):
        """Возвращает reader или None если окно уже закрывается."""
        return self.reader

    @property
    def _tts(self):
        """Возвращает tts_controller или None если окно уже закрывается."""
        r = self.reader
        return r.tts_controller if r is not None else None

    @property
    def _web(self):
        """Возвращает QWebEnginePage или None если окно уже закрывается."""
        r = self.reader
        if r is None:
            return None
        wv = getattr(r, 'web_view', None)
        return wv.page() if wv else None

    def _run_js(self, js: str):
        page = self._web
        if page:
            page.runJavaScript(js)

    def _on_piper_progress(self, vid, pct):
        self._run_js(f"window.onPiperVoiceProgress&&window.onPiperVoiceProgress({json.dumps(vid)},{pct})")

    def _on_piper_finished(self, vid, ok):
        self._run_js(f"window.onPiperVoiceFinished&&window.onPiperVoiceFinished({json.dumps(vid)},{str(ok).lower()})")

    def _on_piper_error(self, vid, err):
        self._run_js(f"window.onPiperVoiceError&&window.onPiperVoiceError({json.dumps(vid)},{json.dumps(err)})")

    @pyqtSlot(str)
    def log(self, message):
        print(f"[JS] {message}")

    @pyqtSlot(int)
    def onSectionChanged(self, index):
        print(f"[Reader] Секция: {index}")

    @pyqtSlot(result=str)
    def getBookData(self):
        if not (self._r and self._r.current_book):
            return json.dumps({'type': 'unknown', 'name': '', 'file_url': '', 'path': ''})
        try:
            book_path = Path(self._r.current_book)
            ext = book_path.suffix.lower()
            book_type = ('epub' if ext == '.epub' else
                         'fb2'  if ext == '.fb2'  else
                         'cbz'  if ext == '.cbz'  else
                         'pdf'  if ext == '.pdf'  else
                         'mobi' if ext == '.mobi' else 'unknown')

            # Передаём file:// URL — JS загружает книгу напрямую через fetch().
            # Это работает благодаря флагам --disable-web-security и
            # --allow-file-access-from-files в Chromium.
            # Выигрыш по памяти для 15 МБ FB2:
            #   base64-путь: ~20 МБ Python + ~20 МБ JS + ~15 МБ Uint8Array = ~55 МБ пиковых
            #   file://-путь: ~15 МБ ArrayBuffer = ~15 МБ пиковых
            file_url = book_path.as_uri()  # → file:///path/to/book.fb2 (кроссплатформенно)
            mb = book_path.stat().st_size / 1024 / 1024
            print(f"[Bridge] {book_type.upper()} {mb:.1f} МБ → file://, передаём URL в JS")

            return json.dumps({
                'type':     book_type,
                'name':     book_path.name,
                'file_url': file_url,
                'path':     str(book_path),
            })
        except Exception as e:
            print(f"[Bridge] getBookData error: {e}")
            return json.dumps({'type': 'unknown', 'name': '', 'file_url': '', 'path': ''})

    @pyqtSlot(result=str)
    def getTheme(self):
        return json.dumps({
            'bg': self._config.get('theme_bg', '#f4ecd8'),
            'text': self._config.get('theme_text', '#5b4636')
        })

    @pyqtSlot(result=str)
    def getAvailableEngines(self):
        tts = self._tts
        if not tts:
            return json.dumps([])
        return json.dumps(tts.get_available_engines())

    @pyqtSlot(str, result=str)
    def getEngineVoices(self, engine_name):
        tts = self._tts
        if not tts:
            return json.dumps([])
        return json.dumps(tts.get_engine_voices(engine_name))

    @pyqtSlot(str)
    def setPreferredEngine(self, engine_name):
        tts = self._tts
        if tts:
            tts.set_preferred_engine(engine_name)

    @pyqtSlot(str)
    def setVoice(self, voice_id):
        tts = self._tts
        if tts:
            tts.set_voice(voice_id)

    @pyqtSlot(float)
    def setRate(self, rate):
        tts = self._tts
        if tts:
            tts.set_rate(rate)

    @pyqtSlot(str)
    def onTTSText(self, text):
        tts = self._tts
        if tts and text:
            print(f"[Reader] onTTSText: {text[:50]}...")
            tts.speak(text, self._on_tts_finished)
        else:
            print(f"[Reader] onTTSText: окно закрывается, игнорируем")

    def _on_tts_finished(self):
        if self.reader is not None:   # окно ещё живо
            self.ttsFinished.emit()

    @pyqtSlot()
    def stopTTS(self):
        tts = self._tts
        if tts:
            tts.stop()

    @pyqtSlot()
    def pauseTTS(self):
        tts = self._tts
        if tts:
            tts.pause()

    @pyqtSlot()
    def resumeTTS(self):
        tts = self._tts
        if tts:
            tts.resume()

    @pyqtSlot(str)
    def copyToClipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        print(f"[Reader] Текст скопирован в буфер: {text[:50]}...")

    @pyqtSlot()
    def showLibrary(self):
        if self._r: self._r.show_library()

    @pyqtSlot()
    def showSettings(self):
        from settings_window import SettingsWindow
        self.settings_window = SettingsWindow(self._config, self.reader)
        self.settings_window.show()

    @pyqtSlot()
    def showTTSCorrection(self):
        from tts_correction_window import TTSCorrectionWindow
        self.correction_window = TTSCorrectionWindow(self._config, self.reader)
        self.correction_window.show()

    @pyqtSlot(str, float)
    def savePosition(self, position_json, progress):
        if not (self._r and self._r.current_book):
            return
        try:
            position = json.loads(position_json)
        except:
            position = {'section': 0}
        self._config.update_progress(self._r.current_book, progress, position)
        print(f"[Reader] Позиция сохранена: секция={position.get('section')}, прогресс={progress:.1%}")

    @pyqtSlot(result=str)
    def getPosition(self):
        if not (self._r and self._r.current_book):
            return json.dumps(None)
        bookmark = self._config.get_bookmark(self._r.current_book)
        if bookmark and bookmark.get('position'):
            return json.dumps(bookmark)
        return json.dumps(None)

    @pyqtSlot(str, float, str)
    def saveBookmark(self, label, progress, position_json):
        if not (self._r and self._r.current_book):
            return
        try:
            position = json.loads(position_json)
        except:
            position = {}
        bookmark = {
            'id': str(uuid.uuid4()),
            'label': label,
            'progress': progress,
            'position': position,
            'timestamp': datetime.now().isoformat()
        }
        self._config.add_bookmark(self._r.current_book, bookmark)
        print(f"[Reader] Закладка добавлена: {label}")

    @pyqtSlot(result=str)
    def getBookmarks(self):
        if not (self._r and self._r.current_book):
            return json.dumps([])
        bookmarks = self._config.get_bookmarks(self._r.current_book)
        return json.dumps(bookmarks)

    @pyqtSlot(str)
    def removeBookmark(self, bookmark_id):
        if self._r and self._r.current_book:
            self._config.remove_bookmark(self._r.current_book, bookmark_id)
            print(f"[Reader] Закладка удалена: {bookmark_id}")

    @pyqtSlot(result=str)
    def getVoicesDir(self):
        return str(self._config.voices_dir)

    @pyqtSlot(result=str)
    def getSettings(self):
        tts_color = self._config.get('tts_highlight_color', 'cyan')
        highlight_style = self._config.get('default_highlight_style', 'highlight')
        settings = {
            'theme_bg': self._config.get('theme_bg', '#f4ecd8'),
            'theme_text': self._config.get('theme_text', '#5b4636'),
            'font_size': self._config.get('font_size', 16),
            'line_height': self._config.get('line_height', 1.5),
            'spread_mode': self._config.get('spread_mode', 'auto'),
            'page_margin': self._config.get('page_margin', 44),
            'default_highlight_style': highlight_style,
            'default_highlight_color': self._config.get('default_highlight_color', 'blue'),
            'tts_speed': self._config.get('tts_rate', 1.0),
            'tts_engine': self._config.get('preferred_engine', 'Piper'),
            'tts_voice': self._config.get(
                'piper_voice' if self._config.get('preferred_engine', 'Piper') == 'Piper'
                else 'edge_tts_voice',
                'ru_RU_irina_medium'
            ),
            'tts_highlight_color': tts_color,
        }
        result = json.dumps(settings)
        print(f"[Reader] Настройки отправлены в JS: стиль={highlight_style}, TTS цвет={tts_color}")
        return result

    @pyqtSlot(str)
    def saveSetting(self, key_value_json):
        try:
            data = json.loads(key_value_json)
            key = data.get('key')
            value = data.get('value')
            if key:
                self._config.set(key, value)
                print(f"[Reader] Настройка сохранена: {key}={value}")
        except Exception as e:
            print(f"[Reader] Ошибка сохранения настройки: {e}")

    @pyqtSlot(result=str)
    def getTTSCorrections(self):
        """Получить список коррекций TTS"""
        corrections = self._config.get('tts_corrections', [])
        return json.dumps(corrections)

    @pyqtSlot(str)
    def saveTTSCorrections(self, corrections_json):
        """Сохранить список коррекций TTS"""
        try:
            corrections = json.loads(corrections_json)
            self._config.set('tts_corrections', corrections)
            print(f"[Reader] Коррекции TTS сохранены: {len(corrections)} пар")
        except Exception as e:
            print(f"[Reader] Ошибка сохранения коррекций: {e}")

    @pyqtSlot(str, str, str, str)
    def saveHighlight(self, text, color, style, cfi):
        try:
            cfi_data = json.loads(cfi) if cfi else {}
            highlight_id = cfi_data.get('id') or str(uuid.uuid4())
            highlight = {
                'id': highlight_id,
                'text': text,
                'color': color,
                'style': style,
                'cfi': cfi,
                'timestamp': datetime.now().isoformat()
            }
            self._config.add_highlight(self._r.current_book, highlight)
            print(f"[Reader] Подсветка сохранена: {highlight['id']}")
        except Exception as e:
            print(f"[Reader] Ошибка сохранения подсветки: {e}")

    @pyqtSlot(result=str)
    def getHighlights(self):
        if not (self._r and self._r.current_book):
            return json.dumps([])
        highlights = self._config.get_highlights(self._r.current_book)
        return json.dumps(highlights)

    @pyqtSlot(str)
    def removeHighlight(self, highlight_id):
        self._config.remove_highlight(self._r.current_book, highlight_id)
        print(f"[Reader] Подсветка удалена: {highlight_id}")

    @pyqtSlot(str)
    def saveQuoteImage(self, base64_data):
        try:
            library_path = Path(self._config.library_path)
            quotes_dir = library_path / 'Quotes'
            quotes_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f'quote_{timestamp}.png'
            filepath = quotes_dir / filename
            image_data = base64.b64decode(base64_data)
            with open(filepath, 'wb') as f:
                f.write(image_data)
            print(f"[Reader] Цитата сохранена: {filepath}")
        except Exception as e:
            print(f"[Reader] Ошибка сохранения цитаты: {e}")
            import traceback
            traceback.print_exc()

    @pyqtSlot(result=str)
    def getPiperVoices(self):
        from piper_voice_downloader import PiperVoiceDownloader
        voices_dir = self._config.voices_dir
        downloader = PiperVoiceDownloader(voices_dir)
        result = []
        for voice_data in downloader.RUSSIAN_VOICES:
            voice_id = voice_data["name"]
            installed = downloader.check_voice_exists(voice_id)
            result.append({
                'id': voice_id,
                'name': voice_data["display_name"],
                'quality': voice_data["quality"],
                'size_mb': 83,
                'installed': installed,
            })
        n_inst = sum(1 for r in result if r['installed'])
        print(f"[Bridge] getPiperVoices: {n_inst}/{len(result)} загружено")
        return json.dumps(result)

    @pyqtSlot(str, result=bool)
    def checkVoiceAvailability(self, voice_id):
        from piper_voice_downloader import PiperVoiceDownloader
        voices_dir = self._config.voices_dir
        downloader = PiperVoiceDownloader(voices_dir)
        return downloader.check_voice_exists(voice_id)

    @pyqtSlot(str)
    def downloadVoice(self, voice_id):
        from piper_voice_downloader import PiperVoiceDownloader, DownloadWorker, PiperVoiceInfo
        voices_dir = self._config.voices_dir
        downloader = PiperVoiceDownloader(voices_dir)
        voice_info = None
        for v in downloader.RUSSIAN_VOICES:
            if v["name"] == voice_id:
                voice_info = PiperVoiceInfo(name=v["name"], quality=v["quality"], onnx_url=v["onnx"], json_url=v["json"])
                break
        if not voice_info:
            print(f"[Bridge] downloadVoice: '{voice_id}' не найден")
            self.piperError.emit(voice_id, f'Голос не найден: {voice_id}')
            return
        print(f"[Bridge] Начало загрузки: {voice_id}")

        def on_progress(downloaded, total):
            pct = int(downloaded * 100 / total) if total > 0 else 0
            self.piperProgress.emit(voice_id, pct)

        worker = DownloadWorker(downloader, voice_info, on_progress)
        worker.finished.connect(lambda ok: self._on_voice_download_finished(voice_id, ok))
        worker.error.connect(lambda err: self._on_voice_download_error(voice_id, err))
        worker.start()

    def _on_voice_download_finished(self, voice_id, ok):
        self.piperFinished.emit(voice_id, ok)

    def _on_voice_download_error(self, voice_id, error):
        self.piperError.emit(voice_id, str(error))

    @pyqtSlot(result=str)
    def getSystemEngines(self):
        if not self._tts:
            return json.dumps([])
        result = []
        for client in self._tts.clients:
            name = client.name
            if name in ('Edge', 'Piper', 'eSpeak'):
                continue
            voices = client.get_voices()
            if not voices:
                continue
            result.append({
                'key': name,
                'label': self._engine_label(name),
                'voices': [{'id': v.get('id', ''), 'name': v.get('name', '')} for v in voices],
            })
        return json.dumps(result)

    @staticmethod
    def _engine_label(key: str) -> str:
        LABELS = {
            'SAPI5': 'SAPI5 (Windows)',
            'RHVoice': 'RHVoice',
            'rhvoice': 'RHVoice',
            'espeak_ng': 'eSpeak NG',
            'espeak': 'eSpeak',
            'festival': 'Festival',
            'flite': 'Flite',
            'SpeechD': 'speech-dispatcher',
        }
        return LABELS.get(key, key)


class ReaderWindow(QMainWindow):
    def __init__(self, config, tts_controller=None, parent=None, app_instance=None):
        super().__init__(parent)
        self.config = config
        self.app_instance = app_instance
        self.current_book = None
        self.page_loaded = False
        self._tts_data_pushed = False
        self.settings_window = None
        self._closing = False  # защита от повторного closeEvent

        # Каждое окно читалки владеет собственным TTSController.
        # Это позволяет открывать несколько книг одновременно без конфликтов.
        if tts_controller is not None:
            # Обратная совместимость: если передан извне — используем его,
            # но при закрытии НЕ вызываем shutdown() (не наш)
            self.tts_controller = tts_controller
            self._owns_tts = False
        else:
            self.tts_controller = TTSController(config)
            self._owns_tts = True

        self.showMaximized()
        self._setup_ui()
        self._setup_webchannel()
        self._setup_shortcuts()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        settings = self.web_view.settings()
        # Включаем только необходимое
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        # Отключаем лишнее для экономии памяти
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)   # нужен для TTS-настроек (localStorage)
        settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False)

        # Профиль WebEngine настраивается централизованно в main.py
        # (до создания любого QWebEngineView) — здесь только добираем view.
        profile = self.web_view.page().profile()
        # Двойная страховка: если окно создано в обход main.py (тесты и т.п.)
        try:
            from PyQt6.QtWebEngineCore import QWebEngineProfile as _P
            profile.setHttpCacheMaximumSize(0)
            profile.setHttpCacheType(_P.HttpCacheType.NoCache)
        except Exception:
            pass

        layout.addWidget(self.web_view)

        # Путь к reader.html: в скомпилированном приложении (PyInstaller)
        # __file__ указывает на директорию извлечённых файлов.
        # В режиме --onefile эта директория меняется при каждом запуске →
        # нужно использовать sys._MEIPASS (стабильный путь при --onedir,
        # или правильный временный при --onefile).
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent
        html_path = base / 'web' / 'reader.html'
        if html_path.exists():
            print(f"[Reader] ✅ HTML: {html_path}")
            self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        else:
            print(f"[Reader] ❌ reader.html не найден: {html_path}")

    def _setup_webchannel(self):
        self.bridge = ReaderBridge(self)
        self.bridge.ttsFinished.connect(self._on_tts_finished)
        self.channel = QWebChannel()
        self.channel.registerObject('readerBridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.web_view.loadFinished.connect(self._on_page_loaded)

    def _on_tts_finished(self):
        print("[Reader] TTS finished → вызываем window.ttsNext()")
        self.web_view.page().runJavaScript("window.ttsNext && window.ttsNext();")

    def _on_page_loaded(self, ok):
        if ok:
            self.page_loaded = True
            if self.current_book:
                QTimer.singleShot(500, self._load_book)
            if not self._tts_data_pushed:
                self._tts_data_pushed = True
                QTimer.singleShot(1500, self._push_tts_data)

    def _push_tts_data(self):
        import json as _json
        try:
            from piper_voice_downloader import PiperVoiceDownloader
            voices_dir = self.config.voices_dir
            downloader = PiperVoiceDownloader(voices_dir)
            piper_voices = []
            for voice_data in downloader.RUSSIAN_VOICES:
                voice_id = voice_data["name"]
                installed = downloader.check_voice_exists(voice_id)
                piper_voices.append({'id': voice_id, 'name': voice_data["display_name"], 'installed': installed, 'size_mb': 83})
            print(f"[Push] Piper: {sum(1 for v in piper_voices if v['installed'])}/{len(piper_voices)} загружено")
            self.web_view.page().runJavaScript(f"window._pushPiperVoices && window._pushPiperVoices({_json.dumps(piper_voices)});")

            sys_engines = []
            if self.tts_controller:
                for client in self.tts_controller.clients:
                    name = client.name
                    if name in ('Edge', 'Piper', 'eSpeak'):
                        continue
                    voices = client.get_voices()
                    if not voices:
                        continue
                    sys_engines.append({'key': name, 'label': self._engine_label(name), 'voices': [{'id': v.get('id',''), 'name': v.get('name','')} for v in voices]})
            print(f"[Push] Системные движки: {[e['key'] for e in sys_engines]}")
            self.web_view.page().runJavaScript(f"window._pushSystemEngines && window._pushSystemEngines({_json.dumps(sys_engines)});")
        except Exception as e:
            import traceback
            print(f"[Push] Ошибка: {e}")
            traceback.print_exc()

    @staticmethod
    def _engine_label(key: str) -> str:
        LABELS = {'SAPI5': 'SAPI5 (Windows)', 'RHVoice': 'RHVoice', 'rhvoice': 'RHVoice', 'espeak_ng': 'eSpeak NG', 'espeak': 'eSpeak', 'festival': 'Festival', 'flite': 'Flite', 'SpeechD': 'speech-dispatcher'}
        return LABELS.get(key, key)

    def _load_book(self):
        js = """
        if (window.bridge && window.loadBook) {
            window.bridge.getBookData(function(data) {
                if (data) window.loadBook(JSON.parse(data));
            });
        }
        """
        self.web_view.page().runJavaScript(js)

    def load_book(self, book_path):
        self.current_book = book_path
        self.setWindowTitle("NovaReader")
        self._tts_data_pushed = False
        if self.page_loaded:
            self._load_book()
        else:
            self.web_view.reload()

    def show_library(self):
        if self.app_instance and hasattr(self.app_instance, 'library_window'):
            self.hide()
            self.app_instance.library_window.show()
            self.app_instance.library_window.raise_()
            self.app_instance.library_window.activateWindow()
            return
        parent = self.parent()
        while parent and not hasattr(parent, 'library_window'):
            parent = parent.parent()
        if parent and hasattr(parent, 'library_window'):
            self.hide()
            parent.library_window.show()
            parent.library_window.raise_()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence('F'), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._on_escape)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self._toggle_tts_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self._page_nav('next'))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self._page_nav('prev'))
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, activated=lambda: self._page_nav('next'))
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, activated=lambda: self._page_nav('prev'))

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _on_escape(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            if self.tts_controller and self.tts_controller.state in ('playing', 'paused'):
                self.tts_controller.stop()
                self.web_view.page().runJavaScript("window.stopTTSFull && window.stopTTSFull();")

    def _toggle_tts_pause(self):
        if not self.tts_controller:
            return
        state = self.tts_controller.state
        if state == 'playing':
            self.tts_controller.pause()
            self.web_view.page().runJavaScript("window.pauseTTS && window.pauseTTS();")
        elif state == 'paused':
            self.tts_controller.resume()
            self.web_view.page().runJavaScript("window.resumeTTS && window.resumeTTS();")

    def _page_nav(self, direction: str):
        if direction == 'next':
            self.web_view.page().runJavaScript("view && view.renderer && view.renderer.next();")
        else:
            self.web_view.page().runJavaScript("view && view.renderer && view.renderer.prev();")

    def _clear_fb2_cache(self):
        """
        Страховка: очищает IndexedDB-базы с именем, содержащим 'folio' или 'fb2'.
        foliate-js в текущей версии IndexedDB не использует (кэши — JS Map в памяти),
        но на случай если в будущей версии появится персистентный кэш — этот метод
        не даст ему накапливаться между сессиями.
        Безопасно: не трогает настройки TTS (STORAGE_KEY / tts_settings в localStorage).
        """
        js = """
        (function() {
            if (!window.indexedDB || !window.indexedDB.databases) return;
            window.indexedDB.databases().then(function(dbs) {
                dbs.forEach(function(db) {
                    var n = (db.name || '').toLowerCase();
                    if (n.includes('folio') || n.includes('fb2') || n.includes('fictionbook')) {
                        window.indexedDB.deleteDatabase(db.name);
                    }
                });
            }).catch(function(){});
        })();
        """
        try:
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    def closeEvent(self, event):
        if self._closing:
            event.accept()
            return
        self._closing = True

        # Страховочная очистка IndexedDB-кэша FB2 перед закрытием
        try:
            if self.current_book and str(self.current_book).lower().endswith('.fb2'):
                self._clear_fb2_cache()
        except Exception:
            pass

        # Останавливаем TTS только если именно это окно что-то воспроизводило.
        # tts_controller.stop() трогает глобальный AudioPlayer — если вызвать его
        # из окна где TTS не играл, это оборвёт воспроизведение в другом окне.
        if self.tts_controller:
            was_active = self.tts_controller.state in ('playing', 'paused')
            if was_active:
                try:
                    self.web_view.page().runJavaScript("window.stopTTSFull && window.stopTTSFull();")
                except Exception:
                    pass
                try:
                    self.tts_controller.stop()
                except Exception:
                    pass
            else:
                # TTS не играл — только сбрасываем состояние клиентов,
                # не трогая глобальный AudioPlayer
                try:
                    self.tts_controller.state = 'stopped'
                    if self.tts_controller.active_client:
                        self.tts_controller.active_client._stop_flag = True
                except Exception:
                    pass
            # Полный шатдаун (включая release_audio_player) только если это
            # последнее открытое окно читалки. Иначе глобальный AudioPlayer
            # убьёт воспроизведение в других окнах.
            if self._owns_tts:
                other_windows = []
                if self.app_instance and hasattr(self.app_instance, 'reader_windows'):
                    other_windows = [w for w in self.app_instance.reader_windows
                                     if w is not self and not getattr(w, '_closing', False)]
                if other_windows:
                    # Другие окна живы — только останавливаем, не трогаем синглтон
                    print(f"[Reader] closeEvent: есть {len(other_windows)} других окон, "
                          f"shutdown() пропущен")
                else:
                    # Последнее окно — полный шатдаун
                    try:
                        self.tts_controller.shutdown()
                    except Exception:
                        pass
            # Отключаем bridge от контроллера — callback'и больше не должны стрелять
            self.tts_controller = None

        # Отключаем bridge от окна чтобы никакие JS-callback'и не дошли
        # после того как окно начнёт разрушаться
        try:
            self.bridge.reader = None
        except Exception:
            pass

        event.accept()
