from .nlu import parse_product_draft
from .providers import get_stt_provider


def transcribe_and_parse(*, audio_bytes=None, text=None, language="uz-UZ") -> dict:
    """
    Возвращает {provider, transcript, draft}.

    Если передан text — используем его как распознанный текст (без STT), иначе
    прогоняем audio_bytes через провайдера. Черновик товара НЕ сохраняется —
    его подтверждает человек.
    """
    provider = get_stt_provider()
    if text is None:
        if audio_bytes is None:
            raise ValueError("Нужен audio или text.")
        transcript = provider.transcribe(audio_bytes, language=language)
        provider_name = provider.name
    else:
        transcript = text
        provider_name = "text"

    draft = parse_product_draft(transcript)
    return {"provider": provider_name, "transcript": transcript, "draft": draft}
