"""
cloud_download.py — получение прямых ссылок на скачивание
из публичных облачных хранилищ.

Поддерживаемые сервисы:
  - Яндекс.Диск  (disk.yandex.ru, yadi.sk)
  - Google Drive  (drive.google.com, docs.google.com)
  - Dropbox       (dropbox.com)

Использование:
    from cloud_download import get_direct_link
    url = get_direct_link('https://disk.yandex.ru/d/xxxx')
    # url — прямая ссылка для скачивания или None при ошибке
"""

from __future__ import annotations
import re
import json


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
}


# ── Определение сервиса ───────────────────────────────────────────────────────

def detect_service(url: str) -> str | None:
    """Определяет облачный сервис по URL."""
    if 'disk.yandex.ru' in url or 'yadi.sk' in url:
        return 'yandex'
    if 'drive.google.com' in url or 'docs.google.com' in url:
        return 'google'
    if 'dropbox.com' in url:
        return 'dropbox'
    return None


def get_direct_link(url: str) -> str | None:
    """
    Возвращает прямую ссылку для скачивания файла из облачного хранилища.
    Если URL уже является прямой ссылкой — возвращает его без изменений.
    Возвращает None если не удалось получить ссылку.
    """
    service = detect_service(url)
    if service == 'yandex':
        return _yandex_direct_link(url)
    if service == 'google':
        return _google_direct_link(url)
    if service == 'dropbox':
        return _dropbox_direct_link(url)
    # Неизвестный сервис — возвращаем как есть (возможно уже прямая ссылка)
    return url


# ── Яндекс.Диск ───────────────────────────────────────────────────────────────

def _yandex_direct_link(page_url: str) -> str | None:
    """
    Получает прямую ссылку с Яндекс.Диска.
    Обходит страницу антивирусного предупреждения для больших файлов.
    """
    import requests
    from urllib.parse import quote as _quote

    print(f'[CloudDL] Яндекс.Диск: {page_url}')

    try:
        # Способ 1: публичный API — самый надёжный
        encoded = _quote(page_url, safe='')
        api_url = (
            'https://cloud-api.yandex.net/v1/disk/public/resources/download'
            f'?public_key={encoded}'
        )
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        print(f'[CloudDL] Яндекс API статус: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            if 'href' in data:
                print('[CloudDL] Яндекс: ссылка получена через API')
                return data['href']

        # Способ 2: парсим HTML + sk/hash для обхода антивирусного предупреждения
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        sk_m    = re.search(r'"sk"\s*:\s*"([^"]+)"', html)
        hash_m  = re.search(r'"hash"\s*:\s*"([^"]+)"', html)
        if sk_m and hash_m:
            dl_resp = requests.post(
                'https://disk.yandex.ru/public/api/download-url',
                json={'hash': hash_m.group(1), 'sk': sk_m.group(1)},
                headers=HEADERS, timeout=15,
            )
            if dl_resp.status_code == 200:
                data = dl_resp.json()
                if 'url' in data:
                    print('[CloudDL] Яндекс: ссылка через sk/hash')
                    return data['url']

        # Способ 3: ищем storage.yandex.net в HTML
        m = re.search(
            r'"file"\s*:\s*"(https://[^"]*storage\.yandex\.net[^"]*)"', html)
        if m:
            return m.group(1).replace('\\/', '/')

        # Способ 4: window.__DATA__
        m = re.search(r'window\.__DATA__\s*=\s*(\{.+?\})\s*;', html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                link = (data.get('downloadUrl')
                        or data.get('file', {}).get('url')
                        or data.get('file', {}).get('href'))
                if link:
                    return link
            except Exception:
                pass

    except Exception as e:
        print(f'[CloudDL] Яндекс ошибка: {e}')

    return None


# ── Google Drive ──────────────────────────────────────────────────────────────

def _google_extract_file_id(url: str) -> str | None:
    """Извлекает ID файла из ссылки Google Drive."""
    # https://drive.google.com/file/d/FILE_ID/view
    m = re.search(r'/file/d/([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(1)
    # https://drive.google.com/open?id=FILE_ID
    m = re.search(r'[?&]id=([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(1)
    # https://docs.google.com/uc?export=download&id=FILE_ID
    m = re.search(r'id=([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(1)
    return None


def _google_direct_link(url: str) -> str | None:
    """
    Получает прямую ссылку с Google Drive.
    Обходит страницу вирусного предупреждения для файлов >40MB.
    """
    import requests

    file_id = _google_extract_file_id(url)
    if not file_id:
        print(f'[CloudDL] Google: не удалось извлечь ID из {url}')
        return None

    print(f'[CloudDL] Google Drive ID: {file_id}')

    session = requests.Session()
    session.headers.update(HEADERS)

    # Первый запрос
    base_url = 'https://drive.usercontent.google.com/download'
    params   = {'id': file_id, 'export': 'download', 'authuser': '0'}
    resp     = session.get(base_url, params=params, stream=True, timeout=30)

    # Если сразу получили файл — отлично
    ctype = resp.headers.get('content-type', '')
    if 'text/html' not in ctype:
        print('[CloudDL] Google: прямое скачивание без подтверждения')
        return resp.url

    # Нужно подтверждение — ищем confirm токен
    html = resp.text

    # Способ 1: cookies
    confirm = None
    for k, v in session.cookies.items():
        if k.startswith('download_warning'):
            confirm = v
            break

    # Способ 2: HTML форма
    if not confirm:
        m = re.search(r'name="confirm"\s+value="([^"]+)"', html)
        if m:
            confirm = m.group(1)

    # Способ 3: uuid параметр (новый формат Google)
    uuid = None
    m = re.search(r'name="uuid"\s+value="([^"]+)"', html)
    if m:
        uuid = m.group(1)

    if confirm or uuid:
        params2 = {'id': file_id, 'export': 'download', 'authuser': '0'}
        if confirm:
            params2['confirm'] = confirm
        if uuid:
            params2['uuid'] = uuid
        resp2 = session.get(base_url, params=params2, stream=True, timeout=30)
        ctype2 = resp2.headers.get('content-type', '')
        if 'text/html' not in ctype2:
            print('[CloudDL] Google: ссылка с подтверждением получена')
            return resp2.url

    # Fallback: старый формат docs.google.com/uc
    fallback_url = f'https://docs.google.com/uc?export=download&id={file_id}&confirm=t'
    print(f'[CloudDL] Google: fallback URL')
    return fallback_url


# ── Dropbox ───────────────────────────────────────────────────────────────────

def _dropbox_direct_link(url: str) -> str:
    """
    Конвертирует публичную ссылку Dropbox в прямую ссылку для скачивания.
    Просто меняем dl=0 → dl=1 (или добавляем dl=1 если нет).
    """
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    print(f'[CloudDL] Dropbox: {url}')

    parsed = urlparse(url)
    # Убираем www. если есть — иногда мешает
    # Меняем dl=0 на dl=1
    if 'dl=0' in url:
        direct = url.replace('dl=0', 'dl=1')
    elif 'dl=1' in url:
        direct = url  # уже прямая
    elif '?' in url:
        direct = url + '&dl=1'
    else:
        direct = url + '?dl=1'

    # Новый формат ссылок Dropbox (scl/fi) также поддерживает dl=1
    print(f'[CloudDL] Dropbox прямая ссылка: {direct}')
    return direct
