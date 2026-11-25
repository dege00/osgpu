import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from config.envlocal import carregar_env_local


class EnvLocalTest(TestCase):
    def test_aplica_ignora_comentarios_remove_aspas_e_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / ".env.local"
            caminho.write_text(
                "# comentario\r\n"
                "\r\n"
                "CHAVE_A=valor\r\n"
                "CHAVE_B=\"com aspas\"\r\n"
                "CHAVE_C='simples'\r\n"
                "EXISTENTE=novo\r\n",
                encoding="utf-8",
            )
            anterior = os.environ.get("EXISTENTE")
            os.environ["EXISTENTE"] = "mantem"
            try:
                os.environ.pop("CHAVE_A", None)
                os.environ.pop("CHAVE_B", None)
                os.environ.pop("CHAVE_C", None)
                carregar_env_local(caminho)
                self.assertEqual(os.environ.get("CHAVE_A"), "valor")
                self.assertEqual(os.environ.get("CHAVE_B"), "com aspas")
                self.assertEqual(os.environ.get("CHAVE_C"), "simples")
                self.assertEqual(os.environ.get("EXISTENTE"), "mantem")
            finally:
                for k in ("CHAVE_A", "CHAVE_B", "CHAVE_C"):
                    os.environ.pop(k, None)
                if anterior is None:
                    os.environ.pop("EXISTENTE", None)
                else:
                    os.environ["EXISTENTE"] = anterior

    def test_arquivo_inexistente_nao_da_erro(self):
        carregar_env_local(Path("C:/caminho/que/nao/existe/.env.local"))


class GerarSenhaTemaGravarEnvTest(TestCase):
    def test_grava_cria_substitui_e_preserva(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            env = base / ".env.local"
            with override_settings(BASE_DIR=base):
                with patch("getpass.getpass", return_value="segredo1"):
                    out = StringIO()
                    call_command("gerar_senha_tema", "--gravar-env", stdout=out)
                texto = env.read_text(encoding="utf-8")
                self.assertIn("PAINEL_TEMA_SENHA_HASH=", texto)
                self.assertTrue(texto.endswith("\n"))

                env.write_text("OUTRA=1\nPAINEL_TEMA_SENHA_HASH=velho\nMAIS=2\n", encoding="utf-8")
                with patch("getpass.getpass", return_value="segredo2"):
                    out = StringIO()
                    call_command("gerar_senha_tema", "--gravar-env", stdout=out)
                linhas = env.read_text(encoding="utf-8").splitlines()
                self.assertEqual(linhas[0], "OUTRA=1")
                self.assertEqual(linhas[2], "MAIS=2")
                self.assertTrue(linhas[1].startswith("PAINEL_TEMA_SENHA_HASH="))
                self.assertNotEqual(linhas[1], "PAINEL_TEMA_SENHA_HASH=velho")


@override_settings(PAINEL_TEMA_SENHA_HASH="")
class PainelDesativadoTest(APITestCase):
    def test_desbloquear_retorna_codigo_painel_desativado(self):
        r = self.client.post("/api/tema/desbloquear/", {"senha": "qualquer"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data.get("codigo"), "painel_desativado")

    def test_patch_retorna_codigo_painel_desativado(self):
        r = self.client.patch("/api/tema/", {"cor_menu": "#000000"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data.get("codigo"), "painel_desativado")


class SettingsImportTest(TestCase):
    def test_settings_importa_sem_env_local(self):
        # settings já foi carregado no processo de teste; valida que módulo está acessível
        self.assertTrue(hasattr(settings, "PAINEL_TEMA_SENHA_HASH"))
