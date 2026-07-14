from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import PayloadTooLarge
from apps.common.permissions import ManageCatalog
from apps.voice.providers import get_stt_provider

from .engine import handle_message
from .serializers import AssistantMessageSerializer


class AssistantMessageView(APIView):
    """
    POST /api/assistant/message/

    Один шаг диалога с помощником. Принимает text или audio (голос → STT) и
    возвращает {conversation_id, reply, state, draft, result}. ИИ только
    понимает и предлагает — запись в БД происходит через существующие сервисы
    только после явного подтверждения (см. engine.py и docs/ASSISTANT.md).

    Приёмка/создание товара — право owner/manager (ManageCatalog).
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [ManageCatalog]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")

        serializer = AssistantMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        text = (data.get("text") or "").strip()
        audio = data.get("audio")
        from_audio = False
        if not text and audio is not None:
            if audio.size > settings.VOICE_MAX_AUDIO_BYTES:
                mb = settings.VOICE_MAX_AUDIO_BYTES // (1024 * 1024)
                raise PayloadTooLarge(f"Аудиофайл слишком большой (макс {mb} МБ).")
            provider = get_stt_provider()
            text = provider.transcribe(audio.read(), language=data.get("language", "uz-UZ"))
            from_audio = True

        result = handle_message(
            tenant=tenant,
            user=request.user,
            membership=request.membership,
            conversation_id=data.get("conversation_id"),
            text=text,
            language=data.get("language", "uz-UZ"),
        )
        # Для голоса возвращаем распознанный текст — чтобы показать в чате, что
        # именно расслышал распознаватель (видно, где теряется слово).
        if from_audio:
            result["transcript"] = text
        return Response(result)
