from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def post(self, request):
        serializer = VoiceParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        audio_bytes = None
        if data.get("audio"):
            audio_bytes = data["audio"].read()

        result = transcribe_and_parse(
            audio_bytes=audio_bytes,
            text=data.get("text"),
            language=data.get("language", "uz-UZ"),
        )
        return Response(result)
