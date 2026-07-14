"""
Движок диалога помощника: детерминированная стейт-машина.

Отвечает за состояние разговора, дозапрос недостающих полей, шаг подтверждения
и — только после явного «Подтверждаю» — выполнение операции через существующий
атомарный сервис (quick_create_product). Мозг (brain.py) лишь понимает язык;
запись в БД — здесь, с повторной проверкой прав (защита в глубину).

Ответы движка локализованы (ru/uz) — язык берётся из запроса и хранится в
состоянии диалога. Состояние — в кэше (Redis в проде, locmem в тестах), ключ по
тенанту, пользователю и conversation_id, TTL 30 минут.
"""

from decimal import Decimal, InvalidOperation
import uuid

from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from apps.catalog.services import quick_create_product
from apps.common.permissions import MANAGER, OWNER
from apps.inventory.models import Warehouse
from apps.voice.number_words import (
    is_number_word,
    is_scale_terminator,
    normalize,
    tokenize,
    words_to_number,
)

from .brain import get_brain

STATE_TTL = 30 * 60  # 30 минут
_INTAKE_ROLES = {OWNER, MANAGER}

# Обязательные текстово-числовые поля (порядок дозапроса) — вопросы в _TEXTS.
_REQUIRED_FIELDS = ["name", "quantity", "sale_price"]

# --- Локализация ответов ---------------------------------------------------
_TEXTS = {
    "ru": {
        "help": (
            "Скажите, что принять на склад. Например: «Прими 20 синих футболок "
            "размера L по 45 тысяч, продажа 79 тысяч»."
        ),
        "cancelled": "Хорошо, отменил.",
        "ask_name": "Как называется товар?",
        "ask_quantity": "Сколько штук приходуем?",
        "ask_sale_price": "По какой цене продаём?",
        "ask_warehouse_one": "На склад «{name}»?",
        "ask_warehouse_pick": "На какой склад? Есть: {names}.",
        "warehouse_not_found": "Не нашёл такой склад. Есть: {names}.",
        "no_warehouse": "Сначала создайте склад, потом повторите приёмку.",
        "bad_number": "Не понял число, повторите пожалуйста.",
        "no_permission": "Недостаточно прав для приёмки товара.",
        "exec_error": "Не получилось: {detail}",
        "confirm_create": "Создать товар «{name}»",
        "confirm_intake": "и оприходовать {qty} шт",
        "confirm_warehouse": "на склад «{name}»",
        "purchase": "закуп {v}",
        "sale": "продажа {v}",
        "done": (
            "Готово: создан товар «{name}», оприходовано {qty} шт на склад «{wh}»."
        ),
    },
    "uz": {
        "help": (
            "Omborga nima qabul qilishni ayting. Masalan: «20 ta ko'k L o'lchamli "
            "futbolka qabul qil, tannarx 45 ming, sotuv 79 ming»."
        ),
        "cancelled": "Yaxshi, bekor qildim.",
        "ask_name": "Tovar nomi qanday?",
        "ask_quantity": "Nechta dona qabul qilamiz?",
        "ask_sale_price": "Sotuv narxi qancha?",
        "ask_warehouse_one": "«{name}» omboriga?",
        "ask_warehouse_pick": "Qaysi omborga? Bor: {names}.",
        "warehouse_not_found": "Bunday ombor topilmadi. Bor: {names}.",
        "no_warehouse": "Avval ombor yarating, keyin qabulni takrorlang.",
        "bad_number": "Sonni tushunmadim, iltimos qaytaring.",
        "no_permission": "Tovar qabul qilishga ruxsat yo'q.",
        "exec_error": "Bo'lmadi: {detail}",
        "confirm_create": "«{name}» tovarini yaratamizmi",
        "confirm_intake": "va {qty} dona qabul qilamiz",
        "confirm_warehouse": "«{name}» omboriga",
        "purchase": "tannarx {v}",
        "sale": "sotuv {v}",
        "done": (
            "Tayyor: «{name}» tovari yaratildi, «{wh}» omboriga {qty} dona qabul qilindi."
        ),
    },
}


def _lang_of(language):
    """uz-UZ → 'uz', остальное → 'ru'."""
    if language and str(language).lower().startswith("uz"):
        return "uz"
    return "ru"


def _t(lang, key, **kw):
    text = _TEXTS.get(lang, _TEXTS["ru"]).get(key, _TEXTS["ru"][key])
    return text.format(**kw) if kw else text


# --- Хранилище состояния ---------------------------------------------------
def _key(tenant, user, conversation_id):
    return f"assistant:{tenant.id}:{user.id}:{conversation_id}"


