import zipfile
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, BinaryIO
import os
import shutil

class ZipHandler:
    """Обработка ZIP-архивов с книгами"""
    
    def __init__(self):
        self.temp_dir = None
        self.extracted_files = {}
        
    def extract_epub(self, zip_path: str) -> Optional[str]:
        """Извлечь EPUB в временную директорию"""
        try:
            # Создаем временную директорию
            self.temp_dir = tempfile.mkdtemp(prefix='ebook_')
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self.temp_dir)
            
            # Ищем container.xml для определения пути к OPF
            container_path = Path(self.temp_dir) / 'META-INF' / 'container.xml'
            if container_path.exists():
                import xml.etree.ElementTree as ET
                tree = ET.parse(container_path)
                root = tree.getroot()
                
                # Ищем путь к OPF
                for elem in root.findall('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile'):
                    opf_path = elem.get('full-path')
                    if opf_path:
                        return str(Path(self.temp_dir) / opf_path)
            
            return self.temp_dir
            
        except Exception as e:
            print(f"Ошибка извлечения EPUB: {e}")
            self.cleanup()
            return None
    
    def extract_fb2_zip(self, zip_path: str) -> Optional[str]:
        """Извлечь FB2 из ZIP"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix='ebook_')
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Ищем первый .fb2 файл
                for name in zf.namelist():
                    if name.endswith('.fb2'):
                        zf.extract(name, self.temp_dir)
                        return str(Path(self.temp_dir) / name)
            
            return None
            
        except Exception as e:
            print(f"Ошибка извлечения FB2: {e}")
            self.cleanup()
            return None
    
    def extract_cbz(self, zip_path: str) -> Optional[str]:
        """Извлечь комикс (CBZ)"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix='comic_')
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(self.temp_dir)
            
            return self.temp_dir
            
        except Exception as e:
            print(f"Ошибка извлечения CBZ: {e}")
            self.cleanup()
            return None
    
    def get_file_list(self) -> List[str]:
        """Получить список извлеченных файлов"""
        if not self.temp_dir:
            return []
        
        files = []
        for root, _, filenames in os.walk(self.temp_dir):
            for f in filenames:
                rel_path = os.path.relpath(os.path.join(root, f), self.temp_dir)
                files.append(rel_path)
        
        return files
    
    def read_file(self, file_path: str) -> Optional[bytes]:
        """Прочитать файл из временной директории"""
        if not self.temp_dir:
            return None
        
        full_path = Path(self.temp_dir) / file_path
        if full_path.exists() and full_path.is_file():
            return full_path.read_bytes()
        return None
    
    def cleanup(self):
        """Очистить временные файлы"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None