#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отдельный процесс для загрузки голоса Piper TTS.
Запускается через QProcess. Пишет прогресс в stdout в формате JSON.
При любой ошибке завершается с кодом 1 и пишет детали в stderr.
"""
import sys
import json
import traceback
from pathlib import Path


def emit_event(event_type: str, data: dict):
    """Выводит событие в stdout. flush=True гарантирует мгновенную отправку."""
    event = {"type": event_type, **data}
    try:
        print(json.dumps(event, ensure_ascii=False), flush=True)
    except Exception as e:
        print(f"EMIT_ERROR: {e}", file=sys.stderr, flush=True)


def download_file(url: str, dest_path: Path, voice_name: str) -> bool:
    """Скачивает файл с прогрессом."""
    print(f"WORKER: download_file: URL={url[:80]}...", file=sys.stderr, flush=True)
    print(f"WORKER: download_file: dest={dest_path}", file=sys.stderr, flush=True)

    try:
        import requests
    except ImportError as e:
        emit_event("error", {"voice": voice_name, "message": f"Модуль requests не установлен: {e}"})
        return False

    try:
        print(f"WORKER: Начинаю запрос к HuggingFace...", file=sys.stderr, flush=True)
        response = requests.get(url, stream=True, timeout=60)
        print(f"WORKER: Статус ответа: {response.status_code}", file=sys.stderr, flush=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        print(f"WORKER: Размер файла: {total_size} байт", file=sys.stderr, flush=True)

        downloaded = 0
        last_pct = -1

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        pct = int(downloaded * 100 / total_size)
                        if pct != last_pct:
                            last_pct = pct
                            emit_event("progress", {"voice": voice_name, "percent": pct})

        print(f"WORKER: Файл успешно скачан", file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print(f"WORKER: Ошибка скачивания: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        emit_event("error", {"voice": voice_name, "message": str(e)})
        return False


def main():
    print(f"WORKER: === ЗАПУСК ===", file=sys.stderr, flush=True)
    print(f"WORKER: Python: {sys.executable}", file=sys.stderr, flush=True)
    print(f"WORKER: Аргументов: {len(sys.argv)}", file=sys.stderr, flush=True)
    print(f"WORKER: sys.argv = {sys.argv}", file=sys.stderr, flush=True)

    if len(sys.argv) < 5:
        print("WORKER: ОШИБКА: недостаточно аргументов!", file=sys.stderr, flush=True)
        print("WORKER: Ожидается: voice_download_worker.py <voice_name> <onnx_url> <json_url> <voices_dir>",
              file=sys.stderr, flush=True)
        sys.exit(1)

    voice_name = sys.argv[1]
    onnx_url = sys.argv[2]
    json_url = sys.argv[3]
    voices_dir = Path(sys.argv[4])

    print(f"WORKER: Голос={voice_name}", file=sys.stderr, flush=True)
    print(f"WORKER: ONNX URL={onnx_url}", file=sys.stderr, flush=True)
    print(f"WORKER: JSON URL={json_url}", file=sys.stderr, flush=True)
    print(f"WORKER: Директория={voices_dir}", file=sys.stderr, flush=True)

    try:
        voices_dir.mkdir(parents=True, exist_ok=True)
        print(f"WORKER: Директория создана/проверена", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"WORKER: Ошибка создания директории: {e}", file=sys.stderr, flush=True)
        emit_event("error", {"voice": voice_name, "message": f"Не удалось создать директорию: {e}"})
        emit_event("finished", {"voice": voice_name, "success": False})
        sys.exit(1)

    # Имя файла с дефисами (как в URL)
    file_name = voice_name.replace('_', '-')
    onnx_path = voices_dir / f"{file_name}.onnx"
    json_path = voices_dir / f"{file_name}.onnx.json"

    print(f"WORKER: ONNX путь={onnx_path}", file=sys.stderr, flush=True)
    print(f"WORKER: JSON путь={json_path}", file=sys.stderr, flush=True)

    emit_event("status", {"voice": voice_name, "message": f"Скачивание {file_name}.onnx..."})

    if not download_file(onnx_url, onnx_path, voice_name):
        print(f"WORKER: ОШИБКА скачивания ONNX", file=sys.stderr, flush=True)
        emit_event("finished", {"voice": voice_name, "success": False})
        sys.exit(1)

    emit_event("status", {"voice": voice_name, "message": f"Скачивание {file_name}.onnx.json..."})

    if not download_file(json_url, json_path, voice_name):
        print(f"WORKER: ОШИБКА скачивания JSON", file=sys.stderr, flush=True)
        emit_event("finished", {"voice": voice_name, "success": False})
        sys.exit(1)

    emit_event("status", {"voice": voice_name, "message": f"Голос {voice_name} успешно загружен!"})
    emit_event("finished", {"voice": voice_name, "success": True})
    print(f"WORKER: === УСПЕШНО ЗАВЕРШЕНО ===", file=sys.stderr, flush=True)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"WORKER: НЕОБРАБОТАННАЯ ОШИБКА: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        try:
            emit_event("error", {"voice": "unknown", "message": f"Необработанная ошибка: {e}"})
            emit_event("finished", {"voice": "unknown", "success": False})
        except Exception:
            pass
        sys.exit(1)
