"""Geração e validação de senhas para os comandos de gestão."""
import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

ALFABETO = string.ascii_letters + string.digits + "!@#$%&*"


def gerar_senha(tamanho=16):
    """Senha aleatória forte (letras, números e símbolos)."""
    return "".join(secrets.choice(ALFABETO) for _ in range(tamanho))


def erros_de_senha(senha, usuario=None):
    """Devolve a lista de erros dos validadores do Django (vazia se a senha for válida)."""
    try:
        validate_password(senha, usuario)
    except ValidationError as e:
        return list(e.messages)
    return []
