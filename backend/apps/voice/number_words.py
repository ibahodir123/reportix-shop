"""
Парсер чисел, произнесённых словами, для русского и узбекского языков.

Примеры:
    "сорок пять тысяч"      -> 45000
    "qirq besh ming"        -> 45000
    "ikki yuz ellik"        -> 250
    "два миллиона триста"   -> 2000300
    "45000" / "20"          -> 45000 / 20

Используется в NLU-разборе голосового ввода товаров (цены, количество).
"""

import re

# kind: unit (складывается), hundred/thousand/million (множители/разряды)
_MAP = {}


def _add(words, value, kind):
    for w in words:
        _MAP[w] = (value, kind)


# --- Русский ---------------------------------------------------------------
_add(["ноль"], 0, "unit")
_add(["один", "одна", "одно"], 1, "unit")
_add(["два", "две"], 2, "unit")
_add(["три"], 3, "unit")
_add(["четыре"], 4, "unit")
_add(["пять"], 5, "unit")
_add(["шесть"], 6, "unit")
_add(["семь"], 7, "unit")
_add(["восемь"], 8, "unit")
_add(["девять"], 9, "unit")
_add(["десять"], 10, "unit")
_add(["одиннадцать"], 11, "unit")
_add(["двенадцать"], 12, "unit")
_add(["тринадцать"], 13, "unit")
_add(["четырнадцать"], 14, "unit")
_add(["пятнадцать"], 15, "unit")
_add(["шестнадцать"], 16, "unit")
_add(["семнадцать"], 17, "unit")
_add(["восемнадцать"], 18, "unit")
_add(["девятнадцать"], 19, "unit")
_add(["двадцать"], 20, "unit")
_add(["тридцать"], 30, "unit")
_add(["сорок"], 40, "unit")
_add(["пятьдесят"], 50, "unit")
_add(["шестьдесят"], 60, "unit")
_add(["семьдесят"], 70, "unit")
_add(["восемьдесят"], 80, "unit")
_add(["девяносто"], 90, "unit")
_add(["сто"], 100, "unit")
_add(["двести"], 200, "unit")
_add(["триста"], 300, "unit")
_add(["четыреста"], 400, "unit")
_add(["пятьсот"], 500, "unit")
_add(["шестьсот"], 600, "unit")
_add(["семьсот"], 700, "unit")
_add(["восемьсот"], 800, "unit")
_add(["девятьсот"], 900, "unit")
_add(["тысяча", "тысячи", "тысяч"], 1000, "thousand")
_add(["миллион", "миллиона", "миллионов"], 1_000_000, "million")

# --- Узбекский (латиница; апострофы приводим к обычным) --------------------
_add(["nol"], 0, "unit")
_add(["bir"], 1, "unit")
_add(["ikki"], 2, "unit")
_add(["uch"], 3, "unit")
_add(["tort", "to'rt", "to‘rt"], 4, "unit")
_add(["besh"], 5, "unit")
_add(["olti"], 6, "unit")
_add(["yetti"], 7, "unit")
_add(["sakkiz"], 8, "unit")
_add(["toqqiz", "to'qqiz", "to‘qqiz"], 9, "unit")
_add(["on", "o'n", "o‘n"], 10, "unit")
_add(["yigirma"], 20, "unit")
_add(["ottiz", "o'ttiz", "o‘ttiz"], 30, "unit")
_add(["qirq"], 40, "unit")
_add(["ellik"], 50, "unit")
_add(["oltmish"], 60, "unit")
_add(["yetmish"], 70, "unit")
_add(["sakson"], 80, "unit")
_add(["toqson", "to'qson", "to‘qson"], 90, "unit")
_add(["yuz"], 100, "hundred")  # узбекские сотни: "ikki yuz" = 2*100
_add(["ming"], 1000, "thousand")
_add(["million"], 1_000_000, "million")


def normalize(word: str) -> str:
    """Приводит апострофы узбекской латиницы к единому виду."""
    return word.replace("‘", "'").replace("ʻ", "'").lower()


def is_number_word(word: str) -> bool:
    w = normalize(word)
    return w.isdigit() or w in _MAP


_TERMINATORS = {w for w, (v, k) in _MAP.items() if k in ("thousand", "million")}


def is_scale_terminator(word: str) -> bool:
    """
    True для «тысяч/ming/миллион…». В рознице цены — круглые тысячи, поэтому
    число закрывается на разряде: «79 тысяч 20 штук» → 79000 и 20 (а не 79020).
    """
    return normalize(word) in _TERMINATORS


def words_to_number(words) -> int:
    """Собирает число из последовательности числовых слов/цифр."""
    total = 0
    current = 0
    for raw in words:
        w = normalize(raw)
        if w.isdigit():
            current += int(w)
            continue
        if w not in _MAP:
            continue
        value, kind = _MAP[w]
        if kind == "unit":
            current += value
        elif kind == "hundred":
            current = (current or 1) * value
        elif kind == "thousand":
            total += (current or 1) * value
            current = 0
        elif kind == "million":
            total += (current or 1) * value
            current = 0
    return total + current


_TOKEN_RE = re.compile(r"\d+|[^\W\d_]+(?:['‘ʻ][^\W\d_]+)*", re.UNICODE)


def tokenize(text: str):
    """Разбивает текст на слова и группы цифр (сохраняя апострофы uz)."""
    return _TOKEN_RE.findall(text.lower())
