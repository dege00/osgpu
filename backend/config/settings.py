import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

if "test" not in sys.argv:
    from .envlocal import carregar_env_local
    carregar_env_local(BASE_DIR / ".env.local")

DEBUG = os.getenv("DEBUG", "1") == "1"
SECRET_KEY_PADRAO = "dev-inseguro-troque-em-producao-123"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = SECRET_KEY_PADRAO
    else:
        raise ImproperlyConfigured("Defina SECRET_KEY no ambiente quando DEBUG=0.")
SECRET_KEYS_INSEGURAS = {SECRET_KEY_PADRAO, "troque-por-uma-string-longa-e-aleatoria"}
if not DEBUG and (SECRET_KEY in SECRET_KEYS_INSEGURAS or len(SECRET_KEY) < 32):
    raise ImproperlyConfigured("Defina uma SECRET_KEY longa e aleat��ria (m��nimo 32 caracteres) com DEBUG=0.")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*" if DEBUG else "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# URL pǧblica do frontend (usada no link de acompanhamento enviado por WhatsApp)
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# Seguran��a em produ��ǜo (proxy HTTPS na frente do Gunicorn/Nginx)
USE_X_FORWARDED_HOST = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt.token_blacklist", "django_filters", "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages"]},
}]
WSGI_APPLICATION = "config.wsgi.application"

if os.getenv("POSTGRES_DB"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"), "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "db"), "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }}
else:  # desenvolvimento rǭpido
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "core.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.Paginacao",
    "PAGE_SIZE": 30,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "publico": "60/min",   # endpoints pǧblicos (ex.: /api/saude/)
        "auth": "10/min",      # login (protege contra for��a bruta de senha)
        "refresh": "60/min",   # renova��ǜo de token (nǜo pode ser tǜo apertada quanto o login)
        "senha": "5/min",      # troca de senha
        "tema": "5/min",       # senha do painel de personaliza��ǜo
    },
    # Quantos proxies confiǭveis existem antes do Django (Caddy + Nginx = 2 em produ��ǜo).
    # Sem isso o limite por IP vǦ sempre o IP do container do Nginx e bloqueia todo mundo junto.
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES", "0")),
}
# Access token curto (60 min) limita o dano de um token vazado. A renova��ǜo Ǹ
# feita pelo refresh token (14 dias). Sem ROTATE_REFRESH_TOKENS de prop��sito: a
# rota��ǜo quebraria a renova��ǜo ǧnica no frontend. Tokens revogados entram na
# blacklist (rest_framework_simplejwt.token_blacklist); limpe os expirados com
# "manage.py flushexpiredtokens" (veja o README).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}

if "test" in sys.argv:  # hash de senha rǭpido s�� nos testes (a su��te fica bem mais veloz)
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Painel secreto de personaliza��ǜo (logo, cores, tela de login). Hash gerado por
# "python manage.py gerar_senha_tema". Sem essa variǭvel o painel fica desativado.
PAINEL_TEMA_SENHA_HASH = os.getenv("PAINEL_TEMA_SENHA_HASH", "")

if (DEBUG and not PAINEL_TEMA_SENHA_HASH and os.environ.get("RUN_MAIN") == "true" and "runserver" in sys.argv):
    print("[assistec] Painel de tema desativado: rode `python manage.py gerar_senha_tema --gravar-env` e reinicie o servidor.", file=sys.stderr)
