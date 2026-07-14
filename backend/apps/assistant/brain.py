"""
Абстракция над «мозгом» помощника (понимание естественного языка).

Мозг только ПОНИМАЕТ сообщение — извлекает намерение, поля товара и трактовку
ответов «да/нет/отмена». Он ничего не пишет в БД: запись выполняет движок
(engine.py) через существующие сервисы после явного подтверждения.

Провайдер выбирается настройкой ASSISTANT_BRAIN, доменный код от неё не зависит
(тот же приём, что и у STT-провайдеров). По умолчанию — RuleBrain: работает без
ключей и интернета, на нём идут тесты. Claude-мозг при любой ошибке откатывается
на правила.

Результат interpret() — словарь:
    {
      "intent": "intake" | "unknown",
      "affirmation": "yes" | "no" | "cancel" | None,
      "slots": {name, color, size, purchase_price, sale_price, quantity},
    }
"""

from abc import ABC, abstractmethod
import json
import logging

from django.conf import settings

from apps.voice.nlu import parse_product_draft
from apps.voice.number_words import normalize, tokenize

logger = logging.getLogger(__name__)

# Слова-триггеры приёмки/создания товара (ru/uz). Удаляются перед NLU, чтобы не
# попадать в наименование товара.
INTAKE_TRIGGERS = {
    # «принять» — команда и её формы (в т.ч. как их слышит распознавание речи).
    "прими", "принять", "приму", "примешь", "примет", "примем", "примете",
    "примут", "принял", "приняла", "приняли", "принято", "принят", "приняты",
    "приём", "прием", "приёмка", "приемка",
    # «приходовать / оприходовать».
    "приход", "приходуй", "приходуем", "приходовать", "оприходуй", "оприходуем",
    "оприходовать", "оприходовал", "оприходовали",
    # «создать / добавить / завести».
    "создай", "создать", "создал", "создаю", "добавь", "добавить", "добавил",
    "заведи", "завести", "завёл", "завел",
    "товар", "товара", "товаров",
    # Узбекский.
    "qabul", "kirim", "qo'sh", "qosh", "qo'shish", "qoshish", "qo'shdim",
    "yarat", "yaratish",
}
_AFFIRM_YES = {
    "да", "ага", "угу", "давай", "подтверждаю", "подтвердить", "подтверждаю.",
    "ок", "окей", "хорошо", "верно", "точно", "конечно", "ha", "xa", "mayli",
    "yes", "ok", "то'г'ри", "togri", "to'g'ri",
}
_AFFIRM_NO = {"нет", "не", "неа", "неверно", "yo'q", "yoq", "yq", "no"}
_AFFIRM_CANCEL = {
    "отмена", "отмени", "отменить", "стоп", "хватит", "bekor", "stop", "cancel",
}


def _affirmation(text: str):
    """Трактует короткий ответ как yes/no/cancel (или None)."""
    words = {normalize(w) for w in tokenize(text)}
    if words & _AFFIRM_CANCEL:
        return "cancel"
    if words & _AFFIRM_NO:
        return "no"
    if words & _AFFIRM_YES:
        return "yes"
    return None


def _strip_triggers(text: str) -> str:
    """Убирает командные слова, чтобы они не попали в название товара."""
    kept = []
    for raw in text.split():
        cleaned = raw.strip(".,;:!?()").strip()
        if normalize(cleaned) in INTAKE_TRIGGERS:
            continue
        kept.append(raw)
    return " ".join(kept)


def _slots_from_draft(text: str) -> dict:
    """Извлекает поля товара из текста через существующий NLU."""
    draft = parse_product_draft(_strip_triggers(text))
    attrs = draft.get("attributes") or {}
    return {
        "name": draft.get("name"),
        "color": attrs.get("color"),
        "size": attrs.get("size"),
        "purchase_price": draft.get("purchase_price"),
        "sale_price": draft.get("sale_price"),
        "quantity": draft.get("quantity"),
    }