def _load(tenant, user, conversation_id):
    if not conversation_id:
        return None
    return cache.get(_key(tenant, user, conversation_id))


def _save(tenant, user, conversation_id, state):
    cache.set(_key(tenant, user, conversation_id), state, STATE_TTL)


def _clear(tenant, user, conversation_id):
    cache.delete(_key(tenant, user, conversation_id))


# --- Утилиты ---------------------------------------------------------------
def first_number(text: str):
    """Первое число из текста (учёт словесных чисел и разряда «тысяч/ming»)."""
    nums = []
    buf = []
    for raw in tokenize(text or ""):
        w = normalize(raw)
        if is_number_word(w):
            buf.append(w)
            if is_scale_terminator(w):
                nums.append(words_to_number(buf))
                buf = []
        else:
            if buf:
                nums.append(words_to_number(buf))
                buf = []
    if buf:
        nums.append(words_to_number(buf))
    return nums[0] if nums else None


def _active_warehouses(tenant):
    return list(Warehouse.objects.filter(tenant=tenant, is_active=True).order_by("name"))


def _match_warehouse(tenant, text):
    t = (text or "").lower()
    for wh in _active_warehouses(tenant):
        if wh.name.lower() in t:
            return wh
    return None


def _dec(value):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _reply(conversation_id, reply, state, draft=None, result=None):
    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "state": state,
        "draft": draft,
        "result": result,
    }


# --- Точка входа -----------------------------------------------------------
def handle_message(*, tenant, user, membership, conversation_id, text, language=None):
    brain = get_brain()
    conversation_id = conversation_id or uuid.uuid4().hex
    state = _load(tenant, user, conversation_id)

    if state and state.get("phase") in ("collecting", "confirm"):
        return _continue(tenant, user, membership, conversation_id, state, text, brain)
    return _start(
        tenant, user, membership, conversation_id, text, brain, _lang_of(language)
    )


def _start(tenant, user, membership, conversation_id, text, brain, lang):
    understanding = brain.interpret(text=text)
    if understanding.get("affirmation") == "cancel":
        return _reply(conversation_id, _t(lang, "cancelled"), "cancelled")
    if understanding.get("intent") != "intake":
        return _reply(conversation_id, _t(lang, "help"), "collecting")

    slots = dict(understanding.get("slots") or {})
    wh = _match_warehouse(tenant, text)
    if wh is not None:
        slots["warehouse_id"] = wh.id
        slots["warehouse_name"] = wh.name

    state = {
        "intent": "intake",
        "phase": "collecting",
        "awaiting": None,
        "slots": slots,
        "draft_token": None,
        "lang": lang,
    }
    return _advance(tenant, user, conversation_id, state)


def _continue(tenant, user, membership, conversation_id, state, text, brain):
    lang = state.get("lang", "ru")
    understanding = brain.interpret(text=text, context=state)
    affirmation = understanding.get("affirmation")

    if affirmation == "cancel":
        _clear(tenant, user, conversation_id)
        return _reply(conversation_id, _t(lang, "cancelled"), "cancelled")

    if state["phase"] == "confirm":
        if affirmation == "yes":
            return _execute(tenant, user, membership, conversation_id, state)
        if affirmation == "no":
            _clear(tenant, user, conversation_id)
            return _reply(conversation_id, _t(lang, "cancelled"), "cancelled")
        return _confirm_reply(tenant, user, conversation_id, state)

    awaiting = state.get("awaiting")
    slots = state["slots"]

    if awaiting == "warehouse":
        if affirmation == "yes" and slots.get("_proposed_wh"):
            wh = Warehouse.objects.filter(
                tenant=tenant, id=slots["_proposed_wh"], is_active=True
            ).first()
            if wh is not None:
                slots["warehouse_id"] = wh.id
                slots["warehouse_name"] = wh.name
            slots.pop("_proposed_wh", None)
        elif affirmation == "no":
            slots.pop("_proposed_wh", None)
            state["awaiting"] = "warehouse_pick"
            _save(tenant, user, conversation_id, state)
            names = ", ".join(f"«{w.name}»" for w in _active_warehouses(tenant))
            return _reply(
                conversation_id, _t(lang, "ask_warehouse_pick", names=names), "collecting"
            )
        else:
            wh = _match_warehouse(tenant, text)
            if wh is not None:
                slots["warehouse_id"] = wh.id
                slots["warehouse_name"] = wh.name
                slots.pop("_proposed_wh", None)
    elif awaiting == "warehouse_pick":
        wh = _match_warehouse(tenant, text)
        if wh is None:
            names = ", ".join(f"«{w.name}»" for w in _active_warehouses(tenant))
            return _reply(
                conversation_id, _t(lang, "warehouse_not_found", names=names), "collecting"
            )
        slots["warehouse_id"] = wh.id
        slots["warehouse_name"] = wh.name
    elif awaiting == "name":
        name = (text or "").strip()
        if name:
            slots["name"] = name[:1].upper() + name[1:]
    elif awaiting in ("quantity", "sale_price", "purchase_price"):
        n = first_number(text)
        if n is None:
            return _reply(conversation_id, _t(lang, "bad_number"), "collecting")
        slots[awaiting] = str(n)
    else:
        for k, v in (understanding.get("slots") or {}).items():
            if v and not slots.get(k):
                slots[k] = v

    return _advance(tenant, user, conversation_id, state)


