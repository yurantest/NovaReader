# status_filter.py
"""
Модуль фильтрации книг по статусу чтения.
Подключается в library_window.py для добавления ComboBox фильтрации.

Использование:
1. Импорт: from status_filter import StatusFilter
2. Создание: self.status_filter = StatusFilter(self.config)
3. Добавление в тулбар: lay.addWidget(self.status_filter.widget)
4. Подключение сигнала: self.status_filter.filter_changed.connect(self._on_filter_changed)
5. Применение фильтра: filtered_books = self.status_filter.apply(books)
"""

from PyQt6.QtWidgets import QComboBox, QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal, QObject


class StatusFilter(QObject):
    """Фильтр книг по статусу чтения."""
    
    filter_changed = pyqtSignal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._widget = None
        self._combo = None
        self._create_widget()
    
    def _create_widget(self):
        """Создаёт виджет с ComboBox для фильтрации."""
        self._widget = QWidget()
        self._widget.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Метка
        label = QLabel("Статус:")
        label.setStyleSheet(f"color: #9aa0a6; font-size: 12px;")
        layout.addWidget(label)
        
        # ComboBox
        self._combo = QComboBox()
        self._combo.addItems([
            "Все книги",
            "Только новые",
            "Только читаемые",
            "Скрыть новые",
            "Скрыть читаемые",
        ])
        self._combo.setFixedSize(180, 34)
        self._combo.setStyleSheet(self._combo_style())
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)
    
    def _combo_style(self) -> str:
        """Стиль ComboBox в стиле NovaReader."""
        from library_window import BG, TEXT, BORDER, ACCENT, SUB
        return (
            f"QComboBox {{ "
            f"background: {BG}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 17px; "
            f"padding: 0 36px 0 14px; font-size: 13px; }} "
            f"QComboBox::drop-down {{ "
            f"subcontrol-origin: padding; subcontrol-position: right center; "
            f"width: 28px; border: none; border-radius: 0 17px 17px 0; }} "
            f"QComboBox::down-arrow {{ "
            f"image: none; "
            f"border-left: 4px solid transparent; "
            f"border-right: 4px solid transparent; "
            f"border-top: 5px solid {SUB}; "
            f"margin-right: 8px; }} "
            f"QComboBox:hover::down-arrow {{ border-top-color: {TEXT}; }} "
            f"QComboBox:focus {{ border-color: {ACCENT}; }} "
            f"QComboBox QAbstractItemView {{ "
            f"background: {BG}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 8px; "
            f"selection-background-color: {ACCENT}; "
            f"selection-color: white; padding: 4px; outline: none; }} "
        )
    
    def _on_combo_changed(self, index):
        """Вызывается при изменении выбранного фильтра."""
        self.filter_changed.emit()
    
    @property
    def widget(self) -> QWidget:
        """Возвращает виджет для добавления в тулбар."""
        return self._widget
    
    @property
    def combo(self) -> QComboBox:
        """Возвращает ComboBox для прямого доступа."""
        return self._combo
    
    def get_current_index(self) -> int:
        """Возвращает текущий индекс выбранного фильтра."""
        return self._combo.currentIndex() if self._combo else 0
    
    def set_current_index(self, index: int):
        """Устанавливает индекс фильтра."""
        if self._combo:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(index)
            self._combo.blockSignals(False)
    
    def apply(self, books: list) -> list:
        """
        Применяет фильтр к списку книг.
        
        Args:
            books: список книг (dict с полями progress, last_read и т.д.)
        
        Returns:
            отфильтрованный список книг
        """
        idx = self.get_current_index()
        
        if idx == 0:  # Все книги
            return books
        elif idx == 1:  # Только новые (не начатые)
            return [b for b in books if not b.get('progress') or b.get('progress', 0) == 0]
        elif idx == 2:  # Только читаемые (начатые, но не законченные)
            return [b for b in books if b.get('progress') and 0 < b.get('progress', 0) < 0.95]
        elif idx == 3:  # Скрыть новые
            return [b for b in books if b.get('progress') and b.get('progress', 0) > 0]
        elif idx == 4:  # Скрыть читаемые
            return [b for b in books if not b.get('progress') or b.get('progress', 0) == 0 or b.get('progress', 0) >= 0.95]
        
        return books
    
    def reset(self):
        """Сбрасывает фильтр к значению по умолчанию (Все книги)."""
        self.set_current_index(0)