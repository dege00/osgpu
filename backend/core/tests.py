import base64
import os
import shutil
import tempfile
import zipfile
from io import BytesIO, StringIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from PIL import Image
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from .models import Cliente, FotoOS, ItemOS, Loja, OrdemServico, Peca, Usuario

MEDIA_TEST = tempfile.mkdtemp(prefix="assistec-test-")


def tearDownModule():
    shutil.rmtree(MEDIA_TEST, ignore_errors=True)


def bytes_imagem(largura=2000, altura=100, formato="JPEG"):
    buf = BytesIO()
    Image.new("RGB", (largura, altura), (100, 150, 200)).save(buf, formato)
    return buf.getvalue()


def bytes_imagem_grande(lado=2200):
    buf = BytesIO()
    Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3)).save(buf, "JPEG", quality=95)
    return buf.getvalue()


class BaseTeste(APITestCase):
    def setUp(self):
        self.loja = Loja.objects.create(nome="Loja A")
        self.outra_loja = Loja.objects.create(nome="Loja B")
        self.admin = Usuario.objects.create_user("admin", password="SenhaForte123", loja=self.loja, cargo="admin")
        self.atendente = Usuario.objects.create_user("atendente", password="SenhaForte123", loja=self.loja, cargo="atendente")
        self.tecnico = Usuario.objects.create_user("tecnico", password="SenhaForte123", loja=self.loja, cargo="tecnico")
        self.tecnico2 = Usuario.objects.create_user("tecnico2", password="SenhaForte123", loja=self.loja, cargo="tecnico")
        self.admin_b = Usuario.objects.create_user("adminb", password="SenhaForte123", loja=self.outra_loja, cargo="admin")
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Cliente A", telefone="86999990000")
        self.peca = Peca.objects.create(loja=self.loja, nome="Tela", custo=30, preco=100, quantidade=10)

    def autenticar(self, usuario):
        self.client.force_authenticate(user=usuario)

    def criar_os(self, tecnico=None, status="em_analise", loja=None):
        return OrdemServico.objects.create(
            loja=loja or self.loja,
            cliente=self.cliente if not loja else Cliente.objects.create(loja=loja, nome="Cliente B"),
            defeito="Não liga",
            status=status,
            tecnico=tecnico,
        )

    def criar_os_api(self, **extra):
        dados = {"cliente": self.cliente.id, "defeito": "Não liga", "marca": "Samsung", "modelo": "A10",
                 "categoria": "celular"}
        dados.update(extra)
        r = self.client.post("/api/os/", dados, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def adicionar_item(self, os_id, **dados):
        base = {"os": os_id, "tipo": "servico", "descricao": "Mão de obra", "valor_unitario": "100", "quantidade": 1}
        base.update(dados)
        return self.client.post("/api/itens/", base, format="json")


class FluxoCompleto(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)

    def test_fluxo(self):
        c = self.client.post("/api/clientes/", {"nome": "João Silva", "telefone": "86988887777"}, format="json").data
        peca = self.client.post("/api/pecas/", {"nome": "Tela A10", "custo": "80", "preco": "150", "quantidade": 3, "minimo": 1}, format="json").data
        os_ = self.client.post("/api/os/", {"cliente": c["id"], "categoria": "celular", "marca": "Samsung", "modelo": "A10", "defeito": "Tela quebrada", "checklist": "Liga: ok\nTela: com defeito"}, format="json")
        self.assertEqual(os_.status_code, 201, os_.data)
        os_ = os_.data
        self.assertEqual(os_["numero"], 1)
        r = self.client.post("/api/itens/", {"os": os_["id"], "tipo": "peca", "peca": peca["id"], "quantidade": 2}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.client.post("/api/itens/", {"os": os_["id"], "tipo": "servico", "descricao": "Mão de obra", "valor_unitario": "50"}, format="json")
        self.assertEqual(self.client.get(f"/api/pecas/{peca['id']}/").data["quantidade"], 1)
        det = self.client.get(f"/api/os/{os_['id']}/").data
        self.assertEqual(float(det["total"]), 350.0)
        self.assertEqual(float(det["lucro"]), 190.0)
        r = self.client.post("/api/itens/", {"os": os_["id"], "tipo": "peca", "peca": peca["id"], "quantidade": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        self.client.post(f"/api/os/{os_['id']}/status/", {"status": "finalizado"}, format="json")
        self.assertIn("wa.me/5586988887777", self.client.get(f"/api/os/{os_['id']}/whatsapp/").data["url"])
        pdf = self.client.get(f"/api/os/{os_['id']}/pdf/")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.client.credentials()
        pub = self.client.get(f"/api/publico/os/{det['token']}/")
        self.assertEqual(pub.status_code, 200)
        self.assertEqual(len(pub.data["historico"]), 2)
        tok = self.client.post("/api/auth/login/", {"username": "admin", "password": "SenhaForte123"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + tok)
        r = self.client.post(f"/api/os/{os_['id']}/pagar/", {"forma": "pix"}, format="json")
        self.assertEqual(r.data["status"], "pago")
        self.assertEqual(float(self.client.get("/api/lancamentos/resumo/").data["entradas"]), 350.0)
        self.assertIn("saldo_mes", self.client.get("/api/dashboard/").data)

    def test_isolamento_entre_lojas(self):
        c = self.client.post("/api/clientes/", {"nome": "Secreto"}, format="json").data
        self.autenticar(self.admin_b)
        self.assertEqual(self.client.get(f"/api/clientes/{c['id']}/").status_code, 404)
        self.assertEqual(self.client.get("/api/clientes/").data["count"], 0)


class PermissoesTest(BaseTeste):
    def test_tecnico_ve_apenas_os_dele_ou_sem_tecnico(self):
        minha = self.criar_os(tecnico=self.tecnico)
        sem_tecnico = self.criar_os()
        de_outro = self.criar_os(tecnico=self.tecnico2)
        self.autenticar(self.tecnico)
        r = self.client.get("/api/os/")
        ids = {o["id"] for o in r.data["results"]}
        self.assertIn(minha.id, ids)
        self.assertIn(sem_tecnico.id, ids)
        self.assertNotIn(de_outro.id, ids)
        self.assertEqual(self.client.get(f"/api/os/{de_outro.id}/").status_code, 404)

    def test_admin_ve_todas_as_os_da_loja(self):
        self.criar_os(tecnico=self.tecnico2)
        self.criar_os()
        self.autenticar(self.admin)
        self.assertEqual(self.client.get("/api/os/").data["count"], 2)

    def test_atendente_nao_ve_custo_nem_financeiro(self):
        self.autenticar(self.admin)
        os_ = self.criar_os()
        r = self.adicionar_item(os_.id, tipo="peca", peca=self.peca.id, quantidade=1)
        self.assertEqual(r.status_code, 201, r.data)
        self.autenticar(self.atendente)
        detail = self.client.get(f"/api/os/{os_.id}/")
        self.assertIsNone(detail.data["custo"])
        self.assertIsNone(detail.data["lucro"])
        self.assertNotIn("custo_unitario", detail.data["itens"][0])
        self.assertNotIn("custo", self.client.get(f"/api/pecas/{self.peca.id}/").data)
        self.assertEqual(self.client.get("/api/lancamentos/").status_code, 403)
        dashboard = self.client.get("/api/dashboard/").data
        self.assertIn("abertas", dashboard)
        self.assertNotIn("saldo_mes", dashboard)

    def test_admin_ve_custo(self):
        self.autenticar(self.admin)
        os_ = self.criar_os()
        self.adicionar_item(os_.id, tipo="peca", peca=self.peca.id, quantidade=1)
        self.assertIsNotNone(self.client.get(f"/api/os/{os_.id}/").data["custo"])
        self.assertEqual(self.client.get(f"/api/pecas/{self.peca.id}/").data["custo"], "30.00")
        self.assertEqual(self.client.get("/api/lancamentos/").status_code, 200)

    def test_tecnico_nao_acessa_dados_de_outra_loja(self):
        os_b = self.criar_os(tecnico=None, loja=self.outra_loja)
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get(f"/api/os/{os_b.id}/").status_code, 404)

    def test_atendente_nao_altera_custo_da_peca(self):
        self.autenticar(self.atendente)
        r = self.client.patch(f"/api/pecas/{self.peca.id}/", {"nome": "Tela nova", "custo": "999"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.nome, "Tela nova")
        self.assertEqual(float(self.peca.custo), 30.0)


class PagamentoParcialTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.os = self.criar_os_api()
        self.adicionar_item(self.os["id"], valor_unitario="100")

    def test_pagamento_parcial_e_quitacao(self):
        r = self.client.post(f"/api/os/{self.os['id']}/pagar/", {"forma": "pix", "valor": "40"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotEqual(r.data["status"], "pago")
        self.assertEqual(float(r.data["pago"]), 40.0)
        self.assertEqual(float(r.data["total"]), 100.0)
        r = self.client.post(f"/api/os/{self.os['id']}/pagar/", {"forma": "dinheiro", "valor": "60"}, format="json")
        self.assertEqual(r.data["status"], "pago")
        self.assertEqual(float(r.data["pago"]), 100.0)

    def test_recusa_valor_maior_que_o_restante(self):
        r = self.client.post(f"/api/os/{self.os['id']}/pagar/", {"forma": "pix", "valor": "150"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("máximo", r.data["detail"])
        self.assertEqual(float(self.client.get(f"/api/os/{self.os['id']}/").data["pago"]), 0.0)

    def test_recusa_valor_invalido(self):
        r = self.client.post(f"/api/os/{self.os['id']}/pagar/", {"forma": "pix", "valor": "abc"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("válido", r.data["detail"])

    def test_nao_recebe_os_cancelada(self):
        self.client.post(f"/api/os/{self.os['id']}/status/", {"status": "cancelado"}, format="json")
        r = self.client.post(f"/api/os/{self.os['id']}/pagar/", {"forma": "pix", "valor": "10"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("cancelada", r.data["detail"])


class EdicaoItemTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.peca.quantidade = 3
        self.peca.save()
        self.autenticar(self.admin)
        self.os = self.criar_os_api()
        self.item = self.adicionar_item(self.os["id"], tipo="peca", peca=self.peca.id, quantidade=2).data

    def estoque(self):
        self.peca.refresh_from_db()
        return self.peca.quantidade

    def test_edita_quantidade_ajustando_estoque_pela_diferenca(self):
        self.assertEqual(self.estoque(), 1)
        r = self.client.patch(f"/api/itens/{self.item['id']}/", {"quantidade": 3}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.estoque(), 0)
        r = self.client.patch(f"/api/itens/{self.item['id']}/", {"quantidade": 1}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.estoque(), 2)

    def test_recusa_quantidade_sem_estoque_e_nao_altera_nada(self):
        r = self.client.patch(f"/api/itens/{self.item['id']}/", {"quantidade": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.estoque(), 1)
        self.item = ItemOS.objects.get(pk=self.item["id"])
        self.assertEqual(self.item.quantidade, 2)

    def test_edita_valor(self):
        r = self.client.patch(f"/api/itens/{self.item['id']}/", {"valor_unitario": "250"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        os_ = self.client.get(f"/api/os/{self.os['id']}/").data
        self.assertEqual(float(os_["total"]), 500.0)
        self.assertEqual(float(os_["lucro"]), 440.0)

    def test_edita_item_de_servico(self):
        servico = self.adicionar_item(self.os["id"], descricao="Limpeza", valor_unitario="50").data
        r = self.client.patch(f"/api/itens/{servico['id']}/", {"quantidade": 2, "valor_unitario": "70"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(float(r.data["subtotal"]), 140.0)

    def test_nao_edita_item_de_os_cancelada(self):
        self.client.post(f"/api/os/{self.os['id']}/status/", {"status": "cancelado"}, format="json")
        r = self.client.patch(f"/api/itens/{self.item['id']}/", {"quantidade": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("cancelada", str(r.data))


class CancelamentoReaberturaTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.peca.quantidade = 5
        self.peca.save()
        self.os = self.criar_os_api()
        self.adicionar_item(self.os["id"], tipo="peca", peca=self.peca.id, quantidade=2)

    def estoque(self):
        self.peca.refresh_from_db()
        return self.peca.quantidade

    def status(self, os_id, novo):
        return self.client.post(f"/api/os/{os_id}/status/", {"status": novo}, format="json")

    def test_cancelar_devolve_e_reabrir_da_baixa(self):
        self.assertEqual(self.estoque(), 3)
        self.assertEqual(self.status(self.os["id"], "cancelado").status_code, 200)
        self.assertEqual(self.estoque(), 5)
        self.assertEqual(self.status(self.os["id"], "em_analise").status_code, 200)
        self.assertEqual(self.estoque(), 3)

    def test_reabrir_sem_estoque_falha_e_mantem_cancelada(self):
        self.status(self.os["id"], "cancelado")
        outra_os = self.criar_os_api(cliente=self.cliente.id, defeito="Outro")
        self.adicionar_item(outra_os["id"], tipo="peca", peca=self.peca.id, quantidade=4)
        self.assertEqual(self.estoque(), 1)
        r = self.status(self.os["id"], "em_analise")
        self.assertEqual(r.status_code, 400)
        self.assertIn("insuficiente", str(r.data).lower())
        self.assertEqual(OrdemServico.objects.get(pk=self.os["id"]).status, "cancelado")
        self.assertEqual(self.estoque(), 1)

    def test_excluir_os_cancelada_nao_devolve_duas_vezes(self):
        self.status(self.os["id"], "cancelado")
        self.assertEqual(self.estoque(), 5)
        r = self.client.delete(f"/api/os/{self.os['id']}/")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.estoque(), 5)


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class ImagemTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.os = self.criar_os_api()

    def test_foto_e_reduzida_para_1600px(self):
        upload = SimpleUploadedFile("foto.jpg", bytes_imagem(2000, 500), content_type="image/jpeg")
        r = self.client.post("/api/fotos/", {"os": self.os["id"], "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["imagem"].startswith("/media/"))
        self.assertNotIn("http", r.data["imagem"])
        foto = FotoOS.objects.get()
        self.assertTrue(foto.imagem.name.startswith("fotos/"))
        with Image.open(foto.imagem.path) as img:
            self.assertEqual(img.width, 1600)
        detalhe = self.client.get(f"/api/os/{self.os['id']}/")
        self.assertTrue(detalhe.data["fotos"][0]["imagem"].startswith("/media/"))

    def test_foto_existente_continua_aparecendo_com_url_relativa(self):
        foto = FotoOS.objects.create(
            os=OrdemServico.objects.get(pk=self.os["id"]),
            imagem=SimpleUploadedFile("antiga.jpg", bytes_imagem(100, 100), content_type="image/jpeg"),
        )
        r = self.client.get(f"/api/os/{self.os['id']}/")
        self.assertEqual(r.status_code, 200)
        dados = next(f for f in r.data["fotos"] if f["id"] == foto.id)
        self.assertEqual(dados["imagem"], foto.imagem.url)
        self.assertTrue(dados["imagem"].startswith("/media/"))

    def test_aceita_foto_grande_e_salva_reduzida(self):
        conteudo = bytes_imagem_grande()
        self.assertGreater(len(conteudo), 5 * 1024 * 1024)
        upload = SimpleUploadedFile("celular.jpg", conteudo, content_type="image/jpeg")
        r = self.client.post("/api/fotos/", {"os": self.os["id"], "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        foto = FotoOS.objects.get()
        with Image.open(foto.imagem.path) as img:
            self.assertEqual(img.width, 1600)
        self.assertLess(os.path.getsize(foto.imagem.path), len(conteudo))

    def test_recusa_imagem_maior_que_20mb(self):
        upload = SimpleUploadedFile("grande.jpg", b"0" * (20 * 1024 * 1024 + 1), content_type="image/jpeg")
        r = self.client.post("/api/fotos/", {"os": self.os["id"], "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("20 MB", str(r.data))

    def test_heic_sem_suporte_devolve_mensagem_clara(self):
        upload = SimpleUploadedFile("foto.heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00", content_type="image/heic")
        r = self.client.post("/api/fotos/", {"os": self.os["id"], "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("HEIC", str(r.data))

    def test_recusa_arquivo_que_nao_e_imagem(self):
        upload = SimpleUploadedFile("arquivo.txt", b"isto nao e imagem", content_type="text/plain")
        r = self.client.post("/api/fotos/", {"os": self.os["id"], "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("imagem válida", str(r.data))

    def test_assinatura_valida_e_invalida(self):
        buf = BytesIO()
        Image.new("RGBA", (100, 50), (0, 0, 0, 0)).save(buf, "PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        r = self.client.post(f"/api/os/{self.os['id']}/assinar/", {"assinatura": data_url}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["assinatura"].startswith("/media/"))
        self.assertNotIn("http", r.data["assinatura"])
        os_ = OrdemServico.objects.get(pk=self.os["id"])
        self.assertTrue(os_.assinatura.name.startswith("assinaturas/"))
        detalhe = self.client.get(f"/api/os/{self.os['id']}/")
        self.assertTrue(detalhe.data["assinatura"].startswith("/media/"))
        r = self.client.post(f"/api/os/{self.os['id']}/assinar/", {"assinatura": "data:image/png;base64,xx"}, format="json")
        self.assertEqual(r.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class FotoVisivelClienteTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.os = self.criar_os_api()
        self.outra_os = self.criar_os_api()
        self.os_outra_loja = self.criar_os(loja=self.outra_loja)

    def enviar(self, os_id, legenda="", visivel=False, tipo="entrada"):
        upload = SimpleUploadedFile("foto.jpg", bytes_imagem(100, 100), content_type="image/jpeg")
        dados = {"os": os_id, "imagem": upload, "legenda": legenda, "tipo": tipo}
        if visivel:
            dados["visivel_cliente"] = "true"
        r = self.client.post("/api/fotos/", dados, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def foto_outra_loja(self, legenda):
        return FotoOS.objects.create(
            os=self.os_outra_loja, legenda=legenda, visivel_cliente=True,
            imagem=SimpleUploadedFile("outra.jpg", bytes_imagem(100, 100), content_type="image/jpeg"),
        )

    def test_nova_foto_comeca_oculta_e_como_entrada(self):
        foto = self.enviar(self.os["id"])
        self.assertFalse(foto["visivel_cliente"])
        self.assertEqual(foto["tipo"], "entrada")

    def test_patch_marca_visivel_tipo_e_legenda(self):
        foto = self.enviar(self.os["id"])
        r = self.client.patch(f"/api/fotos/{foto['id']}/",
                              {"visivel_cliente": True, "tipo": "servico", "legenda": "Tela trincada"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        foto_db = FotoOS.objects.get(pk=foto["id"])
        self.assertTrue(foto_db.visivel_cliente)
        self.assertEqual(foto_db.tipo, "servico")
        self.assertEqual(foto_db.legenda, "Tela trincada")

    def test_publico_mostra_somente_fotos_visiveis(self):
        self.enviar(self.os["id"], legenda="oculta")
        self.enviar(self.os["id"], legenda="visível", visivel=True)
        self.client.force_authenticate(user=None)
        r = self.client.get(f"/api/publico/os/{self.os['token']}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["fotos"]), 1)
        foto = r.data["fotos"][0]
        self.assertEqual(foto["legenda"], "visível")
        self.assertEqual(foto["tipo"], "entrada")
        self.assertTrue(foto["url"].startswith("/media/fotos/"))
        self.assertNotIn("http", foto["url"])
        self.assertIn("criado_em", foto)
        self.assertNotIn("oculta", str(r.data))

    def test_publico_nao_vaza_foto_de_outra_os_ou_loja(self):
        self.enviar(self.os["id"], legenda="minha", visivel=True)
        self.enviar(self.outra_os["id"], legenda="outra os", visivel=True)
        self.foto_outra_loja("outra loja")
        self.client.force_authenticate(user=None)
        r = self.client.get(f"/api/publico/os/{self.os['token']}/")
        self.assertEqual([f["legenda"] for f in r.data["fotos"]], ["minha"])
        r = self.client.get(f"/api/publico/os/{self.outra_os['token']}/")
        self.assertEqual([f["legenda"] for f in r.data["fotos"]], ["outra os"])

    def test_nao_edita_foto_de_outra_loja(self):
        foto = self.foto_outra_loja("secreta")
        r = self.client.patch(f"/api/fotos/{foto.id}/", {"visivel_cliente": False}, format="json")
        self.assertEqual(r.status_code, 404)
        foto.refresh_from_db()
        self.assertTrue(foto.visivel_cliente)

    def test_pdf_inclui_fotos_de_entrada_e_ignora_servico(self):
        self.enviar(self.os["id"], legenda="Entrada <&>", tipo="entrada", visivel=False)
        self.enviar(self.os["id"], legenda="Andamento", tipo="servico", visivel=True)
        r = self.client.get(f"/api/os/{self.os['id']}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r.content.count(b"/Subtype /Image"), 1)


class UsuariosTest(BaseTeste):
    def test_admin_cria_edita_desativa_e_redefine_senha(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/usuarios/", {"username": "novo", "first_name": "Novo", "senha": "SenhaForte123", "cargo": "atendente", "telefone": "86999990000"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        u = Usuario.objects.get(username="novo")
        self.assertEqual(u.loja, self.loja)
        self.assertTrue(u.check_password("SenhaForte123"))
        r = self.client.patch(f"/api/usuarios/{u.id}/", {"cargo": "tecnico", "is_active": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        u.refresh_from_db()
        self.assertEqual(u.cargo, "tecnico")
        self.assertFalse(u.is_active)
        r = self.client.patch(f"/api/usuarios/{u.id}/", {"senha": "OutraSenha123"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        u.refresh_from_db()
        self.assertTrue(u.check_password("OutraSenha123"))

    def test_nao_admin_nao_gerencia_usuarios(self):
        self.autenticar(self.atendente)
        self.assertEqual(self.client.get("/api/usuarios/").status_code, 403)
        self.assertEqual(self.client.post("/api/usuarios/", {"username": "x", "senha": "SenhaForte123"}, format="json").status_code, 403)

    def test_admin_nao_ve_usuarios_de_outra_loja(self):
        outro = Usuario.objects.create_user("forasteiro", password="SenhaForte123", loja=self.outra_loja, cargo="admin")
        self.autenticar(self.admin)
        ids = {u["id"] for u in self.client.get("/api/usuarios/").data["results"]}
        self.assertNotIn(outro.id, ids)
        self.assertEqual(self.client.get(f"/api/usuarios/{outro.id}/").status_code, 404)

    def test_admin_nao_desativa_a_si(self):
        self.autenticar(self.admin)
        r = self.client.patch(f"/api/usuarios/{self.admin.id}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class ConfiguracaoLojaTest(BaseTeste):
    def test_admin_atualiza_dados_e_logo(self):
        self.autenticar(self.admin)
        logo = SimpleUploadedFile("logo.png", bytes_imagem(200, 100, "PNG"), content_type="image/png")
        dados = {"nome": "Nova Assistência", "telefone": "86988887777", "documento": "12345678000199",
                 "endereco": "Rua A, 1", "termo_garantia": "Garantia de 90 dias.", "logo": logo}
        r = self.client.patch("/api/auth/eu/", dados, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.nome, "Nova Assistência")
        self.assertEqual(self.loja.telefone, "86988887777")
        self.assertTrue(self.loja.logo.name.startswith("logos/"))
        self.assertTrue(r.data["loja"]["logo"].startswith("/media/logos/"))
        self.assertNotIn("http", r.data["loja"]["logo"])
        eu = self.client.get("/api/auth/eu/")
        self.assertTrue(eu.data["loja"]["logo"].startswith("/media/logos/"))

    def test_atendente_nao_edita_loja(self):
        self.autenticar(self.atendente)
        r = self.client.patch("/api/auth/eu/", {"nome": "Invadida"}, format="json")
        self.assertEqual(r.status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class IsolamentoNovosEndpointsTest(BaseTeste):
    """Nenhum endpoint novo pode atravessar a fronteira entre lojas."""

    def setUp(self):
        super().setUp()
        self.os_b = self.criar_os(loja=self.outra_loja)
        self.peca_b = Peca.objects.create(loja=self.outra_loja, nome="Peça B", sku="SKU-B", custo=5, preco=10, quantidade=5)
        self.item_b = ItemOS.objects.create(os=self.os_b, tipo="peca", peca=self.peca_b, descricao="Peça B",
                                            quantidade=1, valor_unitario=10, custo_unitario=5)
        self.autenticar(self.admin)

    def test_itens_de_outra_loja_nao_aparecem_nem_sao_editados(self):
        self.assertEqual(self.client.get(f"/api/itens/?os={self.os_b.id}").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/itens/{self.item_b.id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/itens/{self.item_b.id}/", {"quantidade": 2}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/itens/{self.item_b.id}/").status_code, 404)

    def test_nao_insere_item_em_os_de_outra_loja(self):
        r = self.client.post("/api/itens/", {"os": self.os_b.id, "tipo": "servico", "descricao": "Invasão", "valor_unitario": "10"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("OS inválida", str(r.data))

    def test_nao_ve_peca_por_codigo_de_outra_loja(self):
        self.assertEqual(self.client.get("/api/pecas/por_codigo/?codigo=SKU-B").status_code, 404)
        self.assertEqual(self.client.get(f"/api/pecas/{self.peca_b.id}/").status_code, 404)

    def test_nao_muda_status_nem_recebe_os_de_outra_loja(self):
        self.assertEqual(self.client.post(f"/api/os/{self.os_b.id}/status/", {"status": "finalizado"}, format="json").status_code, 404)
        self.assertEqual(self.client.post(f"/api/os/{self.os_b.id}/pagar/", {"forma": "pix"}, format="json").status_code, 404)
        self.assertEqual(OrdemServico.objects.get(pk=self.os_b.pk).status, "em_analise")

    def test_nao_adiciona_foto_em_os_de_outra_loja(self):
        upload = SimpleUploadedFile("foto.jpg", bytes_imagem(100, 100), content_type="image/jpeg")
        r = self.client.post("/api/fotos/", {"os": self.os_b.id, "imagem": upload}, format="multipart")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(FotoOS.objects.filter(os=self.os_b).exists())

    def test_nao_lanca_movimento_em_os_de_outra_loja(self):
        r = self.client.post("/api/lancamentos/", {"os": self.os_b.id, "tipo": "entrada", "descricao": "Invasão", "valor": "10"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("OS inválida", str(r.data))

    def test_nao_atribui_tecnico_de_outra_loja(self):
        r = self.client.post("/api/os/", {"cliente": self.cliente.id, "defeito": "Teste", "categoria": "celular"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.patch(f"/api/os/{r.data['id']}/", {"tecnico": self.admin_b.id}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("tecnico", r.data)


class AparelhoFlexivelTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)

    def criar(self, **dados):
        base = {"cliente": self.cliente.id, "defeito": "Nao liga"}
        base.update(dados)
        return self.client.post("/api/os/", base, format="json")

    def test_os_celular_com_imei_valido(self):
        r = self.criar(categoria="celular", imei="12345678901234")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["tipo_aparelho"], "Celular")
        self.assertEqual(r.data["imei"], "12345678901234")

    def test_celular_forca_tipo_aparelho(self):
        r = self.criar(categoria="celular", tipo_aparelho="Placa", imei="")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["tipo_aparelho"], "Celular")
        self.assertEqual(r.data["imei"], "")

    def test_imei_invalido_rejeitado(self):
        for ruim in ["123", "123456789012345678", "12345abcde67890"]:
            r = self.criar(categoria="celular", imei=ruim)
            self.assertEqual(r.status_code, 400, ruim)
            self.assertIn("imei", r.data)

    def test_os_outro_sem_descricao_rejeitada(self):
        r = self.criar(categoria="outro")
        self.assertEqual(r.status_code, 400)
        self.assertIn("tipo_aparelho", r.data)

    def test_imei_ignorado_quando_outro(self):
        r = self.criar(categoria="outro", tipo_aparelho="Placa de video", imei="12345678901234")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["tipo_aparelho"], "Placa de video")
        self.assertEqual(r.data["imei"], "")

    def test_numero_serie_aceito_nos_dois_casos(self):
        r = self.criar(categoria="outro", tipo_aparelho="Fonte", numero_serie="SN-123")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["numero_serie"], "SN-123")

    def test_busca_por_numero_serie_e_imei(self):
        self.criar(categoria="celular", imei="12345678901234", numero_serie="SERIE-ABC")
        for termo in ["SERIE-ABC", "12345678901234"]:
            r = self.client.get(f"/api/os/?search={termo}")
            self.assertEqual(r.data["count"], 1, termo)


class AcessoPublicoRemovido(APITestCase):
    def test_registro_publico_nao_existe(self):
        r = self.client.post("/api/auth/registrar/", {"loja": "X", "nome": "Y", "username": "z", "senha": "segredo1"}, format="json")
        self.assertEqual(r.status_code, 404)


class LoginThrottleTest(BaseTeste):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_decima_primeira_tentativa_errada_bloqueia(self):
        for i in range(10):
            r = self.client.post("/api/auth/login/", {"username": "admin", "password": "errada"}, format="json")
            self.assertEqual(r.status_code, 401, i)
        r = self.client.post("/api/auth/login/", {"username": "admin", "password": "errada"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_refresh_tem_limite_proprio_mais_folgado(self):
        login = self.client.post("/api/auth/login/", {"username": "admin", "password": "SenhaForte123"}, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        refresh = login.data["refresh"]
        for i in range(12):  # o login usa "auth" (10/min); o refresh usa "refresh" (60/min)
            r = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
            self.assertEqual(r.status_code, 200, i)


class CriarLojaCommandTest(APITestCase):
    def test_cria_loja_e_admin(self):
        call_command("criar_loja", nome_loja="TecnoPI", usuario="ana", nome="Ana",
                     telefone="86999990000", senha="SenhaForte123")
        loja = Loja.objects.get(nome="TecnoPI")
        usuario = Usuario.objects.get(username="ana")
        self.assertEqual(usuario.loja, loja)
        self.assertEqual(usuario.cargo, "admin")
        self.assertTrue(usuario.check_password("SenhaForte123"))

    def test_recusa_usuario_duplicado(self):
        loja = Loja.objects.create(nome="Existente")
        Usuario.objects.create_user("ana", password="SenhaForte123", loja=loja, cargo="admin")
        with self.assertRaises(CommandError):
            call_command("criar_loja", nome_loja="Nova", usuario="ana", nome="Ana", senha="SenhaForte123")
        self.assertFalse(Loja.objects.filter(nome="Nova").exists())

    def test_gera_senha_quando_omitida(self):
        out = StringIO()
        call_command("criar_loja", nome_loja="Auto", usuario="auto", nome="Auto", stdout=out)
        self.assertIn("Senha gerada", out.getvalue())
        self.assertTrue(Usuario.objects.filter(username="auto").exists())


class TrocarSenhaTest(BaseTeste):
    def setUp(self):
        super().setUp()
        cache.clear()  # o limite de "senha" (5/min) é por IP e persiste entre testes

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_exige_senha_atual(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "errada", "nova_senha": "NovaSenha123"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("SenhaForte123"))

    def test_troca_com_senha_atual_correta(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "SenhaForte123", "nova_senha": "NovaSenha123"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("NovaSenha123"))

    def test_recusa_nova_senha_fraca(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "SenhaForte123", "nova_senha": "123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_limite_de_tentativas_de_troca(self):
        self.autenticar(self.admin)
        for i in range(5):
            r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "errada", "nova_senha": "NovaSenha123"}, format="json")
            self.assertEqual(r.status_code, 400, i)
        r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "errada", "nova_senha": "NovaSenha123"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_troca_devolve_novo_par_e_invalida_refresh_antigo(self):
        login = self.client.post("/api/auth/login/", {"username": "admin", "password": "SenhaForte123"}, format="json").data
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login["access"])
        r = self.client.post("/api/auth/trocar-senha/", {"senha_atual": "SenhaForte123", "nova_senha": "NovaSenha123"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)
        self.client.credentials()
        antigo = self.client.post("/api/auth/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(antigo.status_code, 401)
        novo = self.client.post("/api/auth/refresh/", {"refresh": r.data["refresh"]}, format="json")
        self.assertEqual(novo.status_code, 200, novo.data)


class InvalidarSessoesTest(BaseTeste):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_resetar_senha_invalida_refresh_antigo(self):
        login = self.client.post("/api/auth/login/", {"username": "admin", "password": "SenhaForte123"}, format="json").data
        call_command("resetar_senha", usuario="admin", senha="NovaSenha123")
        r = self.client.post("/api/auth/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_usuario_desativado_perde_refresh(self):
        login = self.client.post("/api/auth/login/", {"username": "atendente", "password": "SenhaForte123"}, format="json").data
        self.autenticar(self.admin)
        r = self.client.patch(f"/api/usuarios/{self.atendente.id}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.credentials()
        rr = self.client.post("/api/auth/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(rr.status_code, 401)


class ExportacaoTest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)

    def _planilha(self, resposta):
        self.assertEqual(resposta.status_code, 200, getattr(resposta, "data", None))
        self.assertEqual(resposta["Content-Type"],
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return load_workbook(BytesIO(resposta.content)).active

    def test_admin_baixa_clientes(self):
        Cliente.objects.create(loja=self.loja, nome="Ana Souza", telefone="86999990000",
                               email="ana@ex.com", documento="12345678900", observacoes="VIP")
        r = self.client.get("/api/exportar/clientes/")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn("clientes-", r["Content-Disposition"])
        self.assertTrue(r["Content-Disposition"].endswith('.xlsx"'))
        ws = self._planilha(r)
        self.assertEqual([c.value for c in ws[1]],
                         ["Nome", "Telefone", "E-mail", "CPF/CNPJ", "Observações", "Cadastrado em"])
        self.assertEqual(ws["A2"].value, "Ana Souza")
        self.assertEqual(ws["B2"].value, "86999990000")
        self.assertEqual(ws.freeze_panes, "A2")

    def test_pecas_com_moeda_numerica(self):
        r = self.client.get("/api/exportar/pecas/")
        self.assertIn("pecas-", r["Content-Disposition"])
        ws = self._planilha(r)
        self.assertEqual([c.value for c in ws[1]],
                         ["Nome", "Código", "Custo", "Preço de venda", "Quantidade", "Estoque mínimo"])
        self.assertEqual(float(ws["C2"].value), 30.0)
        self.assertEqual(float(ws["D2"].value), 100.0)
        self.assertIn("R$", ws["C2"].number_format)

    def test_nao_admin_recebe_403(self):
        for usuario in (self.atendente, self.tecnico):
            self.autenticar(usuario)
            self.assertEqual(self.client.get("/api/exportar/clientes/").status_code, 403)
            self.assertEqual(self.client.get("/api/exportar/pecas/").status_code, 403)

    def test_loja_b_nao_ve_dados_da_loja_a(self):
        Cliente.objects.create(loja=self.loja, nome="So da A")
        Cliente.objects.create(loja=self.outra_loja, nome="So da B")
        self.autenticar(self.admin_b)
        ws = self._planilha(self.client.get("/api/exportar/clientes/"))
        self.assertEqual([c.value for c in ws["A"][1:]], ["So da B"])

    def test_celula_com_formula_sai_como_texto(self):
        Cliente.objects.create(loja=self.loja, nome="=1+1", telefone="+55 86 99999-0000")
        ws = self._planilha(self.client.get("/api/exportar/clientes/"))
        self.assertEqual(ws["A2"].value, "=1+1")           # sem apóstrofo
        self.assertEqual(ws["A2"].data_type, "s")          # string de verdade
        self.assertEqual(ws["B2"].value, "+55 86 99999-0000")

    def test_planilha_nao_tem_formula_no_xml(self):
        Cliente.objects.create(loja=self.loja, nome="=1+1", observacoes="@SUM(A1)")
        r = self.client.get("/api/exportar/clientes/")
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        self.assertNotIn("<f>", xml)

    def test_loja_sem_dados_gera_so_cabecalho(self):
        self.autenticar(self.admin_b)
        ws = self._planilha(self.client.get("/api/exportar/clientes/"))
        self.assertEqual(ws.max_row, 1)
        ws = self._planilha(self.client.get("/api/exportar/pecas/"))
        self.assertEqual(ws.max_row, 1)


class SaudeTest(APITestCase):
    def test_saude_publica_responde_ok(self):
        r = self.client.get("/api/saude/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"status": "ok"})


class MigracaoAparelhoTest(TransactionTestCase):
    migrate_from = [("core", "0003_fotoos_tipo_fotoos_visivel_cliente")]
    migrate_to = [("core", "0008_loja_checklist_padrao_criado_and_more")]

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        antigo = self.executor.loader.project_state(self.migrate_from).apps
        Loja = antigo.get_model("core", "Loja")
        Cliente = antigo.get_model("core", "Cliente")
        OS = antigo.get_model("core", "OrdemServico")
        loja = Loja.objects.create(nome="Loja antiga")
        cliente = Cliente.objects.create(loja=loja, nome="Cliente antigo")
        self.os_celular = OS.objects.create(
            loja=loja, cliente=cliente, numero=1, tipo_aparelho="Celular",
            imei="12345678901234567", defeito="Tela",
            checklist={"Liga": True, "Carregamento": False},
        )
        self.os_outro = OS.objects.create(
            loja=loja, cliente=cliente, numero=2, tipo_aparelho="Placa de video",
            imei="SERIE-9", defeito="Sem video", checklist={},
        )

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        super().tearDown()

    def test_converte_dados_antigos(self):
        self.executor = MigrationExecutor(connection)
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)

        cel = OrdemServico.objects.get(pk=self.os_celular.pk)
        self.assertEqual(cel.categoria, "celular")
        self.assertEqual(cel.numero_serie, "12345678901234567")
        self.assertEqual(cel.imei, "12345678901234567")
        self.assertEqual(cel.checklist, "Liga: ok\nCarregamento: com defeito")

        outro = OrdemServico.objects.get(pk=self.os_outro.pk)
        self.assertEqual(outro.categoria, "outro")
        self.assertEqual(outro.numero_serie, "SERIE-9")
        self.assertEqual(outro.imei, "")
        self.assertEqual(outro.checklist, "")
