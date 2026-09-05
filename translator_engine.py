# -*- coding: utf-8 -*-
"""
Морфологический разбор слова для читалки — полностью офлайн (pymorphy3).

Перевод фраз вынесен в отдельное окно (translator_window.py), которое
обращается к онлайн-переводчику — держать тяжёлые офлайн-модели перевода
(Argos Translate тянет за собой ~1.2 ГБ на torch/stanza) в самой читалке
признано неоправданным по весу. Здесь остаётся только словарь: часть речи,
начальная форма, падеж, число, время и т.д. — не требует скачивания
моделей, работает сразу после установки pymorphy3.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    import pymorphy3
    _HAS_PYMORPHY = True
except Exception:
    _HAS_PYMORPHY = False


_POS_LABELS = {
    'NOUN': 'существительное', 'ADJF': 'прилагательное', 'ADJS': 'краткое прилагательное',
    'COMP': 'сравнительная степень', 'VERB': 'глагол', 'INFN': 'глагол (инфинитив)',
    'PRTF': 'причастие', 'PRTS': 'краткое причастие', 'GRND': 'деепричастие',
    'NUMR': 'числительное', 'ADVB': 'наречие', 'NPRO': 'местоимение',
    'PRED': 'предикатив', 'PREP': 'предлог', 'CONJ': 'союз', 'PRCL': 'частица',
    'INTJ': 'междометие', 'LATN': 'латиница', 'NUMB': 'число', 'ROMN': 'римское число',
    'UNKN': 'неизвестно',
}
_CASE_LABELS = {
    'nomn': 'именительный', 'gent': 'родительный', 'datv': 'дательный',
    'accs': 'винительный', 'ablt': 'творительный', 'loct': 'предложный',
    'voct': 'звательный', 'gen1': 'родительный (1)', 'gen2': 'родительный (2, частичный)',
    'acc2': 'винительный (2)', 'loc1': 'предложный (1)', 'loc2': 'предложный (2, местный)',
}
_NUMBER_LABELS = {'sing': 'единственное число', 'plur': 'множественное число'}
_GENDER_LABELS = {'masc': 'мужской род', 'femn': 'женский род', 'neut': 'средний род'}
_TENSE_LABELS = {'past': 'прошедшее время', 'pres': 'настоящее время', 'futr': 'будущее время'}
_ASPECT_LABELS = {'perf': 'совершенный вид', 'impf': 'несовершенный вид'}
_PERSON_LABELS = {'1per': '1-е лицо', '2per': '2-е лицо', '3per': '3-е лицо'}
_MOOD_LABELS = {'indc': 'изъявительное наклонение', 'impr': 'повелительное наклонение'}
_VOICE_LABELS = {'actv': 'действительный залог', 'pssv': 'страдательный залог'}


class WordAnalyzer:
    """Морфологический разбор русского слова через pymorphy3."""

    def __init__(self):
        self._morph = None
        if _HAS_PYMORPHY:
            try:
                self._morph = pymorphy3.MorphAnalyzer()
            except Exception as e:
                print(f'[Translator] Не удалось создать pymorphy3.MorphAnalyzer(): {e!r}')
                self._morph = None

    @property
    def available(self) -> bool:
        return self._morph is not None

    def analyze(self, word: str) -> Optional[dict]:
        """Возвращает словарь с разбором слова, либо None, если pymorphy3
        не установлен или слово пустое."""
        word = (word or '').strip()
        if not self._morph or not word:
            return None

        try:
            parses = self._morph.parse(word)
        except Exception as e:
            print(f'[Translator] Ошибка разбора слова "{word}": {e!r}')
            return None
        if not parses:
            return None

        best = parses[0]
        tag = best.tag

        parts = []
        pos_label = _POS_LABELS.get(tag.POS, tag.POS)
        if pos_label:
            parts.append(pos_label)
        for grammeme, labels in (
            (tag.case, _CASE_LABELS), (tag.number, _NUMBER_LABELS),
            (tag.gender, _GENDER_LABELS), (tag.tense, _TENSE_LABELS),
            (tag.aspect, _ASPECT_LABELS), (tag.person, _PERSON_LABELS),
            (tag.mood, _MOOD_LABELS), (tag.voice, _VOICE_LABELS),
        ):
            if grammeme and grammeme in labels:
                parts.append(labels[grammeme])

        alternatives = []
        seen_forms = {best.normal_form}
        for p in parses[1:4]:
            if p.normal_form in seen_forms:
                continue
            seen_forms.add(p.normal_form)
            alt_pos = _POS_LABELS.get(p.tag.POS, p.tag.POS)
            alternatives.append({
                'normal_form': p.normal_form,
                'pos': alt_pos,
                'score': round(p.score, 2),
            })

        return {
            'word': word,
            'normal_form': best.normal_form,
            'pos': tag.POS,
            'pos_label': pos_label,
            'description': ', '.join(parts) if parts else pos_label,
            'score': round(best.score, 2),
            'alternatives': alternatives,
        }

    def analyze_sentence(self, text: str) -> list:
        """Разбор ВСЕХ слов в тексте (не только одиночного слова) — для
        предложения/фразы. Токенизация простая: последовательности букв
        (плюс дефис внутри слова), всё остальное (знаки препинания,
        цифры, пробелы) считается разделителями и пропускается.
        Возвращает список разборов в порядке появления слов в тексте —
        каждый элемент такой же, как у analyze(), плюс поле 'index'."""
        text = (text or '').strip()
        if not self._morph or not text:
            return []

        words = re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", text, re.UNICODE)
        results = []
        for i, word in enumerate(words):
            parsed = self.analyze(word)
            if parsed:
                parsed['index'] = i
                results.append(parsed)
        return results


_word_analyzer: Optional[WordAnalyzer] = None


def get_word_analyzer() -> WordAnalyzer:
    global _word_analyzer
    if _word_analyzer is None:
        _word_analyzer = WordAnalyzer()
    return _word_analyzer


def is_single_word(text: str) -> bool:
    """Считаем "словом" короткую строку без пробелов, состоящую из букв
    (плюс дефис — для слов вроде "кто-то")."""
    text = (text or '').strip()
    if not text or ' ' in text:
        return False
    return bool(re.fullmatch(r"[^\W\d_]+(-[^\W\d_]+)*", text, re.UNICODE))
