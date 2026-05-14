"""
book_normalizer.py — нормализатор книг для корректной работы TTS.

Исправляет структурные проблемы FB2/EPUB/MOBI, которые приводят к:
- пропуску блоков текста при TTS-воспроизведении
- отсутствию подсветки первой строки
- зависанию на старте с первой страницы

Запускается из контекстного меню библиотеки.
"""

import re
import sys
import zipfile
import shutil
from pathlib import Path
from typing import Callable

# ──────────────────────────────────────────────────────────────
# FB2
# ──────────────────────────────────────────────────────────────

def normalize_fb2(src: Path, dst: Path, log: Callable[[str], None] = print) -> bool:
    """
    Нормализует FB2-файл:
    1. Разделяет теги <title> и следующий <p> если они слиплись на одной строке
    2. Выносит <p> из тела <title> в соседние узлы секции
    3. Удаляет предисловия пиратских распространителей (включая Nota bene, searchfloor.org)
    4. Нормализует пустые строки и пробелы
    """
    try:
        log(" Читаем FB2...")
        text = src.read_text(encoding='utf-8', errors='replace')
        original_len = len(text)
        changes = 0

        # 1. Разбиваем слипшиеся теги на отдельные строки для читаемости
        new_text, n = re.subn(r'(</title>)(<(?:p|section|epigraph|subtitle|empty-line))', 
                               r'\1\n\2', text)
        if n:
            log(f"   Разделены слипшиеся </title><tag>: {n} случаев")
            changes += n
            text = new_text

        # 2. Основная проблема: <p> с телом текста внутри <title>
        def fix_title_with_body(m):
            nonlocal changes
            inner = m.group(1)
            paragraphs = re.findall(r'<p[^>]*>.*?</p>', inner, re.DOTALL)
            if len(paragraphs) <= 1:
                return m.group(0)
            title_p   = paragraphs[0]
            body_ps   = paragraphs[1:]
            real_body = [p for p in body_ps 
                         if len(re.sub(r'<[^>]+>', '', p).strip()) > 60]
            if not real_body:
                return m.group(0)
            log(f"   Вынесен текст из <title>: {len(real_body)} абзацев")
            changes += len(real_body)
            kept_in_title = [p for p in body_ps if p not in real_body]
            new_title = f"<title>{title_p}{''.join(kept_in_title)}</title>"
            return new_title + '\n' + '\n'.join(real_body)

        text = re.sub(r'<title>(.*?)</title>', fix_title_with_body, text, flags=re.DOTALL)

        # 3. Удаляем блоки-предисловия пиратских распространителей
        distributor_phrases = [
            'цокольный этаж', 'сайт заблокирован', 'censor.tracker',
            'антизапретом', 'телеграм-бот', 'telegram-бот',
            'наградите автора лайком', 'понравилась книга',
            'liters.ru', 'litres.ru',
            'nota bene', 'нота бене', 'searchfloor.org', 'с вами был',
            'бесплатные книги', 'скачать бесплатно', 'электронная библиотека',
        ]
        
        def remove_distributor_section(m):
            nonlocal changes
            content = m.group(0).lower()
            
            # Специальная проверка на "Nota bene" и "С вами был"
            if 'nota bene' in content or 'нота бене' in content:
                log(f"   Удалена секция Nota bene")
                changes += 1
                return ''
            
            if 'с вами был' in content and ('searchfloor' in content or 'бесплатных книг' in content):
                log(f"   Удалена секция с сайтом searchfloor.org")
                changes += 1
                return ''
            
            for phrase in distributor_phrases:
                if phrase in content:
                    if len(content) < 5000:
                        log(f"   Удалена секция распространителя ({phrase!r})")
                        changes += 1
                        return ''
            return m.group(0)

        text = re.sub(r'<section>.*?</section>', remove_distributor_section, 
                      text, flags=re.DOTALL | re.IGNORECASE)

        # 4. Убираем двойные пустые строки
        text = re.sub(r'\n{3,}', '\n\n', text)

        if changes == 0:
            log("  ℹ Структурных проблем не обнаружено — файл и так корректен")
        
        log(f"   Изменений: {changes}, размер: {original_len} → {len(text)} байт")
        dst.write_text(text, encoding='utf-8')
        log(f" FB2 сохранён: {dst.name}")
        return True

    except Exception as e:
        log(f" Ошибка нормализации FB2: {e}")
        import traceback; traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────
