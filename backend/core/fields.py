from rest_framework import serializers


class RelativeImageField(serializers.ImageField):
    """Imagem sempre representada por caminho relativo (/media/...)."""

    def to_representation(self, value):
        if not value:
            return None
        try:
            return value.url
        except (AttributeError, ValueError):
            return None
