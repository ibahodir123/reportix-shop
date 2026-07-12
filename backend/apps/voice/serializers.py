from rest_framework import serializers


class VoiceParseSerializer(serializers.Serializer):
    """Вход: либо аудиофайл (audio), либо готовый текст (text) для отладки."""

    audio = serializers.FileField(required=False)
    text = serializers.CharField(required=False, allow_blank=False)
    language = serializers.CharField(required=False, default="uz-UZ")

    def validate(self, attrs):
        if not attrs.get("audio") and not attrs.get("text"):
            raise serializers.ValidationError("Передайте audio или text.")
        return attrs