# EPUB
# ──────────────────────────────────────────────────────────────

def normalize_epub(src: Path, dst: Path, log: Callable[[str], None] = print) -> bool:
    """
    Нормализует EPUB-файл:
    1. Обходит все HTML/XHTML файлы внутри ZIP
    2. Исправляет заголовки h1-h6 со встроенным телом текста
    3. Гарантирует что body-текст не находится внутри <hN> элементов
    4. Удаляет секции пиратских распространителей (включая Nota bene, searchfloor.org)
    """
    try:
        import zipfile as zf

        log(" Читаем EPUB...")
        shutil.copy2(src, dst)
        
        changes_total = 0

        with zf.ZipFile(dst, 'r') as z_in:
            names = z_in.namelist()
            html_files = [n for n in names 
                          if n.lower().endswith(('.html', '.xhtml', '.htm'))]
            log(f"   Найдено HTML-файлов: {len(html_files)}")

        # Перезаписываем ZIP с исправленными файлами
        tmp = dst.with_suffix('.tmp.epub')
        with zf.ZipFile(src, 'r') as z_in, zf.ZipFile(tmp, 'w', zf.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                data = z_in.read(item.filename)
                
                if item.filename in html_files:
                    try:
                        html = data.decode('utf-8', errors='replace')
                        fixed, n = _fix_epub_html(html, item.filename, log)
                        changes_total += n
                        data = fixed.encode('utf-8')
                    except Exception as e:
                        log(f"   Ошибка в {item.filename}: {e}")
                
                z_out.writestr(item, data)

        tmp.replace(dst)
        
        if changes_total == 0:
            log("  ℹ Структурных проблем не обнаружено — файл и так корректен")
        
        log(f" EPUB сохранён: {dst.name} (изменений: {changes_total})")
        return True

    except Exception as e:
        log(f" Ошибка нормализации EPUB: {e}")
        import traceback; traceback.print_exc()
        if dst.exists():
            dst.unlink(missing_ok=True)
        return False


def _fix_epub_html(html: str, filename: str, log: Callable) -> tuple[str, int]:
    """Исправляет HTML-файл внутри EPUB. Возвращает (новый HTML, кол-во изменений)."""
    changes = 0

    # 1. Текст внутри <h1>-<h6> вместе с <p> — <p> выносим наружу
    def fix_heading_with_body(m):
        nonlocal changes
        tag   = m.group(1)
        attrs = m.group(2)
        inner = m.group(3)
        
        p_blocks = re.findall(r'<p[^>]*>.*?</p>', inner, re.DOTALL)
        if not p_blocks:
            return m.group(0)
        
        inner_clean = re.sub(r'<p[^>]*>.*?</p>', '', inner, flags=re.DOTALL).strip()
        real_body = [p for p in p_blocks 
                     if len(re.sub(r'<[^>]+>', '', p).strip()) > 60]
        if not real_body:
            return m.group(0)
        
        log(f"     {filename}: вынесен текст из <{tag}>: {len(real_body)} абзацев")
        changes += len(real_body)
        heading = f"<{tag}{attrs}>{inner_clean}</{tag}>"
        return heading + '\n' + '\n'.join(real_body)

    html = re.sub(
        r'<(h[1-6])([^>]*)>(.*?)</h[1-6]>',
        fix_heading_with_body,
        html, flags=re.DOTALL | re.IGNORECASE
    )

    # 2. Удаляем секции распространителей (включая Nota bene, searchfloor.org)
    distributor_phrases = [
        'цокольный этаж', 'censor.tracker', 'антизапретом',
        'наградите автора лайком', 'litres.ru', 'liters.ru',
        'nota bene', 'нота бене', 'searchfloor.org', 'с вами был',
        'бесплатные книги', 'скачать бесплатно', 'электронная библиотека',
    ]
    
    def remove_distributor_div(m):
        nonlocal changes
        content = m.group(0).lower()
        
        # Специальная проверка на "Nota bene"
        if 'nota bene' in content or 'нота бене' in content:
            log(f"     {filename}: удалена секция Nota bene")
            changes += 1
            return ''
        
        if 'с вами был' in content and ('searchfloor' in content or 'бесплатных книг' in content):
            log(f"     {filename}: удалена секция с сайтом searchfloor.org")
            changes += 1
            return ''
        
        for phrase in distributor_phrases:
            if phrase in content:
                if len(content) < 5000:
                    log(f"     {filename}: удалена секция распространителя ({phrase!r})")
                    changes += 1
                    return ''
        return m.group(0)

    html = re.sub(r'<(?:div|section|article)[^>]*>.*?</(?:div|section|article)>',
                  remove_distributor_div, html, flags=re.DOTALL | re.IGNORECASE)

    return html, changes


# ──────────────────────────────────────────────────────────────
# MOBI / AZW3
# ──────────────────────────────────────────────────────────────

def normalize_mobi(src: Path, dst: Path, log: Callable[[str], None] = print) -> bool:
    """
    Нормализует MOBI/AZW3:
    Конвертирует в EPUB через mobi Python-библиотеку,
    затем применяет нормализацию EPUB.
    """
    try:
        log(" MOBI: пробуем извлечь через mobi...")
        try:
            import mobi
        except ImportError:
            log("   Библиотека mobi не установлена. Устанавливаем...")
            import subprocess, sys
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mobi', '--quiet'])
            import mobi

        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            log("   Извлекаем MOBI...")
            
            # Пробуем разные способы вызова mobi.extract
            result_dir = None
            try:
                # Способ 1: без параметров (возвращает временную папку)
                result_dir = mobi.extract(str(src))
            except TypeError:
                try:
                    # Способ 2: параметр outdir
                    result_dir = mobi.extract(str(src), outdir=tmp_dir)
                except TypeError:
                    # Способ 3: параметр output_dir (старая версия)
                    result_dir = mobi.extract(str(src), output_dir=tmp_dir)
            
            if not result_dir:
                log("   Не удалось извлечь MOBI")
                return False
            
            result_path = Path(result_dir)
            
            # Ищем EPUB внутри
            epub_files = list(result_path.rglob('*.epub'))
            if epub_files:
                epub_src = epub_files[0]
                log(f"   Найден EPUB внутри MOBI: {epub_src.name}")
                epub_dst = dst.with_suffix('.epub')
                return normalize_epub(epub_src, epub_dst, log)
            
            # Если EPUB нет — ищем HTML
            html_files = list(result_path.rglob('*.html')) + list(result_path.rglob('*.htm'))
            if html_files:
                log(f"   Найдено HTML файлов: {len(html_files)}, собираем EPUB...")
                epub_dst = dst.with_suffix('.epub')
                _pack_html_to_epub(html_files, result_path, epub_dst, log)
                return normalize_epub(epub_dst, epub_dst, log)
            
            log("   Не удалось извлечь содержимое MOBI")
            return False

    except Exception as e:
        log(f" Ошибка нормализации MOBI: {e}")
        import traceback; traceback.print_exc()
        return False


def _pack_html_to_epub(html_files: list, base_dir: Path, dst: Path, log: Callable):
    """Упаковывает HTML-файлы в минимальный EPUB."""
    import zipfile as zf
    with zf.ZipFile(dst, 'w', zf.ZIP_DEFLATED) as z:
        # mimetype — первым, без сжатия
        z.writestr(zf.ZipInfo('mimetype'), b'application/epub+zip')
        # META-INF/container.xml
        container = '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
        z.writestr('META-INF/container.xml', container)
        # Копируем HTML-файлы
        manifest_items = []
        spine_items    = []
        for i, hf in enumerate(sorted(html_files)):
            arcname = f'OEBPS/chapter{i:03d}.xhtml'
            z.write(hf, arcname)
            manifest_items.append(f'<item id="c{i}" href="chapter{i:03d}.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="c{i}"/>')
        # content.opf
        opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Book</dc:title></metadata>
<manifest>{''.join(manifest_items)}</manifest>
<spine>{''.join(spine_items)}</spine>
</package>'''
        z.writestr('OEBPS/content.opf', opf)
    log(f"   Упакован EPUB: {dst.name}")


# ──────────────────────────────────────────────────────────────
# Универсальный вход
# ──────────────────────────────────────────────────────────────

SUPPORTED = {'.fb2', '.epub', '.mobi', '.azw3'}


def normalize_book(src_path: str, dst_path: str,
                   log: Callable[[str], None] = print) -> bool:
    """
    Нормализует книгу src_path и сохраняет в dst_path.
    Поддерживает: FB2, EPUB, MOBI, AZW3.
    Возвращает True при успехе.
    """
    src = Path(src_path)
    dst = Path(dst_path)

    if not src.exists():
        log(f" Файл не найден: {src}")
        return False

    ext = src.suffix.lower()

    if ext not in SUPPORTED:
        log(f" Формат {ext} не поддерживается (только FB2, EPUB, MOBI, AZW3)")
        return False

    log(f" Нормализация: {src.name}")
    log(f"   Формат: {ext.upper()}")
    log(f"   Сохранение: {dst}")
    log("─" * 50)

    if ext == '.fb2':
        return normalize_fb2(src, dst, log)
    elif ext == '.epub':
        return normalize_epub(src, dst, log)
    elif ext in ('.mobi', '.azw3'):
        return normalize_mobi(src, dst, log)

    return False

# ──────────────────────────────────────────────────────────────
# КОНВЕРТАЦИЯ
# ──────────────────────────────────────────────────────────────

CONVERT_FORMATS = ['epub', 'fb2', 'mobi', 'azw3', 'txt', 'pdf']

def _find_calibre() -> str | None:
    """Возвращает путь к ebook-convert Calibre или None."""
    import shutil
    candidates = ['ebook-convert']
    if sys.platform == 'win32':
        candidates += [
            r'C:\Program Files\Calibre2\ebook-convert.exe',
            r'C:\Program Files (x86)\Calibre2\ebook-convert.exe',
        ]
    elif sys.platform == 'darwin':
        candidates += ['/Applications/calibre.app/Contents/MacOS/ebook-convert']
    else:
        candidates += ['/usr/bin/ebook-convert', '/usr/local/bin/ebook-convert',
                       '/opt/calibre/ebook-convert']
    for c in candidates:
        found = shutil.which(c) or (Path(c).exists() and c)
        if found:
            return str(found)
    return None


def _find_fb2c() -> Path | None:
    """
    Ищет бинарник fb2c в папке tools/fb2c/ рядом с программой.
    Оба бинарника лежат в одной папке — программа сама выбирает нужный:
        tools/fb2c/fb2c          (Linux)
        tools/fb2c/fb2c.exe      (Windows)
    """
    import stat as _stat
    base = Path(__file__).parent
    fb2c_dir = base / 'tools' / 'fb2c'

    binary = fb2c_dir / ('fb2c.exe' if sys.platform == 'win32' else 'fb2c')
    if binary.exists():
        if sys.platform != 'win32':
            try:
                binary.chmod(binary.stat().st_mode | _stat.S_IEXEC)
            except Exception:
                pass
        return binary
    return None


def convert_fb2_to_epub(src: Path, dst: Path,
                        log: Callable[[str], None] = print,
                        stop_flag: list | None = None) -> bool:
    """
    Встроенный конвертер FB2 -> EPUB.
    Нулевые зависимости — только стандартная библиотека Python.
    Работает на любом Python 3.8+.
    """
    import re, zipfile, base64, html as _html, uuid
    from xml.etree import ElementTree as ET

    FBns  = 'http://www.gribuser.ru/xml/fictionbook/2.0'
    XLns  = 'http://www.w3.org/1999/xlink'
    NL    = '\n'

    def fb(tag):
        return '{' + FBns + '}' + tag

    def xl(tag):
        return '{' + XLns + '}' + tag

    def get_text(el, tag):
        child = el.find(fb(tag)) if el is not None else None
        return (child.text or '').strip() if child is not None else ''

    def esc(s):
        return _html.escape(s or '')

    def inner_html(el):
        """Сериализует текст и дочерние элементы в HTML."""
        TAG = {
            fb('strong'):      'strong',
            fb('emphasis'):    'em',
            fb('strikethrough'): 's',
            fb('sub'):         'sub',
            fb('sup'):         'sup',
            fb('code'):        'code',
        }
        parts = [esc(el.text or '')]
        for child in el:
            ctag = child.tag
            if ctag == fb('image'):
                href = child.get(xl('href'), '')
                alt  = esc(child.get('alt', ''))
                if href.startswith('#'):
                    src = href[1:]
                    parts.append('<img src="images/' + src + '" alt="' + alt + '"/>')
            elif ctag == fb('a'):
                href = child.get(xl('href'), '')
                parts.append('<a href="' + esc(href) + '">' + inner_html(child) + '</a>')
            elif ctag in TAG:
                t = TAG[ctag]
                parts.append('<' + t + '>' + inner_html(child) + '</' + t + '>')
            else:
                parts.append(inner_html(child))
            parts.append(esc(child.tail or ''))
        return ''.join(parts)

    def section_to_html(sec, depth=0):
        parts = []
        sec_id = sec.get('id', '')
        for child in sec:
            ctag = child.tag
            if ctag == fb('title'):
                level = min(depth + 2, 5)
                h = 'h' + str(level)
                t_id = child.get('id', '')
                id_attr = ' id="' + esc(t_id) + '"' if t_id else ''
                parts.append('<' + h + id_attr + '>' + inner_html(child) + '</' + h + '>')
            elif ctag == fb('p'):
                p_id = child.get('id', '')
                id_attr = ' id="' + esc(p_id) + '"' if p_id else ''
                parts.append('<p' + id_attr + '>' + inner_html(child) + '</p>')
            elif ctag == fb('empty-line'):
                parts.append('<p class="empty-line"> </p>')
            elif ctag == fb('image'):
                href = child.get(xl('href'), '')
                alt  = esc(child.get('alt', ''))
                if href.startswith('#'):
                    src = href[1:]
                    parts.append('<img src="images/' + src + '" alt="' + alt + '"/>')
            elif ctag == fb('epigraph'):
                parts.append('<blockquote class="epigraph">' + inner_html(child) + '</blockquote>')
            elif ctag == fb('cite'):
                parts.append('<blockquote>' + inner_html(child) + '</blockquote>')
            elif ctag == fb('subtitle'):
                parts.append('<h3>' + inner_html(child) + '</h3>')
            elif ctag == fb('poem'):
                poem_parts = ['<div class="poem">']
                for pc in child:
                    if pc.tag == fb('stanza'):
                        poem_parts.append('<div class="stanza">')
                        for v in pc.findall(fb('v')):
                            poem_parts.append('<p class="verse-line">' + inner_html(v) + '</p>')
                        poem_parts.append('</div>')
                    elif pc.tag == fb('title'):
                        poem_parts.append('<h4>' + inner_html(pc) + '</h4>')
                    elif pc.tag == fb('text-author'):
                        poem_parts.append('<p class="text-author">' + inner_html(pc) + '</p>')
                poem_parts.append('</div>')
                parts.append(''.join(poem_parts))
            elif ctag == fb('section'):
                parts.append(section_to_html(child, depth + 1))
            elif ctag == fb('table'):
                rows = []
                for row in child.findall(fb('tr')):
                    cells = []
                    for cell in row:
                        ct = 'th' if cell.tag == fb('th') else 'td'
                        cells.append('<' + ct + '>' + inner_html(cell) + '</' + ct + '>')
                    rows.append('<tr>' + ''.join(cells) + '</tr>')
                parts.append('<table>' + ''.join(rows) + '</table>')
            elif ctag == fb('annotation'):
                parts.append('<aside>' + inner_html(child) + '</aside>')

        id_attr = ' id="' + esc(sec_id) + '"' if sec_id else ''
        return '<section' + id_attr + '>' + NL + NL.join(parts) + NL + '</section>'

    CSS = (
        'body{font-family:serif;margin:1em 2em;line-height:1.6}' + NL +
        'h1,h2,h3,h4,h5{text-align:center;margin:1em 0 .5em}' + NL +
        'p{text-indent:1em;margin:0}' + NL +
        'p.empty-line{text-indent:0;margin:.5em 0}' + NL +
        '.poem{margin:1em 2em}.stanza{margin-bottom:.5em}' + NL +
        'p.verse-line{text-indent:0;margin:0}' + NL +
        'p.text-author{text-align:right;font-style:italic}' + NL +
        'blockquote{margin:1em 2em;border-left:3px solid #ccc;padding-left:1em}' + NL +
        'img{max-width:100%;display:block;margin:1em auto}' + NL +
        'table{border-collapse:collapse;width:100%}' + NL +
        'td,th{border:1px solid #ccc;padding:.3em .5em}' + NL
    )

    def make_xhtml(body_content, doc_title, lang):
        return (
            '<?xml version="1.0" encoding="utf-8"?>' + NL +
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="' + lang + '">' + NL +
            '<head><meta charset="utf-8"/>' + NL +
            '<title>' + esc(doc_title) + '</title>' + NL +
            '<link rel="stylesheet" type="text/css" href="../styles/main.css"/>' + NL +
            '</head>' + NL +
            '<body>' + NL + body_content + NL + '</body>' + NL + '</html>' + NL
        )

    try:
        log(' Читаем FB2 (' + str(src.stat().st_size // 1024) + ' КБ)...')

        raw = src.read_bytes()
        # Убираем нулевые байты если есть
        if b'\x00' in raw:
            raw = raw.replace(b'\x00', b'')

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            log('  XML ошибка: ' + str(e) + ', пробуем восстановить...')
            # Убираем невалидные XML-символы
            raw = re.sub(rb'[\x01-\x08\x0b\x0c\x0e-\x1f]', b'', raw)
            root = ET.fromstring(raw)

        log('    XML разобран')
        if stop_flag and stop_flag[0]:
            return False

        ti    = root.find('.//' + fb('title-info'))
        title = get_text(ti, 'book-title') if ti else src.stem
        lang  = get_text(ti, 'lang') if ti else 'ru'
        if not lang:
            lang = 'ru'
        book_uuid = str(uuid.uuid4())

        authors = []
        if ti:
            for a in ti.findall(fb('author')):
                parts = [get_text(a, x) for x in ('first-name', 'middle-name', 'last-name')]
                name = ' '.join(p for p in parts if p)
                if name:
                    authors.append(name)
        author_str = ', '.join(authors) or 'Unknown'
        log('    ' + title + ' / ' + author_str)

        # Изображения
        images = {}
        for binary in root.findall('.//' + fb('binary')):
            img_id  = binary.get('id', '')
            ctype   = binary.get('content-type', 'image/jpeg')
            b64data = (binary.text or '').replace('\n', '').replace(' ', '')
            if img_id and b64data:
                try:
                    images[img_id] = (ctype, base64.b64decode(b64data))
                except Exception:
                    pass
        log('     Изображений: ' + str(len(images)))

        if stop_flag and stop_flag[0]:
            return False

        # Обложка
        cover_id = None
        cov_el = root.find('.//' + fb('coverpage') + '/' + fb('image'))
        if cov_el is None:
            cov_el = root.find('.//' + fb('coverpage') + '//' + fb('image'))
        if cov_el is not None:
            href = cov_el.get(xl('href'), '')
            if href.startswith('#'):
                cover_id = href[1:]

        # Секции
        chapters = []
        bodies = root.findall('.//' + fb('body'))
        for bi, body in enumerate(bodies):
            is_notes = body.get('name', '') == 'notes'
            sections = body.findall(fb('section'))
            for si, sec in enumerate(sections):
                if stop_flag and stop_flag[0]:
                    return False
                title_el = sec.find(fb('title'))
                if title_el is not None:
                    sec_title = re.sub(r'<[^>]+>', '', inner_html(title_el)).strip()
                    sec_title = re.sub(r'\s+', ' ', sec_title)
                else:
                    sec_title = 'Примечания' if is_notes else ('Глава ' + str(si + 1))
                fname    = 'chapter_' + str(bi).zfill(2) + '_' + str(si).zfill(4) + '.xhtml'
                body_html = section_to_html(sec)
                xhtml    = make_xhtml(body_html, sec_title or title, lang)
                chapters.append((fname, sec_title, xhtml, is_notes))
                if (si + 1) % 20 == 0:
                    log('    Секций: ' + str(si + 1) + '/' + str(len(sections)))

        log('    Секций: ' + str(len(chapters)))
        if stop_flag and stop_flag[0]:
            return False

        # Пишем EPUB
        log('    Упаковываем EPUB...')
        with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(zipfile.ZipInfo('mimetype'),
                        b'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', (
                '<?xml version="1.0"?>' + NL +
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">' + NL +
                '<rootfiles>' + NL +
                '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>' + NL +
                '</rootfiles>' + NL + '</container>' + NL
            ))
            zf.writestr('OEBPS/styles/main.css', CSS)

            for img_id, (ctype, data) in images.items():
                zf.writestr('OEBPS/images/' + img_id, data)

            for fname, ch_title, xhtml, _ in chapters:
                zf.writestr('OEBPS/Text/' + fname, xhtml.encode('utf-8'))

            manifest = ['<item id="css" href="styles/main.css" media-type="text/css"/>']
            spine    = []
            for img_id, (ctype, _) in images.items():
                props = ' properties="cover-image"' if img_id == cover_id else ''
                manifest.append(
                    '<item id="img_' + img_id + '" href="images/' + img_id + '" '
                    'media-type="' + ctype + '"' + props + '/>')
            for i, (fname, _, _, is_notes) in enumerate(chapters):
                iid = 'ch' + str(i).zfill(4)
                lin = ' linear="no"' if is_notes else ''
                manifest.append('<item id="' + iid + '" href="Text/' + fname +
                                '" media-type="application/xhtml+xml"/>')
                spine.append('<itemref idref="' + iid + '"' + lin + '/>')

            toc_items = []
            play_order = 1
            for i, (fname, ch_title, _, is_notes) in enumerate(chapters):
                if not is_notes and ch_title:
                    toc_items.append(
                        '<navPoint id="nav' + str(i) + '" playOrder="' + str(play_order) + '">' + NL +
                        '<navLabel><text>' + esc(ch_title[:80]) + '</text></navLabel>' + NL +
                        '<content src="Text/' + fname + '"/>' + NL + '</navPoint>')
                    play_order += 1

            cover_meta = ('<meta name="cover" content="img_' + cover_id + '"/>' if cover_id else '')
            opf = (
                '<?xml version="1.0" encoding="utf-8"?>' + NL +
                '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">' + NL +
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">' + NL +
                '<dc:title>' + esc(title) + '</dc:title>' + NL +
                '<dc:creator>' + esc(author_str) + '</dc:creator>' + NL +
                '<dc:language>' + lang + '</dc:language>' + NL +
                '<dc:identifier id="BookId">urn:uuid:' + book_uuid + '</dc:identifier>' + NL +
                cover_meta + NL +
                '</metadata>' + NL +
                '<manifest>' + NL + NL.join(manifest) + NL +
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>' + NL +
                '</manifest>' + NL +
                '<spine toc="ncx">' + NL + NL.join(spine) + NL + '</spine>' + NL +
                '</package>' + NL
            )
            zf.writestr('OEBPS/content.opf', opf.encode('utf-8'))

            ncx = (
                '<?xml version="1.0" encoding="utf-8"?>' + NL +
                '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">' + NL +
                '<head><meta name="dtb:uid" content="urn:uuid:' + book_uuid + '"/></head>' + NL +
                '<docTitle><text>' + esc(title) + '</text></docTitle>' + NL +
                '<navMap>' + NL + NL.join(toc_items) + NL + '</navMap>' + NL +
                '</ncx>' + NL
            )
            zf.writestr('OEBPS/toc.ncx', ncx.encode('utf-8'))

        size_kb = dst.stat().st_size // 1024
        log(' EPUB сохранён: ' + dst.name + ' (' + str(size_kb) + ' КБ)')
        return True

    except Exception as e:
        log(' Ошибка конвертации FB2→EPUB: ' + str(e))
        import traceback; traceback.print_exc()
        if dst.exists():
            dst.unlink(missing_ok=True)
        return False


def convert_book_fb2c(src: Path, dst_dir: Path,
                      out_fmt: str = 'epub',
                      log: Callable[[str], None] = print,
                      stop_flag: list | None = None) -> Path | None:
    """
    Конвертирует FB2 через fb2c (rupor-github/fb2c).
    Бинарник должен лежать в tools/fb2c/fb2c(.exe).

    Команда: fb2c convert --nodirs --to epub <src.fb2> <tmp_dir/>
    fb2c пишет во временную папку (ext4/tmpfs) — там нет ограничений NTFS.
    После конвертации файл переименовывается (_safe_name) и перемещается в dst_dir.
    Возвращает Path к результирующему файлу или None при ошибке.
    """
    import subprocess, tempfile, shutil, re as _re, unicodedata as _ud, os

    fb2c = _find_fb2c()
    if not fb2c:
        log(" fb2c не найден.")
        log("   Скачайте бинарник: https://github.com/rupor-github/fb2c/releases")
        log("   Положите в папку: tools/fb2c/fb2c (Linux) или tools/fb2c/fb2c.exe (Windows)")
        return None

    dst_dir.mkdir(parents=True, exist_ok=True)
    log(f" fb2c: {src.name} → {out_fmt.upper()}")

    def _safe_filename(name: str, max_len: int = 180) -> str:
        """Очистить имя файла от символов, недопустимых на NTFS."""
        name = "".join(ch for ch in name
                       if _ud.category(ch) not in ("Cc", "Cf") and ord(ch) >= 0x20)
        FORBIDDEN = set('<>:"/\\|?*\'&;=+,[]{|}^%@!~`')
        name = "".join("_" if ch in FORBIDDEN else ch for ch in name)
        name = _re.sub(r'_+', '_', name)
        name = _re.sub(r' +', ' ', name)
        name = name.strip(". ")
        return name[:max_len] or "book"

    # Конфиг fb2c хранится в папке конфигурации NovaReader:
    #   Linux:   ~/.config/NovaReader/fb2c.yaml
    #   Windows: %APPDATA%/NovaReader/fb2c.yaml
    if sys.platform == 'win32':
        _base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        _base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    cfg_path = _base / 'NovaReader' / 'novareader.yaml'
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if not cfg_path.exists():
        cfg_path.write_text(
            "document:\n"
            "  output_name_template: |\n"
            "    {{- with first .Authors -}}{{- .LastName -}}"
            " - {{- end -}}{{- .Title -}}\n",
            encoding="utf-8")
        log(f"   Создан конфиг: {cfg_path}")

    # Конвертируем во временную папку.
    # Linux/Mac: /tmp — ext4/tmpfs, любые символы допустимы.
    # Windows: fb2c сам не добавляет кавычки благодаря конфигу.
    # _safe_filename дополнительно чистит результат для NTFS3.
    with tempfile.TemporaryDirectory(prefix="novareader_fb2c_") as tmp_str:
        tmp_dir = Path(tmp_str)
        tmp_out = tmp_dir / "out"
        tmp_out.mkdir()

        cmd = [
            str(fb2c),
            '--config', str(cfg_path),
            'convert',
            '--nodirs',
            '--ow',
            '--to', out_fmt,
            str(src),
            str(tmp_out),
        ]

        try:
            kwargs = {}
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **kwargs,
            )

            last_status = ''
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if line != last_status:
                    log(f"   {line}")
                    last_status = line
                if stop_flag and stop_flag[0]:
                    proc.terminate()
                    log(" Отменено")
                    return None

            proc.wait()

            if proc.returncode != 0:
                log(f" fb2c вернул код {proc.returncode}")
                return None

            # Ищем созданный файл в папке вывода
            ext = '.' + out_fmt
            results = list(tmp_out.glob(f'*{ext}'))
            if not results:
                log(f" Результат не найден во временной папке")
                return None

            tmp_result = max(results, key=lambda p: p.stat().st_mtime)

            # Очищаем имя файла от символов, запрещённых NTFS3
            clean_stem = _safe_filename(tmp_result.stem)
            clean_name = clean_stem + tmp_result.suffix
            final_path = dst_dir / clean_name

            # Если имя изменилось — сообщаем
            if clean_name != tmp_result.name:
                log(f"   Имя очищено: {tmp_result.name!r} → {clean_name!r}")

            # Перемещаем из tmp (ext4) в dst_dir (может быть NTFS)
            shutil.move(str(tmp_result), str(final_path))

            size_kb = final_path.stat().st_size // 1024
            log(f" Готово: {final_path.name} ({size_kb} КБ)")
            return final_path

        except subprocess.TimeoutExpired:
            log(" Таймаут")
            return None
        except Exception as e:
            log(f" Ошибка: {e}")
            return None


