"""Invalidação de sessões (refresh tokens) de um usuário.

Usado quando a senha muda (troca pelo próprio usuário, reset por comando) ou
quando um usuário é desativado: todos os refresh tokens já emitidos passam a
ser recusados na renovação.
"""
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


def invalidar_tokens(usuario):
    """Marca como blacklist todos os refresh tokens emitidos para o usuário."""
    for token in OutstandingToken.objects.filter(user=usuario):
        BlacklistedToken.objects.get_or_create(token=token)
