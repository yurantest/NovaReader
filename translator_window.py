# -*- coding: utf-8 -*-
"""
Отдельное окно переводчика — открывается по кнопке словаря в читалке.

Оформлено в общем стиле приложения (см. _build_style() в
tts_correction_window.py — тот же, что использует AudioRecorderWindow).

Перевод — цепочка провайдеров, каждый следующий пробуется, если
предыдущий недоступен/лимитирован:
  1. Google (неофициальный анонимный эндпоинт translate.googleapis.com,
     без ключа) — иногда отвечает 429 Too Many Requests при частых
     запросах с одного IP, поэтому есть ретрай с паузой и переход
     на следующего провайдера.
  2. MyMemory (mymemory.translated.net) — тоже бесплатный, без
     регистрации, официально документированный анонимный лимит.
  3. Yandex Cloud Translate — ТОЛЬКО если пользователь сам вписал свой
     API-ключ и folder_id в настройки (yandex_translate_api_key /
     yandex_translate_folder_id). Бесплатный публичный API Яндекса без
     регистрации был закрыт в 2018 году — сейчас это платный сервис
     Yandex Cloud, ключ выдаётся только через личный кабинет пользователя.

Выполняется в фоновом потоке (QThread), не блокируя UI. Это отдельное
окно уровня приложения (как AudioRecorderWindow/BookSearchWindow), а не
встроенный в WebEngine попап — сеть тут уместна и не противоречит
офлайн-модели самого рендера книги: сетевой доступ есть только у явно
вызванных пользователем окон приложения (поиск книг, скачивание голосов
Piper и вот теперь перевод), но никогда — у процесса, который рендерит
содержимое самой книги.

Дополнительно показывает морфологический разбор слова (pymorphy3,
translator_engine.py) — полностью офлайн, мгновенно, без сети.
"""
from __future__ import annotations

import time
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QComboBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette

from tts_correction_window import _build_style, _sys, _blend
import translator_engine


_TW_S = {
    'ru': {
        'title': 'Переводчик',
        'source_label': 'Исходный текст',
        'target_label': 'Перевести на:',
        'translate_btn': 'Перевести',
        'translating': 'Перевожу…',
        'result_label': 'Перевод',
        'morphology_label': 'Разбор слова',
        'close': 'Закрыть',
        'provider_label': 'Источник: {provider}',
        'err_network': 'Не удалось связаться ни с одним сервисом перевода.\nПоследняя ошибка: {error}',
        'err_empty': 'Введите текст для перевода',
        'alt_forms': 'Другие варианты: {alts}',
    },
    'en': {
        'title': 'Translator',
        'source_label': 'Source text',
        'target_label': 'Translate to:',
        'translate_btn': 'Translate',
        'translating': 'Translating…',
        'result_label': 'Translation',
        'morphology_label': 'Word analysis',
        'close': 'Close',
        'provider_label': 'Source: {provider}',
        'err_network': 'Could not reach any translation service.\nLast error: {error}',
        'err_empty': 'Enter text to translate',
        'alt_forms': 'Other forms: {alts}',
    },
}

_LANGUAGES = [
    ('en', 'English'), ('ru', 'Русский'), ('de', 'Deutsch'), ('fr', 'Français'),
    ('es', 'Español'), ('it', 'Italiano'), ('pt', 'Português'), ('pl', 'Polski'),
    ('uk', 'Українська'), ('tr', 'Türkçe'), ('zh-CN', '中文'), ('ja', '日本語'),
    ('ko', '한국어'), ('ar', 'العربية'),
]


