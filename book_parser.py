import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, List
import re


class BookParser:
    """Парсер метаданных книг"""

    @staticmethod
    def extract_metadata(file_path: str) -> Optional[Dict]:
        """Извлечь метаданные из книги"""
        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            if ext == '.epub':
                return BookParser._parse_epub(file_path)
            elif ext == '.fb2':
                return BookParser._parse_fb2(file_path)
            elif ext == '.mobi' or ext == '.azw3':
                return BookParser._parse_mobi(file_path)
            elif ext == '.cbz':
                return BookParser._parse_cbz(file_path)
            elif ext == '.pdf':
                return BookParser._parse_pdf(file_path)
            else:
                # Для других форматов используем имя файла
                return {
                    'title': path.stem.replace('_', ' ').replace('-', ' '),
                    'author': 'Неизвестен',
                    'format': ext[1:],
                }
        except Exception as e:
            print(f"Ошибка парсинга {file_path}: {e}")
            return {
                'title': path.stem.replace('_', ' ').replace('-', ' '),
                'author': 'Неизвестен',
                'format': ext[1:],
            }

    @staticmethod
    def _parse_epub(file_path: str) -> Dict:
        """Парсинг EPUB"""
        metadata = {
            'title': 'Без названия',
            'author': 'Неизвестен',
            'series': None,
            'series_number': None,
            'description': None,
            'language': None,
            'publisher': None,
            'published': None,
            'isbn': None,
        }

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Ищем container.xml
                if 'META-INF/container.xml' in zf.namelist():
                    container = ET.fromstring(zf.read('META-INF/container.xml'))
                    ns = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                    rootfile = container.find('.//c:rootfile', ns)
                    if rootfile is not None:
                        opf_path = rootfile.get('full-path')

                        # Читаем OPF
                        opf_content = zf.read(opf_path)
                        opf = ET.fromstring(opf_content)

                        # Пространства имен
                        ns = {
                            'opf': 'http://www.idpf.org/2007/opf',
                            'dc': 'http://purl.org/dc/elements/1.1/'
                        }

                        # Название
                        title_elem = opf.find('.//dc:title', ns)
                        if title_elem is not None and title_elem.text:
                            metadata['title'] = title_elem.text.strip()

                        # Автор
                        creator_elem = opf.find('.//dc:creator', ns)
                        if creator_elem is not None and creator_elem.text:
                            metadata['author'] = creator_elem.text.strip()

                        # Язык
                        lang_elem = opf.find('.//dc:language', ns)
                        if lang_elem is not None and lang_elem.text:
                            metadata['language'] = lang_elem.text.strip()

                        # Издатель
                        pub_elem = opf.find('.//dc:publisher', ns)
                        if pub_elem is not None and pub_elem.text:
                            metadata['publisher'] = pub_elem.text.strip()

                        # Дата
                        date_elem = opf.find('.//dc:date', ns)
                        if date_elem is not None and date_elem.text:
                            metadata['published'] = date_elem.text.strip()

                        # Серия (ищем в meta)
                        for meta in opf.findall('.//opf:meta', ns):
                            name = meta.get('name', '')
                            content = meta.get('content', '')

                            if name == 'calibre:series':
                                metadata['series'] = content
                            elif name == 'calibre:series_index':
                                try:
                                    metadata['series_number'] = float(content)
                                except:
                                    pass

                            # ISBN
                            if name == 'calibre:isbn' or 'isbn' in name.lower():
                                metadata['isbn'] = content

                            # Описание
                            if name == 'description':
                                metadata['description'] = content
        except:
            pass

        return metadata

    @staticmethod
    def _parse_fb2(file_path: str) -> Dict:
        """Парсинг FB2"""
        metadata = {
            'title': 'Без названия',
            'author': 'Неизвестен',
            'series': None,
            'series_number': None,
            'description': None,
            'language': None,
        }

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Убираем namespace
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            # Title-info
            title_info = root.find('.//title-info')
            if title_info is not None:
                # Название
                book_title = title_info.find('book-title')
                if book_title is not None and book_title.text:
                    metadata['title'] = book_title.text.strip()

                # Автор
                author = title_info.find('author')
                if author is not None:
                    first = author.find('first-name')
                    last = author.find('last-name')
                    middle = author.find('middle-name')

                    parts = []
                    if last is not None and last.text:
                        parts.append(last.text.strip())
                    if first is not None and first.text:
                        parts.append(first.text.strip())
                    if middle is not None and middle.text:
                        parts.append(middle.text.strip())

                    if parts:
                        metadata['author'] = ' '.join(parts)

                # Язык
                lang = title_info.find('lang')
                if lang is not None and lang.text:
                    metadata['language'] = lang.text.strip()

                # Аннотация
                annotation = title_info.find('annotation')
                if annotation is not None:
                    text = ''.join(annotation.itertext())
                    metadata['description'] = text.strip()

                # Серия
                sequence = title_info.find('sequence')
                if sequence is not None:
                    metadata['series'] = sequence.get('name')
                    try:
                        metadata['series_number'] = float(sequence.get('number', 0))
                    except:
                        pass
        except:
            pass

        return metadata

    @staticmethod
    def _parse_mobi(file_path: str) -> Dict:
        """Парсинг MOBI/AZW3 (упрощенно)"""
        path = Path(file_path)
        return {
            'title': path.stem.replace('_', ' ').replace('-', ' '),
            'author': 'Неизвестен',
            'format': 'mobi',
        }

    @staticmethod
    def extract_cover(file_path: str) -> Optional[bytes]:
        """Извлечь обложку: EPUB — по OPF metadata, FB2 — по coverpage, CBZ — первое изображение."""
        path = Path(file_path)
        ext = path.suffix.lower()
        try:
            if ext == '.epub':
                import xml.etree.ElementTree as _ET
                with zipfile.ZipFile(file_path, 'r') as zf:
                    names = zf.namelist()
                    IMG = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

                    # 1. Читаем OPF через container.xml
                    opf_path = None
                    if 'META-INF/container.xml' in names:
                        try:
                            cont = _ET.fromstring(zf.read('META-INF/container.xml'))
                            for rf in cont.iter():
                                if rf.tag.endswith('rootfile'):
                                    opf_path = rf.get('full-path'); break
                        except Exception: pass

                    if opf_path and opf_path in names:
                        try:
                            opf = _ET.fromstring(zf.read(opf_path))
                            opf_dir = opf_path.rsplit('/', 1)[0] if '/' in opf_path else ''

                            # a) meta name="cover" → item id → href
                            cover_id = None
                            for el in opf.iter():
                                tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                                if tag == 'meta' and el.get('name','').lower() == 'cover':
                                    cover_id = el.get('content'); break

                            for item in opf.iter():
                                tag = item.tag.split('}')[-1] if '}' in item.tag else item.tag
                                if tag == 'item':
                                    props = item.get('properties', '')
                                    if 'cover-image' in props or \
                                       (cover_id and item.get('id') == cover_id):
                                        href = item.get('href', '')
                                        full = (opf_dir + '/' + href).lstrip('/') if opf_dir else href
                                        if full in names:
                                            return zf.read(full)
                        except Exception: pass

                    # 2. Файлы с 'cover' в имени — берём самый крупный
                    covers = [n for n in names
                              if 'cover' in n.lower().split('/')[-1] and n.lower().endswith(IMG)]
                    if covers:
                        covers.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
                        return zf.read(covers[0])

                    # 3. Самое крупное изображение во всём архиве
                    imgs = [n for n in names if n.lower().endswith(IMG)]
                    if imgs:
                        imgs.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
                        return zf.read(imgs[0])

            elif ext == '.fb2':
                tree = ET.parse(file_path)
                root = tree.getroot()
                # Убираем namespace
                for el in root.iter():
                    if '}' in el.tag:
                        el.tag = el.tag.split('}', 1)[1]
                    for k, v in list(el.attrib.items()):
                        if '}' in k:
                            el.attrib[k.split('}', 1)[1]] = el.attrib.pop(k)

                # 1. <coverpage><image href="#id"/>  →  <binary id="id">
                cp = root.find('.//coverpage')
                if cp is not None:
                    img_el = cp.find('.//image')
                    if img_el is not None:
                        href = img_el.get('href') or img_el.get('l:href') or ''
                        bin_id = href.lstrip('#')
                        if bin_id:
                            for binary in root.findall('.//binary'):
                                if binary.get('id') == bin_id and binary.text:
                                    import base64
                                    return base64.b64decode(binary.text.strip())

                # 2. Fallback: первый binary image/*
                for binary in root.findall('.//binary'):
                    if 'image' in binary.get('content-type', '') and binary.text:
                        import base64
                        return base64.b64decode(binary.text.strip())

            elif ext == '.cbz':
                # CBZ: первое изображение в ZIP-архиве
                with zipfile.ZipFile(file_path, 'r') as zf:
                    names = zf.namelist()
                    IMG = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
                    
                    # 1. Ищем файлы с 'cover' в имени
                    covers = [n for n in names
                              if 'cover' in n.lower().split('/')[-1] and n.lower().endswith(IMG)]
                    if covers:
                        covers.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
                        return zf.read(covers[0])
                    
                    # 2. Первое изображение (обычно это обложка)
                    imgs = [n for n in names if n.lower().endswith(IMG)]
                    if imgs:
                        # Сортируем по имени, чтобы взять первое
                        imgs.sort()
                        return zf.read(imgs[0])

            elif ext == '.mobi' or ext == '.azw3':
                # MOBI: пытаемся извлечь обложку через mobi-библиотеку или как первое изображение
                try:
                    # Простой подход: читаем файл и ищем JPEG/PNG данные
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        # Ищем JPEG маркеры
                        jpeg_start = data.find(b'\xff\xd8\xff')
                        if jpeg_start >= 0:
                            jpeg_end = data.find(b'\xff\xd9', jpeg_start)
                            if jpeg_end > 0:
                                return data[jpeg_start:jpeg_end + 2]
                except Exception as e:
                    print(f"[Parser] MOBI cover error: {e}")

            elif ext == '.cbz':
                # CBZ: первое изображение в ZIP-архиве
                with zipfile.ZipFile(file_path, 'r') as zf:
                    names = zf.namelist()
                    IMG = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
                    
                    # 1. Ищем файлы с 'cover' в имени
                    covers = [n for n in names
                              if 'cover' in n.lower().split('/')[-1] and n.lower().endswith(IMG)]
                    if covers:
                        covers.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
                        return zf.read(covers[0])
                    
                    # 2. Первое изображение (обычно это обложка)
                    imgs = [n for n in names if n.lower().endswith(IMG)]
                    if imgs:
                        # Сортируем по имени, чтобы взять первое
                        imgs.sort()
                        return zf.read(imgs[0])

        except Exception as e:
            print(f"[Parser] Cover error {file_path}: {e}")
        return None

    @staticmethod
    def _parse_cbz(file_path: str) -> Dict:
        """
        Парсинг CBZ (Comic Book ZIP) — комиксы в формате ZIP с изображениями.
        Извлекаем метаданные из названия файла и первой страницы.
        """
        metadata = {
            'title': Path(file_path).stem.replace('_', ' ').replace('-', ' '),
            'author': 'Неизвестен',
            'series': None,
            'series_number': None,
            'description': None,
            'language': None,
            'publisher': None,
            'published': None,
            'isbn': None,
            'format': 'cbz',
        }

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Ищем файл ComicInfo.xml (стандарт для комиксов)
                if 'ComicInfo.xml' in zf.namelist():
                    comic_info = ET.fromstring(zf.read('ComicInfo.xml'))
                    
                    # Название
                    title_elem = comic_info.find('.//Series')
                    if title_elem is not None and title_elem.text:
                        metadata['title'] = title_elem.text.strip()
                    
                    # Автор
                    writer_elem = comic_info.find('.//Writer')
                    if writer_elem is not None and writer_elem.text:
                        metadata['author'] = writer_elem.text.strip()
                    
                    # Серия
                    series_elem = comic_info.find('.//Series')
                    if series_elem is not None and series_elem.text:
                        metadata['series'] = series_elem.text.strip()
                    
                    # Номер выпуска
                    number_elem = comic_info.find('.//Number')
                    if number_elem is not None and number_elem.text:
                        metadata['series_number'] = number_elem.text.strip()
                    
                    # Описание
                    summary_elem = comic_info.find('.//Summary')
                    if summary_elem is not None and summary_elem.text:
                        metadata['description'] = summary_elem.text.strip()
                    
                    # Год публикации
                    year_elem = comic_info.find('.//Year')
                    if year_elem is not None and year_elem.text:
                        metadata['published'] = year_elem.text.strip()
                
                # Если нет ComicInfo.xml, пробуем извлечь название из имени файла
                # Формат: "Series Name - Issue #001.cbz" или "Series Name (2020) - 001.cbz"
                filename = Path(file_path).stem
                cbz_pattern = r'^(.+?)\s*[-–—]\s*(?:#?(\d+))?'
                match = re.match(cbz_pattern, filename)
                if match:
                    metadata['title'] = match.group(1).strip()
                    if match.group(2):
                        metadata['series_number'] = match.group(2)

        except Exception as e:
            print(f"[Parser] CBZ error {file_path}: {e}")

        return metadata

    @staticmethod
    def _parse_pdf(file_path: str) -> Dict:
        """
        Парсинг PDF — только базовые метаданные.
        foliate-js использует PDF.js для отображения и извлечения текста.
        TTS работает через PDF.js напрямую.
        """
        return {
            'title': Path(file_path).stem.replace('_', ' ').replace('-', ' '),
            'author': 'Неизвестен',
            'series': None,
            'series_number': None,
            'description': None,
            'language': None,
            'publisher': None,
            'published': None,
            'isbn': None,
            'format': 'pdf',
        }
