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


# Фразы-маркеры рекламных секций пиратских сайтов.
# Если текст СОДЕРЖИТ хотя бы одну из этих фраз — он полностью пропускается.
# Используется как резервный фильтр на уровне Python после JS-фильтрации.
_AD_MARKERS = [
    'searchfloor.org',
    'цокольным этажом',
    'цокольный этаж',
    'книга предоставлена',
    'сайт заблокирован в России',
    'наградите автора лайком',
    'telegram-бот',
    'антизапрет',
    'censor tracker',
    'от автора раздачи',
    'от оцифровщика',
    'от сканировщика',
]


def is_ad_text(text: str) -> bool:
    """
    Возвращает True если текст содержит маркеры рекламных секций.
    Используется как резервный фильтр перед отправкой в TTS.
    Визуально скрытый текст (display:none) фильтруется в JS,
    этот фильтр ловит то что JS мог пропустить.
    """
    lower = text.lower()
    return any(marker in lower for marker in _AD_MARKERS)


def preprocess_ssml(text: str) -> str:
    """
    Очищает SSML перед отправкой в TTS.
    Удаляет/заменяет проблемные теги и символы.
    Возвращает пустую строку если текст является рекламой или разделителем.
    """
    # Резервный фильтр рекламных секций пиратских сайтов
    if is_ad_text(text):
        return ''

    # Фильтр разделителей глав/секций: *** / * * * / --- и т.п.
    # Если весь текст — только звёздочки, дефисы и пробелы → пропускаем целиком.
    if re.match(r'^[\s*\-–—_~]+$', text):
        return ''
    # Если *** встречается внутри текста — удаляем его, не озвучиваем.
    text = re.sub(r'\s*\*\s*\*\s*\*\s*', ' ', text)

    # Удаляем emphasis теги: <emphasis[^>]*>([^<]+)</emphasis> → $1
    text = re.sub(r'<emphasis[^>]*>([^<]+)</emphasis>', r'\1', text)

    # Конвертируем em dash/en dash в запятые — НО не между числами.
    # "20–30" (диапазон) → "от 20 до 30", а "слово — слово" → "слово, слово"
    def replace_dash(m):
        before = m.string[max(0, m.start()-3):m.start()]
        after  = m.string[m.end():m.end()+3]
        # Если с обеих сторон цифры — это диапазон
        if re.search(r'\d$', before) and re.search(r'^\d', after):
            return ' до '
        return ','
    text = re.sub(r'[–—]', replace_dash, text)

    # Заменяем break теги на пробел
    text = re.sub(r'<break\s*/?>', ' ', text)

    # Нормализуем многоточия
    text = re.sub(r'\.{3,}', '…', text)

    # Удаляем другие XML-подобные теги (кроме базовых)
    text = re.sub(r'<[^>]+>', '', text)

    return text.strip()


def apply_user_corrections(text: str, config, book_path: str = None) -> str:
    """
    Применяет пользовательские замены произношения.
    Сначала книжные (локальные), потом глобальные.
    Поддерживает опцию case_insensitive для каждой пары.
    """
    import re

    def apply_list(corrections: list, src: str) -> str:
        for item in corrections:
            wrong   = item.get('wrong', '').strip()
            correct = item.get('correct', '').strip()
            if not wrong:
                continue
            case_insensitive = item.get('case_insensitive', True)
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                new_src = re.sub(re.escape(wrong), correct, src, flags=flags)
            except re.error:
                new_src = src.replace(wrong, correct)
            if new_src != src:
                print(f"[TTS] Замена: '{wrong}' → '{correct}'")
                src = new_src
        return src

    # 1. Книжные замены (приоритет выше)
    if book_path and hasattr(config, 'get_corrections_for_book'):
        book_corrections = config.get_corrections_for_book(book_path)
        if book_corrections:
            text = apply_list(book_corrections, text)

    # 2. Глобальные замены
    if hasattr(config, 'get_corrections_global'):
        global_corrections = config.get_corrections_global()
    else:
        global_corrections = config.get('tts_corrections_global', []) or config.get('tts_corrections', [])
    if global_corrections:
        text = apply_list(global_corrections, text)

    return text


def normalize_text_for_tts(text: str, config=None, book_path: str = None) -> str:
    """
    Полная нормализация текста для TTS.
    Включает:
        - Конвертацию римских цифр в арабские
        - Очистку SSML
    """
    # Сначала пользовательские замены — до любой нормализации,
    # чтобы пользователь мог заменять текст в оригинальном виде
    # (например "рублей 20–30" с тире, до того как тире → "до")
    if config is not None:
        text = apply_user_corrections(text, config, book_path)
    # Затем конвертируем римские цифры
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