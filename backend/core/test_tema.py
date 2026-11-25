import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from core.models import Tema

MEDIA_TEMP = tempfile.mkdtemp(prefix="assistec-tema-teste-")
SENHA = "Senha@Forte123"
HASH = make_password(SENHA)


def tearDownModule():
    shutil.rmtree(MEDIA_TEMP, ignore_errors=True)


def imagem_png(nome="logo.png"):
    buf = BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, format="PNG")
    return SimpleUploadedFile(nome, buf.getvalue(), content_type="image/png")


@override_settings(PAINEL_TEMA_SENHA_HASH=HASH, MEDIA_ROOT=MEDIA_TEMP)
class TemaApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        r = self.client.post("/api/tema/desbloquear/", {"senha": SENHA}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_X_TEMA_TOKEN=r.data["token"])

    def test_patch_de_cor_funciona(self):
        r = self.client.patch("/api/tema/", {"cor_menu": "#112233"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Tema.carregar().cor_menu, "#112233")

    def test_upload_de_imagem_e_renomeado_com_uuid(self):
        r = self.client.patch("/api/tema/", {"logo": imagem_png("malicioso.html")}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        caminho = r.data["logo"]
        self.assertTrue(caminho.startswith("/media/tema/"))
        self.assertTrue(caminho.endswith(".png"))
        self.assertNotIn("malicioso", caminho)
        self.assertTrue((Path(MEDIA_TEMP) / caminho.removeprefix("/media/")).exists())

    def test_upload_de_video_com_extensao_perigosa_e_recusado(self):
        video = SimpleUploadedFile("x.html", b"<script>alert(1)</script>", content_type="text/html")
        r = self.client.patch("/api/tema/", {"login_video": video}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("login_video", r.data)

    def test_erro_de_validacao_nao_apaga_midia_antiga(self):
        r = self.client.patch("/api/tema/", {"logo": imagem_png()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        antigo = r.data["logo"]
        r = self.client.patch("/api/tema/", {"login_fundo_tipo": "imagem"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertTrue((Path(MEDIA_TEMP) / antigo.removeprefix("/media/")).exists())
        self.assertEqual(Tema.carregar().logo.name, antigo.removeprefix("/media/"))

    def test_token_e_invalidado_quando_a_senha_muda(self):
        with self.settings(PAINEL_TEMA_SENHA_HASH=make_password("Outra@Senha123")):
            r = self.client.patch("/api/tema/", {"cor_menu": "#AABBCC"}, format="json")
        self.assertEqual(r.status_code, 403)
