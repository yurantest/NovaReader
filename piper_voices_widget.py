# -*- coding: utf-8 -*-
"""
Виджет загрузки голосов Piper TTS для окна настроек
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont
from pathlib import Path
import json

from piper_voice_downloader import PiperVoiceDownloader, PiperVoiceInfo, DownloadWorker


class VoiceDownloadThread(QThread):
    """Поток для загрузки голоса"""
    progress = pyqtSignal(str, int)  # voice_id, percent
    finished = pyqtSignal(str, bool)  # voice_id, success
    status = pyqtSignal(str, str)  # voice_id, message
    
    def __init__(self, downloader, voice_info):
        super().__init__()
        self.downloader = downloader
        self.voice_info = voice_info
        self.voice_id = voice_info.name
        
    def run(self):
        def on_progress(downloaded, total):
            pct = int(downloaded * 100 / total) if total > 0 else 0
            self.progress.emit(self.voice_id, pct)
        
        def on_status(msg):
            self.status.emit(self.voice_id, msg)
        
        def on_finished(success):
            self.finished.emit(self.voice_id, success)
        
        worker = DownloadWorker(self.downloader, self.voice_info, on_progress, on_status, on_finished)
        worker.run()  # Запускаем синхронно в этом потоке


class PiperVoicesWidget(QWidget):
    """Виджет управления голосами Piper TTS"""
    
    voicesChanged = pyqtSignal()  # Сигнал: список голосов изменился
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.voices_dir = config.voices_dir
        self.downloader = PiperVoiceDownloader(self.voices_dir)
        
        self.download_threads = {}  # voice_id -> VoiceDownloadThread
        
        self._init_ui()
        self._load_voices()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Заголовок
        title = QLabel("Голоса Piper TTS")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        hint = QLabel("Нажмите ⬇️ для загрузки голоса. После загрузки голос станет доступен в читалке.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        layout.addWidget(hint)
        
        # Скролл-область для списка голосов
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #2a2a3a;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #5a5a70;
                border-radius: 4px;
                min-height: 20px;
            }
        """)
        
        self.voices_container = QWidget()
        self.voices_layout = QVBoxLayout(self.voices_container)
        self.voices_layout.setContentsMargins(0, 0, 0, 0)
        self.voices_layout.setSpacing(6)
        self.voices_layout.addStretch()
        
        self.scroll.setWidget(self.voices_container)
        layout.addWidget(self.scroll)
    
    def _load_voices(self):
        """Загрузить список голосов"""
        # Очищаем контейнер
        while self.voices_layout.count() > 1:  # Оставляем stretch
            item = self.voices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Добавляем голоса
        for voice_data in self.downloader.RUSSIAN_VOICES:
            voice_id = voice_data["name"]
            voice_name = voice_data["display_name"]
            voice_quality = voice_data["quality"]
            
            installed = self.downloader.check_voice_exists(voice_id)
            
            widget = self._create_voice_widget(voice_id, voice_name, voice_quality, installed)
            self.voices_layout.insertWidget(self.voices_layout.count() - 1, widget)
    
    def _create_voice_widget(self, voice_id, voice_name, quality, installed):
        """Создать виджет одного голоса"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 8px;
            }
            QFrame:hover {
                background: rgba(255,255,255,0.08);
            }
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Информация о голосе
        info_layout = QVBoxLayout()
        
        name_label = QLabel(f"<b>{voice_name}</b>")
        name_label.setStyleSheet("color: #e8eaed; font-size: 14px;")
        info_layout.addWidget(name_label)
        
        quality_label = QLabel(f"Качество: <span style='color: #7ecfff;'>{quality}</span>")
        quality_label.setStyleSheet("color: #9aa0a6; font-size: 12px;")
        info_layout.addWidget(quality_label)
        
        layout.addLayout(info_layout, 1)
        
        # Статус и кнопка
        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if installed:
            # Голос установлен
            status_label = QLabel("✅ Установлен")
            status_label.setStyleSheet("color: #4caf50; font-size: 12px; font-weight: bold;")
            status_layout.addWidget(status_label)
        else:
            # Голос не установлен - кнопка загрузки
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            download_btn = QPushButton("⬇️ Загрузить")
            download_btn.setStyleSheet("""
                QPushButton {
                    background: #1a73e8;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #1557b0;
                }
                QPushButton:pressed {
                    background: #0d47a1;
                }
            """)
            download_btn.clicked.connect(lambda checked, vid=voice_id: self._download_voice(vid))
            btn_layout.addWidget(download_btn)
            status_layout.addLayout(btn_layout)
            
            # Прогресс бар (скрыт по умолчанию)
            progress = QProgressBar()
            progress.setObjectName(f"progress_{voice_id}")
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(True)
            progress.setFormat("%p%")
            progress.setStyleSheet("""
                QProgressBar {
                    background: #2a2a3a;
                    border: 1px solid #3a3a50;
                    border-radius: 3px;
                    height: 16px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background: #1a73e8;
                    border-radius: 2px;
                }
            """)
            progress.hide()
            status_layout.addWidget(progress)
        
        layout.addLayout(status_layout)
        
        return frame
    
    def _download_voice(self, voice_id):
        """Начать загрузку голоса"""
        # Ищем информацию о голосе
        voice_info = None
        for v in self.downloader.RUSSIAN_VOICES:
            if v["name"] == voice_id:
                voice_info = PiperVoiceInfo(
                    name=v["name"],
                    quality=v["quality"],
                    onnx_url=v["onnx"],
                    json_url=v["json"]
                )
                break
        
        if not voice_info:
            return
        
        # Находим виджет прогресса
        progress_bar = self.findChild(QProgressBar, f"progress_{voice_id}")
        if not progress_bar:
            return
        
        # Блокируем кнопку загрузки
        btn = self._find_download_button(voice_id)
        if btn:
            btn.setEnabled(False)
            btn.setText("⏳ Загрузка...")
        
        # Показываем прогресс
        progress_bar.show()
        progress_bar.setValue(0)
        
        # Запускаем загрузку
        thread = VoiceDownloadThread(self.downloader, voice_info)
        thread.progress.connect(lambda vid, pct: self._on_progress(voice_id, pct, progress_bar))
        thread.finished.connect(lambda vid, ok: self._on_finished(voice_id, ok, progress_bar, btn))
        thread.status.connect(lambda vid, msg: self._on_status(voice_id, msg))
        
        self.download_threads[voice_id] = thread
        thread.start()
    
    def _find_download_button(self, voice_id):
        """Найти кнопку загрузки для голоса"""
        for i in range(self.voices_layout.count()):
            item = self.voices_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                btn = widget.findChild(QPushButton)
                if btn and btn.text() in ["⬇️ Загрузить", "⏳ Загрузка..."]:
                    return btn
        return None
    
    def _on_progress(self, voice_id, percent, progress_bar):
        """Обновление прогресса"""
        progress_bar.setValue(percent)
    
    def _on_status(self, voice_id, msg):
        """Статус загрузки"""
        print(f"[PiperVoices] {voice_id}: {msg}")
    
    def _on_finished(self, voice_id, success, progress_bar, btn):
        """Загрузка завершена"""
        progress_bar.hide()
        
        if btn:
            btn.setEnabled(True)
        
        if success:
            # Перезагружаем список голосов
            self._load_voices()
            self.voicesChanged.emit()  # Уведомляем об изменении
        else:
            if btn:
                btn.setText("⬇️ Загрузить")
                btn.setEnabled(True)
    
    def get_installed_voices(self):
        """Вернуть список установленных голосов для reader.html"""
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
