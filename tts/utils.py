# tts/utils.py
import re


def roman_to_arabic(text: str) -> str:
    """
    Заменяет римские цифры на арабские с контекстом для TTS.
    
    Примеры:
        "Глава I" → "Глава 1"
        "Век II" → "Век 2"
        "III раздел" → "3 раздел"
        "XIX век" → "19 век"
    """
    # Римские цифры от 1 до 3999 (сортируем по длине — сначала длинные)
    roman_map = {
        'MMM': 3000, 'MM': 2000, 'CM': 900, 'DCCC': 800, 'DCC': 700, 'DC': 600,
        'D': 500, 'CD': 400, 'CCC': 300, 'CC': 200, 'C': 100, 'XC': 90,
        'LXXX': 80, 'LXX': 70, 'LX': 60, 'L': 50, 'XL': 40,
        'XXX': 30, 'XXV': 25, 'XXIV': 24, 'XXIII': 23, 'XXII': 22,
        'XXI': 21, 'XX': 20, 'XIX': 19, 'XVIII': 18, 'XVII': 17,
        'XVI': 16, 'XV': 15, 'XIV': 14, 'XIII': 13, 'XII': 12,
        'XI': 11, 'X': 10, 'IX': 9, 'VIII': 8, 'VII': 7, 'VI': 6,
        'V': 5, 'IV': 4, 'III': 3, 'II': 2, 'I': 1,
    }
    
    result = text
    
    # Проходим по римским цифрам от длинных к коротким
    for roman, arabic in roman_map.items():
        # Используем границы слов \b для точного совпадения
        # \b работает только с ASCII, поэтому используем явные границы
        pattern = r'(?<![A-Za-z])(' + roman + r')(?![A-Za-z])'
        
        # Проверяем контекст — должна быть рядом "книжная" лексика
        # или римская цифра должна быть отдельно
        def replace_func(match):
            start = match.start()
            end = match.end()
            
            # Получаем контекст вокруг
            before = result[max(0, start-20):start].lower()
            after = result[end:end+20].lower()
            
            # Ключевые слова для определения контекста
            book_keywords = ['глава', 'раздел', 'часть', 'книга', 'том', 'кн.', 'кн',
                           'век', 'века', 'год', 'года', 'эра', 'н.э.', 'до н.э.',
                           'съезд', 'конгресс', 'олимпиада', 'чемпионат', 'турнир',
                           'круг', 'этап', 'параграф', 'пункт', 'статья', 'урок']
            
            # Проверяем, есть ли ключевые слова рядом
            has_context = any(kw in before or kw in after for kw in book_keywords)
            
            # Также считаем контекстом, если цифра между пробелами/знаками препинания
            char_before = result[start-1:start] if start > 0 else ' '
            char_after = result[end:end+1] if end < len(result) else ' '
            
            is_standalone = (
                char_before.strip() == '' or char_before in '.,;:()[]«"\'-'
            ) and (
                char_after.strip() == '' or char_after in '.,;:()[]«"\'-'
            )
            
            # Для одиночной "I" требуем кириллический контекст (чтобы не заменять английские слова)
            if roman == 'I':
                # Проверяем, есть ли кириллица в контексте
                has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in before + after)
                if not has_cyrillic:
                    return match.group(0)  # Не заменяем "I" в английских словах
            
            if has_context or is_standalone:
                return str(arabic)
            return match.group(0)  # Не заменяем, если нет контекста
        
        result = re.sub(pattern, replace_func, result, flags=re.IGNORECASE)
    
    return result


def preprocess_ssml(text: str) -> str:
    """
    Очищает SSML перед отправкой в TTS (как в Readest)
    Удаляет/заменяет проблемные теги и символы
    """
    # Удаляем emphasis теги: <emphasis[^>]*>([^<]+)</emphasis> → $1
    text = re.sub(r'<emphasis[^>]*>([^<]+)</emphasis>', r'\1', text)

    # Конвертируем em dash в запятые
    text = re.sub(r'[–—]', ',', text)

    # Заменяем break теги на пробел
    text = re.sub(r'<break\s*/?>', ' ', text)

    # Нормализуем многоточия
    text = re.sub(r'\.{3,}', '…', text)

    # Удаляем другие XML-подобные теги (кроме базовых)
    text = re.sub(r'<[^>]+>', '', text)

    return text.strip()


def normalize_text_for_tts(text: str) -> str:
    """
    Полная нормализация текста для TTS.
    Включает:
        - Конвертацию римских цифр в арабские
        - Очистку SSML
    """
    # Сначала конвертируем римские цифры
    text = roman_to_arabic(text)
    # Затем очищаем SSML
    text = preprocess_ssml(text)
    return text


def split_into_sentences(text: str) -> list:
    """Разбивает текст на предложения (простая версия)"""
    # Используем регулярное выражение для разбиения по .!?…
    sentences = re.findall(r'[^.!?…]+[.!?…]', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def create_queue():
    """Создает очередь для TTS запросов (предотвращает рекурсию)"""
    import queue
    return queue.Queue()