def _advance(tenant, user, conversation_id, state):
    lang = state.get("lang", "ru")
    slots = state["slots"]

    for field in _REQUIRED_FIELDS:
        if not slots.get(field):
            state["awaiting"] = field
            _save(tenant, user, conversation_id, state)
            return _reply(conversation_id, _t(lang, f"ask_{field}"), "collecting")

    if not slots.get("warehouse_id"):
        warehouses = _active_warehouses(tenant)
        if not warehouses:
            _clear(tenant, user, conversation_id)
            return _reply(conversation_id, _t(lang, "no_warehouse"), "cancelled")
        proposed = warehouses[0]
        slots["_proposed_wh"] = proposed.id
        state["awaiting"] = "warehouse"
        _save(tenant, user, conversation_id, state)
        return _reply(
            conversation_id, _t(lang, "ask_warehouse_one", name=proposed.name), "collecting"
        )

    state["phase"] = "confirm"
    state["awaiting"] = "confirm"
    state["draft_token"] = uuid.uuid4().hex
    slots.pop("_proposed_wh", None)
    _save(tenant, user, conversation_id, state)
    return _confirm_reply(tenant, user, conversation_id, state)


def _draft_payload(state):
    slots = state["slots"]
    return {
        "intent": "intake",
        "token": state.get("draft_token"),
        "product": {
            "name": slots.get("name"),
            "color": slots.get("color"),
            "size": slots.get("size"),
            "purchase_price": slots.get("purchase_price"),
            "sale_price": slots.get("sale_price"),
            "quantity": slots.get("quantity"),
            "warehouse_name": slots.get("warehouse_name"),
        },
    }


def _confirm_reply(tenant, user, conversation_id, state):
    lang = state.get("lang", "ru")
    slots = state["slots"]
    parts = [_t(lang, "confirm_create", name=slots.get("name"))]
    attrs = [a for a in (slots.get("color"), slots.get("size")) if a]
    if attrs:
        parts.append("(" + ", ".join(attrs) + ")")
    parts.append(_t(lang, "confirm_intake", qty=slots.get("quantity")))
    parts.append(_t(lang, "confirm_warehouse", name=slots.get("warehouse_name")))
    prices = []
    if slots.get("purchase_price"):
        prices.append(_t(lang, "purchase", v=slots["purchase_price"]))
    if slots.get("sale_price"):
        prices.append(_t(lang, "sale", v=slots["sale_price"]))
    tail = f" ({', '.join(prices)})" if prices else ""
    reply = " ".join(parts) + tail + "?"
    return _reply(conversation_id, reply, "confirm", draft=_draft_payload(state))


def _execute(tenant, user, membership, conversation_id, state):
    lang = state.get("lang", "ru")
    role = getattr(membership, "role", None)
    if role not in _INTAKE_ROLES:
        _clear(tenant, user, conversation_id)
        return _reply(conversation_id, _t(lang, "no_permission"), "cancelled")

    slots = state["slots"]
    data = {
        "name": slots.get("name"),
        "color": slots.get("color") or "",
        "size": slots.get("size") or "",
        "purchase_price": _dec(slots.get("purchase_price")),
        "sale_price": _dec(slots.get("sale_price")),
        "quantity": _dec(slots.get("quantity")),
        "warehouse": slots.get("warehouse_id"),
    }
    try:
        product = quick_create_product(tenant=tenant, data=data)
    except ValidationError as exc:
        _clear(tenant, user, conversation_id)
        return _reply(conversation_id, _t(lang, "exec_error", detail=exc.detail), "cancelled")

    state["phase"] = "done"
    state["awaiting"] = None
    _save(tenant, user, conversation_id, state)

    result = {
        "product_id": product.id,
        "name": product.name,
        "quantity": slots.get("quantity"),
        "warehouse_name": slots.get("warehouse_name"),
    }
    reply = _t(
        lang,
        "done",
        name=product.name,
        qty=slots.get("quantity"),
        wh=slots.get("warehouse_name"),
    )
    return _reply(conversation_id, reply, "done", result=result)
