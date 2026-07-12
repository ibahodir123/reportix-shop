"""
Извлечение структуры товара из распознанного текста (ru/uz).

Из фразы вида «Футболка синяя размер эль закуп 45 тысяч продажа 79 тысяч 20 штук»
получаем черновик:
    {name, attributes{color,size}, purchase_price, sale_price, quantity, unit, confidence}

ВАЖНО: результат — всегда ЧЕРНОВИК. Он показывается человеку на подтверждение и
никогда не пишется в БД напрямую (см. apps/voice/views.py).
"""

from .number_words import (
    is_number_word,
    is_scale_terminator,
    normalize,
    tokenize,
    words_to_number,
)

PURCHASE_KW = {
    "закуп", "закупка", "закупочная", "закупка", "приход", "себестоимость",
    "olish", "kirim", "tannarx", "xarid",
}
SALE_KW = {
    "продажа", "продажная", "розница", "цена", "sotuv", "sotish", "narx",
}
QTY_KW = {
    "штук", "штука", "штуки", "шт", "количество", "дона", "dona", "soni", "ta",
}
SIZE_KW = {"размер", "размера", "o'lcham", "olcham"}

COLORS = {
    "синий": "синий", "синяя": "синий", "красный": "красный", "красная": "красный",
    "белый": "белый", "белая": "белый", "чёрный": "чёрный", "черный": "чёрный",
    "чёрная": "чёрный", "черная": "чёрный", "зелёный": "зелёный", "зеленый": "зелёный",
    "жёлтый": "жёлтый", "желтый": "жёлтый",
    "ko'k": "синий", "qizil": "красный", "oq": "белый", "qora": "чёрный",
    "yashil": "зелёный", "sariq": "жёлтый",
}
SIZES = {
    "s": "S", "m": "M", "l": "L", "xl": "XL", "xxl": "XXL", "xs": "XS",
    "эс": "S", "эм": "M", "эль": "L",
    "маленький": "S", "средний": "M", "большой": "L",
}

_STOP_FOR_NAME = PURCHASE_KW | SALE_KW | QTY_KW | SIZE_KW | set(COLORS) | set(SIZES)


def _to_tokens(text: str):
    """Токены: числовые слова/цифры сворачиваются в один num-токен."""
    tokens = []
    buf = []

    def flush():
        if buf:
            tokens.append({"type": "num", "value": words_to_number(buf)})
            buf.clear()

    for raw in tokenize(text):
        w = normalize(raw)
        if is_number_word(w):
            buf.append(w)
            # Закрываем число на разряде «тысяч/ming» — чтобы цена и следующее
            # количество не слились в одно число.
            if is_scale_terminator(w):
                flush()
        else:
            flush()
            tokens.append({"type": "word", "text": w})
    flush()
    return tokens


def parse_product_draft(text: str) -> dict:
    tokens = _to_tokens(text)

    purchase_price = None
    sale_price = None
    quantity = None
    color = None
    size = None
    name_words = []
    name_open = True

    for idx, tok in enumerate(tokens):
        if tok["type"] == "word":
            w = tok["text"]
            if w in COLORS:
                color = COLORS[w]
                name_open = False
            elif w in SIZES and (size is None):
                # размер как отдельное слово (S/M/L/эль/…)
                size = SIZES[w]
                name_open = False
            elif w in _STOP_FOR_NAME:
                name_open = False
            elif name_open:
                name_words.append(raw_text(text, w))
            continue

        # num-токен: определяем назначение по соседним словам
        value = tok["value"]
        prev_word = _neighbor_word(tokens, idx, -1)
        next_word = _neighbor_word(tokens, idx, +1)

        if prev_word in PURCHASE_KW:
            purchase_price = value
        elif prev_word in SALE_KW:
            sale_price = value
        elif next_word in QTY_KW or prev_word in QTY_KW:
            quantity = value
        elif next_word in SIZE_KW or prev_word in SIZE_KW:
            size = str(value)
        else:
            # нераспознанное число — если цены ещё не заданы, заполняем по порядку
            if purchase_price is None:
                purchase_price = value
            elif sale_price is None:
                sale_price = value
        name_open = False

    attributes = {}
    if color:
        attributes["color"] = color
    if size:
        attributes["size"] = size

    draft = {
        "name": " ".join(name_words).strip().capitalize() or None,
        "attributes": attributes,
        "purchase_price": str(purchase_price) if purchase_price is not None else None,
        "sale_price": str(sale_price) if sale_price is not None else None,
        "quantity": str(quantity) if quantity is not None else None,
        "unit": None,
        "confidence": "estimated",
    }
    return draft


def _neighbor_word(tokens, idx, step):
    """Непосредственно соседнее слово (без перескока через числа)."""
    j = idx + step
    if 0 <= j < len(tokens) and tokens[j]["type"] == "word":
        return tokens[j]["text"]
    return None


def raw_text(text: str, normalized_word: str) -> str:
    """Возвращает слово с исходным регистром (простое сопоставление по lower)."""
    for token in text.split():
        cleaned = token.strip(".,;:!?()").strip()
        if normalize(cleaned) == normalized_word:
            return cleaned
    return normalized_word