def _has_intake_signal(text: str, slots: dict) -> bool:
    words = {normalize(w.strip(".,;:!?()")) for w in text.split()}
    if words & INTAKE_TRIGGERS:
        return True
    # Название + хотя бы цена или количество — тоже похоже на приёмку.
    if slots.get("name") and (slots.get("sale_price") or slots.get("quantity")):
        return True
    return False


class AssistantBrain(ABC):
    name = "base"

    @abstractmethod
    def interpret(self, *, text: str, context: dict | None = None) -> dict:
        raise NotImplementedError


class RuleBrain(AssistantBrain):
    """
    Детерминированный мозг: правила + NLU из голосового модуля. Без ключей и
    интернета. Ограничен словарём NLU — «грязный» язык лучше разбирает Claude,
    но базовый сценарий приёмки работает и здесь.
    """

    name = "rule"

    def interpret(self, *, text: str, context: dict | None = None) -> dict:
        text = text or ""
        slots = _slots_from_draft(text)
        intent = "intake" if _has_intake_signal(text, slots) else "unknown"
        return {
            "intent": intent,
            "affirmation": _affirmation(text),
            "slots": slots,
        }


# --- Claude (понимание через LLM) ------------------------------------------
_LLM_SYSTEM = """Ты — слой понимания языка для помощника учёта розничного магазина в Узбекистане. Пользователь пишет по-русски или по-узбекски. Извлеки из сообщения намерение и поля товара и верни СТРОГО один JSON-объект, без пояснений и без markdown.

Формат ответа:
{"intent": "intake"|"unknown", "affirmation": "yes"|"no"|"cancel"|null, "slots": {"name": строка|null, "color": строка|null, "size": строка|null, "purchase_price": число|null, "sale_price": число|null, "quantity": число|null}}

Правила:
- intent = "intake", если пользователь хочет принять/создать/оприходовать товар; иначе "unknown".
- name — наименование товара в именительном падеже единственного числа (например «футболок» → «Футболка»), без слов-команд («прими», «оприходуй»).
- size — размер одежды латиницей S/M/L/XL/XXL: «эс»→S, «эм»→M, «эль» (а также «а.л.», «эл», «al»)→L, «икс эль»→XL, «икс икс эль»→XXL.
- Цены и количество — числа: «сорок пять тысяч» → 45000, «двадцать» → 20.
- Если поле явно есть в сообщении — обязательно извлеки его; ставь null только когда поля действительно нет.
- affirmation — только для коротких ответов да/нет/отмена, иначе null.

Пример:
Сообщение: Прими двадцать синих футболок размер L закуп сорок пять тысяч продажа семьдесят девять тысяч
Ответ: {"intent":"intake","affirmation":null,"slots":{"name":"Футболка","color":"синий","size":"L","purchase_price":45000,"sale_price":79000,"quantity":20}}"""

_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["intake", "unknown"]},
        "affirmation": {"type": ["string", "null"], "enum": ["yes", "no", "cancel", None]},
        "slots": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "color": {"type": ["string", "null"]},
                "size": {"type": ["string", "null"]},
                "purchase_price": {"type": ["number", "null"]},
                "sale_price": {"type": ["number", "null"]},
                "quantity": {"type": ["number", "null"]},
            },
            "required": [
                "name", "color", "size", "purchase_price", "sale_price", "quantity",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["intent", "affirmation", "slots"],
    "additionalProperties": False,
}