def _translate_via_google(text: str, source: str, target: str) -> str:
    """Неофициальный анонимный эндпоинт (используется многими опенсорсными
    библиотеками вроде googletrans). Без ключа, но без гарантий — может
    отвечать 429 при частых запросах с одного IP. Один ретрай с паузой
    перед тем, как отдать эстафету следующему провайдеру."""
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.get(
                'https://translate.googleapis.com/translate_a/single',
                params={'client': 'gtx', 'sl': source, 'tl': target, 'dt': 't', 'q': text},
                timeout=10,
            )
            if resp.status_code == 429:
                last_error = '429 Too Many Requests'
                time.sleep(1.5)
                continue
            resp.raise_for_status()
            data = resp.json()
            return ''.join(chunk[0] for chunk in data[0] if chunk[0])
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(f'Google: {last_error}')


def _translate_via_mymemory(text: str, source: str, target: str) -> str:
    """MyMemory — бесплатный документированный API, анонимный лимит
    ~5000 символов/день без ключа. https://mymemory.translated.net/doc/spec.php
    ВАЖНО: в отличие от Google, 'auto' здесь НЕ поддерживается как исходный
    язык — API возвращает явную ошибку ("'AUTO' IS AN INVALID SOURCE
    LANGUAGE"), нужен конкретный код (ru, en, ...)."""
    try:
        resp = requests.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text, 'langpair': f'{source}|{target}'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        translated = data.get('responseData', {}).get('translatedText')
        status = data.get('responseStatus')
        if status and str(status) != '200':
            raise RuntimeError(str(data.get('responseDetails', status)))
        if not translated:
            raise RuntimeError('пустой ответ')
        return translated
    except Exception as e:
        raise RuntimeError(f'MyMemory: {e}')


