import hashlib

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import signing
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Tema

TOKEN_SALT = "tema-painel"
TOKEN_MAX_AGE = 60 * 30


class PainelDesativado(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = {
        "detail": "O painel de tema não está ativado neste servidor.",
        "codigo": "painel_desativado",
    }


class SessaoExpirada(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Sessão do painel expirada. Entre de novo."


def painel_ativo():
    return bool(getattr(settings, "PAINEL_TEMA_SENHA_HASH", ""))


def _marca_senha():
    return hashlib.sha256(settings.PAINEL_TEMA_SENHA_HASH.encode()).hexdigest()


def _token_valido(token):
    if not token:
        return False
    try:
        dados = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        return dados.get("senha") == _marca_senha()
    except Exception:
        return False


def exigir_token(request):

    if not painel_ativo():
        raise PainelDesativado()
    token = request.headers.get("X-Tema-Token") or request.META.get("HTTP_X_TEMA_TOKEN")
    if not _token_valido(token):
        raise SessaoExpirada()


class TemaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "tema"
    throttle_classes = [ScopedRateThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        if self.request.method == "GET":
            return []
        return super().get_throttles()

    def get(self, request):
        tema = Tema.carregar()
        return Response(tema.para_dict(request))

    def patch(self, request):
        exigir_token(request)
        tema = Tema.carregar()
        erros = tema.aplicar(request.data, request.FILES)
        if erros:
            return Response(erros, status=status.HTTP_400_BAD_REQUEST)
        tema.salvar_com_arquivos()
        return Response(tema.para_dict(request))



class DesbloquearTema(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "tema"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        if not painel_ativo():
            raise PainelDesativado()
        senha = (request.data.get("senha") or "").strip()
        if not senha or not check_password(senha, settings.PAINEL_TEMA_SENHA_HASH):
            return Response({"detail": "Senha incorreta."}, status=status.HTTP_403_FORBIDDEN)
        token = signing.dumps({"ok": True, "senha": _marca_senha()}, salt=TOKEN_SALT)

        return Response({"token": token})


class RestaurarTema(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "tema"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        exigir_token(request)
        tema = Tema.carregar()
        tema.restaurar_padrao()
        tema.salvar_com_arquivos()
        return Response(tema.para_dict(request))

