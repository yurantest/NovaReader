"""
book_normalizer.py — нормализатор книг для корректной работы TTS.

Исправляет структурные проблемы FB2/EPUB/MOBI, которые приводят к:
- пропуску блоков текста при TTS-воспроизведении
- отсутствию подсветки первой строки
- зависанию на старте с первой страницы

Запускается из контекстного меню библиотеки.
"""

import re
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
        log("📖 Читаем FB2...")
        text = src.read_text(encoding='utf-8', errors='replace')
        original_len = len(text)
        changes = 0

        # 1. Разбиваем слипшиеся теги на отдельные строки для читаемости
        new_text, n = re.subn(r'(</title>)(<(?:p|section|epigraph|subtitle|empty-line))', 
                               r'\1\n\2', text)
        if n:
            log(f"  ✅ Разделены слипшиеся </title><tag>: {n} случаев")
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
            log(f"  ✅ Вынесен текст из <title>: {len(real_body)} абзацев")
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
                log(f"  🗑️ Удалена секция Nota bene")
                changes += 1
                return ''
            
            if 'с вами был' in content and ('searchfloor' in content or 'бесплатных книг' in content):
                log(f"  🗑️ Удалена секция с сайтом searchfloor.org")
                changes += 1
                return ''
            
            for phrase in distributor_phrases:
                if phrase in content:
                    if len(content) < 5000:
                        log(f"  🗑️ Удалена секция распространителя ({phrase!r})")
                        changes += 1
                        return ''
            return m.group(0)

        text = re.sub(r'<section>.*?</section>', remove_distributor_section, 
                      text, flags=re.DOTALL | re.IGNORECASE)

        # 4. Убираем двойные пустые строки
        text = re.sub(r'\n{3,}', '\n\n', text)

        if changes == 0:
            log("  ℹ️ Структурных проблем не обнаружено — файл и так корректен")
        
        log(f"  📊 Изменений: {changes}, размер: {original_len} → {len(text)} байт")
        dst.write_text(text, encoding='utf-8')
        log(f"✅ FB2 сохранён: {dst.name}")
        return True

    except Exception as e:
        log(f"❌ Ошибка нормализации FB2: {e}")
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

        log("📖 Читаем EPUB...")
        shutil.copy2(src, dst)
        
        changes_total = 0

        with zf.ZipFile(dst, 'r') as z_in:
            names = z_in.namelist()
            html_files = [n for n in names 
                          if n.lower().endswith(('.html', '.xhtml', '.htm'))]
            log(f"  📄 Найдено HTML-файлов: {len(html_files)}")

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
                        log(f"  ⚠️ Ошибка в {item.filename}: {e}")
                
                z_out.writestr(item, data)

        tmp.replace(dst)
        
        if changes_total == 0:
            log("  ℹ️ Структурных проблем не обнаружено — файл и так корректен")
        
        log(f"✅ EPUB сохранён: {dst.name} (изменений: {changes_total})")
        return True

    except Exception as e:
        log(f"❌ Ошибка нормализации EPUB: {e}")
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
        
        log(f"    ✅ {filename}: вынесен текст из <{tag}>: {len(real_body)} абзацев")
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
            log(f"    🗑️ {filename}: удалена секция Nota bene")
            changes += 1
            return ''
        
        if 'с вами был' in content and ('searchfloor' in content or 'бесплатных книг' in content):
            log(f"    🗑️ {filename}: удалена секция с сайтом searchfloor.org")
            changes += 1
            return ''
        
        for phrase in distributor_phrases:
            if phrase in content:
                if len(content) < 5000:
                    log(f"    🗑️ {filename}: удалена секция распространителя ({phrase!r})")
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
        log("📖 MOBI: пробуем извлечь через mobi...")
        try:
            import mobi
        except ImportError:
            log("  ⚠️ Библиотека mobi не установлена. Устанавливаем...")
            import subprocess, sys
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mobi', '--quiet'])
            import mobi

        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            log("  📦 Извлекаем MOBI...")
            
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
                log("  ❌ Не удалось извлечь MOBI")
                return False
            
            result_path = Path(result_dir)
            
            # Ищем EPUB внутри
            epub_files = list(result_path.rglob('*.epub'))
            if epub_files:
                epub_src = epub_files[0]
                log(f"  ✅ Найден EPUB внутри MOBI: {epub_src.name}")
                epub_dst = dst.with_suffix('.epub')
                return normalize_epub(epub_src, epub_dst, log)
            
            # Если EPUB нет — ищем HTML
            html_files = list(result_path.rglob('*.html')) + list(result_path.rglob('*.htm'))
            if html_files:
                log(f"  📄 Найдено HTML файлов: {len(html_files)}, собираем EPUB...")
                epub_dst = dst.with_suffix('.epub')
                _pack_html_to_epub(html_files, result_path, epub_dst, log)
                return normalize_epub(epub_dst, epub_dst, log)
            
            log("  ❌ Не удалось извлечь содержимое MOBI")
            return False

    except Exception as e:
        log(f"❌ Ошибка нормализации MOBI: {e}")
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
    log(f"  📦 Упакован EPUB: {dst.name}")


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
        log(f"❌ Файл не найден: {src}")
        return False

    ext = src.suffix.lower()

    if ext not in SUPPORTED:
        log(f"❌ Формат {ext} не поддерживается (только FB2, EPUB, MOBI, AZW3)")
        return False

    log(f"🔧 Нормализация: {src.name}")
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