class _ClaudeBrainBase(AssistantBrain):
    """
    Общая логика Claude-мозга. Клиент создаётся лениво в наследнике. При любой
    ошибке (нет доступа/пакета, плохой ответ) — откат на RuleBrain, чтобы
    помощник не падал.
    """

    def _client(self):
        raise NotImplementedError

    def interpret(self, *, text: str, context: dict | None = None) -> dict:
        try:
            return self._call(text=text, context=context)
        except Exception:  # noqa: BLE001 — резервный путь важнее типа ошибки
            logger.exception("assistant Claude brain failed; falling back to rules")
            return RuleBrain().interpret(text=text, context=context)

    def _call(self, *, text: str, context: dict | None) -> dict:
        client = self._client()
        model = getattr(settings, "ASSISTANT_MODEL", "claude-opus-4-8")
        user = text or ""
        if context and context.get("awaiting"):
            user = f"[ожидается ответ на: {context['awaiting']}]\n{user}"
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _LLM_SCHEMA}},
        )
        raw = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(raw)
        slots = data.get("slots") or {}
        return {
            "intent": data.get("intent") or "unknown",
            "affirmation": data.get("affirmation"),
            "slots": {
                "name": slots.get("name"),
                "color": slots.get("color"),
                "size": slots.get("size"),
                "purchase_price": _num_str(slots.get("purchase_price")),
                "sale_price": _num_str(slots.get("sale_price")),
                "quantity": _num_str(slots.get("quantity")),
            },
        }


def _num_str(value):
    if value is None:
        return None
    return str(value)


class ClaudeVertexBrain(_ClaudeBrainBase):
    """Claude через Google Cloud Vertex AI (аутентификация через GCP ADC)."""

    name = "claude_vertex"

    def _client(self):
        from anthropic import AnthropicVertex  # ленивый импорт

        return AnthropicVertex(
            project_id=getattr(settings, "VERTEX_PROJECT_ID", "") or None,
            region=getattr(settings, "VERTEX_REGION", "us-east5"),
        )


class ClaudeApiBrain(_ClaudeBrainBase):
    """Claude по прямому ключу Anthropic (ANTHROPIC_API_KEY)."""

    name = "claude"

    def _client(self):
        import anthropic  # ленивый импорт

        key = getattr(settings, "ANTHROPIC_API_KEY", "") or None
        return anthropic.Anthropic(api_key=key)


class GeminiVertexBrain(AssistantBrain):
    """
    Gemini через Google Cloud Vertex AI (аутентификация через GCP ADC).

    В отличие от Claude на Vertex не требует одобрения Model Garden и не имеет
    гео-ограничений Anthropic — работает на любом проекте Google Cloud с
    включённым Vertex AI API. При любой ошибке — откат на RuleBrain.
    """

    name = "gemini"

    def interpret(self, *, text: str, context: dict | None = None) -> dict:
        try:
            return self._call(text=text, context=context)
        except Exception:  # noqa: BLE001 — резервный путь важнее типа ошибки
            logger.exception("assistant Gemini brain failed; falling back to rules")
            return RuleBrain().interpret(text=text, context=context)

    def _call(self, *, text: str, context: dict | None) -> dict:
        from google import genai  # ленивый импорт
        from google.genai import types

        client = genai.Client(
            vertexai=True,
            project=getattr(settings, "VERTEX_PROJECT_ID", "") or None,
            location=getattr(settings, "GEMINI_LOCATION", "us-central1"),
        )
        user = text or ""
        if context and context.get("awaiting"):
            user = f"[ожидается ответ на: {context['awaiting']}]\n{user}"
        model = getattr(settings, "ASSISTANT_GEMINI_MODEL", "gemini-2.5-flash")
        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=_LLM_SYSTEM,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        data = json.loads(resp.text)
        slots = data.get("slots") or {}
        return {
            "intent": data.get("intent") or "unknown",
            "affirmation": data.get("affirmation"),
            "slots": {
                "name": slots.get("name"),
                "color": slots.get("color"),
                "size": slots.get("size"),
                "purchase_price": _num_str(slots.get("purchase_price")),
                "sale_price": _num_str(slots.get("sale_price")),
                "quantity": _num_str(slots.get("quantity")),
            },
        }


_BRAINS = {
    "rule": RuleBrain,
    "claude_vertex": ClaudeVertexBrain,
    "claude": ClaudeApiBrain,
    "gemini": GeminiVertexBrain,
}


def get_brain() -> AssistantBrain:
    key = getattr(settings, "ASSISTANT_BRAIN", "rule")
    return _BRAINS.get(key, RuleBrain)()
