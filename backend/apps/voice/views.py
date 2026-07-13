from django.conf import settings
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import PayloadTooLarge
from apps.common.permissions import ManageCatalog

from .serializers import VoiceParseSerializer
from .services import transcribe_and_parse


class ParseProductView(APIView):
    """
    POST /api/voice/parse-product/

    Принимает аудио (multipart, поле audio) или text (json/form) и возвращает
    {provider, transcript, draft}. Черновик товара НЕ сохраняется в БД —
    его правит и подтверждает пользователь в форме.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [ManageCatalog]

    def post(self, request):
        serializer = VoiceParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        audio_bytes = None
        audio = data.get("audio")
        if audio is not None:
            if audio.size > settings.VOICE_MAX_AUDIO_BYTES:
                mb = settings.VOICE_MAX_AUDIO_BYTES // (1024 * 1024)
                raise PayloadTooLarge(f"Аудиофайл слишком большой (макс {mb} МБ).")
            audio_bytes = audio.read()

        result = transcribe_and_parse(
            audio_bytes=audio_bytes,
            text=data.get("text"),
            language=data.get("language", "uz-UZ"),
        )
        return Response(result)
