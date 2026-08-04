"""
book_search_window.py — окно поиска книг с агрегацией.
Функции:
Поиск книг на author.today
Параллельный поиск на searchfloor.org (Цокольный этаж)
Параллельный поиск на moreknig.org
Параллельный поиск на flibusta.is (с корректным обходом страниц серий)
Отображение карточек книг с обложками
Возможность открыть книгу на author.today или скачать с searchfloor/moreknig/flibusta
Использование:
from book_search_window import BookSearchWindow
window = BookSearchWindow()
window.show()
"""
import sys
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QScrollArea, QGridLayout, QLabel,
                             QLineEdit, QDialog, QTextEdit, QFileDialog, QMessageBox,
                             QFrame, QComboBox, QCheckBox, QMenu)
from PyQt6.QtWidgets import QProgressBar
from PyQt6.QtGui import QPixmap, QDesktopServices, QFontDatabase, QFont, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer

# Импортируем стили и цвета из библиотеки
try:
    from library_window import (
        BG, SURFACE, BORDER, ACCENT, TEXT, SUB, SERIES, TOOLBAR, PROGRESS,
        DARK_THEME, LIGHT_THEME, _apply_theme_to_globals, init_lib_colors,
        CARD_W, CARD_H, CARD_S, _combo_style, _apply_msgbox_style, _styled_question
    )
    THEME_BG = BG
    THEME_SURFACE = SURFACE
    THEME_BORDER = BORDER
    THEME_ACCENT = ACCENT
    THEME_TEXT = TEXT
    THEME_SUB = SUB
    THEME_SERIES = SERIES
    THEME_TOOLBAR = TOOLBAR
except ImportError:
    DARK_THEME = {
        "BG":        "#1e1e2e",
        "SURFACE":   "#282838",
        "BORDER":    "#3a3a50",
        "ACCENT":    "#1a73e8",
        "TEXT":      "#e8eaed",
        "SUB":       "#9aa0a6",
        "SERIES":    "#7ecfff",
        "TOOLBAR":   "#252535",
    }
    THEME_BG = DARK_THEME["BG"]
    THEME_SURFACE = DARK_THEME["SURFACE"]
    THEME_BORDER = DARK_THEME["BORDER"]
    THEME_ACCENT = DARK_THEME["ACCENT"]
    THEME_TEXT = DARK_THEME["TEXT"]
    THEME_SUB = DARK_THEME["SUB"]
    THEME_SERIES = DARK_THEME["SERIES"]
    THEME_TOOLBAR = DARK_THEME["TOOLBAR"]

# Базовые URL
AUTHOR_BASE = "https://author.today"


def _resolve_save_path(config, filename):
    """
    Возвращает путь для сохранения книги без диалога выбора файла:
    папка берётся из настроек (config.get_download_path()) — если она
    там не задана, используется папка по умолчанию, которая создаётся
    автоматически. Если файл с таким именем уже существует, к имени
    добавляется суффикс (2), (3) и т.д., чтобы не перезаписывать книгу.
    """
    if config is not None:
        folder = config.get_download_path()
    else:
        from pathlib import Path
        folder = Path.home() / "NovaReader Downloads"
        folder.mkdir(parents=True, exist_ok=True)

    from pathlib import Path as _Path
    folder = _Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    target = folder / filename
    if not target.exists():
        return str(target)

    stem = target.stem
    # у "name.fb2.zip" стем через Path — "name.fb2", суффикс — ".zip";
    # это нормально, дубликаты всё равно будут отличаться по (2)/(3).
    suffix = target.suffix
    n = 2
    while True:
        candidate = folder / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return str(candidate)
        n += 1


