from rest_framework import serializers


class AssistantMessageSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=64
    )
    text = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    audio = serializers.FileField(required=False)
    language = serializers.CharField(required=False, default="uz-UZ")

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        if not text and not attrs.get("audio"):
            raise serializers.ValidationError("Нужен text или audio.")
        return attrs
