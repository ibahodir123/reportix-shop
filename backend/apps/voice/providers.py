"""
Абстракция над провайдером распознавания речи (STT).

Доменный код зависит только от интерфейса STTProvider, поэтому провайдера
(mock / Google / локальный UZ / Yandex / Whisper) можно менять через настройку
STT_PROVIDER без изменения логики. Пока нет ключей — работает MockSTTProvider.
"""

from abc import ABC, abstractmethod

from django.conf import settings


class STTProvider(ABC):
    name = "base"

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str = "uz-UZ") -> str:
        """Возвращает распознанный текст для аудио."""
        raise NotImplementedError


class MockSTTProvider(STTProvider):
    """
    Заглушка для разработки без ключей. Возвращает фиксированный текст, чтобы
    можно было отлаживать весь конвейер (STT → NLU → черновик → форма).
    """

    name = "mock"
    SAMPLE = "Футболка синяя размер эль закуп 45 тысяч продажа 79 тысяч 20 штук"

    def transcribe(self, audio_bytes: bytes, language: str = "uz-UZ") -> str:
        return self.SAMPLE


class GoogleCloudSTTProvider(STTProvider):
    """
    Google Cloud Speech-to-Text. Узбекский — код uz-UZ (лучшее качество на
    модели Chirp 3, требует v2 API + recognizer; здесь v1 как отправная точка).

    Требует пакет google-cloud-speech и учётные данные
    (GOOGLE_APPLICATION_CREDENTIALS). Импорт ленивый — mock работает без пакета.
    """

    name = "google"

    def transcribe(self, audio_bytes: bytes, language: str = "uz-UZ") -> str:
        from google.cloud import speech  # ленивый импорт

        client = speech.SpeechClient()
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language,
            enable_automatic_punctuation=True,
            model=getattr(settings, "GOOGLE_STT_MODEL", "default"),
        )
        response = client.recognize(config=config, audio=audio)
        parts = [r.alternatives[0].transcript for r in response.results if r.alternatives]
        return " ".join(parts).strip()


_PROVIDERS = {
    "mock": MockSTTProvider,
    "google": GoogleCloudSTTProvider,
}


def get_stt_provider() -> STTProvider:
    key = getattr(settings, "STT_PROVIDER", "mock")
    provider_cls = _PROVIDERS.get(key, MockSTTProvider)
    return provider_cls()