class _ToastNotification(QWidget):
    """
    Всплывающее уведомление в стиле push-нотификации: появляется в углу
    окна и закрывается само через некоторое время (по умолчанию 10 сек),
    без необходимости нажимать «ОК».
    """
    _active = []  # уже показанные тосты — чтобы новые вставали в стопку, а не поверх друг друга

    def __init__(self, anchor_window, title, message, success=True, duration_ms=3000):
        super().__init__(None, Qt.WindowType.Tool
                          | Qt.WindowType.FramelessWindowHint
                          | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._anchor_window = anchor_window

        accent = THEME_ACCENT if success else "#e74c3c"
        has_mi = 'Material Icons' in QFontDatabase.families()
        icon_char = ('check_circle' if success else 'error') if has_mi else ('✓' if success else '!')

        card = QFrame(self)
        card.setObjectName("ToastCard")
        card.setStyleSheet(f"""
            QFrame#ToastCard {{
                background: {THEME_SURFACE};
                border: 1px solid {accent};
                border-radius: 10px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setStyleSheet(f"color:{accent}; font-size:22px; background:transparent;")
        if has_mi:
            icon_lbl.setFont(QFont('Material Icons', 22))
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{accent}; font-size:13px; font-weight:bold; background:transparent;")
        text_col.addWidget(title_lbl)
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet(f"color:{THEME_TEXT}; font-size:12px; background:transparent;")
        msg_lbl.setWordWrap(True)
        msg_lbl.setMaximumWidth(300)
        text_col.addWidget(msg_lbl)
        lay.addLayout(text_col, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{THEME_SUB};border:none;font-size:12px;}}"
            f"QPushButton:hover{{color:{THEME_TEXT};}}"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        lay.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.setFixedWidth(360)
        self.adjustSize()

        self._position()
        _ToastNotification._active.append(self)
        QTimer.singleShot(duration_ms, self.close)

    def _position(self):
        margin = 16
        spacing = 10
        if self._anchor_window is not None:
            geo = self._anchor_window.geometry()
            base_x = geo.x() + geo.width() - self.width() - margin
            base_y = geo.y() + geo.height() - margin
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            base_x = screen.x() + screen.width() - self.width() - margin
            base_y = screen.y() + screen.height() - margin

        y = base_y - self.height()
        for t in _ToastNotification._active:
            if t is self or not t.isVisible():
                continue
            y -= (t.height() + spacing)
        self.move(base_x, y)

    def closeEvent(self, e):
        if self in _ToastNotification._active:
            _ToastNotification._active.remove(self)
        super().closeEvent(e)


def _show_toast(parent, title, message, success=True, duration_ms=3000):
    """Показывает push-уведомление вместо модального QMessageBox.
    QTimer.singleShot(0, ...) гарантирует, что сам QWidget создаётся
    в главном GUI-потоке, даже если сигнал finished пришёл из QThread —
    иначе создание top-level окна из чужого потока подвешивает Qt."""
    anchor = parent.window() if parent is not None else None

    def _create():
        toast = _ToastNotification(anchor, title, message, success=success, duration_ms=duration_ms)
        toast.show()

    QTimer.singleShot(0, _create)
AUTHOR_SEARCH = f"{AUTHOR_BASE}/search"
SEARCHFLOOR_BASE = "https://searchfloor.org"
SEARCHFLOOR_SEARCH = f"{SEARCHFLOOR_BASE}/search"
MOREKNIG_BASE = "https://moreknig.org"
MOREKNIG_SEARCH = f"{MOREKNIG_BASE}/index.php?do=search&subaction=search"
FLIBUSTA_BASE = "https://flibusta.is"
FLIBUSTA_STATIC = "https://static.flibusta.is"

# Заголовки для запросов
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': AUTHOR_BASE
}

# Fallback для иконок
_ICON_FALLBACK = {
    "search":  "🔍",
    "add":  "+",
    "settings":  "",
    "back":  "←",
    "close":  "✕",
}

def _mbtn(icon_name, tooltip, sz=36):
    """Кнопка с Material Icons или Unicode-символом как fallback."""
    has_mi = 'Material Icons' in QFontDatabase.families()
    label = icon_name if has_mi else _ICON_FALLBACK.get(icon_name, icon_name[:1])
    font_family = "'Material Icons'" if has_mi else "sans-serif"
    font_size = sz // 2 if has_mi else sz // 2 + 4
    b = QPushButton(label)
    b.setFixedSize(sz, sz)
    b.setToolTip(tooltip)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;border:none;"
        f"border-radius:{sz//2}px;color:{THEME_SUB};"
        f"font-family:{font_family};font-size:{font_size}px;}}"
        f"QPushButton:hover{{background:rgba(255,255,255,.08);color:{THEME_TEXT};}}"
        f"QPushButton:pressed{{background:rgba(255,255,255,.15);}}")
    return b

def _apply_search_style(app):
    """Применить стили библиотеки к приложению поиска."""
    app.setStyleSheet(f"""
QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: {THEME_BG};
    color: {THEME_TEXT};
}}
QScrollArea {{
    border: none;
    background: {THEME_BG};
}}
QScrollBar:vertical {{
    border: none;
    background: {THEME_SURFACE};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {THEME_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {THEME_ACCENT};
}}
QLineEdit {{
    padding: 10px;
    border: 2px solid {THEME_BORDER};
    border-radius: 17px;
    font-size: 14px;
    background: {THEME_BG};
    color: {THEME_TEXT};
}}
QLineEdit:focus {{
    border: 2px solid {THEME_ACCENT};
}}
QLineEdit::placeholder {{
    color: {THEME_SUB};
}}
QPushButton {{
    padding: 10px 30px;
    background: {THEME_ACCENT};
    color: white;
    border: none;
    border-radius: 17px;
    font-weight: bold;
    font-size: 14px;
}}
QPushButton:hover {{
    background: #1557b0;
}}
QPushButton:disabled {{
    background: {THEME_BORDER};
    color: {THEME_SUB};
}}
QLabel {{
    background: transparent;
    color: {THEME_TEXT};
}}
QTextEdit {{
    background: {THEME_SURFACE};
    color: {THEME_TEXT};
    border: 1px solid {THEME_BORDER};
    border-radius: 8px;
    padding: 10px;
}}
QComboBox {{
    background: {THEME_BG};
    color: {THEME_TEXT};
    border: 1px solid {THEME_BORDER};
    border-radius: 17px;
    padding: 8px 14px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {THEME_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {THEME_SURFACE};
    color: {THEME_TEXT};
    border: 1px solid {THEME_BORDER};
    border-radius: 8px;
    selection-background-color: {THEME_ACCENT};
}}
""")

# ─────────────────────────────────────────────────────────────────────────────
# Парсер книг ───────────────────────────────────────────────────────────────
class BookParser:
    """Парсер книг с Author.Today, SearchFloor, MoreKnig и Flibusta"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.max_workers = 10

    def search_books(self, query, limit=100, max_pages=10, callback=None):
        """Поиск книг с пагинацией и параллельным парсингом (Author.Today)"""
        print(f" Поиск AT: {query}")
        books = []
        seen_urls = set()
        seen_books = {}
        title_groups = {}

        clean_query = query.strip()
        if clean_query.endswith('.'):
            clean_query = clean_query[:-1]
        encoded_query = quote_plus(clean_query)

        all_book_urls = []
        for page in range(1, max_pages + 1):
            if len(books) >= limit:
                break

            try:
                search_url = f"{AUTHOR_SEARCH}?category=works&q={encoded_query}&page={page}"
                print(f"  Страница {page}: {search_url}")
                response = self.session.get(search_url, timeout=45)

                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                no_results = soup.find(string=re.compile(r'Ничего не найдено|Нет результатов|No results', re.I))
                if no_results:
                    break

                page_urls = []
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '/work/' in href and '/reviews' not in href and 'search' not in href and 'page' not in href:
                        work_match = re.search(r'/work/(\d+)', href)
                        if work_match:
                            book_url = urljoin(AUTHOR_BASE, href)
                            if book_url not in seen_urls:
                                seen_urls.add(book_url)
                                page_urls.append(book_url)

                print(f"    Найдено книг на странице {page}: {len(page_urls)}")
                all_book_urls.extend(page_urls)

                pagination = soup.find('ul', class_=re.compile(r'pagination', re.I))
                if pagination:
                    next_link = pagination.find('a', string=re.compile(r'Вперед|Next|→', re.I))
                    if not next_link:
                        break
                else:
                    if page > 1:
                        break

            except Exception as e:
                print(f"  ❌ Ошибка на странице {page}: {e}")
                break

        print(f"  Всего найдено ссылок: {len(all_book_urls)}")

        if all_book_urls:
            print(f"  ⚡ Начинаем параллельный парсинг...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {executor.submit(self._parse_author_book, url): url for url in all_book_urls[:limit]}
                completed = 0
                total = len(future_to_url)
                temp_books = []

                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        book = future.result(timeout=30)
                        completed += 1
                        if book and book.get('title') != 'Без названия' and len(book.get('title', '')) > 2:
                            sf_info = self._search_on_searchfloor(book)
                            book['searchfloor_url'] = sf_info.get('url')
                            book['searchfloor_available'] = sf_info.get('available', False)
                            temp_books.append(book)

                            if callback:
                                callback(book)

                        if completed % 5 == 0:
                            print(f"    Обработано {completed}/{total} книг")

                    except Exception as e:
                        print(f"    ❌ Ошибка парсинга: {e}")

            for book in temp_books:
                title_key = book.get('title', '').lower().strip()
                if title_key not in title_groups:
                    title_groups[title_key] = []
                title_groups[title_key].append(book)

            for title_key, group in title_groups.items():
                group.sort(key=lambda x: (not x.get('searchfloor_available', False), x.get('work_id', '')))
                best_book = group[0]

                unique_key = self._create_unique_key(best_book)
                if unique_key and unique_key not in seen_books:
                    seen_books[unique_key] = best_book
                    books.append(best_book)

        print(f"  Всего найдено уникальных книг: {len(books)}")
        return books[:limit]

    def _create_unique_key(self, book):
        key_parts = []
        if book.get('title'):
            title = book['title'].lower().strip()
            title = re.sub(r'["\']', '', title)
            title = re.sub(r'\s+', ' ', title)
            key_parts.append(title)
        if book.get('authors') and len(book['authors']) > 0:
            authors = []
            for author in book['authors']:
                clean_author = author.lower().strip()
                clean_author = re.sub(r'\s+', ' ', clean_author)
                authors.append(clean_author)
            key_parts.append('|'.join(sorted(authors)))
        if book.get('series_number'):
            key_parts.append(f"series:{book['series_number']}")
        return '||'.join(key_parts) if key_parts else None

    def _parse_author_book(self, url):
        try:
            clean_url = re.sub(r'/reviews$', '', url)
            clean_url = clean_url.rstrip('/')

            response = self.session.get(clean_url, timeout=45)
            soup = BeautifulSoup(response.text, 'html.parser')

            book = {
                'title': 'Без названия',
                'cover': None,
                'description': '',
                'authors': [],
                'genres': [],
                'series': None,
                'series_number': None,
                'url': clean_url,
                'work_id': None,
                'searchfloor_url': None,
                'searchfloor_available': False
            }

            work_id_match = re.search(r'/work/(\d+)', clean_url)
            if work_id_match:
                book['work_id'] = work_id_match.group(1)

            h1 = soup.find('h1')
            if h1:
                title = h1.text.strip()
                if title:
                    book['title'] = title

            if book['title'] == 'Без названия':
                title_selectors = ['.work-title', '.book-title', '.title']
                for selector in title_selectors:
                    tag = soup.select_one(selector)
                    if tag:
                        title = tag.text.strip()
                        if title:
                            book['title'] = title
                            break

            cover_selectors = ['.book-cover img', '.work-cover img', '.cover img', 'meta[property="og:image"]']
            for selector in cover_selectors:
                if selector.startswith('meta'):
                    tag = soup.find('meta', {'property': 'og:image'})
                    if tag:
                        src = tag.get('content', '')
                        if src:
                            book['cover'] = urljoin(AUTHOR_BASE, src)
                            break
                else:
                    tag = soup.select_one(selector)
                    if tag:
                        src = tag.get('src')
                        if src:
                            book['cover'] = urljoin(AUTHOR_BASE, src)
                            break

            desc_selectors = ['.description', '.book-description', '.work-description', '.annotation', 'meta[name="description"]']
            for selector in desc_selectors:
                if selector.startswith('meta'):
                    tag = soup.find('meta', {'name': 'description'})
                    if tag:
                        desc = tag.get('content', '').strip()
                        if desc and len(desc) > 20:
                            book['description'] = desc[:300] + '...' if len(desc) > 300 else desc
                            break
                else:
                    tag = soup.select_one(selector)
                    if tag:
                        text = tag.text.strip()
                        if text and len(text) > 20:
                            book['description'] = text[:300] + '...' if len(text) > 300 else text
                            break

            author_selectors = ['.author', '.book-author', '.work-author']
            for selector in author_selectors:
                tags = soup.select(selector)
                if tags:
                    authors = [tag.text.strip() for tag in tags if tag.text.strip()]
                    if authors:
                        book['authors'] = authors
                        break

            genre_selectors = ['.genre', '.book-genre', '.work-genre', '.tag']
            for selector in genre_selectors:
                tags = soup.select(selector)
                if tags:
                    genres = [tag.text.strip() for tag in tags[:3] if tag.text.strip()]
                    if genres:
                        book['genres'] = genres
                        break

            series_selectors = ['.series', '.book-series', '.work-series']
            for selector in series_selectors:
                tag = soup.select_one(selector)
                if tag:
                    series_text = tag.text.strip()
                    number_match = re.search(r'(\d+)\s*[,.]?\s*(?:книг|том|часть|book|part)', series_text, re.I)
                    if number_match:
                        book['series_number'] = int(number_match.group(1))
                    series_name = re.sub(r'\d+\s*[,.]?\s*(?:книг|том|часть|book|part)\s*', '', series_text, flags=re.I).strip()
                    if series_name:
                        book['series'] = series_name
                    break

            return book
        except Exception as e:
            return None

    def _search_on_searchfloor(self, book):
        try:
            search_parts = []
            if book.get('title'):
                search_parts.append(book['title'])
            if book.get('authors') and len(book['authors']) > 0:
                search_parts.append(book['authors'][0])

            if not search_parts:
                return {'url': None, 'available': False}

            search_query = ' '.join(search_parts)
            encoded_query = quote_plus(search_query)
            search_url = f"{SEARCHFLOOR_SEARCH}?q={encoded_query}"

            response = self.session.get(search_url, timeout=10)
            if response.status_code == 404:
                return {'url': None, 'available': False}

            soup = BeautifulSoup(response.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/b/' in href:
                    full_url = urljoin(SEARCHFLOOR_BASE, href)
                    return {'url': full_url, 'available': True}

            return {'url': None, 'available': False}
        except Exception as e:
            return {'url': None, 'available': False}

    def search_on_moreknig(self, query, limit=50, max_pages=10, callback=None):
        books = []
        try:
            init_url = f"{MOREKNIG_SEARCH}&story={quote_plus(query)}"
            self.session.get(init_url, timeout=45)

            for page in range(max_pages):
                if len(books) >= limit:
                    break

                start_offset = page * 26
                url = f"{MOREKNIG_BASE}/index.php?do=search&subaction=search&story={quote_plus(query)}&search_start={start_offset}&result_from={start_offset + 1}"
                print(f"  MoreKnig стр.{page+1} (offset={start_offset})...")

                fresh_session = requests.Session()
                fresh_session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                })

                response = fresh_session.get(url, timeout=45, allow_redirects=True)
                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                page_urls = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if '.html' in href and 'moreknig.org' in href:
                        full_url = urljoin(MOREKNIG_BASE, href)
                        if full_url not in page_urls:
                            page_urls.append(full_url)

                if not page_urls:
                    break

                print(f"    Найдено {len(page_urls)} книг")

                for url in page_urls:
                    if len(books) >= limit:
                        break
                    try:
                        book = self._parse_moreknig_book(url)
                        if book and book.get('title'):
                            book['source'] = 'moreknig'
                            has_download = book.get('download_urls') and len(book.get('download_urls', [])) > 0
                            if not has_download:
                                sf_info = self._search_on_searchfloor(book)
                                book['searchfloor_url'] = sf_info.get('url')
                                book['searchfloor_available'] = sf_info.get('available', False)

                            books.append(book)
                            if callback:
                                callback(book)
                    except Exception as e:
                        print(f"      Ошибка: {e}")

                print(f"    Итого: {len(books)}")

            print(f"  MoreKnig: всего {len(books)} книг")
        except Exception as e:
            print(f"  MoreKnig: ошибка: {e}")

        return books

    def _parse_moreknig_book(self, url):
        try:
            response = self.session.get(url, timeout=45)
            soup = BeautifulSoup(response.text, 'html.parser')

            book = {
                'title': 'Без названия',
                'cover': None,
                'description': '',
                'authors': [],
                'genres': [],
                'series': None,
                'series_number': None,
                'url': url,
                'moreknig_url': url,
                'moreknig_available': True,
                'download_urls': []
            }

            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
                if title:
                    book['title'] = title

            cover_div = soup.find('div', class_='fpos')
            if cover_div:
                img = cover_div.find('img')
                if img and img.get('src') and 'uploads' in img.get('src'):
                    src = img.get('src')
                    book['cover'] = urljoin(MOREKNIG_BASE, src) if not src.startswith('http') else src

            if not book['cover']:
                og_image = soup.find('meta', {'property': 'og:image'})
                if og_image and og_image.get('content') and 'uploads' in og_image.get('content'):
                    og_url = og_image.get('content')
                    book['cover'] = urljoin(MOREKNIG_BASE, og_url) if not og_url.startswith('http') else og_url

            author_links = soup.find_all('a', href=lambda x: x and '/knigi-filtr/autor/' in x if x else False)
            for author_link in author_links:
                author_name = author_link.get_text(strip=True)
                if author_name and 1 < len(author_name) < 50 and not author_name[0].isdigit():
                    book['authors'] = [author_name]
                    break

            if not book['authors']:
                author_meta = soup.find('meta', {'name': 'author'})
                if author_meta and author_meta.get('content'):
                    book['authors'] = [author_meta.get('content').strip()]

            desc_div = soup.find('div', class_='full-text')
            if desc_div:
                desc_text = desc_div.get_text(strip=True)
                if desc_text and len(desc_text) > 20:
                    book['description'] = desc_text[:500] + '...' if len(desc_text) > 500 else desc_text

            download_links = soup.find_all('a', href=lambda x: x and 'download.php' in x if x else False)
            for link in download_links[:5]:
                href = link.get('href')
                text = link.get_text(strip=True).lower()
                if href:
                    full_url = urljoin(MOREKNIG_BASE, href)
                    fmt = 'fb2'
                    if '.pdf' in text or 'pdf' in text: fmt = 'pdf'
                    elif '.epub' in text or 'epub' in text: fmt = 'epub'
                    elif '.txt' in text or 'txt' in text: fmt = 'txt'
                    elif '.rtf' in text or 'rtf' in text: fmt = 'rtf'

                    book['download_urls'].append({'url': full_url, 'format': fmt})

            return book
        except Exception as e:
            print(f"    MoreKnig: ошибка парсинга: {e}")
            return None

    def search_on_flibusta(self, query, limit=50, max_pages=5, callback=None):
        """Поиск на flibusta.is с корректным обходом страниц серий"""
        books = []
        seen_urls = set()  # Отслеживаем ВСЕ найденные URL книг
        try:
            encoded_query = quote_plus(query.strip())
            for page in range(1, max_pages + 1):
                if len(books) >= limit:
                    break

                search_url = f"{FLIBUSTA_BASE}/booksearch?ask={encoded_query}"
                if page > 1:
                    search_url += f"&p={page}"

                print(f"  Flibusta стр.{page}...")
                response = self.session.get(search_url, timeout=45)
                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, 'html.parser')

                # 1. Собираем ссылки на книги (/b/ID)
                page_book_urls = []
                for a in soup.find_all('a', href=re.compile(r'^/b/\d+$')):
                    full_url = urljoin(FLIBUSTA_BASE, a['href'])
                    if full_url not in seen_urls and full_url not in page_book_urls:
                        page_book_urls.append(full_url)

                # 2. Собираем ссылки на серии (/sequence/ID или /s/ID)
                page_series_urls = []
                for a in soup.find_all('a', href=re.compile(r'^/(sequence|s)/\d+$')):
                    full_url = urljoin(FLIBUSTA_BASE, a['href'])
                    if full_url not in page_series_urls:
                        page_series_urls.append(full_url)

                print(f"    Найдено книг: {len(page_book_urls)}, серий: {len(page_series_urls)}")

                # Парсим книги напрямую (только если еще не видели этот URL)
                for url in page_book_urls[:min(20, limit - len(books))]:
                    if len(books) >= limit:
                        break
                    if url in seen_urls:
                        continue

                    try:
                        book = self._parse_flibusta_book(url)
                        if book and book.get('title') and book['title'] != 'Без названия':
                            book['source'] = 'flibusta'
                            books.append(book)
                            seen_urls.add(url)  # Запоминаем URL
                            if callback:
                                callback(book)
                    except Exception:
                        pass

                # Парсим каждую серию и извлекаем ВСЕ книги из неё
                for series_url in page_series_urls[:3]:  # Ограничиваем до 3 серий на страницу
                    if len(books) >= limit:
                        break
                    try:
                        print(f"    Переходим в серию: {series_url}")
                        series_books = self._parse_flibusta_series_page(series_url)
                        for book in series_books:
                            if len(books) >= limit:
                                break
                            # Добавляем книгу ТОЛЬКО если еще не видели этот URL
                            if book and book.get('url') and book['url'] not in seen_urls:
                                if book.get('title') and book['title'] != 'Без названия':
                                    book['source'] = 'flibusta'
                                    books.append(book)
                                    seen_urls.add(book['url'])  # Запоминаем URL
                                    if callback:
                                        callback(book)
                    except Exception as e:
                        print(f"    Ошибка парсинга серии {series_url}: {e}")

                if not soup.find('a', string=re.compile(r'Следующая|Next|→', re.I)):
                    break

            print(f"  Flibusta (с сериями): всего {len(books)} книг")
        except Exception as e:
            print(f"  Flibusta: ошибка: {e}")

        return books

    def _parse_flibusta_series_page(self, url):
        """Парсинг страницы серии на Флибусте — извлекает ТОЛЬКО книги из этой серии"""
        books = []
        try:
            response = self.session.get(url, timeout=45)
            if response.status_code != 200:
                return books

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем только ссылки на книги (/b/ID) внутри страницы серии
            book_links = soup.find_all('a', href=re.compile(r'^/b/\d+$'))
            book_urls = []

            for a in book_links:
                full_url = urljoin(FLIBUSTA_BASE, a['href'])
                if full_url not in book_urls:
                    book_urls.append(full_url)

            # Парсим каждую книгу, ограничиваем чтобы не зависать
            for book_url in book_urls[:15]:
                try:
                    book = self._parse_flibusta_book(book_url)
                    # Строгая проверка: добавляем только если это реальная книга
                    if book and book.get('title') and book['title'] != 'Без названия':
                        books.append(book)
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка парсинга серии {url}: {e}")

        return books

    def _parse_flibusta_book(self, url):
        try:
            response = self.session.get(url, timeout=45)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            book = {
                'title': 'Без названия',
                'cover': None,
                'description': '',
                'authors': [],
                'genres': [],
                'series': None,
                'series_number': None,
                'url': url,
                'flibusta_url': url,
                'flibusta_available': True,
                'download_urls': [],
                'book_id': None
            }

            book_id_match = re.search(r'/b/(\d+)', url)
            if book_id_match:
                book['book_id'] = book_id_match.group(1)

            # Название и автор из title страницы
            title_tag = soup.find('title')
            if title_tag:
                full_title = title_tag.get_text(strip=True)
                # Убираем "(fb2)"/"(epub)"/"(mobi)" где бы они ни стояли —
                # не только в самом конце строки, т.к. после скобки иногда
                # остаётся хвост вроде " |" от разметки страницы.
                full_title = re.sub(r'\s*\((?:fb2|epub|mobi)\)\s*', ' ', full_title, flags=re.I)
                if 'Флибуста' in full_title:
                    full_title = full_title.replace('Флибуста', '').strip()
                # Убираем висячие разделители, оставшиеся после вырезания скобок
                full_title = re.sub(r'\s*\|\s*$', '', full_title).strip()
                full_title = re.sub(r'\s{2,}', ' ', full_title).strip()

                if ' - ' in full_title:
                    parts = full_title.rsplit(' - ', 1)
                    book['title'] = parts[0].strip()
                    if len(parts) > 1:
                        book['authors'] = [parts[1].strip()]
                else:
                    book['title'] = full_title

            # Дополнительная проверка автора рядом с h1
            h1 = soup.find('h1')
            if h1 and not book['authors']:
                next_elem = h1.find_next_sibling()
                if next_elem and next_elem.name == 'a':
                    author = next_elem.get_text(strip=True)
                    if author:
                        book['authors'] = [author]

            # Обложка
            cover_img = soup.find('img', src=re.compile(r'/i/\d+/\d+/[\w-]+\.jpg', re.I))
            if cover_img and cover_img.get('src'):
                book['cover'] = urljoin(FLIBUSTA_BASE, cover_img['src'])

            # Аннотация — заголовок "Аннотация" может быть в любом теге
            # (div/h2/h3/b и т.д.), а сам текст идёт в одном или нескольких
            # следующих элементах (обычно <p>), а не строго в одном div.
            desc = ''
            annotation_tag = soup.find(
                lambda t: t.name in ('div', 'h1', 'h2', 'h3', 'h4', 'b', 'strong', 'p')
                and t.get_text(strip=True) == 'Аннотация'
            )
            if annotation_tag:
                parts = []
                for sib in annotation_tag.find_next_siblings():
                    text = sib.get_text(strip=True)
                    if not text:
                        continue
                    # останавливаемся на следующем заголовке раздела
                    if text in ('Рекомендации:', 'Читать онлайн', 'Похожие книги') or sib.name in ('h1', 'h2', 'h3'):
                        break
                    parts.append(text)
                    if sum(len(p) for p in parts) > 500:
                        break
                desc = ' '.join(parts).strip()

            if desc and len(desc) > 20:
                book['description'] = desc[:500] + '...' if len(desc) > 500 else desc

            # Формируем ссылки для скачивания (Флибуста сама обработает редирект на статический сервер)
            if book['book_id']:
                book_id = book['book_id']
                book['download_urls'].append({'url': f"{FLIBUSTA_BASE}/b/{book_id}/fb2", 'format': 'fb2', 'is_zip': True})
                book['download_urls'].append({'url': f"{FLIBUSTA_BASE}/b/{book_id}/epub", 'format': 'epub', 'is_zip': False})
                book['download_urls'].append({'url': f"{FLIBUSTA_BASE}/b/{book_id}/mobi", 'format': 'mobi', 'is_zip': False})

            return book
        except Exception as e:
            print(f"    Flibusta: ошибка парсинга: {e}")
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Виджеты интерфейса ────────────────────────────────────────────────────────

class BookCard(QFrame):
    """Карточка книги в стиле библиотеки"""
    clicked = pyqtSignal(object)

    def __init__(self, book_data, config=None, parent=None):
        super().__init__(parent)
        self.book_data = book_data
        self.config = config
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(170, 280)
        self._paint(False)
        self._build()
        if book_data.get('cover'):
            self.load_cover()
        else:
            self.show_placeholder()

    def _paint(self, hov):
        c, w = (THEME_ACCENT, 2) if hov else (THEME_BORDER, 1)
        self.setStyleSheet(f"QFrame{{background:{THEME_SURFACE};border-radius:10px;border:{w}px solid {c};}}")

    def enterEvent(self, e):
        self._paint(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._paint(False)
        super().leaveEvent(e)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 190)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(f"background:{THEME_BG};border-radius:6px;color:{THEME_SUB};font-size:38px;")
        layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignCenter)

        title = self.book_data.get('title', 'Без названия')
        title_label = QLabel((title[:37] + '...') if len(title) > 40 else title)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(36)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color:{THEME_TEXT};font-size:10px;font-weight:bold;")
        layout.addWidget(title_label)

        if self.book_data.get('authors'):
            authors_text = ', '.join(self.book_data['authors'][:2])
            authors_label = QLabel((authors_text[:27] + '...') if len(authors_text) > 30 else authors_text)
            authors_label.setWordWrap(True)
            authors_label.setMaximumHeight(30)
            authors_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            authors_label.setStyleSheet(f"color:{THEME_SUB};font-size:11px;")
            layout.addWidget(authors_label)

        series_info = []
        if self.book_data.get('series'):
            series_info.append(self.book_data['series'])
        if self.book_data.get('series_number'):
            series_info.append(f"Книга {self.book_data['series_number']}")
        if series_info:
            series_label = QLabel(' | '.join(series_info))
            series_label.setWordWrap(True)
            series_label.setMaximumHeight(28)
            series_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            series_label.setStyleSheet(f"color:{THEME_SERIES};font-size:10px;font-weight:bold;")
            layout.addWidget(series_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)

        if self.book_data.get('url'):
            author_btn = QPushButton("Читать")
            author_btn.setStyleSheet(f"QPushButton{{padding:5px 10px;background:{THEME_ACCENT};color:white;border:none;border-radius:3px;font-size:9px;font-weight:bold;}}QPushButton:hover{{background:#1557b0;}}")
            author_btn.clicked.connect(lambda: self._open_url(self.book_data['url']))
            btn_layout.addWidget(author_btn)

        if self.book_data.get('searchfloor_available') and self.book_data.get('searchfloor_url'):
            searchfloor_btn = QPushButton("Скачать")
            searchfloor_btn.setStyleSheet("QPushButton{padding:5px 10px;background:#e67e22;color:white;border:none;border-radius:3px;font-size:9px;font-weight:bold;}QPushButton:hover{background:#d35400;}")
            searchfloor_btn.clicked.connect(lambda: self._download_from_searchfloor(self.book_data))
            btn_layout.addWidget(searchfloor_btn)

        elif self.book_data.get('moreknig_available') and self.book_data.get('download_urls'):
            moreknig_btn = QPushButton("Скачать")
            moreknig_btn.setStyleSheet("QPushButton{padding:5px 10px;background:#27ae60;color:white;border:none;border-radius:3px;font-size:9px;font-weight:bold;}QPushButton:hover{background:#1e8449;}")
            moreknig_btn.clicked.connect(lambda: self._download_from_moreknig(self.book_data))
            btn_layout.addWidget(moreknig_btn)

        elif self.book_data.get('flibusta_available') and self.book_data.get('download_urls'):
            formats = [item.get('format', '').upper() for item in self.book_data.get('download_urls', [])]
            btn_text = f"({ '/'.join(formats[:2]) })" if len(formats) > 1 else f"({formats[0]})"

            flibusta_btn = QPushButton(f"Скачать {btn_text}")
            flibusta_btn.setStyleSheet("QPushButton{padding:5px 8px;background:#27ae60;color:white;border:none;border-radius:3px;font-size:8px;font-weight:bold;}QPushButton:hover{background:#1e8449;}")
            flibusta_btn.clicked.connect(lambda: self._download_from_flibusta(self.book_data))
            btn_layout.addWidget(flibusta_btn)

        layout.addLayout(btn_layout)

    def _open_url(self, url):
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _download_from_searchfloor(self, book_data):
        sf_url = book_data.get('searchfloor_url')
        if not sf_url:
            return

        book_id_match = re.search(r'/b/(\d+)', sf_url)
        if not book_id_match:
            QMessageBox.warning(self, "Ошибка", "Не удалось извлечь ID книги")
            return

        book_id = book_id_match.group(1)
        download_url = f"https://searchfloor.org/book/{book_id}"

        title = re.sub(r'[<>:"/\\|?*]', '', book_data.get('title', 'book'))
        save_path = _resolve_save_path(self.config, f"{title}.zip")

        self.downloader = DownloadWorker(download_url, save_path)
        self.downloader.progress.connect(self.on_download_progress)
        self.downloader.finished.connect(lambda success, msg: self.on_download_complete(success, msg, book_data))
        self.downloader.start()

        self.status_label = QLabel("⬇ Скачивание...")
        self.status_label.setStyleSheet("color: #e67e22; font-size: 11px;")
        self.layout().addWidget(self.status_label)

    def on_download_progress(self, percent):
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"⬇ Скачивание... {percent}%")

    def _download_from_moreknig(self, book_data):
        download_urls = book_data.get('download_urls', [])
        if not download_urls:
            return

        dlg_url = download_urls[0]['url']
        dlg_fmt = download_urls[0].get('format', 'fb2')

        title = re.sub(r'[<>:"/\\|?*]', '', book_data.get('title', 'book'))
        save_path = _resolve_save_path(self.config, f"{title}.{dlg_fmt}")

        self.downloader = DownloadWorker(dlg_url, save_path)
        self.downloader.progress.connect(self.on_download_progress)
        self.downloader.finished.connect(lambda success, msg: self.on_download_complete(success, msg, book_data))
        self.downloader.start()

    def _download_from_flibusta(self, book_data):
        """Показываем меню выбора формата для скачивания с flibusta.is"""
        download_urls = book_data.get('download_urls', [])
        if not download_urls:
            QMessageBox.warning(self, "Ошибка", "Нет доступных форматов для скачивания")
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {THEME_SURFACE}; border: 1px solid {THEME_BORDER}; border-radius: 5px; padding: 5px; }}
            QAction {{ color: {THEME_TEXT}; padding: 8px; }}
            QAction:hover {{ background: {THEME_ACCENT}; }}
        """)

        for item in download_urls:
            fmt = item.get('format', '').upper()
            action = menu.addAction(f"Скачать {fmt}")
            action.triggered.connect(lambda checked, url=item['url'], f=fmt: self._start_flibusta_download(url, f, book_data))

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _start_flibusta_download(self, url, fmt, book_data):
        # FB2 на Флибусте — это ZIP архив, поэтому расширение должно быть .fb2.zip
        extension = 'fb2.zip' if fmt.lower() == 'fb2' else fmt.lower()
        title = re.sub(r'[<>:"/\\|?*]', '', book_data.get('title', 'book'))

        save_path = _resolve_save_path(self.config, f"{title}.{extension}")

        self.downloader = FlibustaDownloadWorker(url, save_path)
        self.downloader.progress.connect(self.on_download_progress)
        self.downloader.finished.connect(lambda success, msg: self.on_download_complete(success, msg, book_data))
        self.downloader.start()

        self.status_label = QLabel(f"⬇ Скачивание {fmt.upper()}...")
        self.status_label.setStyleSheet("color: #27ae60; font-size: 11px;")
        self.layout().addWidget(self.status_label)

    def on_download_complete(self, success, message, book_data):
        if hasattr(self, 'status_label'):
            self.status_label.deleteLater()
        if success:
            _show_toast(self, "Успех", f"Книга сохранена:\n{message}", success=True)
        else:
            _show_toast(self, "Ошибка", f"Не удалось скачать:\n{message}", success=False)

    def show_placeholder(self):
        self.cover_label.setText("")
        self.cover_label.setStyleSheet("QLabel{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f0f0f0,stop:1 #e0e0e0);border:1px solid #ddd;border-radius:8px;font-size:48px;}")

    def load_cover(self):
        self.loader = CoverLoader(self.book_data['cover'])
        self.loader.finished.connect(self.on_cover_loaded)
        self.loader.start()

    def on_cover_loaded(self, pixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(150, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(scaled)
            self.cover_label.setStyleSheet("QLabel{background:white;border:1px solid #ddd;border-radius:8px;}")
        else:
            self.show_placeholder()

    def mousePressEvent(self, event):
        self.clicked.emit(self.book_data)


class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            session = requests.Session()
            session.headers.update(HEADERS)
            response = session.get(self.url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(int((downloaded / total_size) * 100))

            self.finished.emit(True, self.save_path)
        except Exception as e:
            self.finished.emit(False, str(e))


class FlibustaDownloadWorker(QThread):
    """Поток для скачивания книги с Флибусты с правильными заголовками и обработкой редиректов"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Referer': FLIBUSTA_BASE,
            })

            # allow_redirects=True критически важен для Флибусты, чтобы получить файл со статического сервера
            response = session.get(self.url, stream=True, timeout=60, allow_redirects=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(int((downloaded / total_size) * 100))

            self.finished.emit(True, self.save_path)
        except Exception as e:
            self.finished.emit(False, str(e))


class CoverLoader(QThread):
    finished = pyqtSignal(QPixmap)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self.finished.emit(pixmap)
            else:
                self.finished.emit(QPixmap())
        except Exception:
            self.finished.emit(QPixmap())


class BookDetailDialog(QDialog):
    def __init__(self, book_data, config=None, parent=None):
        super().__init__(parent)
        self.book_data = book_data
        self.config = config
        self.setWindowTitle(book_data.get('title', 'Книга'))
        self.setModal(True)
        self.resize(650, 550)
        self.setStyleSheet(f"QDialog{{background:{THEME_BG};color:{THEME_TEXT};}}")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()

        cover_label = QLabel()
        cover_label.setFixedSize(150, 200)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet(f"border: 1px solid {THEME_BORDER}; border-radius: 8px; background: {THEME_SURFACE};")

        if self.book_data.get('cover'):
            try:
                response = requests.get(self.book_data['cover'], headers=HEADERS, timeout=5)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if not pixmap.isNull():
                    cover_label.setPixmap(pixmap.scaled(150, 200, Qt.AspectRatioMode.KeepAspectRatio))
            except:
                cover_label.setText("")
        else:
            cover_label.setText("")

        top_layout.addWidget(cover_label)

        info_layout = QVBoxLayout()
        title = QLabel(self.book_data.get('title', 'Без названия'))
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {THEME_TEXT};")
        title.setWordWrap(True)
        info_layout.addWidget(title)

        if self.book_data.get('authors'):
            info_layout.addWidget(QLabel(f"{', '.join(self.book_data['authors'])}"))
        if self.book_data.get('genres'):
            info_layout.addWidget(QLabel(f"{', '.join(self.book_data['genres'])}"))

        series_info = []
        if self.book_data.get('series'):
            series_info.append(f"Серия: {self.book_data['series']}")
        if self.book_data.get('series_number'):
            series_info.append(f"Книга {self.book_data['series_number']}")
        if series_info:
            info_layout.addWidget(QLabel(' | '.join(series_info)))

        info_layout.addStretch()
        top_layout.addLayout(info_layout, 1)
        layout.addLayout(top_layout)

        desc_text = QTextEdit()
        desc_text.setReadOnly(True)
        desc_text.setPlainText(self.book_data.get('description', 'Описание отсутствует'))
        desc_text.setStyleSheet(f"background: {THEME_SURFACE}; border-radius: 5px; padding: 10px; font-size: 13px; color: {THEME_TEXT}; border: 1px solid {THEME_BORDER};")
        desc_text.setMinimumHeight(150)
        layout.addWidget(desc_text)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet(f"QPushButton{{padding:10px 30px;background:{THEME_SURFACE};color:{THEME_TEXT};border:1px solid {THEME_BORDER};border-radius:5px;font-weight:bold;}}QPushButton:hover{{border-color:{THEME_ACCENT};background:{THEME_BG};}}")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _download_from_searchfloor(self, book_data):
        sf_url = book_data.get('searchfloor_url')
        if not sf_url:
            return

        book_id_match = re.search(r'/b/(\d+)', sf_url)
        if not book_id_match:
            return

        title = re.sub(r'[<>:"/\\|?*]', '', book_data.get('title', 'book'))
        save_path = _resolve_save_path(self.config, f"{title}.zip")

        downloader = DownloadWorker(f"https://searchfloor.org/book/{book_id_match.group(1)}", save_path)
        downloader.finished.connect(lambda success, msg: _show_toast(
            self, "Успех" if success else "Ошибка",
            f"Книга сохранена:\n{msg}" if success else f"Не удалось скачать:\n{msg}",
            success=success))
        downloader.start()

    def _download_from_flibusta(self, book_data):
        download_urls = book_data.get('download_urls', [])
        if not download_urls:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {THEME_SURFACE}; border: 1px solid {THEME_BORDER}; border-radius: 5px; padding: 5px; }}
            QAction {{ color: {THEME_TEXT}; padding: 8px; }}
            QAction:hover {{ background: {THEME_ACCENT}; }}
        """)

        for item in download_urls:
            fmt = item.get('format', '').upper()
            action = menu.addAction(f"Скачать {fmt}")
            action.triggered.connect(lambda checked, url=item['url'], f=fmt: self._start_flibusta_download(url, f, book_data))

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _start_flibusta_download(self, url, fmt, book_data):
        extension = 'fb2.zip' if fmt.lower() == 'fb2' else fmt.lower()
        title = re.sub(r'[<>:"/\\|?*]', '', book_data.get('title', 'book'))

        save_path = _resolve_save_path(self.config, f"{title}.{extension}")

        downloader = FlibustaDownloadWorker(url, save_path)
        downloader.finished.connect(lambda success, msg: _show_toast(
            self, "Успех" if success else "Ошибка",
            f"Книга сохранена:\n{msg}" if success else f"Не удалось скачать:\n{msg}",
            success=success))
        downloader.start()


class SearchTab(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent = parent
        self.is_searching = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        search_label = QLabel("Введите название книги или серии")
        search_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {THEME_TEXT}; padding: 5px 0;")
        layout.addWidget(search_label)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Например: Мастер и Маргарита, Орудие смерти, Касандра Клэр...")
        self.search_input.setStyleSheet(f"QLineEdit{{padding:10px;border:2px solid {THEME_BORDER};border-radius:17px;font-size:14px;background:{THEME_BG};color:{THEME_TEXT};}}QLineEdit:focus{{border:2px solid {THEME_ACCENT};}}QLineEdit::placeholder{{color:{THEME_SUB};}}")
        self.search_input.returnPressed.connect(self.do_search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Найти")
        self.search_btn.setStyleSheet(f"QPushButton{{padding:10px 30px;background:{THEME_ACCENT};color:white;border:none;border-radius:17px;font-weight:bold;font-size:14px;}}QPushButton:hover{{background:#1557b0;}}QPushButton:disabled{{background:{THEME_BORDER};color:{THEME_SUB};}}")
        self.search_btn.clicked.connect(self.do_search)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        services_layout = QHBoxLayout()
        services_layout.setSpacing(15)
        services_layout.addWidget(QLabel("Искать на:"))

        self.chk_author = QCheckBox("Author.Today")
        self.chk_author.setChecked(True)
        services_layout.addWidget(self.chk_author)

        self.chk_searchfloor = QCheckBox("Цокольный этаж")
        self.chk_searchfloor.setChecked(True)
        services_layout.addWidget(self.chk_searchfloor)

        self.chk_moreknig = QCheckBox("MoreKnig")
        self.chk_moreknig.setChecked(True)
        services_layout.addWidget(self.chk_moreknig)

        self.chk_flibusta = QCheckBox("Флибуста")
        self.chk_flibusta.setChecked(True)
        services_layout.addWidget(self.chk_flibusta)

        services_layout.addStretch()
        layout.addLayout(services_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"border: none; background: {THEME_BG};")

        self.container = QWidget()
        self.container.setStyleSheet(f"background: {THEME_BG};")
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14)
        self.grid.setContentsMargins(16, 16, 16, 16)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.status = QLabel("Введите название книги или серии и нажмите «Найти»")
        self.status.setStyleSheet(f"padding: 10px; background: {THEME_SURFACE}; border-radius: 5px; font-size: 13px; color: {THEME_SUB};")
        layout.addWidget(self.status)

    def add_book_card(self, book):
        row = self.grid.rowCount()
        col = 0
        for r in range(row + 1):
            for c in range(6):
                if self.grid.itemAtPosition(r, c) is None:
                    row, col = r, c
                    break
            else:
                continue
            break

        card = BookCard(book, self.config)
        card.clicked.connect(self.show_book_details)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grid.addWidget(card, row, col)

    def show_book_details(self, book_data):
        dialog = BookDetailDialog(book_data, self.config, self)
        dialog.exec()

    def do_search(self):
        if self.is_searching:
            return

        query = self.search_input.text().strip()
        if not query:
            self.status.setText("Введите название книги или серии")
            self.status.setStyleSheet(f"padding: 10px; background: #fdebd0; border-radius: 5px; font-size: 13px; color: #e74c3c;")
            return

        # Очистка сетки
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget:
                widget.deleteLater()

        self.is_searching = True
        self.search_btn.setEnabled(False)
        self.status.setText(f"Поиск: {query}...")
        self.status.setStyleSheet(f"padding: 10px; background: {THEME_SURFACE}; border-radius: 5px; font-size: 13px; color: {THEME_TEXT};")

        services = []
        if self.chk_author.isChecked(): services.append('author')
        if self.chk_searchfloor.isChecked(): services.append('searchfloor')
        if self.chk_moreknig.isChecked(): services.append('moreknig')
        if self.chk_flibusta.isChecked(): services.append('flibusta')

        if not services:
            self.status.setText("Выберите хотя бы один сервис для поиска")
            self.status.setStyleSheet(f"padding: 10px; background: #fdebd0; border-radius: 5px; font-size: 13px; color: #e74c3c;")
            self.is_searching = False
            self.search_btn.setEnabled(True)
            return

        self.loader = SearchLoader(query, services)
        self.loader.book_ready.connect(self.add_book_card)
        self.loader.finished.connect(self.on_search_finished)
        self.loader.start()

    def on_search_finished(self, total_count):
        self.is_searching = False
        self.search_btn.setEnabled(True)

        if total_count == 0:
            self.status.setText("Книги не найдены. Попробуйте изменить запрос.")
            self.status.setStyleSheet(f"padding: 10px; background: #fdebd0; border-radius: 5px; font-size: 13px; color: #e74c3c;")
        else:
            self.status.setText(f"Найдено {total_count} уникальных книг")
            self.status.setStyleSheet(f"padding: 10px; background: #d5f5e3; border-radius: 5px; font-size: 13px; color: #27ae60;")


class SearchLoader(QThread):
    book_ready = pyqtSignal(dict)
    finished = pyqtSignal(int)

    def __init__(self, query, services=None):
        super().__init__()
        self.query = query
        self.services = services or ['author', 'searchfloor', 'moreknig', 'flibusta']

    def run(self):
        parser = BookParser()

        def on_book_found(book):
            self.book_ready.emit(book)

        total = 0

        if 'author' in self.services:
            books = parser.search_books(self.query, limit=100, max_pages=10, callback=on_book_found)
            total += len(books)

        if 'moreknig' in self.services:
            moreknig_books = parser.search_on_moreknig(self.query, limit=30, callback=on_book_found)
            total += len(moreknig_books)

        if 'flibusta' in self.services:
            # Используем новый метод с корректным обходом серий
            flibusta_books = parser.search_on_flibusta(self.query, limit=30, callback=on_book_found)
            total += len(flibusta_books)

        self.finished.emit(total)


class BookSearchWindow(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Поиск книг - Author.Today + Цокольный этаж + MoreKnig + Флибуста")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(f"background: {THEME_BG}; color: {THEME_TEXT};")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Поиск книг")
        header.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {THEME_TEXT}; padding: 10px;")
        layout.addWidget(header)

        desc = QLabel("Поиск выполняется на Author.Today, Цокольном этаже, MoreKnig и Флибусте. Поддерживается поиск по сериям книг.")
        desc.setStyleSheet(f"font-size: 12px; color: {THEME_SUB}; padding: 0 10px 10px 10px;")
        layout.addWidget(desc)

        self.search_tab = SearchTab(self.config, self)
        layout.addWidget(self.search_tab)


def create_search_button(config=None, parent=None):
    """Создаёт кнопку поиска книг для тулбара библиотеки"""
    from PyQt6.QtWidgets import QToolButton

    has_mi = 'Material Icons' in QFontDatabase.families()
    icon_label = 'search' if has_mi else '🔍'
    font_family = "'Material Icons'" if has_mi else "sans-serif"
    font_size = 18

    btn = QToolButton()
    btn.setText(icon_label)
    btn.setToolTip("Поиск книг (Author.Today + Цокольный этаж + MoreKnig + Флибуста)")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFont(QFont(font_family, font_size))

    btn_style = (
        f"QToolButton {{"
        f"border:none;background:transparent;padding:8px;"
        f"border-radius:18px;color:{THEME_SUB};"
        f"font-family:{font_family};font-size:{font_size}px;"
        f"}}"
        f"QToolButton:hover{{background:rgba(255,255,255,0.08);color:{THEME_TEXT};}}"
    )
    btn.setStyleSheet(btn_style)

    return btn

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    app.setStyleSheet(f"""
        QWidget {{ font-family: 'Segoe UI', Arial, sans-serif; background: {THEME_BG}; color: {THEME_TEXT}; }}
        QScrollArea {{ border: none; background: {THEME_BG}; }}
        QScrollBar:vertical {{ border: none; background: {THEME_SURFACE}; width: 8px; border-radius: 4px; }}
        QScrollBar::handle:vertical {{ background: {THEME_BORDER}; border-radius: 4px; min-height: 20px; }}
        QScrollBar::handle:vertical:hover {{ background: {THEME_ACCENT}; }}
        QLineEdit {{ padding: 10px; border: 2px solid {THEME_BORDER}; border-radius: 17px; font-size: 14px; background: {THEME_BG}; color: {THEME_TEXT}; }}
        QLineEdit:focus {{ border: 2px solid {THEME_ACCENT}; }}
        QLineEdit::placeholder {{ color: {THEME_SUB}; }}
        QPushButton {{ padding: 10px 30px; background: {THEME_ACCENT}; color: white; border: none; border-radius: 17px; font-weight: bold; }}
        QPushButton:hover {{ background: #1557b0; }}
        QPushButton:disabled {{ background: {THEME_BORDER}; color: {THEME_SUB}; }}
        QLabel {{ background: transparent; color: {THEME_TEXT}; }}
    """)

    window = BookSearchWindow()
    window.show()

    sys.exit(app.exec())