def _translate_via_yandex(text: str, source: str, target: str, api_key: str, folder_id: str) -> str:
    """Yandex Cloud Translate — официальный API, но требует СВОЙ платный
    ключ и folder_id (бесплатный публичный API Яндекса закрыт в 2018).
    Настраивается пользователем отдельно, не работает "из коробки"."""
    try:
        resp = requests.post(
            'https://translate.api.cloud.yandex.net/translate/v2/translate',
            headers={'Authorization': f'Api-Key {api_key}'},
            json={'sourceLanguageCode': source, 'targetLanguageCode': target,
                  'texts': [text], 'folderId': folder_id},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['translations'][0]['text']
    except Exception as e:
        raise RuntimeError(f'Yandex: {e}')


class _TranslateWorker(QThread):
    finished_ok = pyqtSignal(str, str)   # (перевод, имя провайдера)
    finished_err = pyqtSignal(str)

    def __init__(self, text: str, source_lang: str, target_lang: str,
                 yandex_key: str = '', yandex_folder: str = ''):
        super().__init__()
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.yandex_key = yandex_key
        self.yandex_folder = yandex_folder

    def run(self):
        errors = []
        for name, fn in self._providers():
            try:
                result = fn()
                self.finished_ok.emit(result, name)
                return
            except Exception as e:
                errors.append(str(e))
        self.finished_err.emit('; '.join(errors))

    def _providers(self):
        # Google поддерживает реальный автодетект языка ('auto') — там он
        # и остаётся, это даёт более точный результат, чем жёстко
        # зашитый источник. MyMemory/Yandex 'auto' не поддерживают вовсе
        # (MyMemory прямо возвращает ошибку) — для них используем явный
        # код языка интерфейса как лучшее доступное приближение.
        providers = [
            ('Google', lambda: _translate_via_google(self.text, 'auto', self.target_lang)),
            ('MyMemory', lambda: _translate_via_mymemory(self.text, self.source_lang, self.target_lang)),
        ]
        if self.yandex_key and self.yandex_folder:
            providers.append((
                'Yandex',
                lambda: _translate_via_yandex(self.text, self.source_lang, self.target_lang,
                                               self.yandex_key, self.yandex_folder),
            ))
        return providers


class TranslatorWindow(QDialog):
    """Полностью независимое окно (без родителя — иначе оконный менеджер
    группирует его с окном читалки на панели задач, см. AudioRecorderWindow
    для того же самого паттерна)."""

    def __init__(self, config, initial_text: str = ''):
        super().__init__(None)
        self.config = config
        self._worker = None

        lang = config.get('language', 'ru')
        self._s = _TW_S.get(lang, _TW_S['ru'])

        self.setWindowTitle(self._t('title'))
        self.setMinimumWidth(480)
        self.setMinimumHeight(460)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )

        bg, style = _build_style()
        self.setStyleSheet(style + self._extra_style())

        self._build_ui()
        if initial_text:
            self.source_edit.setPlainText(initial_text)
            self._update_morphology(initial_text)

    def _t(self, key, **kwargs):
        text = self._s.get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _extra_style(self):
        accent = _sys(QPalette.ColorRole.Highlight)
        border = _sys(QPalette.ColorRole.Mid)
        surface = _sys(QPalette.ColorRole.Base)
        text = _sys(QPalette.ColorRole.WindowText)
        return f"""
        QComboBox {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 10px;
            color: {text};
            font-size: 13px;
        }}
        QComboBox:hover {{ border-color: {accent}; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background: {surface};
            color: {text};
            selection-background-color: {accent};
            border: 1px solid {border};
            outline: none;
        }}
        QTextEdit {{
            background: {surface};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 8px 10px;
            color: {text};
            font-size: 13px;
        }}
        QTextEdit:focus {{ border-color: {accent}; }}
        """

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        layout.addWidget(self._label(self._t('source_label'), bold=True))
        self.source_edit = QTextEdit()
        self.source_edit.setMaximumHeight(90)
        self.source_edit.textChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_edit)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(self._t('target_label')))
        self.target_combo = QComboBox()
        for code, name in _LANGUAGES:
            self.target_combo.addItem(name, code)
        last_target = self.config.get('translation_target_lang', 'en')
        idx = self.target_combo.findData(last_target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        target_row.addWidget(self.target_combo, stretch=1)
        layout.addLayout(target_row)

        self.translate_btn = QPushButton(self._t('translate_btn'))
        self.translate_btn.setDefault(True)
        self.translate_btn.clicked.connect(self._on_translate_clicked)
        layout.addWidget(self.translate_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        border = _sys(QPalette.ColorRole.Mid)
        sep.setStyleSheet(f"background: {border}; max-height: 1px; border: none;")
        layout.addWidget(sep)

        # Морфологический разбор — офлайн, показывается сразу, без клика.
        # Для одного слова — подробный разбор с альтернативами. Для
        # фразы/предложения — разбор КАЖДОГО слова по отдельности (без
        # учёта контекста — омонимы вроде "мыла" могут разобраться не
        # в том смысле, который имелся в виду в предложении, это
        # ограничение pymorphy3, а не баг).
        self.morphology_box = QFrame()
        morphology_layout = QVBoxLayout(self.morphology_box)
        morphology_layout.setContentsMargins(0, 0, 0, 0)
        morphology_layout.setSpacing(4)
        morphology_layout.addWidget(self._label(self._t('morphology_label'), bold=True))
        self.morphology_view = QTextEdit('')
        self.morphology_view.setReadOnly(True)
        self.morphology_view.setMaximumHeight(130)
        sub = _blend(_sys(QPalette.ColorRole.WindowText), _sys(QPalette.ColorRole.Window), 0.45)
        self.morphology_view.setStyleSheet(f"color: {sub}; font-size: 12px;")
        morphology_layout.addWidget(self.morphology_view)
        self.morphology_box.setVisible(False)
        layout.addWidget(self.morphology_box)

        self.result_label_widget = self._label(self._t('result_label'), bold=True)
        layout.addWidget(self.result_label_widget)
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        layout.addWidget(self.result_edit, stretch=1)

        self.provider_label = QLabel('')
        self.provider_label.setStyleSheet(f"color: {sub}; font-size: 11px;")
        layout.addWidget(self.provider_label)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton(self._t('close'))
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _label(self, text, bold=False):
        lbl = QLabel(text)
        if bold:
            lbl.setStyleSheet("font-size: 12px; font-weight: 600; opacity: 0.85;")
        else:
            lbl.setStyleSheet("font-size: 12px; opacity: 0.7;")
        return lbl

    def _on_source_changed(self):
        self._update_morphology(self.source_edit.toPlainText())

    def _update_morphology(self, text: str):
        """Офлайн-разбор через pymorphy3 — мгновенно, без сети, показывается
        независимо от того, нажали ли "Перевести". Для одного слова —
        подробный разбор с альтернативами. Для фразы/предложения — разбор
        каждого слова по отдельности (без учёта контекста, см. комментарий
        у analyze_sentence() в translator_engine.py)."""
        text = (text or '').strip()
        lang = self.config.get('language', 'ru')
        if lang != 'ru' or not text:
            self.morphology_box.setVisible(False)
            self.morphology_view.setPlainText('')
            return

        analyzer = translator_engine.get_word_analyzer()
        if not analyzer.available:
            self.morphology_box.setVisible(False)
            self.morphology_view.setPlainText('')
            return

        if translator_engine.is_single_word(text):
            parsed = analyzer.analyze(text)
            if not parsed:
                self.morphology_box.setVisible(False)
                self.morphology_view.setPlainText('')
                return
            self.morphology_box.setVisible(True)
            desc = parsed['description']
            if parsed['normal_form'] != text:
                desc += f" — начальная форма: {parsed['normal_form']}"
            if parsed['alternatives']:
                alts = ', '.join(f"{a['pos']}: {a['normal_form']}" for a in parsed['alternatives'])
                desc += '\n' + self._t('alt_forms', alts=alts)
            self.morphology_view.setPlainText(desc)
            return

        # Несколько слов — разбираем каждое по отдельности
        results = analyzer.analyze_sentence(text)
        if not results:
            self.morphology_box.setVisible(False)
            self.morphology_view.setPlainText('')
            return

        self.morphology_box.setVisible(True)
        lines = []
        for r in results:
            line = f"{r['word']}: {r['description']}"
            if r['normal_form'] != r['word']:
                line += f" ({r['normal_form']})"
            lines.append(line)
        self.morphology_view.setPlainText('\n'.join(lines))

    def _on_translate_clicked(self):
        text = self.source_edit.toPlainText().strip()
        if not text:
            self.result_edit.setPlainText(self._t('err_empty'))
            self.provider_label.setText('')
            return

        target_code = self.target_combo.currentData()
        self.config.set('translation_target_lang', target_code)

        self.translate_btn.setEnabled(False)
        self.result_edit.setPlainText(self._t('translating'))
        self.provider_label.setText('')

        yandex_key = self.config.get('yandex_translate_api_key', '')
        yandex_folder = self.config.get('yandex_translate_folder_id', '')

        # Явный исходный язык для MyMemory/Yandex (Google справляется и с
        # 'auto', см. _providers). Берём язык интерфейса как лучшее
        # доступное приближение; если он совпадает с целевым (например,
        # интерфейс на русском и пользователь тоже выбрал перевод на
        # русский — вставил английский текст) — откатываемся на 'en' как
        # наиболее вероятный источник.
        source_lang = self.config.get('language', 'ru')
        if source_lang == target_code:
            source_lang = 'en' if target_code != 'en' else 'ru'

        self._worker = _TranslateWorker(text, source_lang, target_code, yandex_key, yandex_folder)
        self._worker.finished_ok.connect(self._on_translate_ok)
        self._worker.finished_err.connect(self._on_translate_err)
        self._worker.start()

    def _on_translate_ok(self, translated: str, provider: str):
        self.translate_btn.setEnabled(True)
        self.result_edit.setPlainText(translated)
        self.provider_label.setText(self._t('provider_label', provider=provider))

    def _on_translate_err(self, error: str):
        self.translate_btn.setEnabled(True)
        self.result_edit.setPlainText(self._t('err_network', error=error))
        self.provider_label.setText('')
